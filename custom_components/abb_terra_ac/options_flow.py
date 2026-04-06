"""Options flow for ABB Terra AC (runtime settings separate from host/port)."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)


class AbbTerraAcOptionsFlow(config_entries.OptionsFlow):
    """Options flow: polling interval and future runtime-only settings."""

    async def async_step_init(
        self, user_input: dict[str, int] | None = None
    ) -> ConfigFlowResult:
        """Offer options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = int(
            self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                }
            ),
            {CONF_SCAN_INTERVAL: current},
        )

        return self.async_show_form(step_id="init", data_schema=schema)
