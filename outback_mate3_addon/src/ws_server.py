"""aiohttp-based WebSocket broadcast server.

Serves one endpoint, ``/ws``. On client connect, sends a ``snapshot`` message
with the registry's current device list. Subsequent :class:`DeviceAdded` /
:class:`StateUpdated` events are broadcast to all connected clients via
:meth:`WSServer.broadcast`. Clients whose sockets have closed or errored are
pruned from the fan-out set on the next broadcast.

Ping/pong is handled by aiohttp's protocol-level heartbeat
(:class:`WebSocketResponse` ``heartbeat`` argument).
"""
from __future__ import annotations

import logging
from typing import Any

from aiohttp import WSMsgType, web

from src.state import DeviceAdded, DeviceRegistry, Event, StateUpdated

_LOGGER = logging.getLogger(__name__)

# Send a ping every 30s; close the socket if no pong within 10s.
HEARTBEAT_S = 30.0


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
    raise TypeError(f"Unknown event type: {type(event).__name__}")


class WSServer:
    def __init__(self, registry: DeviceRegistry, heartbeat: float = HEARTBEAT_S) -> None:
        self._registry = registry
        self._heartbeat = heartbeat
        self._clients: set[web.WebSocketResponse] = set()
        self.app = web.Application()
        self.app.router.add_get("/ws", self._handle_ws)

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def _handle_ws(self, request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=self._heartbeat)
        await ws.prepare(request)

        await ws.send_json({"type": "snapshot", "devices": self._registry.snapshot()})

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

    async def broadcast(self, events: list[Event]) -> None:
        """Send events to every connected client. Drops dead clients silently."""
        if not events or not self._clients:
            return
        messages = [event_to_message(e) for e in events]
        # Snapshot the client set so we can mutate it while iterating.
        for ws in list(self._clients):
            try:
                for msg in messages:
                    await ws.send_json(msg)
            except (ConnectionResetError, RuntimeError) as exc:
                _LOGGER.debug("Dropping dead WS client: %s", exc)
                self._clients.discard(ws)

    async def close_all(self) -> None:
        """Close all currently connected clients (for graceful shutdown)."""
        for ws in list(self._clients):
            await ws.close()
        self._clients.clear()
