"""Periodic MATE3 HTTP config poller.

Polls each known MATE3 (by source IP learned from the UDP stream) for its
``CONFIG.xml`` on a fixed interval, stores the parsed result in the
``DeviceRegistry``, and broadcasts a ``ConfigSnapshot`` event over the
WebSocket when the parsed dict differs from the previous one.

Waits for the first UDP datagram before the first poll, since without it
we don't know which IP to reach. Subsequent polls iterate every known
source on each tick.
"""
from __future__ import annotations

import asyncio
import logging

from src.mate3_http import fetch_config
from src.state import ConfigSnapshot, DeviceRegistry
from src.ws_server import WSServer

_LOGGER = logging.getLogger(__name__)


async def run(
    registry: DeviceRegistry,
    server: WSServer,
    interval_s: float,
    stop: asyncio.Event,
) -> None:
    """Run the poll loop until ``stop`` is set. Disabled when interval_s <= 0."""
    if interval_s <= 0:
        _LOGGER.info("Config polling disabled (interval=%s)", interval_s)
        await stop.wait()
        return

    _LOGGER.info("Config poller starting; interval=%.0fs", interval_s)

    # Wait for the first UDP datagram so we know at least one MATE3 IP.
    while not registry.known_sources() and not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=5)
        except asyncio.TimeoutError:
            pass
    if stop.is_set():
        return

    while not stop.is_set():
        for mac, host in registry.known_sources():
            _LOGGER.debug("Polling CONFIG.xml from %s (mac=%s)", host, mac)
            config = await fetch_config(host)
            if config is None:
                _LOGGER.debug("No config returned from %s", host)
                continue
            changed = registry.set_config(mac, config)
            if changed:
                _LOGGER.info("Config for %s (%s) changed; broadcasting", mac, host)
                server.enqueue_broadcast([ConfigSnapshot(mac=mac, config=config)])
            else:
                _LOGGER.debug("Config for %s (%s) unchanged", mac, host)

        try:
            await asyncio.wait_for(stop.wait(), timeout=interval_s)
        except asyncio.TimeoutError:
            pass  # interval elapsed, loop for another poll
