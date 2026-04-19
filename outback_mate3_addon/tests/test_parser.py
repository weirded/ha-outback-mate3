"""Characterization tests for parser.parse_frame against captured MATE3 frames.

Expected values were taken by running the original integration's parser
(``custom_components/outback_mate3/__init__.py``) against the same fixtures,
so any divergence here would represent a behavior change.
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest
from src.parser import (
    KIND_CHARGE_CONTROLLER,
    KIND_INVERTER,
    DeviceUpdate,
    parse_frame,
)

FIXTURES = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "mate3_frames"
EXPECTED_MAC = "AAAAAABBBBBB"
REMOTE_IP = "192.168.200.9"


def _load(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


# --- Frame structure ---------------------------------------------------------

def test_telemetry_00_returns_four_devices():
    updates = parse_frame(_load("telemetry_00.bin"), REMOTE_IP)
    assert len(updates) == 4
    assert [u.kind for u in updates] == [
        KIND_INVERTER,
        KIND_INVERTER,
        KIND_CHARGE_CONTROLLER,
        KIND_CHARGE_CONTROLLER,
    ]
    assert [u.index for u in updates] == [1, 2, 1, 2]
    assert {u.mac for u in updates} == {EXPECTED_MAC}


def test_all_telemetry_fixtures_parse_to_four_devices():
    for i in range(5):
        updates = parse_frame(_load(f"telemetry_{i:02d}.bin"), REMOTE_IP)
        assert len(updates) == 4, f"telemetry_{i:02d}.bin produced {len(updates)} updates"


# --- Noise frames (non-telemetry) should be ignored --------------------------

@pytest.mark.parametrize("fixture", ["noise_fsop.bin", "noise_httpost.bin"])
def test_noise_frames_return_empty(fixture):
    assert parse_frame(_load(fixture), REMOTE_IP) == []


def test_empty_and_garbage_frames_return_empty():
    assert parse_frame(b"", REMOTE_IP) == []
    assert parse_frame(b"not a mate3 frame", REMOTE_IP) == []
    # Valid MAC prefix but no device blocks.
    assert parse_frame(b"[AAAAAA-BBBBBB]", REMOTE_IP) == []


def test_non_utf8_payload_is_ignored():
    assert parse_frame(b"\xff\xfe\xff\xfe", REMOTE_IP) == []


# --- Inverter value correctness (from telemetry_00.bin) ----------------------

@pytest.fixture
def t00_devices():
    return parse_frame(_load("telemetry_00.bin"), REMOTE_IP)


def _approx(actual, expected):
    assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9), (actual, expected)


def test_inverter_1_values(t00_devices):
    inv = next(u for u in t00_devices if u.kind == KIND_INVERTER and u.index == 1).state

    _approx(inv["l1_inverter_current"], 2.0)
    _approx(inv["l1_charger_current"], 0.0)
    _approx(inv["l1_buy_current"], 0.0)
    _approx(inv["l1_sell_current"], 1.0)
    _approx(inv["l1_ac_input_voltage"], 123.0)
    _approx(inv["l1_ac_output_voltage"], 123.0)
    _approx(inv["l1_grid_power"], -123.0)
    _approx(inv["l1_inverter_power"], 246.0)
    _approx(inv["l1_charger_power"], 0.0)

    _approx(inv["l2_inverter_current"], 2.0)
    _approx(inv["l2_buy_current"], 4.0)
    _approx(inv["l2_ac_input_voltage"], 124.0)
    _approx(inv["l2_ac_output_voltage"], 123.0)
    _approx(inv["l2_grid_power"], 496.0)

    _approx(inv["grid_power"], 373.0)
    _approx(inv["inverter_power"], 492.0)
    _approx(inv["charger_power"], 0.0)
    _approx(inv["total_ac_input_voltage"], 247.0)
    _approx(inv["total_ac_output_voltage"], 246.0)
    _approx(inv["battery_voltage"], 0.0)

    assert inv["inverter_mode"] == "offsetting"
    assert inv["ac_mode"] == "ac-use"
    assert inv["grid_mode"] == "generator"


def test_inverter_2_values(t00_devices):
    inv = next(u for u in t00_devices if u.kind == KIND_INVERTER and u.index == 2).state
    _approx(inv["grid_power"], 122.0)
    _approx(inv["inverter_power"], 494.0)
    assert inv["inverter_mode"] == "slave-on"
    assert inv["ac_mode"] == "ac-use"


# --- Charge controller value correctness (from telemetry_00.bin) -------------

def test_charge_controller_1_values(t00_devices):
    cc = next(
        u for u in t00_devices if u.kind == KIND_CHARGE_CONTROLLER and u.index == 1
    ).state
    _approx(cc["pv_current"], 11.0)
    _approx(cc["pv_voltage"], 88.0)
    _approx(cc["output_current"], 18.0)
    _approx(cc["pv_power"], 968.0)
    _approx(cc["battery_voltage"], 53.4)
    _approx(cc["output_power"], 18.0 * 53.4)
    _approx(cc["kwh_today"], 0.0)
    assert cc["charge_mode"] == "bulk"


def test_charge_controller_2_values(t00_devices):
    cc = next(
        u for u in t00_devices if u.kind == KIND_CHARGE_CONTROLLER and u.index == 2
    ).state
    _approx(cc["pv_current"], 8.0)
    _approx(cc["pv_voltage"], 85.0)
    _approx(cc["battery_voltage"], 53.5)
    assert cc["charge_mode"] == "bulk"


# --- 240V AC factor branch ---------------------------------------------------

def test_port_10_charge_controller_is_not_dropped():
    """R5 regression: the old filter required blocks to start with '0', which
    silently dropped any device on port 10+. Build a synthetic frame with a
    single charge controller on port 10 and confirm the parser returns it."""
    # CC block minimal: id, type=3, v2, v3 (output_current), v4 (pv_current),
    # v5 (pv_voltage), then fill up through v13 (kwh_today) — indices
    # referenced by _parse_charge_controller.
    cc_fields = ["10","3","0","7","5","80","0","0","0","0","1","534","0","0.5"]
    payload = f"[AAAAAA-BBBBBB]<{','.join(cc_fields)}>".encode()
    updates = parse_frame(payload, REMOTE_IP)
    assert len(updates) == 1
    assert updates[0].kind == KIND_CHARGE_CONTROLLER
    # `index` is type-local; with only one CC in the frame, it's 1.
    assert updates[0].index == 1
    _approx(updates[0].state["pv_current"], 5.0)
    _approx(updates[0].state["pv_voltage"], 80.0)


def test_malformed_block_without_port_prefix_is_skipped():
    """Trailing garbage after the last device should not crash the parser."""
    payload = b"[AAAAAA-BBBBBB]<01,3,0,1,2,50,0,0,0,0,0,500,0,0><garbage>"
    updates = parse_frame(payload, REMOTE_IP)
    assert len(updates) == 1
    assert updates[0].kind == KIND_CHARGE_CONTROLLER


def test_240v_ac_factor_doubles_voltage():
    """If raw L1 input voltage > 150, the parser treats it as 240V-ish and scales all voltages x2."""
    # Build a synthetic inverter block where values[6] > 150.
    # Layout: <id,type,v2..v20,...> — we need at least indices 2..20 populated.
    # Index:     0  1  2  3  4  5  6   7  8  9 10 11 12 13  14  15  16 17  18 19 20
    fields = ["01","6","1","0","0","0","200","00","100","0","0","0","0","0","0","0","0","0","0","0","0"]
    payload = f"[AAAAAA-BBBBBB]<{','.join(fields)}>".encode()
    updates = parse_frame(payload, REMOTE_IP)
    assert len(updates) == 1
    inv = updates[0].state
    _approx(inv["l1_ac_input_voltage"], 400.0)  # 200 * 2
    _approx(inv["l1_ac_output_voltage"], 200.0)  # 100 * 2


# --- Object identity ---------------------------------------------------------

def test_device_update_is_immutable():
    with pytest.raises(Exception):
        DeviceUpdate(mac="x", kind=KIND_INVERTER, index=1, state={}).mac = "y"  # type: ignore[misc]
