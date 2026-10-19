"""Home Assistant exceptions for ABB Terra AC."""

from __future__ import annotations

from collections.abc import Awaitable

from homeassistant.exceptions import HomeAssistantError
from modbus_connection import ModbusExceptionError

from .const import DOMAIN


def build_service_error(translation_key: str) -> HomeAssistantError:
    """Build a translated Home Assistant service error."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
    )


async def async_run_device_action(action: Awaitable[None]) -> None:
    """Await a device write and translate Modbus failures into HA errors.

    A Modbus exception response means the charger answered and refused the
    change (``write_failed``). Any other failure means it could not be reached
    (``charger_unavailable``).
    """
    try:
        await action
    except ModbusExceptionError as err:
        raise build_service_error("write_failed") from err
    except ValueError:
        # A rejected input value is a caller bug, not an unreachable charger.
        raise
    except Exception as err:  # noqa: BLE001 - any other failure: charger unreachable
        raise build_service_error("charger_unavailable") from err
