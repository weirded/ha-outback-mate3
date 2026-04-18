"""Config flow for Outback MATE3 integration."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from . import CONF_URL, DEFAULT_URL, DOMAIN


async def _probe_ws_url(url: str, timeout_s: float = 5.0) -> str | None:
    """Return ``None`` on success, or a short error code on failure."""
    try:
        async with aiohttp.ClientSession() as session:
            async with asyncio.timeout(timeout_s):
                async with session.ws_connect(url) as ws:
                    msg = await ws.receive()
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        return "bad_handshake"
                    try:
                        payload = msg.json()
                    except ValueError:
                        return "bad_handshake"
                    if payload.get("type") != "snapshot":
                        return "bad_handshake"
                    return None
    except asyncio.TimeoutError:
        return "timeout"
    except aiohttp.ClientError:
        return "cannot_connect"
    except Exception:  # noqa: BLE001
        return "unknown"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Outback MATE3."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL]
            error = await _probe_ws_url(url)
            if error is None:
                await self.async_set_unique_id(f"mate3_{url}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"MATE3 ({url})",
                    data={CONF_URL: url},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=DEFAULT_URL): str,
                }
            ),
            errors=errors,
        )
