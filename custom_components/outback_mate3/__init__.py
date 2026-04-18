"""The Outback MATE3 integration.

Connects to the companion ``outback_mate3`` add-on over WebSocket and mirrors
its device state into HA entities. The add-on owns UDP I/O and MATE3 frame
parsing; this integration is a thin reactive client that turns
``snapshot`` / ``device_added`` / ``state_updated`` events into HA entity
lifecycle and state updates.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from aiohttp import ClientWebSocketResponse, WSMsgType

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

DOMAIN = "outback_mate3"
PLATFORMS = [Platform.SENSOR]

CONF_URL = "url"
DEFAULT_URL = "ws://a0d7b954-outback-mate3:8099/ws"

KIND_INVERTER = "inverter"
KIND_CHARGE_CONTROLLER = "charge_controller"

_INITIAL_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 30.0
_WS_HEARTBEAT_S = 30.0


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

        # Per-MAC state dicts that sensor.py reads from directly.
        self.inverters: dict[str, dict[int, dict[str, Any]]] = {}
        self.charge_controllers: dict[str, dict[int, dict[str, Any]]] = {}

        # Device keys we've already announced to HA via the add-entities callback.
        # Same format as the legacy code so user-facing unique IDs don't change.
        self.discovered_devices: set[str] = set()

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
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _ws_loop(self) -> None:
        """Connect to the add-on and consume events; reconnect with backoff."""
        backoff = _INITIAL_BACKOFF_S
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(
                        self.url, heartbeat=_WS_HEARTBEAT_S
                    ) as ws:
                        _LOGGER.info("Connected to MATE3 add-on at %s", self.url)
                        self._connected = True
                        backoff = _INITIAL_BACKOFF_S
                        await self._consume(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                _LOGGER.warning(
                    "MATE3 add-on connection to %s failed: %s", self.url, exc
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
            backoff = min(backoff * 2, _MAX_BACKOFF_S)

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
        else:
            _LOGGER.debug("Ignoring unknown WS message type %r", mtype)
            return
        self.async_set_updated_data(None)

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
