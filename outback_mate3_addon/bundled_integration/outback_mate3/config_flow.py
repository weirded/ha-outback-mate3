"""Config flow for Outback MATE3 integration."""
from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import CONF_URL, DEFAULT_URL, DOMAIN


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
    except TimeoutError:
        return "timeout"
    except aiohttp.ClientError:
        return "cannot_connect"
    except Exception:
        return "unknown"


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Outback MATE3."""

    VERSION = 2

    def __init__(self) -> None:
        self._discovered_url: str | None = None
        self._discovered_name: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

    async def async_step_hassio(
        self, discovery_info: HassioServiceInfo
    ) -> ConfigFlowResult:
        """Handle auto-discovery from the Outback MATE3 Supervisor add-on."""
        host = discovery_info.config["host"]
        port = discovery_info.config["port"]
        url = f"ws://{host}:{port}/ws"

        # One config entry per add-on installation. Subsequent announces with
        # a changed URL (e.g. different port) should update the existing entry
        # rather than create a duplicate or be silently ignored.
        await self.async_set_unique_id(f"hassio_{discovery_info.slug}")
        self._abort_if_unique_id_configured(updates={CONF_URL: url})

        self._discovered_url = url
        self._discovered_name = discovery_info.name
        # Label the entry nicely in the "Discovered" card.
        self.context["title_placeholders"] = {"name": discovery_info.name}
        return await self.async_step_hassio_confirm()

    async def async_step_hassio_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask the user to confirm the discovered add-on before adding it."""
        assert self._discovered_url is not None
        if user_input is not None:
            return self.async_create_entry(
                title=self._discovered_name or "Outback MATE3",
                data={CONF_URL: self._discovered_url},
            )
        return self.async_show_form(
            step_id="hassio_confirm",
            description_placeholders={
                "name": self._discovered_name or "Outback MATE3",
                "url": self._discovered_url,
            },
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let users update the WS URL post-setup without deleting the entry.

        Reaches here when the user clicks "Reconfigure" on the entry card —
        typically to retarget the add-on after a hostname change or when
        running against a remote add-on over the internal network.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        current_url = entry.data.get(CONF_URL, DEFAULT_URL)

        if user_input is not None:
            url = user_input[CONF_URL]
            error = await _probe_ws_url(url)
            if error is None:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates={CONF_URL: url},
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_URL, default=current_url): str,
                }
            ),
            errors=errors,
        )
