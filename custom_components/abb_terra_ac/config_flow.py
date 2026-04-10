"""Config flow for ABB Terra AC."""
from __future__ import annotations

import asyncio
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import AbortFlow
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MODBUS_READ_TIMEOUT,
)
from .modbus import async_close_client, async_modbus_call
from .options_flow import AbbTerraAcOptionsFlow

_LOGGER = logging.getLogger(__name__)


class AbbTerraAcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ABB Terra AC."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> AbbTerraAcOptionsFlow:
        """Provide the options flow for scan interval and other runtime settings."""
        return AbbTerraAcOptionsFlow()

    @staticmethod
    def _data_schema() -> vol.Schema:
        """Return the shared config schema."""
        return vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        })

    def _show_form(
        self,
        *,
        step_id: str,
        user_input: dict[str, str | int] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Show the requested form with the provided suggested values."""
        suggested_values = user_input
        if suggested_values is None and step_id == "reconfigure":
            entry = self._get_reconfigure_entry()
            suggested_values = {
                CONF_HOST: entry.data[CONF_HOST],
                CONF_PORT: entry.data[CONF_PORT],
            }

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
        client = AsyncModbusTcpClient(
            host=host,
            port=port,
            timeout=MODBUS_READ_TIMEOUT,
        )

        try:
            result = await async_modbus_call(
                client,
                "read_holding_registers",
                retry=False,
                address=16384,
                count=1,
            )
            if result.isError():
                msg = "invalid_response"
                raise ValueError(msg)
        except ConnectionException as err:
            if str(err) == "connect() returned False":
                msg = "cannot_connect"
                raise ValueError(msg) from err
            raise
        finally:
            if client.connected:
                await async_close_client(client)

    async def async_step_reconfigure(
        self, user_input: dict[str, str | int] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the existing entry."""
        if user_input is None:
            return self._show_form(step_id="reconfigure")

        errors = {}
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        new_unique_id = f"{host}:{port}"

        try:
            await self._async_validate_input(user_input)
            await self.async_set_unique_id(new_unique_id)

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
        except ValueError as err:
            errors["base"] = str(err)
        except (asyncio.TimeoutError, ModbusIOException):
            errors["base"] = "timeout"
        except AbortFlow:
            raise
        except Exception:
            _LOGGER.exception("Unexpected error during connection test")
            errors["base"] = "unknown"

        return self._show_form(step_id="reconfigure", user_input=user_input, errors=errors)

    async def async_step_user(
        self, user_input: dict[str, str | int] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step."""
        if user_input is None:
            return self._show_form(step_id="user")

        errors = {}
        host = user_input[CONF_HOST]
        port = user_input[CONF_PORT]
        new_unique_id = f"{host}:{port}"

        try:
            await self._async_validate_input(user_input)
            await self.async_set_unique_id(new_unique_id)

            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"ABB Terra AC ({host})",
                data=user_input,
                options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
            )
        except ValueError as err:
            errors["base"] = str(err)
        except (asyncio.TimeoutError, ModbusIOException):
            errors["base"] = "timeout"
        except AbortFlow:
            raise
        except Exception:
            _LOGGER.exception("Unexpected error during connection test")
            errors["base"] = "unknown"

        return self._show_form(step_id="user", user_input=user_input, errors=errors)
