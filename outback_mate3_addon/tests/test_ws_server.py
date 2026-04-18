"""Tests for the WebSocket broadcast server."""
from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer

from src.parser import KIND_INVERTER, parse_frame
from src.state import DeviceAdded, DeviceRegistry, StateUpdated
from src.ws_server import WSServer, event_to_message

FIXTURES = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "mate3_frames"


class FakeClock:
    def __init__(self, t: datetime):
        self.t = t

    def __call__(self) -> datetime:
        return self.t


def _populated_registry() -> DeviceRegistry:
    reg = DeviceRegistry(min_update_interval_s=0, clock=FakeClock(datetime(2026, 4, 17)))
    reg.apply(parse_frame((FIXTURES / "telemetry_00.bin").read_bytes(), "192.168.200.9"))
    return reg


@pytest_asyncio.fixture
async def ws_setup():
    server = WSServer(_populated_registry(), heartbeat=100)
    async with TestClient(TestServer(server.app)) as client:
        yield server, client


# --- event_to_message -------------------------------------------------------

def test_event_to_message_for_device_added():
    evt = DeviceAdded(mac="A", kind=KIND_INVERTER, index=1, state={"x": 1})
    assert event_to_message(evt) == {
        "type": "device_added",
        "mac": "A",
        "kind": KIND_INVERTER,
        "index": 1,
        "state": {"x": 1},
    }


def test_event_to_message_for_state_updated():
    evt = StateUpdated(mac="A", kind=KIND_INVERTER, index=1, state={"x": 2})
    assert event_to_message(evt)["type"] == "state_updated"


def test_event_to_message_rejects_unknown_type():
    with pytest.raises(TypeError):
        event_to_message("not an event")  # type: ignore[arg-type]


# --- Snapshot on connect ----------------------------------------------------

@pytest.mark.asyncio
async def test_new_client_receives_snapshot(ws_setup):
    _, ws_client = ws_setup
    async with ws_client.ws_connect("/ws") as ws:
        msg = await asyncio.wait_for(ws.receive_json(), timeout=2)
        assert msg["type"] == "snapshot"
        assert len(msg["devices"]) == 4
        kinds = sorted(d["kind"] for d in msg["devices"])
        assert kinds == ["charge_controller", "charge_controller", "inverter", "inverter"]


@pytest.mark.asyncio
async def test_snapshot_contains_state(ws_setup):
    _, ws_client = ws_setup
    async with ws_client.ws_connect("/ws") as ws:
        msg = await asyncio.wait_for(ws.receive_json(), timeout=2)
        inv1 = next(d for d in msg["devices"] if d["kind"] == "inverter" and d["index"] == 1)
        assert inv1["state"]["inverter_mode"] == "offsetting"


# --- Broadcast --------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_delivers_to_connected_client(ws_setup):
    server, ws_client = ws_setup
    async with ws_client.ws_connect("/ws") as ws:
        await ws.receive_json()  # consume snapshot
        await asyncio.sleep(0.05)

        evt = StateUpdated(mac="A", kind=KIND_INVERTER, index=1, state={"grid_power": 42})
        await server.broadcast([evt])

        msg = await asyncio.wait_for(ws.receive_json(), timeout=2)
        assert msg["type"] == "state_updated"
        assert msg["state"] == {"grid_power": 42}


@pytest.mark.asyncio
async def test_broadcast_delivers_to_multiple_clients(ws_setup):
    server, ws_client = ws_setup
    async with ws_client.ws_connect("/ws") as ws1, ws_client.ws_connect("/ws") as ws2:
        await ws1.receive_json()
        await ws2.receive_json()
        await asyncio.sleep(0.05)
        assert server.client_count == 2

        evt = DeviceAdded(mac="A", kind=KIND_INVERTER, index=99, state={"new": True})
        await server.broadcast([evt])

        m1 = await asyncio.wait_for(ws1.receive_json(), timeout=2)
        m2 = await asyncio.wait_for(ws2.receive_json(), timeout=2)
        assert m1["type"] == m2["type"] == "device_added"
        assert m1["index"] == m2["index"] == 99


@pytest.mark.asyncio
async def test_broadcast_with_no_clients_is_noop(ws_setup):
    server, _ = ws_setup
    await server.broadcast([DeviceAdded(mac="A", kind=KIND_INVERTER, index=1, state={})])


@pytest.mark.asyncio
async def test_disconnected_client_is_removed_from_clients_set(ws_setup):
    server, ws_client = ws_setup
    async with ws_client.ws_connect("/ws") as ws:
        await ws.receive_json()
        await asyncio.sleep(0.05)
        assert server.client_count == 1
    await asyncio.sleep(0.1)
    assert server.client_count == 0
