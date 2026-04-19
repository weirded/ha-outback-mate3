"""Tests for DeviceRegistry."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from src.parser import KIND_CHARGE_CONTROLLER, KIND_INVERTER, DeviceUpdate, parse_frame
from src.state import DeviceAdded, DeviceRegistry, StateUpdated

FIXTURES = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "mate3_frames"
MAC = "AAAAAABBBBBB"


class FakeClock:
    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _updates(filename: str) -> list[DeviceUpdate]:
    return parse_frame((FIXTURES / filename).read_bytes(), "192.168.200.9")


# --- First-time ingestion ---------------------------------------------------


def test_first_frame_emits_device_added_for_every_device():
    clock = FakeClock(datetime(2026, 4, 17, 12, 0, 0))
    reg = DeviceRegistry(min_update_interval_s=30, clock=clock)
    events = reg.apply(_updates("telemetry_00.bin"))

    assert len(events) == 4
    assert all(isinstance(e, DeviceAdded) for e in events)
    assert [(e.kind, e.index) for e in events] == [
        (KIND_INVERTER, 1),
        (KIND_INVERTER, 2),
        (KIND_CHARGE_CONTROLLER, 1),
        (KIND_CHARGE_CONTROLLER, 2),
    ]
    assert len(reg) == 4


def test_snapshot_reflects_registered_devices():
    clock = FakeClock(datetime(2026, 4, 17, 12, 0, 0))
    reg = DeviceRegistry(min_update_interval_s=30, clock=clock)
    reg.apply(_updates("telemetry_00.bin"))

    snap = reg.snapshot()
    assert len(snap) == 4
    keys = {(s["mac"], s["kind"], s["index"]) for s in snap}
    assert keys == {
        (MAC, KIND_INVERTER, 1),
        (MAC, KIND_INVERTER, 2),
        (MAC, KIND_CHARGE_CONTROLLER, 1),
        (MAC, KIND_CHARGE_CONTROLLER, 2),
    }
    inv1 = next(s for s in snap if s["kind"] == KIND_INVERTER and s["index"] == 1)
    assert inv1["state"]["inverter_mode"] == "offsetting"


# --- Throttling ------------------------------------------------------------


def test_frame_within_throttle_window_is_dropped():
    clock = FakeClock(datetime(2026, 4, 17, 12, 0, 0))
    reg = DeviceRegistry(min_update_interval_s=30, clock=clock)
    reg.apply(_updates("telemetry_00.bin"))

    clock.advance(5)
    events = reg.apply(_updates("telemetry_01.bin"))
    assert events == []


def test_frame_past_throttle_window_emits_state_updated():
    clock = FakeClock(datetime(2026, 4, 17, 12, 0, 0))
    reg = DeviceRegistry(min_update_interval_s=30, clock=clock)
    reg.apply(_updates("telemetry_00.bin"))

    clock.advance(31)
    events = reg.apply(_updates("telemetry_01.bin"))

    assert len(events) == 4
    assert all(isinstance(e, StateUpdated) for e in events)


def test_throttle_is_per_mac():
    clock = FakeClock(datetime(2026, 4, 17, 12, 0, 0))
    reg = DeviceRegistry(min_update_interval_s=30, clock=clock)
    reg.apply(_updates("telemetry_00.bin"))

    clock.advance(1)
    # Updates from a DIFFERENT MAC should go through even inside the window.
    other = [DeviceUpdate(mac="OTHER1111111", kind=KIND_INVERTER, index=1, state={"x": 1})]
    events = reg.apply(other)
    assert len(events) == 1
    assert isinstance(events[0], DeviceAdded)


# --- Update semantics ------------------------------------------------------


def test_second_frame_for_same_device_emits_state_updated_not_added():
    clock = FakeClock(datetime(2026, 4, 17, 12, 0, 0))
    reg = DeviceRegistry(min_update_interval_s=0, clock=clock)

    reg.apply(_updates("telemetry_00.bin"))
    events = reg.apply(_updates("telemetry_01.bin"))

    assert len(events) == 4
    assert all(isinstance(e, StateUpdated) for e in events)


def test_registry_stores_latest_state():
    clock = FakeClock(datetime(2026, 4, 17, 12, 0, 0))
    reg = DeviceRegistry(min_update_interval_s=0, clock=clock)

    reg.apply(_updates("telemetry_00.bin"))
    reg.apply(_updates("telemetry_04.bin"))

    state = reg.device(MAC, KIND_INVERTER, 1)
    last_frame_inv1 = next(
        u for u in _updates("telemetry_04.bin") if u.kind == KIND_INVERTER and u.index == 1
    ).state
    assert state == last_frame_inv1


def test_apply_empty_is_noop():
    reg = DeviceRegistry()
    assert reg.apply([]) == []
    assert len(reg) == 0


def test_mixed_mac_batch_raises():
    reg = DeviceRegistry()
    batch = [
        DeviceUpdate(mac="A", kind=KIND_INVERTER, index=1, state={}),
        DeviceUpdate(mac="B", kind=KIND_INVERTER, index=1, state={}),
    ]
    try:
        reg.apply(batch)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for mixed-MAC batch")


def test_state_in_event_is_a_copy():
    """Mutating an emitted event's state dict must not affect the registry's stored copy."""
    clock = FakeClock(datetime(2026, 4, 17, 12, 0, 0))
    reg = DeviceRegistry(min_update_interval_s=0, clock=clock)
    events = reg.apply(_updates("telemetry_00.bin"))
    events[0].state["inverter_mode"] = "TAMPERED"

    inv1 = reg.device(MAC, KIND_INVERTER, 1)
    assert inv1 is not None
    assert inv1["inverter_mode"] != "TAMPERED"
