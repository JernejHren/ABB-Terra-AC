"""Config flow tests for the ``abb_terra_ac`` custom integration."""

import asyncio
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.abb_terra_ac.const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.const import mock_config_entry_kwargs
from tests.helpers.modbus import create_mock_modbus_client

_FLOW_MODBUS = "custom_components.abb_terra_ac.config_flow.AsyncModbusTcpClient"


async def test_user_form(hass: HomeAssistant) -> None:
    """Show the initial form when no input is provided."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}


@pytest.mark.parametrize(
    ("connect", "read_error", "expected_error"),
    [
        (False, False, "cannot_connect"),
        (True, True, "invalid_response"),
    ],
)
async def test_connection_errors(
    hass: HomeAssistant,
    connect: bool,
    read_error: bool,
    expected_error: str,
) -> None:
    """Map Modbus outcomes to form errors."""
    mock_client = create_mock_modbus_client(connect=connect, read_error=read_error)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(_FLOW_MODBUS, return_value=mock_client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error


async def test_unexpected_error(hass: HomeAssistant) -> None:
    """Unexpected exception becomes base=unknown."""
    mock_client = create_mock_modbus_client(connect=True, read_error=False)

    async def _broken_read(*args, **kwargs):
        msg = "boom"
        raise RuntimeError(msg)

    mock_client.read_holding_registers = _broken_read

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(_FLOW_MODBUS, return_value=mock_client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


async def test_connect_timeout_maps_to_timeout_error(hass: HomeAssistant) -> None:
    """Timeout while opening the TCP connection becomes base=timeout."""
    mock_client = create_mock_modbus_client(connect=True, read_error=False)

    async def _timeout_connect():
        raise asyncio.TimeoutError

    mock_client.connect.side_effect = _timeout_connect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(_FLOW_MODBUS, return_value=mock_client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "timeout"


async def test_read_timeout_maps_to_timeout_error(hass: HomeAssistant) -> None:
    """Timeout during the probe read becomes base=timeout."""
    mock_client = create_mock_modbus_client(connect=True, read_error=False)

    async def _timeout_read(*args, **kwargs):
        raise asyncio.TimeoutError

    mock_client.read_holding_registers.side_effect = _timeout_read

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(_FLOW_MODBUS, return_value=mock_client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "timeout"


async def test_successful_flow(hass: HomeAssistant) -> None:
    """Successful Modbus probe yields a config entry."""
    mock_client = create_mock_modbus_client(connect=True, read_error=False)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(_FLOW_MODBUS, return_value=mock_client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ABB Terra AC (192.168.1.50)"
    assert result["data"] == {CONF_HOST: "192.168.1.50", CONF_PORT: 502}
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].options[CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL


async def test_already_configured(hass: HomeAssistant) -> None:
    """Abort when unique_id host:port is already registered."""
    MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="192.168.1.50:502",
        data={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    ).add_to_hass(hass)

    mock_client = create_mock_modbus_client(connect=True, read_error=False)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(_FLOW_MODBUS, return_value=mock_client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_updates_existing_entry(hass: HomeAssistant) -> None:
    """Reconfigure should update host/port, title, and unique_id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="192.168.1.50:502",
        title="ABB Terra AC (192.168.1.50)",
        data={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )
    entry.add_to_hass(hass)

    mock_client = create_mock_modbus_client(connect=True, read_error=False)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(_FLOW_MODBUS, return_value=mock_client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.60", CONF_PORT: 1502},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {CONF_HOST: "192.168.1.60", CONF_PORT: 1502}
    assert entry.title == "ABB Terra AC (192.168.1.60)"
    assert entry.unique_id == "192.168.1.60:1502"


async def test_reconfigure_keeps_reconfigure_step_on_validation_error(
    hass: HomeAssistant,
) -> None:
    """Reconfigure errors should keep the flow on the reconfigure step."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        unique_id="192.168.1.50:502",
        title="ABB Terra AC (192.168.1.50)",
        data={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        options={CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL},
    )
    entry.add_to_hass(hass)

    mock_client = create_mock_modbus_client(connect=False, read_error=False)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    with patch(_FLOW_MODBUS, return_value=mock_client):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.60", CONF_PORT: 1502},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"]["base"] == "cannot_connect"


async def test_options_flow_updates_scan_interval(hass: HomeAssistant) -> None:
    """Options flow should persist scan_interval without touching host/port."""
    entry = MockConfigEntry(**mock_config_entry_kwargs())
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 45},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_SCAN_INTERVAL] == 45
