"""Config flow for ABB Terra AC."""
import asyncio
import inspect
import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from pymodbus.client import AsyncModbusTcpClient

from .const import DOMAIN, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)


class AbbTerraAcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for ABB Terra AC."""

    VERSION = 1

    async def _async_close_client(self, client: AsyncModbusTcpClient) -> None:
        """Safely close Modbus client regardless of whether close() is awaitable."""
        try:
            close_result = client.close()
            if inspect.isawaitable(close_result):
                await close_result
        except Exception:
            _LOGGER.debug("Failed to close Modbus client", exc_info=True)

    async def async_step_user(self, user_input=None):
        """Handle the user step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            try:
                client = AsyncModbusTcpClient(host=host, port=port)

                connected = await asyncio.wait_for(
                    client.connect(),
                    timeout=5.0
                )

                if not connected:
                    errors["base"] = "cannot_connect"
                else:
                    try:
                        result = await asyncio.wait_for(
                            client.read_holding_registers(address=16384, count=1),
                            timeout=3.0
                        )

                        if result.isError():
                            errors["base"] = "invalid_response"
                        else:
                            await self._async_close_client(client)

                            await self.async_set_unique_id(f"{host}:{port}")
                            self._abort_if_unique_id_configured()

                            return self.async_create_entry(
                                title=f"ABB Terra AC ({host})",
                                data=user_input
                            )
                    except asyncio.TimeoutError:
                        errors["base"] = "timeout"
                    finally:
                        if client.connected:
                            await self._async_close_client(client)

            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except Exception:
                _LOGGER.exception("Unexpected error during connection test")
                errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors
        )
