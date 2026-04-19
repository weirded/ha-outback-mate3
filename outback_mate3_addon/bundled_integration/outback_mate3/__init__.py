"""The Outback MATE3 integration.

Connects to the companion ``outback_mate3`` add-on over WebSocket and mirrors
its device state into HA entities. The add-on owns UDP I/O and MATE3 frame
parsing; this integration is a thin reactive client that turns
``snapshot`` / ``device_added`` / ``state_updated`` events into HA entity
lifecycle and state updates.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from typing import Any

import aiohttp
from aiohttp import ClientWebSocketResponse, WSMsgType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.loader import async_get_integration

from .const import (
    ADDON_OFFLINE_GRACE_S,
    CONF_URL,
    DEFAULT_URL,
    DOMAIN,
    INITIAL_BACKOFF_S,
    ISSUE_ADDON_OFFLINE,
    ISSUE_VERSION_DRIFT,
    KIND_CHARGE_CONTROLLER,
    KIND_INVERTER,
    MAX_BACKOFF_S,
    PLATFORMS,
    WS_HEARTBEAT_S,
)

__all__ = ["CONF_URL", "DEFAULT_URL", "DOMAIN", "MateConfigEntry", "OutbackMate3"]

# ConfigEntry[OutbackMate3] gives platforms typed access to the coordinator
# via `entry.runtime_data` without any cast/assertion dance.
type MateConfigEntry = ConfigEntry["OutbackMate3"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: MateConfigEntry) -> bool:
    """Set up Outback MATE3 from a config entry."""
    url = entry.data.get(CONF_URL, DEFAULT_URL)
    integration = await async_get_integration(hass, DOMAIN)
    # integration.version is an AwesomeVersion; coerce to str so string equality
    # against the add-on's self-reported version string works cleanly.
    integration_version = str(integration.version) if integration.version else None
    mate3 = OutbackMate3(hass, url, integration_version=integration_version)
    entry.runtime_data = mate3

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    mate3.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MateConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        mate3 = entry.runtime_data
        await mate3.stop()
        # Clear any Repairs issues we raised so a subsequent setup starts clean.
        ir.async_delete_issue(hass, DOMAIN, ISSUE_ADDON_OFFLINE)
        ir.async_delete_issue(hass, DOMAIN, ISSUE_VERSION_DRIFT)
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: MateConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Allow users to remove stale MATE3 devices via the UI.

    Returns True if the device is no longer part of the current known state
    (i.e. not in self.inverters / self.charge_controllers); returning False
    would block the delete button in HA.
    """
    mate3 = entry.runtime_data

    # Identifiers look like ("outback_mate3", "inverter_<MAC>_<index>")
    # or ("outback_mate3", "system"). If the device still matches a live
    # (mac, kind, index), refuse — the user is likely removing something
    # that'll immediately re-appear on the next update.
    for domain, identifier in device.identifiers:
        if domain != DOMAIN:
            continue
        if identifier == "system":
            # System device is global and regenerates from any known MAC.
            return not (mate3.inverters or mate3.charge_controllers)
        parts = identifier.split("_")
        if len(parts) < 3:
            continue
        kind = "_".join(parts[:-2])
        mac = parts[-2]
        try:
            index = int(parts[-1])
        except ValueError:
            continue
        if kind == "inverter" and mac in mate3.inverters and index in mate3.inverters[mac]:
            return False
        if (
            kind == "charge_controller"
            and mac in mate3.charge_controllers
            and index in mate3.charge_controllers[mac]
        ):
            return False
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate legacy UDP-port config entries to the new WebSocket URL form."""
    if entry.version == 1:
        # Old entries stored {"port": 57027}. The add-on listens for UDP locally now,
        # so we can't preserve "listen directly" mode — set a sensible default URL
        # and let the user edit it if the add-on hostname differs.
        new_data = {CONF_URL: DEFAULT_URL}
        hass.config_entries.async_update_entry(entry, data=new_data, version=2)
        _LOGGER.info(
            "Migrated Outback MATE3 entry from UDP-port config to WS URL %s",
            DEFAULT_URL,
        )
    return True


class OutbackMate3(DataUpdateCoordinator[None]):
    """Reactive WebSocket client that mirrors the add-on's device state.

    Parameterized with ``None`` because we don't ship a polled payload —
    entity state lives on ``self.inverters`` / ``self.charge_controllers`` /
    ``self.config_by_mac`` and ``async_set_updated_data(None)`` is only used
    as a broadcast notification to CoordinatorEntity subscribers.
    """

    def __init__(
        self, hass: HomeAssistant, url: str, *, integration_version: str | None = None
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.hass = hass
        self.url = url
        self.integration_version = integration_version

        self._task: asyncio.Task | None = None
        self._running = False
        self._add_entities_callback: AddEntitiesCallback | None = None

        # Monotonic timestamp of the most recently-applied UDP-derived payload
        # (snapshot with devices, device_added, or state_updated). Used by the
        # `binary_sensor.mate3_system_receiving_data` connectivity entity; None
        # means we've never received a UDP frame yet.
        self.last_udp_at: float | None = None

        # Per-MAC state dicts that sensor.py reads from directly.
        self.inverters: dict[str, dict[int, dict[str, Any]]] = {}
        self.charge_controllers: dict[str, dict[int, dict[str, Any]]] = {}
        # Per-MAC parsed CONFIG.xml (firmware, nameplate, setpoints).
        self.config_by_mac: dict[str, dict[str, Any]] = {}

        # Device keys we've already announced to HA via the add-entities callback.
        # Same format as the legacy code so user-facing unique IDs don't change.
        self.discovered_devices: set[str] = set()
        # MACs we've already created config-derived diagnostic entities for;
        # we wait for the first successful config_snapshot before materializing
        # them so there are no permanently-unavailable phantoms when the
        # MATE3's HTTP endpoint is unreachable.
        self._config_entities_created: set[str] = set()

        self._connected = False
        # Populated by the add-on's `hello` message on first connect; drives
        # the `version_drift` Repairs issue.
        self.addon_version: str | None = None
        # Scheduled `addon_offline` issue creation. Cancelled on reconnect so
        # brief Supervisor restarts don't flap a Repair in and out.
        self._addon_offline_handle: asyncio.TimerHandle | None = None

    def set_add_entities_callback(self, callback: AddEntitiesCallback) -> None:
        self._add_entities_callback = callback

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = self.hass.loop.create_task(self._ws_loop())

    async def stop(self) -> None:
        self._running = False
        if self._addon_offline_handle is not None:
            self._addon_offline_handle.cancel()
            self._addon_offline_handle = None
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _ws_loop(self) -> None:
        """Connect to the add-on and consume events; reconnect with backoff."""
        backoff = INITIAL_BACKOFF_S
        # Warn once on the first consecutive connect failure; drop to DEBUG
        # while we keep retrying so the HA log doesn't fill up with one WARN
        # every <backoff>s when the add-on is stopped.
        warned_while_disconnected = False
        while self._running:
            try:
                async with aiohttp.ClientSession() as session, session.ws_connect(
                    self.url, heartbeat=WS_HEARTBEAT_S
                ) as ws:
                    _LOGGER.info("Connected to MATE3 add-on at %s", self.url)
                    self._connected = True
                    backoff = INITIAL_BACKOFF_S
                    warned_while_disconnected = False
                    self._on_connected()
                    await self._consume(ws)
            except asyncio.CancelledError:
                raise
            except (aiohttp.ClientError, TimeoutError, OSError) as exc:
                # Transient network failures: add-on stopped, Supervisor
                # routing hiccup, TCP reset, DNS flap, heartbeat timeout.
                # Log once at WARNING then drop to DEBUG while we retry so
                # the HA log isn't flooded with "add-on not running" noise.
                if not warned_while_disconnected:
                    _LOGGER.warning(
                        "MATE3 add-on connection to %s failed: %s (retrying)",
                        self.url, exc,
                    )
                    warned_while_disconnected = True
                else:
                    _LOGGER.debug(
                        "MATE3 add-on still unreachable at %s: %s", self.url, exc
                    )

            self._connected = False
            self._mark_entities_stale()
            self._on_disconnected()
            if not self._running:
                break
            _LOGGER.debug("Reconnecting to %s in %.1fs", self.url, backoff)
            try:
                await asyncio.sleep(backoff)
            except asyncio.CancelledError:
                break
            backoff = min(backoff * 2, MAX_BACKOFF_S)

    async def _consume(self, ws: ClientWebSocketResponse) -> None:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    payload = msg.json()
                except ValueError:
                    _LOGGER.warning("Non-JSON WS message: %r", msg.data[:80])
                    continue
                self._handle_message(payload)
            elif msg.type == WSMsgType.ERROR:
                _LOGGER.warning("WS error: %s", ws.exception())
                return

    # ---- Message dispatch --------------------------------------------------

    def _handle_message(self, msg: dict[str, Any]) -> None:
        mtype = msg.get("type")
        if mtype == "hello":
            self._apply_hello(msg)
            return
        if mtype == "snapshot":
            # Reset per-device state but keep discovered_devices so we don't
            # re-announce entities HA already knows about.
            self.inverters.clear()
            self.charge_controllers.clear()
            for device in msg.get("devices", []):
                self._apply_device(device, emit_discovery=True)
        elif mtype == "device_added":
            self._apply_device(msg, emit_discovery=True)
        elif mtype == "state_updated":
            self._apply_device(msg, emit_discovery=False)
        elif mtype == "config_snapshot":
            self._apply_config(msg)
        else:
            _LOGGER.debug("Ignoring unknown WS message type %r", mtype)
            return
        self.async_set_updated_data(None)

    def _apply_hello(self, payload: dict[str, Any]) -> None:
        addon_version = payload.get("addon_version")
        if not isinstance(addon_version, str) or not addon_version:
            _LOGGER.debug("hello without addon_version: %r", payload)
            return
        self.addon_version = addon_version
        self._reconcile_version_drift()

    def _reconcile_version_drift(self) -> None:
        """Create or clear the version_drift Repairs issue.

        The add-on and integration ship together and share a single version
        string. A mismatch means the user upgraded one half but not the other.
        """
        if not self.integration_version or not self.addon_version:
            return
        if self.integration_version == self.addon_version:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_VERSION_DRIFT)
            return
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_VERSION_DRIFT,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_VERSION_DRIFT,
            translation_placeholders={
                "integration_version": self.integration_version,
                "addon_version": self.addon_version,
            },
        )

    def _on_connected(self) -> None:
        """Hook called each time the WS handshake succeeds.

        Cancels any pending `addon_offline` issue creation and clears an
        already-raised issue so a reconnect inside the grace window never
        flashes a Repair the user notices.
        """
        if self._addon_offline_handle is not None:
            self._addon_offline_handle.cancel()
            self._addon_offline_handle = None
        ir.async_delete_issue(self.hass, DOMAIN, ISSUE_ADDON_OFFLINE)

    def _on_disconnected(self) -> None:
        """Hook called each time the WS loop drops the connection.

        Starts (or leaves running) a grace timer that raises the
        `addon_offline` Repairs issue. Short Supervisor bounces or TCP
        hiccups complete a reconnect before the timer fires, so they never
        surface as a Repair.
        """
        if not self._running:
            return
        if self._addon_offline_handle is not None:
            return
        self._addon_offline_handle = self.hass.loop.call_later(
            ADDON_OFFLINE_GRACE_S, self._raise_addon_offline
        )

    def _raise_addon_offline(self) -> None:
        self._addon_offline_handle = None
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            ISSUE_ADDON_OFFLINE,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=ISSUE_ADDON_OFFLINE,
            translation_placeholders={"url": self.url},
        )

    def _apply_config(self, payload: dict[str, Any]) -> None:
        mac = payload.get("mac")
        config = payload.get("config")
        if not mac or not isinstance(config, dict):
            _LOGGER.debug("Malformed config_snapshot payload: %r", payload)
            return
        self.config_by_mac[mac] = config

        # First config_snapshot for this MAC → materialize the config-derived
        # diagnostic entities. Later snapshots just update state through
        # async_set_updated_data (the entities read config_by_mac on every
        # refresh). This gating ensures we never create phantom config
        # entities for MATE3s whose HTTP endpoint we can't reach.
        if mac in self._config_entities_created:
            return
        if self._add_entities_callback is None:
            return
        self._config_entities_created.add(mac)
        from .sensor_config import create_config_entities

        entities = create_config_entities(self, mac)
        if entities:
            self._add_entities_callback(entities)

    def _apply_device(self, payload: dict[str, Any], *, emit_discovery: bool) -> None:
        mac = payload["mac"]
        kind = payload["kind"]
        index = payload["index"]
        state = payload["state"]

        if kind == KIND_INVERTER:
            self.inverters.setdefault(mac, {})[index] = state
            type_code = 6
        elif kind == KIND_CHARGE_CONTROLLER:
            self.charge_controllers.setdefault(mac, {})[index] = state
            type_code = 3
        else:
            _LOGGER.debug("Ignoring unknown device kind %r", kind)
            return

        # Any UDP-derived payload is fresh evidence the MATE3 is streaming.
        self.last_udp_at = time.monotonic()

        # Preserve legacy device_key format so existing entity unique IDs stay stable.
        device_key = f"{mac}_{type_code}_{index}"
        is_new = device_key not in self.discovered_devices
        if emit_discovery and is_new:
            self.discovered_devices.add(device_key)
            if self._add_entities_callback is not None:
                from .sensor import create_device_entities

                entities = create_device_entities(self, mac)
                if entities:
                    self._add_entities_callback(entities)

    def _mark_entities_stale(self) -> None:
        """Trigger a coordinator refresh so CoordinatorEntity.available reflects the drop."""
        self.async_set_updated_data(None)

    # ---- Status helpers ----------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected
