"""Config-derived diagnostic sensors for the Outback MATE3 integration.

All 400+ entities here come from the add-on's periodic HTTP poll of
``http://<mate3>/CONFIG.xml`` (firmware, nameplate, setpoints, AGS /
Grid_Use / HVT / LVC / SunSpec / etc.). They're factored out of
``sensor.py`` to keep that file focused on the UDP live-data path, and
are all registered as ``EntityCategory.DIAGNOSTIC`` and
``entity_registry_enabled_default=False`` — the recorder stays quiet
and users opt in only to the ones they care about.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import OutbackMate3
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Maps wire-format unit / device_class strings to HA enum constants.
# Shared with sensor.py via duplication (10 lines) to avoid a new module.
_UNIT_MAP = {
    "V": "V",  # passed through; HA accepts plain "V" for voltage sensors
    "A": "A",
    "W": "W",
}


def _to_device_class(s: str | None) -> SensorDeviceClass | None:
    return SensorDeviceClass(s) if s else None


def create_config_entities(mate3: OutbackMate3, mac_address: str) -> list[SensorEntity]:
    """Diagnostic entities derived from the HTTP CONFIG.xml poll.

    Only called after the first ``config_snapshot`` arrives for a MAC, so the
    integration never shows phantom "unavailable" config entities when the
    MATE3's HTTP endpoint is unreachable.
    """
    config = mate3.config_by_mac.get(mac_address)
    if config is None:
        return []
    schema = mate3.config_entity_schema
    if not schema:
        return []

    entities: list[SensorEntity] = []

    for spec in schema.get("system", []):
        entities.append(OutbackConfigDiagnosticSensor(mate3, mac_address, "system", 0, spec))

    n_inverters = len(config.get("inverters", []))
    for idx in range(1, n_inverters + 1):
        for spec in schema.get("inverter", []):
            entities.append(
                OutbackConfigDiagnosticSensor(mate3, mac_address, "inverter", idx, spec)
            )

    n_ccs = len(config.get("charge_controllers", []))
    for idx in range(1, n_ccs + 1):
        for spec in schema.get("charge_controller", []):
            entities.append(
                OutbackConfigDiagnosticSensor(mate3, mac_address, "charge_controller", idx, spec)
            )

    _LOGGER.debug("Created %d config entities for MAC %s", len(entities), mac_address)
    return entities


class OutbackConfigDiagnosticSensor(CoordinatorEntity[OutbackMate3], SensorEntity):
    """A diagnostic sensor read from OutbackMate3.config_by_mac.

    Covers firmware versions, nameplate, setpoints, AGS / Grid_Use /
    Grid-Mode-Schedule / HVT / LGT / SunSpec / etc. — everything the
    periodic HTTP CONFIG.xml poll produces. These values change rarely,
    so they're disabled by default: the entity registry knows about them
    (so they show up in HA's UI and can be opted in), but HA doesn't
    record or expose them as states until the user enables the ones
    they care about. Keeps the recorder quiet given 400+ possible
    diagnostic entities on a populated system.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        mate3: OutbackMate3,
        mac_address: str,
        device_kind: str,  # "system" | "inverter" | "charge_controller"
        device_id: int,  # 0 for system; 1-based for inverter/cc
        spec: dict[str, Any],
    ) -> None:
        super().__init__(mate3)
        self._mate3 = mate3
        self._mac_address = mac_address
        self._device_kind = device_kind
        self._device_id = device_id
        self._spec = spec

        key = spec["key"]
        mac_id = mac_address.replace(".", "_")
        # Gold-tier entity-translations: name comes from
        # `entity.sensor.<key>.name` in strings.json. `name` is kept in the
        # spec as the readable English source for those entries,
        # but isn't consulted at runtime.
        self._attr_translation_key = key
        self._attr_native_unit_of_measurement = spec.get("unit")
        self._attr_device_class = _to_device_class(spec.get("device_class"))

        if device_kind == "system":
            self.entity_id = f"sensor.mate3_system_{key}"
            self._attr_unique_id = f"{DOMAIN}_system_{key}"
            device_info = DeviceInfo(
                identifiers={(DOMAIN, "system")},
                name="Outback System",
                manufacturer="Outback Power",
                model="System",
            )
        else:
            self.entity_id = f"sensor.mate3_{mac_id}_{device_kind}_{device_id}_{key}"
            self._attr_unique_id = f"{DOMAIN}_{mac_address}_{device_kind}_{device_id}_{key}"
            device_info = DeviceInfo(
                identifiers={(DOMAIN, f"{device_kind}_{mac_address}_{device_id}")},
                name=f"Outback {device_kind.replace('_', ' ').title()} {device_id}",
                manufacturer="Outback Power",
                model=device_kind.replace("_", " ").title(),
            )

        # Surface firmware string on the device page too.
        if spec.get("is_firmware"):
            fw = self._read_value()
            if fw is not None:
                device_info["sw_version"] = str(fw)
        self._attr_device_info = device_info

    def _read_value(self):
        config = self._mate3.config_by_mac.get(self._mac_address)
        if config is None:
            return None
        try:
            device_kind = self._device_kind
            if device_kind == "system":
                return config.get(self._spec["section"], {}).get(self._spec["source_key"])
            elif device_kind == "inverter":
                inverters = config.get("inverters") or []
                idx = self._device_id - 1
                if idx >= len(inverters):
                    return None
                return inverters[idx].get(self._spec["source_key"])
            else:  # charge_controller
                ccs = config.get("charge_controllers") or []
                idx = self._device_id - 1
                if idx >= len(ccs):
                    return None
                return ccs[idx].get(self._spec["source_key"])
        except (IndexError, KeyError, TypeError):
            return None

    @property
    def native_value(self):
        v = self._read_value()
        if v is None:
            return None
        # Numeric sensors (unit set) should keep their native numeric type so
        # HA formats them correctly and units display. Anything else is
        # rendered as a string.
        if self._attr_native_unit_of_measurement is not None and isinstance(v, int | float):
            return v
        return str(v)

    @property
    def available(self) -> bool:
        return self._read_value() is not None
