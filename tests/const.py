"""Shared test defaults for ``abb_terra_ac``."""

from __future__ import annotations

from custom_components.abb_terra_ac.const import CONF_SCAN_INTERVAL, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

MOCK_HOST = "192.168.1.50"
MOCK_PORT = 502
MOCK_ENTRY_OPTIONS = {CONF_SCAN_INTERVAL: 15}


def mock_config_entry_data() -> dict:
    """Typical config entry data for tests."""
    return {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT}


def mock_config_entry_kwargs() -> dict:
    """Kwargs for MockConfigEntry matching integration version 2."""
    return {
        "domain": DOMAIN,
        "version": 2,
        "data": mock_config_entry_data(),
        "options": MOCK_ENTRY_OPTIONS.copy(),
    }
