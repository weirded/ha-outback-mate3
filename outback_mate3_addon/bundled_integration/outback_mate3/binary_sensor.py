"""Binary sensors for the Outback MATE3 integration.

Ships one sensor today: ``Receiving Data from MATE3`` on the Outback System
device. Flips to off after ``_STALE_AFTER_S`` seconds without a UDP
datagram, so automations can notice when the MATE3 stops streaming (cable
pulled, firmware destination-IP glitch, power cycle).
"""
from __future__ import annotations

import time
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from . import DOMAIN, OutbackMate3

_STALE_AFTER_S = 300.0
_POLL_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    mate3: OutbackMate3 = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([OutbackReceivingDataSensor(mate3)])


class OutbackReceivingDataSensor(BinarySensorEntity):
    """`Receiving Data from MATE3` — connectivity indicator on the system device."""

    _attr_has_entity_name = True
    _attr_name = "Receiving Data from MATE3"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_should_poll = False
    _attr_unique_id = f"{DOMAIN}_system_receiving_data"
    entity_id = "binary_sensor.mate3_system_receiving_data"

    def __init__(self, mate3: OutbackMate3) -> None:
        self._mate3 = mate3
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, "system")},
            name="Outback System",
            manufacturer="Outback Power",
            model="System",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Two refresh paths:
        #  1. coordinator ticks whenever a WS message lands — captures the
        #     off→on transition immediately.
        #  2. a 30s timer — captures the on→off transition (no WS messages
        #     to hook when the stream has gone silent).
        self.async_on_remove(
            self._mate3.async_add_listener(self._refresh)
        )
        self.async_on_remove(
            async_track_time_interval(self.hass, self._timer_tick, _POLL_INTERVAL)
        )

    @callback
    def _refresh(self) -> None:
        self.async_write_ha_state()

    @callback
    def _timer_tick(self, _now) -> None:
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool:
        last = self._mate3.last_udp_at
        if last is None:
            return False
        return (time.monotonic() - last) < _STALE_AFTER_S
