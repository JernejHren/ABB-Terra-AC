"""Diagnostics support for ABB Terra AC."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import AbbTerraAcRuntimeData
from .const import AbbTerraAcData

_REDACT_CONFIG = {CONF_HOST}
_REDACT_RUNTIME = {"serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data: AbbTerraAcRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    coordinator_data: AbbTerraAcData = coordinator.data

    return {
        "entry": async_redact_data(
            {
                "entry_id": entry.entry_id,
                "data": dict(entry.data),
                "options": dict(entry.options),
            },
            _REDACT_CONFIG,
        ),
        "client": {
            "connected": client.connected,
            "host": async_redact_data({CONF_HOST: entry.data[CONF_HOST]}, _REDACT_CONFIG)[CONF_HOST],
            "port": entry.data[CONF_PORT],
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "is_available": coordinator._is_available,
            "serial_number_cached": coordinator.serial_number is not None,
            "last_valid_fallback_limit": coordinator._last_valid_fallback_limit,
            "fallback_fix_attempted": coordinator._fallback_fix_attempted,
            "last_valid_current_limit": coordinator._last_valid_current_limit,
            "current_limit_fix_attempted": coordinator._current_limit_fix_attempted,
            "data": async_redact_data(dict(coordinator_data), _REDACT_RUNTIME),
        },
    }
