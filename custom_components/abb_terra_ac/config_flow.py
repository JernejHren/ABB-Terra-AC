"""Config flow za ABB Terra AC."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from pymodbus.client import AsyncModbusTcpClient
import asyncio

from .const import DOMAIN, DEFAULT_PORT


class AbbTerraAcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Obravnava config flow za ABB Terra AC."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Obravnava korak, ki ga sproži uporabnik."""
        errors = {}
        
        if user_input is not None:
            # Preizkus povezave s polnilnico
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            
            try:
                # Poskusi vzpostaviti povezavo
                client = AsyncModbusTcpClient(host=host, port=port)
                
                # Timeout za povezavo
                connected = await asyncio.wait_for(
                    client.connect(), 
                    timeout=5.0
                )
                
                if not connected:
                    errors["base"] = "cannot_connect"
                else:
                    # Poskusi prebrati register za dodatno validacijo
                    try:
                        result = await asyncio.wait_for(
                            client.read_holding_registers(address=16384, count=1),
                            timeout=3.0
                        )
                        
                        if result.isError():
                            errors["base"] = "invalid_response"
                        else:
                            # Povezava uspešna, zapri jo in ustvari vnos
                            await client.close()
                            
                            # Preveri, če vnos že obstaja
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
                            await client.close()
                            
            except asyncio.TimeoutError:
                errors["base"] = "timeout"
            except Exception:
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
