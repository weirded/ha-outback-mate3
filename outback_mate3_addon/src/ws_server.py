"""aiohttp-based WebSocket broadcast server.

Serves one endpoint, ``/ws``. On client connect, sends a ``snapshot`` message
with the registry's current device list. Subsequent :class:`DeviceAdded` /
:class:`StateUpdated` events flow through :meth:`WSServer.enqueue_broadcast`
(a non-blocking, bounded enqueue the UDP callback can call from sync
context), get picked up by :meth:`WSServer.run_broadcaster`, and fan out to
each connected client in parallel with a per-send timeout so one slow
client can't stall the others.

Ping/pong is handled by aiohttp's protocol-level heartbeat
(:class:`WebSocketResponse` ``heartbeat`` argument).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import WSMsgType, web

from src.state import ConfigSnapshot, DeviceAdded, DeviceRegistry, Event, StateUpdated

_LOGGER = logging.getLogger(__name__)

# Send a ping every 30s; close the socket if no pong within 10s.
HEARTBEAT_S = 30.0

# Upper bound on the broadcast queue. The MATE3 streams one frame/second per
# device; with the 30 s per-MAC throttle we typically enqueue one batch every
# 30 s, so 200 accommodates ~100 minutes of stalled fan-out before we start
# dropping — far beyond any realistic recovery window.
_BROADCAST_QUEUE_MAX = 200
# Per-client send timeout. A client this slow is effectively dead; drop it so
# one stuck consumer can't hold up the fan-out forever.
_SEND_TIMEOUT_S = 10.0


def event_to_message(event: Event) -> dict[str, Any]:
    """Serialize an event to its on-wire JSON shape."""
    if isinstance(event, DeviceAdded):
        return {
            "type": "device_added",
            "mac": event.mac,
            "kind": event.kind,
            "index": event.index,
            "state": event.state,
        }
    if isinstance(event, StateUpdated):
        return {
            "type": "state_updated",
            "mac": event.mac,
            "kind": event.kind,
            "index": event.index,
            "state": event.state,
        }
    if isinstance(event, ConfigSnapshot):
        return {
            "type": "config_snapshot",
            "mac": event.mac,
            "config": event.config,
        }
    raise TypeError(f"Unknown event type: {type(event).__name__}")


class WSServer:
    def __init__(
        self,
        registry: DeviceRegistry,
        heartbeat: float = HEARTBEAT_S,
        queue_max: int = _BROADCAST_QUEUE_MAX,
        send_timeout_s: float = _SEND_TIMEOUT_S,
        addon_version: str | None = None,
    ) -> None:
        self._registry = registry
        self._heartbeat = heartbeat
        self._send_timeout_s = send_timeout_s
        self._addon_version = addon_version
        self._clients: set[web.WebSocketResponse] = set()
        self._queue: asyncio.Queue[list[Event]] = asyncio.Queue(maxsize=queue_max)
        self._dropped_batches = 0
        self.app = web.Application()
        self.app.router.add_get("/ws", self._handle_ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    @property
    def dropped_batches(self) -> int:
        """How many enqueue attempts were rejected because the queue was full."""
        return self._dropped_batches

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=self._heartbeat)
        await ws.prepare(request)

        # Send a hello first so the integration can surface a Repairs issue
        # if its own manifest version doesn't match ours. Omitted when we
        # don't know our own version (e.g. unit tests that don't set it) so
        # the test fakes don't have to hand-drain an extra frame.
        if self._addon_version is not None:
            await ws.send_json(
                {"type": "hello", "addon_version": self._addon_version}
            )
        await ws.send_json({"type": "snapshot", "devices": self._registry.snapshot()})
        # Replay the last known config for each MAC so new clients get the
        # full picture without having to wait for the next poll interval.
        for mac, config in self._registry.configs().items():
            await ws.send_json({"type": "config_snapshot", "mac": mac, "config": config})

        self._clients.add(ws)
        peer = request.remote or "unknown"
        _LOGGER.info("WS client connected (%s); %d total", peer, len(self._clients))

        try:
            async for msg in ws:
                # Clients aren't expected to send anything meaningful today.
                # Consume messages so aiohttp keeps the socket alive and heartbeat works.
                if msg.type == WSMsgType.ERROR:
                    _LOGGER.warning("WS error from %s: %s", peer, ws.exception())
                    break
        finally:
            self._clients.discard(ws)
            _LOGGER.info("WS client disconnected (%s); %d remain", peer, len(self._clients))

        return ws

    def enqueue_broadcast(self, events: list[Event]) -> None:
        """Schedule ``events`` for broadcast. Safe to call from sync context.

        Non-blocking: if the queue is full (consumer stalled), the batch is
        dropped and the drop count is logged periodically. This is the path
        used by :mod:`udp_listener` from its datagram callback.
        """
        if not events:
            return
        try:
            self._queue.put_nowait(events)
        except asyncio.QueueFull:
            self._dropped_batches += 1
            # Log every Nth drop so a persistent stall is visible without
            # flooding the log.
            if self._dropped_batches == 1 or self._dropped_batches % 100 == 0:
                _LOGGER.warning(
                    "Broadcast queue full; dropped %d event batches total",
                    self._dropped_batches,
                )

    async def run_broadcaster(self, stop: asyncio.Event) -> None:
        """Consume enqueued event batches and fan out to clients until ``stop``.

        One consumer task serializes broadcast ordering across all producers
        (UDP + config poller). Within a batch, clients are sent to in parallel
        with a per-client timeout so one slow client can't stall the rest.
        """
        while not stop.is_set():
            try:
                events = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except TimeoutError:
                continue
            try:
                await self.broadcast(events)
            except Exception:
                _LOGGER.exception("WS broadcast failed")

    async def broadcast(self, events: list[Event]) -> None:
        """Send events to every connected client in parallel.

        Clients that error or hit the per-send timeout are dropped.
        """
        if not events or not self._clients:
            return
        messages = [event_to_message(e) for e in events]
        clients = list(self._clients)
        results = await asyncio.gather(
            *(self._send_to(ws, messages) for ws in clients),
            return_exceptions=True,
        )
        for ws, result in zip(clients, results, strict=False):
            if isinstance(result, BaseException):
                _LOGGER.debug("Dropping unresponsive WS client: %r", result)
                self._clients.discard(ws)

    async def _send_to(
        self, ws: web.WebSocketResponse, messages: list[dict[str, Any]]
    ) -> None:
        """Send ``messages`` to a single client within the configured timeout."""
        async with asyncio.timeout(self._send_timeout_s):
            for msg in messages:
                await ws.send_json(msg)

    async def close_all(self) -> None:
        """Close all currently connected clients (for graceful shutdown)."""
        for ws in list(self._clients):
            await ws.close()
        self._clients.clear()
