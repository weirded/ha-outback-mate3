"""End-to-end test: UDP datagram in → WebSocket event out."""

from __future__ import annotations

import asyncio
import socket
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from aiohttp.test_utils import TestClient, TestServer
from src.state import DeviceRegistry
from src.udp_listener import start_listener
from src.ws_server import WSServer

FIXTURES = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "mate3_frames"


class FakeClock:
    def __init__(self, t: datetime):
        self.t = t

    def __call__(self) -> datetime:
        return self.t


@pytest_asyncio.fixture
async def pipeline():
    """Start a full pipeline on an ephemeral UDP port and a TestClient-managed WS."""
    registry = DeviceRegistry(min_update_interval_s=0, clock=FakeClock(datetime(2026, 4, 17)))
    server = WSServer(registry, heartbeat=100)

    # Bind UDP to ephemeral port (host loopback).
    # Can't use port 0 with create_datagram_endpoint the usual way; we let the OS pick.
    transport = await start_listener("127.0.0.1", 0, registry, server)
    sockname = transport.get_extra_info("sockname")
    udp_port = sockname[1]

    # Kick off the broadcaster consumer that drains WSServer's queue; in
    # production this is started by `main.py`.
    stop = asyncio.Event()
    broadcaster = asyncio.create_task(server.run_broadcaster(stop))

    async with TestClient(TestServer(server.app)) as ws_client:
        yield udp_port, ws_client

    transport.close()
    stop.set()
    await broadcaster


@pytest.mark.asyncio
async def test_udp_frame_propagates_to_ws_client(pipeline):
    udp_port, ws_client = pipeline

    async with ws_client.ws_connect("/ws") as ws:
        # Consume initial (empty) snapshot.
        snap = await asyncio.wait_for(ws.receive_json(), timeout=2)
        assert snap == {"type": "snapshot", "devices": []}
        await asyncio.sleep(0.05)  # let server register this client

        # Send one real telemetry frame over UDP to the listener.
        payload = (FIXTURES / "telemetry_00.bin").read_bytes()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(payload, ("127.0.0.1", udp_port))
        finally:
            sock.close()

        # We should receive 4 device_added events (2 inverters, 2 chargers).
        received = []
        for _ in range(4):
            msg = await asyncio.wait_for(ws.receive_json(), timeout=2)
            received.append(msg)

        assert all(m["type"] == "device_added" for m in received)
        kinds = sorted(m["kind"] for m in received)
        assert kinds == ["charge_controller", "charge_controller", "inverter", "inverter"]


@pytest.mark.asyncio
async def test_noise_udp_frame_produces_no_events(pipeline):
    udp_port, ws_client = pipeline

    async with ws_client.ws_connect("/ws") as ws:
        await ws.receive_json()  # empty snapshot
        await asyncio.sleep(0.05)

        # Send a non-telemetry payload (HTTP log line fixture).
        payload = (FIXTURES / "noise_httpost.bin").read_bytes()
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.sendto(payload, ("127.0.0.1", udp_port))
        finally:
            sock.close()

        # Nothing should be received within a short window.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.receive_json(), timeout=0.3)
