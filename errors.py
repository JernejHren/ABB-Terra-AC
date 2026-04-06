"""Home Assistant exceptions for ABB Terra AC."""

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN


def build_service_error(translation_key: str) -> HomeAssistantError:
    """Build a translated Home Assistant service error."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
    )
