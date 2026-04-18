"""asyncio UDP listener that wires MATE3 frames through the parser,
registry, and WebSocket broadcast.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.parser import parse_frame
from src.state import DeviceRegistry
from src.ws_server import WSServer

_LOGGER = logging.getLogger(__name__)


class _Mate3DatagramProtocol(asyncio.DatagramProtocol):
    """Hands every datagram to ``on_datagram(data, remote_ip)``."""

    def __init__(self, on_datagram) -> None:
        self._on_datagram = on_datagram

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._on_datagram(data, addr[0])

    def error_received(self, exc: Exception) -> None:
        _LOGGER.warning("UDP receive error: %s", exc)


async def start_listener(
    host: str,
    port: int,
    registry: DeviceRegistry,
    server: WSServer,
) -> asyncio.DatagramTransport:
    """Bind a UDP socket that feeds every MATE3 frame through the pipeline.

    Returns the asyncio datagram transport so the caller can close it on shutdown.
    """
    loop = asyncio.get_running_loop()

    def handle(data: bytes, remote_ip: str) -> None:
        try:
            updates = parse_frame(data, remote_ip)
        except Exception:
            _LOGGER.exception("parse_frame failed for datagram from %s", remote_ip)
            return
        if not updates:
            return
        events = registry.apply(updates)
        if not events:
            return
        # Fire-and-forget broadcast; exceptions get logged but don't block ingress.
        asyncio.create_task(_safe_broadcast(server, events))

    transport, _ = await loop.create_datagram_endpoint(
        lambda: _Mate3DatagramProtocol(handle),
        local_addr=(host, port),
    )
    _LOGGER.info("Listening for MATE3 UDP on %s:%d", host, port)
    return transport  # type: ignore[return-value]


async def _safe_broadcast(server: WSServer, events: list[Any]) -> None:
    try:
        await server.broadcast(events)
    except Exception:
        _LOGGER.exception("WS broadcast failed")
