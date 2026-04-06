"""Diagnostics support for ABB Terra AC."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from . import AbbTerraAcRuntimeData
from .const import AbbTerraAcData, CONF_SCAN_INTERVAL

# Config entry data and client host are PII (network identity; treat as sensitive).
_REDACT_CONFIG = {CONF_HOST}
_REDACT_RUNTIME = {"serial_number"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry (host and serial redacted)."""
    runtime_data: AbbTerraAcRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    coordinator_data: AbbTerraAcData = coordinator.data

    entry_data = async_redact_data(dict(entry.data), _REDACT_CONFIG)
    # Ensure host is never leaked even if schema changes.
    if CONF_HOST in entry.data:
        entry_data[CONF_HOST] = "**REDACTED**"

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "data": entry_data,
            "options": {
                CONF_SCAN_INTERVAL: entry.options.get(CONF_SCAN_INTERVAL),
            },
        },
        "client": {
            "connected": client.connected,
            "host": "**REDACTED**",
            "port": entry.data[CONF_PORT],
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success,
            "is_available": coordinator._is_available,
            "serial_number_cached": coordinator.serial_number is not None,
            "last_command": coordinator.last_command,
            "session_state": coordinator.session_state.value,
            "last_valid_fallback_limit": coordinator._last_valid_fallback_limit,
            "fallback_fix_attempted": coordinator._fallback_fix_attempted,
            "last_valid_current_limit": coordinator._last_valid_current_limit,
            "current_limit_fix_attempted": coordinator._current_limit_fix_attempted,
            "data": async_redact_data(dict(coordinator_data), _REDACT_RUNTIME),
        },
    }
