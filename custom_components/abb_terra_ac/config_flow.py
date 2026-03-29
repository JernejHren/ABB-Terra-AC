"""Config flow for ABB Terra AC."""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import AbortFlow
from pymodbus.client import AsyncModbusTcpClient

from .const import DOMAIN, DEFAULT_PORT
from .modbus import async_close_client

_LOGGER = logging.getLogger(__name__)


class AbbTerraAcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ABB Terra AC."""

    VERSION = 1

    @staticmethod
    def _data_schema() -> vol.Schema:
        """Return the shared config schema."""
        return vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        })

    def _show_form(
        self,
        user_input: dict[str, str | int] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the user or reconfigure form."""
        suggested_values = user_input
        step_id = "user"

        if suggested_values is None and self.source == config_entries.SOURCE_RECONFIGURE:
            entry = self._get_reconfigure_entry()
            suggested_values = {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: entry.data[CONF_PORT],
            }
            step_id = "reconfigure"

        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(
                self._data_schema(),
                suggested_values,
            ),
            errors=errors or {},
        )

    async def _async_validate_input(self, user_input: dict[str, int | str]) -> None:
        """Validate connection details by probing the charger."""
        host = str(user_input[CONF_HOST])
        port = int(user_input[CONF_PORT])
        client = AsyncModbusTcpClient(host=host, port=port)

        try:
            connected = await asyncio.wait_for(client.connect(), timeout=5.0)
            if not connected:
                msg = "cannot_connect"
                raise ValueError(msg)

            result = await asyncio.wait_for(
                client.read_holding_registers(address=16384, count=1),
                timeout=3.0,
            )
            if result.isError():
                msg = "invalid_response"
                raise ValueError(msg)
        finally:
            if client.connected:
                await async_close_client(client)

    async def async_step_reconfigure(
        self, user_input: dict[str, str | int] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the existing entry."""
        return await self.async_step_user(user_input)

    async def async_step_user(
        self, user_input: dict[str, str | int] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        if user_input is None:
            return self._show_form()

        errors = {}
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        new_unique_id = f"{host}:{port}"

        try:
            await self._async_validate_input(user_input)
            await self.async_set_unique_id(new_unique_id)

            if self.source == config_entries.SOURCE_RECONFIGURE:
                entry = self._get_reconfigure_entry()
                existing_entry = self.hass.config_entries.async_entry_for_domain_unique_id(
                    DOMAIN, new_unique_id
                )
                if existing_entry is not None and existing_entry.entry_id != entry.entry_id:
                    self._abort_if_unique_id_configured()

                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=new_unique_id,
                    title=f"ABB Terra AC ({host})",
                    data_updates=user_input,
                )

            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"ABB Terra AC ({host})",
                data=user_input
            )
        except ValueError as err:
            errors["base"] = str(err)
        except asyncio.TimeoutError:
            errors["base"] = "timeout"
        except AbortFlow:
            raise
        except Exception:
            _LOGGER.exception("Unexpected error during connection test")
            errors["base"] = "unknown"

        return self._show_form(user_input, errors)
