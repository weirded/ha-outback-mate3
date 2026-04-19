"""asyncio UDP listener that wires MATE3 frames through the parser,
registry, and WebSocket broadcast.
"""

from __future__ import annotations

import asyncio
import logging

from src.parser import parse_frame
from src.state import DeviceRegistry
from src.ws_server import WSServer

_LOGGER = logging.getLogger(__name__)


class _Mate3DatagramProtocol(asyncio.DatagramProtocol):
    """Hands every datagram to ``on_datagram(data, remote_ip)``.

    Also logs the first datagram from each new source at INFO so operators
    can confirm traffic is landing without needing to flip to DEBUG.
    """

    def __init__(self, on_datagram) -> None:
        self._on_datagram = on_datagram
        self._seen_sources: set[str] = set()

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        remote_ip = addr[0]
        if remote_ip not in self._seen_sources:
            self._seen_sources.add(remote_ip)
            _LOGGER.info("First UDP datagram from %s (%d bytes)", remote_ip, len(data))
        _LOGGER.debug("UDP %d bytes from %s: %r", len(data), remote_ip, data[:80])
        self._on_datagram(data, remote_ip)

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
            _LOGGER.debug(
                "Datagram from %s produced no device updates (ignored as non-telemetry)",
                remote_ip,
            )
            return
        _LOGGER.debug("Parsed %d device updates from %s", len(updates), remote_ip)
        events = registry.apply(updates, remote_ip=remote_ip)
        if not events:
            _LOGGER.debug("Registry produced no events for %s (likely throttled)", remote_ip)
            return
        _LOGGER.debug("Broadcasting %d events", len(events))
        # Non-blocking, bounded enqueue. The single broadcaster consumer
        # task in WSServer pulls from here and does the actual fan-out,
        # so we can't leak an unbounded number of pending send tasks
        # even if the WS clients stall.
        server.enqueue_broadcast(events)

    transport, _ = await loop.create_datagram_endpoint(
        lambda: _Mate3DatagramProtocol(handle),
        local_addr=(host, port),
    )
    _LOGGER.info("Listening for MATE3 UDP on %s:%d", host, port)
    return transport  # type: ignore[return-value]
