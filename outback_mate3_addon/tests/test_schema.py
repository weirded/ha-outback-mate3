"""Tests for the WS entity_schema published by the add-on.

The schema tells the integration what per-device-kind entities to
materialize, with all MATE3-specific metadata (unit, device_class,
state_class, translation_key, enum options) sourced from the add-on
instead of duplicated in the integration.
"""

from __future__ import annotations

import json

from src.parser import KIND_CHARGE_CONTROLLER, KIND_INVERTER
from src.schema import (
    CHARGE_CONTROLLER_ENTITIES,
    INVERTER_ENTITIES,
    EntitySpec,
    build_live_schema,
)

# --- EntitySpec shape ------------------------------------------------------


def test_entity_spec_is_jsonable():
    """Every field is a JSON primitive so the schema serializes without helpers."""
    spec = EntitySpec(
        key="battery_voltage",
        name="Battery Voltage",
        device_class="voltage",
        unit="V",
        state_class="measurement",
    )
    as_dict = spec.to_dict()
    json.dumps(as_dict)  # must not raise
    assert as_dict["key"] == "battery_voltage"
    assert as_dict["translation_key"] == "battery_voltage"  # defaults to key


def test_entity_spec_translation_key_override():
    spec = EntitySpec(
        key="battery_voltage",
        name="Battery Voltage",
        device_class="voltage",
        unit="V",
        state_class="measurement",
        translation_key="system_battery_voltage",
    )
    assert spec.to_dict()["translation_key"] == "system_battery_voltage"


def test_entity_spec_enum_options_serialize_as_list():
    spec = EntitySpec(
        key="inverter_mode",
        name="Inverter Mode",
        device_class="enum",
        unit=None,
        state_class=None,
        options=("off", "search", "inverting"),
    )
    as_dict = spec.to_dict()
    assert as_dict["device_class"] == "enum"
    assert as_dict["state_class"] is None
    assert as_dict["options"] == ["off", "search", "inverting"]


# --- Inverter entities -----------------------------------------------------


def test_inverter_entities_cover_every_parser_state_key():
    """The schema must describe every field the inverter parser emits —
    otherwise the integration would fail to render a live field."""
    from pathlib import Path

    from src.parser import parse_frame

    fixtures = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "mate3_frames"
    updates = parse_frame((fixtures / "telemetry_00.bin").read_bytes(), "192.168.200.9")
    inverter_state = next(u.state for u in updates if u.kind == KIND_INVERTER)

    spec_keys = {spec.key for spec in INVERTER_ENTITIES}
    missing = set(inverter_state.keys()) - spec_keys
    assert not missing, f"Inverter parser emits keys not in schema: {missing}"


def test_charge_controller_entities_cover_every_parser_state_key():
    from pathlib import Path

    from src.parser import parse_frame

    fixtures = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "mate3_frames"
    updates = parse_frame((fixtures / "telemetry_00.bin").read_bytes(), "192.168.200.9")
    cc_state = next(u.state for u in updates if u.kind == KIND_CHARGE_CONTROLLER)

    spec_keys = {spec.key for spec in CHARGE_CONTROLLER_ENTITIES}
    missing = set(cc_state.keys()) - spec_keys
    assert not missing, f"Charge-controller parser emits keys not in schema: {missing}"


def test_inverter_battery_voltage_is_voltage_with_measurement():
    spec = next(s for s in INVERTER_ENTITIES if s.key == "battery_voltage")
    assert spec.device_class == "voltage"
    assert spec.unit == "V"
    assert spec.state_class == "measurement"


def test_inverter_mode_is_enum_with_all_parser_options():
    """inverter_mode options must cover every value _INVERTER_MODE can produce,
    otherwise HA will reject values it hasn't been told about."""
    from src.parser import _INVERTER_MODE

    spec = next(s for s in INVERTER_ENTITIES if s.key == "inverter_mode")
    assert spec.device_class == "enum"
    assert spec.state_class is None
    assert spec.options is not None
    # Every parser output value must appear in options; include "unknown"
    # since the parser emits that as a fallback for unmapped mode ints.
    expected = set(_INVERTER_MODE.values()) | {"unknown"}
    assert set(spec.options) == expected


def test_ac_mode_and_grid_mode_are_enums_with_options():
    ac = next(s for s in INVERTER_ENTITIES if s.key == "ac_mode")
    assert ac.device_class == "enum"
    assert set(ac.options or ()) == {"no-ac", "ac-drop", "ac-use", "unknown"}

    grid = next(s for s in INVERTER_ENTITIES if s.key == "grid_mode")
    assert grid.device_class == "enum"
    assert set(grid.options or ()) == {"grid", "generator"}


# --- Charge controller entities --------------------------------------------


def test_cc_daily_ah_is_total_increasing_counter():
    """F3: daily_ah resets at midnight → TOTAL_INCREASING."""
    spec = next(s for s in CHARGE_CONTROLLER_ENTITIES if s.key == "daily_ah")
    assert spec.device_class is None
    assert spec.unit == "Ah"
    assert spec.state_class == "total_increasing"


def test_cc_kwh_today_is_energy_total_increasing():
    spec = next(s for s in CHARGE_CONTROLLER_ENTITIES if s.key == "kwh_today")
    assert spec.device_class == "energy"
    assert spec.unit == "kWh"
    assert spec.state_class == "total_increasing"


def test_cc_charge_mode_enum_options():
    from src.parser import _CHARGE_MODE

    spec = next(s for s in CHARGE_CONTROLLER_ENTITIES if s.key == "charge_mode")
    assert spec.device_class == "enum"
    expected = set(_CHARGE_MODE.values()) | {"unknown"}
    assert set(spec.options or ()) == expected


# --- build_live_schema -----------------------------------------------------


def test_build_live_schema_covers_both_device_kinds():
    schema = build_live_schema()
    assert set(schema.keys()) == {KIND_INVERTER, KIND_CHARGE_CONTROLLER}
    assert len(schema[KIND_INVERTER]) == len(INVERTER_ENTITIES)
    assert len(schema[KIND_CHARGE_CONTROLLER]) == len(CHARGE_CONTROLLER_ENTITIES)


def test_build_live_schema_is_json_serializable():
    json.dumps(build_live_schema())  # must not raise


def test_build_live_schema_entries_have_required_fields():
    schema = build_live_schema()
    required = {
        "key",
        "name",
        "device_class",
        "unit",
        "state_class",
        "entity_category",
        "translation_key",
        "options",
    }
    for kind, entries in schema.items():
        for entry in entries:
            assert required.issubset(
                entry.keys()
            ), f"{kind}.{entry.get('key')} missing keys: {required - entry.keys()}"
