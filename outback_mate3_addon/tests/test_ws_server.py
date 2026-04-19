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


# --- Backpressure queue + broadcaster (R2) ----------------------------------


@pytest.mark.asyncio
async def test_enqueue_broadcast_is_delivered_via_run_broadcaster(ws_setup):
    """enqueue_broadcast() + run_broadcaster() == broadcast() as far as the client sees."""
    server, ws_client = ws_setup
    stop = asyncio.Event()
    consumer = asyncio.create_task(server.run_broadcaster(stop))
    try:
        async with ws_client.ws_connect("/ws") as ws:
            await ws.receive_json()  # snapshot
            await asyncio.sleep(0.05)

            server.enqueue_broadcast(
                [StateUpdated(mac="A", kind=KIND_INVERTER, index=1, state={"grid_power": 77})]
            )
            msg = await asyncio.wait_for(ws.receive_json(), timeout=2)
            assert msg == {
                "type": "state_updated",
                "mac": "A",
                "kind": KIND_INVERTER,
                "index": 1,
                "state": {"grid_power": 77},
            }
    finally:
        stop.set()
        await consumer


def test_enqueue_broadcast_full_queue_drops_and_counts():
    """When the consumer isn't running, the queue fills up and excess batches drop."""
    server = WSServer(_populated_registry(), heartbeat=100, queue_max=3)
    # No broadcaster running; the queue has capacity 3 — push 5 and see 2 drops.
    for i in range(5):
        server.enqueue_broadcast(
            [StateUpdated(mac="A", kind=KIND_INVERTER, index=i, state={})]
        )
    assert server.dropped_batches == 2


# --- Per-client isolation (R3) ---------------------------------------------


@pytest.mark.asyncio
async def test_one_slow_client_does_not_stall_other_clients(ws_setup):
    """A client that blocks inside send_json should not delay the other client."""
    server, ws_client = ws_setup

    # Two real clients connected; we'll monkey-patch one's send_json to hang.
    async with ws_client.ws_connect("/ws") as fast_ws, ws_client.ws_connect("/ws") as _slow_ws:
        await fast_ws.receive_json()
        await _slow_ws.receive_json()
        await asyncio.sleep(0.05)

        # Identify the server-side client objects and wrap one's send_json to
        # sleep long enough to blow past _SEND_TIMEOUT_S; the other should
        # receive its broadcast within the normal quick window.
        server._send_timeout_s = 0.2  # tighten so the test doesn't linger
        server_clients = list(server._clients)
        assert len(server_clients) == 2
        # Wrap an arbitrary one of the two — the test passes as long as the
        # OTHER client (whichever that is) still gets its message promptly.
        slow_client = server_clients[0]
        fast_client = server_clients[1]
        real_send = slow_client.send_json

        async def stuck_send(*a, **kw):
            await asyncio.sleep(5.0)  # way longer than the timeout

        slow_client.send_json = stuck_send  # type: ignore[method-assign]

        evt = DeviceAdded(mac="B", kind=KIND_INVERTER, index=7, state={"p": 1})
        start = asyncio.get_running_loop().time()
        await server.broadcast([evt])
        elapsed = asyncio.get_running_loop().time() - start

        # broadcast() must return in roughly the send timeout, not 5 s.
        assert elapsed < 1.0, f"broadcast stalled for {elapsed:.2f}s; timeout/parallelism broken"
        # And the slow client got dropped because it timed out.
        assert slow_client not in server._clients
        assert fast_client in server._clients
        # Restore so test cleanup doesn't trip.
        slow_client.send_json = real_send  # type: ignore[method-assign]
