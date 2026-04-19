"""Hass.io discovery announce.

When the add-on starts up inside Home Assistant, it registers itself with the
Supervisor's discovery endpoint so the companion integration receives an
auto-discovery notification with a ready-to-use WebSocket URL. When the
add-on stops, it withdraws the announcement.

Outside Home Assistant (plain Docker), ``SUPERVISOR_TOKEN`` is unset — the
announce/withdraw calls are no-ops in that case so the add-on still boots.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)

_SUPERVISOR_URL = "http://supervisor"
_SERVICE_NAME = "outback_mate3"
_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def announce(ws_port: int) -> str | None:
    """Register the add-on's WebSocket endpoint with Supervisor discovery.

    Returns the discovery UUID for later withdrawal, or ``None`` if the add-on
    is running outside Home Assistant or the announce failed.
    """
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        _LOGGER.info("SUPERVISOR_TOKEN not set; skipping discovery announce")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession(timeout=_HTTP_TIMEOUT) as session:
        try:
            async with session.get(
                f"{_SUPERVISOR_URL}/addons/self/info", headers=headers
            ) as resp:
                resp.raise_for_status()
                info = await resp.json()
        except Exception as exc:
            _LOGGER.warning("Couldn't fetch add-on info: %s", exc)
            return None
        hostname = info.get("data", {}).get("hostname")
        if not hostname:
            _LOGGER.warning("Supervisor returned no hostname; discovery skipped")
            return None

        payload: dict[str, Any] = {
            "service": _SERVICE_NAME,
            "config": {"host": hostname, "port": ws_port},
        }
        try:
            async with session.post(
                f"{_SUPERVISOR_URL}/discovery", headers=headers, json=payload
            ) as resp:
                resp.raise_for_status()
                body = await resp.json()
        except Exception as exc:
            _LOGGER.warning("Failed to announce discovery: %s", exc)
            return None

    uuid = body.get("data", {}).get("uuid")
    if not uuid:
        _LOGGER.warning("Supervisor accepted announce but returned no uuid: %s", body)
        return None
    _LOGGER.info("Announced discovery to Supervisor (uuid=%s, host=%s:%d)",
                 uuid, hostname, ws_port)
    return uuid


async def withdraw(uuid: str | None) -> None:
    """Remove the announcement on shutdown. Safe to call with ``None``."""
    if not uuid:
        return
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return
    async with aiohttp.ClientSession(timeout=_HTTP_TIMEOUT) as session:
        try:
            await session.delete(
                f"{_SUPERVISOR_URL}/discovery/{uuid}",
                headers={"Authorization": f"Bearer {token}"},
            )
            _LOGGER.info("Withdrew discovery uuid=%s", uuid)
        except Exception as exc:
            _LOGGER.warning("Failed to withdraw discovery uuid=%s: %s", uuid, exc)
