"""Entry point for the Outback MATE3 add-on.

Reads configuration from environment variables populated by ``run.sh`` (which
pulls them out of ``/data/options.json`` via bashio), wires the pipeline
(UDP → parser → registry → WebSocket broadcast), and serves both the UDP
listener and the HTTP/WebSocket server until SIGTERM/SIGINT.
"""
from __future__ import annotations

import asyncio
import logging
import os
import signal

from aiohttp import web

from src.state import DeviceRegistry
from src.udp_listener import start_listener
from src.ws_server import WSServer

_LOGGER = logging.getLogger("outback_mate3_addon")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    # bashio returns the literal string "null" for unset options; treat as missing.
    if not raw or raw.lower() == "null":
        return default
    return int(raw)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw or raw.lower() == "null":
        return default
    return float(raw)


def _configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


async def run() -> None:
    udp_port = _env_int("UDP_PORT", 57027)
    ws_port = _env_int("WS_PORT", 8099)
    log_level = os.environ.get("LOG_LEVEL", "info")
    min_interval = _env_float("MIN_UPDATE_INTERVAL_S", 30.0)

    _configure_logging(log_level)
    _LOGGER.info(
        "Starting Outback MATE3 relay: UDP :%d → WS :%d (throttle %.1fs)",
        udp_port, ws_port, min_interval,
    )

    registry = DeviceRegistry(min_update_interval_s=min_interval)
    server = WSServer(registry)

    runner = web.AppRunner(server.app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", ws_port)
    await site.start()
    _LOGGER.info("WebSocket server listening on 0.0.0.0:%d/ws", ws_port)

    transport = await start_listener("0.0.0.0", udp_port, registry, server)

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()

    _LOGGER.info("Shutdown signal received; closing transports")
    transport.close()
    await server.close_all()
    await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(run())
