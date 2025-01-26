"""Config flow for Outback MATE3 integration."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PORT
from homeassistant.data_entry_flow import FlowResult

from . import DOMAIN, DEFAULT_PORT

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Outback MATE3."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
                    }
                ),
            )

        await self.async_set_unique_id(f"mate3_{user_input[CONF_PORT]}")
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=f"MATE3 (Port {user_input[CONF_PORT]})",
            data=user_input,
        )
