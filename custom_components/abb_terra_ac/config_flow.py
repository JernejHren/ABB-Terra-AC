"""Config flow za ABB Terra AC."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN, DEFAULT_PORT

class AbbTerraAcConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Obravnava config flow za ABB Terra AC."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Obravnava korak, ki ga sproži uporabnik."""
        errors = {}
        if user_input is not None:
            # Tukaj bi lahko dodali logiko za preverjanje povezave
            # s polnilnico preden shranimo konfiguracijo.
            # Zaenkrat predpostavimo, da je vnos pravilen.
            return self.async_create_entry(title=user_input[CONF_HOST], data=user_input)

        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Optional(CONF_PORT, default=DEFAULT_PORT): int,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )