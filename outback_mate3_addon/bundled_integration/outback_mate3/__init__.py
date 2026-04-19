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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_URL,
    DEFAULT_URL,
    DOMAIN,
    INITIAL_BACKOFF_S,
    KIND_CHARGE_CONTROLLER,
    KIND_INVERTER,
    MAX_BACKOFF_S,
    PLATFORMS,
    WS_HEARTBEAT_S,
)

__all__ = ["CONF_URL", "DEFAULT_URL", "DOMAIN", "OutbackMate3"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Outback MATE3 from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    url = entry.data.get(CONF_URL, DEFAULT_URL)
    mate3 = OutbackMate3(hass, url)
    hass.data[DOMAIN][entry.entry_id] = mate3

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    mate3.start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        mate3 = hass.data[DOMAIN].pop(entry.entry_id)
        await mate3.stop()
    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> bool:
    """Allow users to remove stale MATE3 devices via the UI.

    Returns True if the device is no longer part of the current known state
    (i.e. not in self.inverters / self.charge_controllers); returning False
    would block the delete button in HA.
    """
    mate3: OutbackMate3 | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if mate3 is None:
        return True

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


class OutbackMate3(DataUpdateCoordinator):
    """Reactive WebSocket client that mirrors the add-on's device state."""

    def __init__(self, hass: HomeAssistant, url: str) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN)
        self.hass = hass
        self.url = url

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

    def set_add_entities_callback(self, callback: AddEntitiesCallback) -> None:
        self._add_entities_callback = callback

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = self.hass.loop.create_task(self._ws_loop())

    async def stop(self) -> None:
        self._running = False
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
                    await self._consume(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
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
        from .sensor import create_config_entities

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
