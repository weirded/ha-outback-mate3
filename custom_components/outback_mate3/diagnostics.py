"""Diagnostics support for Outback MATE3.

Exposes a snapshot of the coordinator's current view — config entry,
device counts, last UDP timestamp, a sanitized sample of parsed CONFIG.xml
per MAC, and the live inverter/charge-controller state. MAC addresses
(which Outback uses as stable device identifiers but some users still
consider sensitive) are redacted by default.
"""

from __future__ import annotations

import time
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import MateConfigEntry

TO_REDACT = {"mac", "serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MateConfigEntry
) -> dict[str, Any]:
    mate3 = getattr(entry, "runtime_data", None)
    if mate3 is None:
        return {"entry": _entry_to_dict(entry), "coordinator": None}

    now = time.monotonic()
    last_udp_at = mate3.last_udp_at
    seconds_since_udp = (now - last_udp_at) if last_udp_at is not None else None

    by_mac: dict[str, Any] = {}
    for mac in set(mate3.inverters) | set(mate3.charge_controllers) | set(mate3.config_by_mac):
        by_mac[mac] = {
            "inverters": mate3.inverters.get(mac, {}),
            "charge_controllers": mate3.charge_controllers.get(mac, {}),
            "config": mate3.config_by_mac.get(mac, {}),
        }

    coordinator_snapshot: dict[str, Any] = {
        "url": mate3.url,
        "connected": mate3.is_connected,
        "integration_version": mate3.integration_version,
        "addon_version": mate3.addon_version,
        "seconds_since_last_udp": seconds_since_udp,
        "discovered_devices": sorted(mate3.discovered_devices),
        "config_entities_created": sorted(mate3._config_entities_created),
        "by_mac": by_mac,
    }

    return {
        "entry": _entry_to_dict(entry),
        "coordinator": async_redact_data(coordinator_snapshot, TO_REDACT),
    }


def _entry_to_dict(entry: ConfigEntry) -> dict[str, Any]:
    return {
        "entry_id": entry.entry_id,
        "version": entry.version,
        "domain": entry.domain,
        "title": entry.title,
        "source": entry.source,
        "data": async_redact_data(dict(entry.data), TO_REDACT),
        "unique_id": entry.unique_id,
    }
