"""Tests for the WS config-entity schema published by the add-on.

The config schema tells the integration what entities to materialize from
the MATE3's HTTP CONFIG.xml poll. It lives next to the live entity schema
so the integration can be a pure rendering layer with zero MATE3-specific
knowledge.
"""

from __future__ import annotations

import json

from src.config_schema import (
    CC_CONFIG_ENTITIES,
    INVERTER_CONFIG_ENTITIES,
    SYSTEM_CONFIG_ENTITIES,
    ConfigEntitySpec,
    build_config_schema,
)


def test_config_entity_spec_is_jsonable():
    spec = ConfigEntitySpec(
        key="mate3_firmware",
        name="MATE3 Firmware",
        section="mate3",
        device_class=None,
        unit=None,
        is_firmware=True,
    )
    as_dict = spec.to_dict()
    json.dumps(as_dict)
    assert as_dict["key"] == "mate3_firmware"
    assert as_dict["section"] == "mate3"
    assert as_dict["is_firmware"] is True
    assert as_dict["translation_key"] == "mate3_firmware"


def test_system_schema_includes_nominal_voltage_with_voltage_device_class():
    spec = next(s for s in SYSTEM_CONFIG_ENTITIES if s.key == "nominal_voltage")
    assert spec.section == "system"
    assert spec.device_class == "voltage"
    assert spec.unit == "V"
    assert spec.is_firmware is False


def test_system_schema_includes_mate3_firmware_as_firmware():
    spec = next(s for s in SYSTEM_CONFIG_ENTITIES if s.key == "mate3_firmware")
    assert spec.section == "mate3"
    assert spec.is_firmware is True


def test_system_schema_includes_precomputed_data_stream_target():
    """The composite `data_stream_target` field is precomputed by the add-on
    into the mate3 config block so the spec table stays declarative."""
    spec = next(s for s in SYSTEM_CONFIG_ENTITIES if s.key == "data_stream_target")
    assert spec.section == "mate3"
    assert spec.device_class is None
    assert spec.unit is None


def test_system_schema_includes_grid_use_programmatic_entries():
    """Grid_Use time-of-use specs are generated programmatically (19 per profile
    x 3 profiles = 57) — the total spec count must reflect that."""
    keys = {s.key for s in SYSTEM_CONFIG_ENTITIES}
    # Mode + 18 drop/use hour/min entries per profile.
    for prefix in ("grid_use", "grid_use_p2", "grid_use_p3"):
        assert f"{prefix}_mode" in keys
        assert f"{prefix}_weekday_drop_hour" in keys
        assert f"{prefix}_weekend_use_min" in keys


def test_inverter_schema_firmware_is_marked():
    spec = next(s for s in INVERTER_CONFIG_ENTITIES if s.key == "firmware")
    assert spec.is_firmware is True
    assert spec.section is None


def test_inverter_schema_voltage_setpoint_carries_device_class():
    spec = next(s for s in INVERTER_CONFIG_ENTITIES if s.key == "charger_absorb_voltage")
    assert spec.device_class == "voltage"
    assert spec.unit == "V"


def test_inverter_schema_configured_type_renames_source_key():
    """`configured_type` reads from `type` in the config dict to avoid name
    collision with the live inverter type field."""
    spec = next(s for s in INVERTER_CONFIG_ENTITIES if s.key == "configured_type")
    assert spec.effective_source_key == "type"


def test_inverter_schema_configured_inverter_mode_renames_source_key():
    spec = next(s for s in INVERTER_CONFIG_ENTITIES if s.key == "configured_inverter_mode")
    assert spec.effective_source_key == "inverter_mode"


def test_cc_schema_firmware_is_marked():
    spec = next(s for s in CC_CONFIG_ENTITIES if s.key == "firmware")
    assert spec.is_firmware is True


def test_cc_schema_mppt_upick_percentage_unit():
    spec = next(s for s in CC_CONFIG_ENTITIES if s.key == "mppt_upick_percentage")
    assert spec.unit == "%"
    assert spec.device_class is None


def test_build_config_schema_has_three_sections():
    schema = build_config_schema()
    assert set(schema.keys()) == {"system", "inverter", "charge_controller"}
    assert len(schema["system"]) == len(SYSTEM_CONFIG_ENTITIES)
    assert len(schema["inverter"]) == len(INVERTER_CONFIG_ENTITIES)
    assert len(schema["charge_controller"]) == len(CC_CONFIG_ENTITIES)


def test_build_config_schema_is_json_serializable():
    json.dumps(build_config_schema())


def test_build_config_schema_entries_have_required_fields():
    schema = build_config_schema()
    required = {
        "key",
        "name",
        "device_class",
        "unit",
        "is_firmware",
        "translation_key",
        "source_key",
    }
    for kind, entries in schema.items():
        for entry in entries:
            assert required.issubset(
                entry.keys()
            ), f"{kind}.{entry.get('key')} missing: {required - entry.keys()}"
    # Only system entries carry a section.
    for entry in schema["system"]:
        assert "section" in entry
        assert entry["section"] in ("system", "mate3")
    for entry in schema["inverter"]:
        assert entry.get("section") is None
    for entry in schema["charge_controller"]:
        assert entry.get("section") is None


def test_source_key_defaults_to_key_when_not_renamed():
    """Most entries have no explicit source_key rename — serialized form must
    fall back to the spec's key so the integration can just look it up."""
    spec = next(s for s in INVERTER_CONFIG_ENTITIES if s.key == "charger_absorb_voltage")
    assert spec.to_dict()["source_key"] == "charger_absorb_voltage"
    spec = next(s for s in CC_CONFIG_ENTITIES if s.key == "mppt_mode")
    assert spec.to_dict()["source_key"] == "mppt_mode"


def test_source_key_rename_preserved_in_serialization():
    spec = next(s for s in INVERTER_CONFIG_ENTITIES if s.key == "configured_type")
    assert spec.to_dict()["source_key"] == "type"
