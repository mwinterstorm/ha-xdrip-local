"""Config flow for xDrip Local integration."""
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, CONF_API_SECRET

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Optional(CONF_API_SECRET, default=""): str,
    }
)

class XDripLocalConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for xDrip Local."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Enforce unique ID on IP Address so we don't duplicate
            await self.async_set_unique_id(user_input[CONF_IP_ADDRESS])
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=f"xDrip ({user_input[CONF_IP_ADDRESS]})", 
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
