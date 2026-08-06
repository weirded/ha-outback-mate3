"""MATE3 entity schema — the add-on's description of live entities for the integration.

The add-on is the sole source of MATE3 protocol knowledge. This module
expresses that knowledge as data: for each device kind (inverter,
charge_controller), a list of :class:`EntitySpec` describing every live
state field the parser emits.

The integration consumes the serialized form (via the ``entity_schema`` WS
message) and materializes Home Assistant entities directly from it. No
MATE3 field names or units live on the integration side.

Design notes
------------
* Strings, not Python symbols: ``device_class`` / ``state_class`` / ``unit``
  are plain strings matching Home Assistant's wire-compatible constants
  (``"voltage"``, ``"measurement"``, ``"V"``, ...). The add-on has zero
  HA imports; the integration is responsible for mapping them back to
  :class:`~homeassistant.components.sensor.SensorDeviceClass` etc.
* ``options`` for enum fields is the exhaustive set of values the parser
  can emit, including the ``"unknown"`` fallback; HA rejects states not
  present in the advertised options list.
* ``system`` aggregates (from_grid, solar_production, ...) are intentionally
  *not* in this schema — they're integration-side rollups computed from
  per-device state, not MATE3 protocol artifacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.parser import (
    _AC_MODE,
    _CHARGE_MODE,
    _INVERTER_MODE,
    KIND_CHARGE_CONTROLLER,
    KIND_FNDC,
    KIND_INVERTER,
)

# HA wire-compatible device classes. Plain strings so the add-on stays
# framework-agnostic.
_DC_CURRENT = "current"
_DC_VOLTAGE = "voltage"
_DC_POWER = "power"
_DC_ENERGY = "energy"
_DC_ENUM = "enum"

_SC_MEASUREMENT = "measurement"
_SC_TOTAL_INCREASING = "total_increasing"

_U_A = "A"
_U_V = "V"
_U_W = "W"
_U_KWH = "kWh"
_U_AH = "Ah"
_U_PCT = "%"

_DC_BATTERY = "battery"


@dataclass(frozen=True)
class EntitySpec:
    """One live entity the integration should materialize."""

    key: str
    name: str
    device_class: str | None
    unit: str | None
    state_class: str | None
    entity_category: str | None = None
    translation_key: str | None = None
    options: tuple[str, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "device_class": self.device_class,
            "unit": self.unit,
            "state_class": self.state_class,
            "entity_category": self.entity_category,
            "translation_key": self.translation_key or self.key,
            "options": list(self.options) if self.options is not None else None,
        }


def _current(key: str, name: str) -> EntitySpec:
    return EntitySpec(key, name, _DC_CURRENT, _U_A, _SC_MEASUREMENT)


def _voltage(key: str, name: str) -> EntitySpec:
    return EntitySpec(key, name, _DC_VOLTAGE, _U_V, _SC_MEASUREMENT)


def _power(key: str, name: str) -> EntitySpec:
    return EntitySpec(key, name, _DC_POWER, _U_W, _SC_MEASUREMENT)


# Enum options are derived from the parser so additions stay in lockstep.
# "unknown" is the parser's fallback for unmapped raw values (see
# ``_INVERTER_MODE.get(int(values[16]), "unknown")``).
_INVERTER_MODE_OPTIONS = tuple(sorted(set(_INVERTER_MODE.values()) | {"unknown"}))
_AC_MODE_OPTIONS = tuple(sorted(set(_AC_MODE.values()) | {"unknown"}))
_CHARGE_MODE_OPTIONS = tuple(sorted(set(_CHARGE_MODE.values()) | {"unknown"}))
_GRID_MODE_OPTIONS = ("grid", "generator")


INVERTER_ENTITIES: tuple[EntitySpec, ...] = (
    # L1 currents
    _current("l1_inverter_current", "L1 Inverter Current"),
    _current("l1_charger_current", "L1 Charger Current"),
    _current("l1_buy_current", "L1 Buy Current"),
    _current("l1_sell_current", "L1 Sell Current"),
    # L2 currents
    _current("l2_inverter_current", "L2 Inverter Current"),
    _current("l2_charger_current", "L2 Charger Current"),
    _current("l2_buy_current", "L2 Buy Current"),
    _current("l2_sell_current", "L2 Sell Current"),
    # Combined currents
    _current("inverter_current", "Total Inverter Current"),
    _current("charger_current", "Total Charger Current"),
    # L1 voltages
    _voltage("l1_ac_input_voltage", "L1 AC Input Voltage"),
    _voltage("l1_ac_output_voltage", "L1 AC Output Voltage"),
    # L2 voltages
    _voltage("l2_ac_input_voltage", "L2 AC Input Voltage"),
    _voltage("l2_ac_output_voltage", "L2 AC Output Voltage"),
    # Combined voltages
    _voltage("total_ac_input_voltage", "Total AC Input Voltage"),
    _voltage("total_ac_output_voltage", "Total AC Output Voltage"),
    # L1 power
    _power("l1_grid_power", "L1 Grid Power"),
    _power("l1_inverter_power", "L1 Inverter Power"),
    _power("l1_charger_power", "L1 Charger Power"),
    # L2 power
    _power("l2_grid_power", "L2 Grid Power"),
    _power("l2_inverter_power", "L2 Inverter Power"),
    _power("l2_charger_power", "L2 Charger Power"),
    # Combined power
    _power("grid_power", "Total Grid Power"),
    _power("inverter_power", "Total Inverter Power"),
    _power("charger_power", "Total Charger Power"),
    # Battery
    _voltage("battery_voltage", "Battery Voltage"),
    # Enums
    EntitySpec(
        "inverter_mode",
        "Inverter Mode",
        device_class=_DC_ENUM,
        unit=None,
        state_class=None,
        options=_INVERTER_MODE_OPTIONS,
    ),
    EntitySpec(
        "ac_mode",
        "AC Mode",
        device_class=_DC_ENUM,
        unit=None,
        state_class=None,
        options=_AC_MODE_OPTIONS,
    ),
    EntitySpec(
        "grid_mode",
        "Grid Mode",
        device_class=_DC_ENUM,
        unit=None,
        state_class=None,
        options=_GRID_MODE_OPTIONS,
    ),
)


CHARGE_CONTROLLER_ENTITIES: tuple[EntitySpec, ...] = (
    _current("pv_current", "PV Current"),
    _voltage("pv_voltage", "PV Voltage"),
    _power("pv_power", "PV Power"),
    _current("output_current", "Output Current"),
    _power("output_power", "Output Power"),
    _voltage("battery_voltage", "Battery Voltage"),
    # kwh_today resets daily → TOTAL_INCREASING so the Energy dashboard
    # treats midnight reset as counter rollover.
    EntitySpec(
        "kwh_today",
        "kWh Today",
        device_class=_DC_ENERGY,
        unit=_U_KWH,
        state_class=_SC_TOTAL_INCREASING,
    ),
    # F3: Amp-hours has no HA device_class; state_class carries the
    # TOTAL_INCREASING semantic on its own.
    EntitySpec(
        "daily_ah",
        "Daily Ah",
        device_class=None,
        unit=_U_AH,
        state_class=_SC_TOTAL_INCREASING,
    ),
    EntitySpec(
        "charge_mode",
        "Charge Mode",
        device_class=_DC_ENUM,
        unit=None,
        state_class=None,
        options=_CHARGE_MODE_OPTIONS,
    ),
)


FNDC_ENTITIES: tuple[EntitySpec, ...] = (
    _current("shunt_a_current", "Shunt A Current"),
    _current("shunt_b_current", "Shunt B Current"),
    _current("shunt_c_current", "Shunt C Current"),
    _voltage("battery_voltage", "Battery Voltage"),
    EntitySpec(
        "soc",
        "State of Charge",
        device_class=_DC_BATTERY,
        unit=_U_PCT,
        state_class=_SC_MEASUREMENT,
    ),
)


def build_live_schema() -> dict[str, list[dict[str, Any]]]:
    """Return the JSON-ready live-entity schema, keyed by device kind."""
    return {
        KIND_INVERTER: [spec.to_dict() for spec in INVERTER_ENTITIES],
        KIND_CHARGE_CONTROLLER: [spec.to_dict() for spec in CHARGE_CONTROLLER_ENTITIES],
        KIND_FNDC: [spec.to_dict() for spec in FNDC_ENTITIES],
    }
