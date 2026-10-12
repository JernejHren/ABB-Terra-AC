"""Config flow tests for the ``abb_terra_ac`` custom integration."""

from unittest.mock import patch

import pytest
from modbus_connection import ModbusTimeoutError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.abb_terra_ac.const import (
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.data_entry_flow import FlowResultType

from tests.const import mock_config_entry_kwargs
from tests.helpers.modbus import create_mock_modbus_unit, temporary_unit_factory

_FLOW_UNIT = "custom_components.abb_terra_ac.config_flow.async_get_temporary_unit"
_SETUP_ENTRY = "custom_components.abb_terra_ac.async_setup_entry"


def _patch_unit(unit):
    """Patch the config flow's temporary unit so it yields ``unit``."""
    return patch(_FLOW_UNIT, new=temporary_unit_factory(unit))


async def _start_user_flow(hass: HomeAssistant):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    return result


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
    unit = create_mock_modbus_unit(connect=connect, read_error=read_error)
    result = await _start_user_flow(hass)

    with _patch_unit(unit):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == expected_error


async def test_connection_conflict_error(hass: HomeAssistant) -> None:
    """A shared connection with different link settings gets its own form error."""
    result = await _start_user_flow(hass)

    with patch(_FLOW_UNIT, side_effect=HomeAssistantError("different link settings")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "connection_conflict"


async def test_unexpected_error(hass: HomeAssistant) -> None:
    """Unexpected exception becomes base=unknown."""
    unit = create_mock_modbus_unit(connect=True, read_error=False)
    unit.read_holding_registers.side_effect = RuntimeError("boom")
    result = await _start_user_flow(hass)

    with _patch_unit(unit):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"


@pytest.mark.parametrize("error", [ModbusTimeoutError("timed out"), TimeoutError()])
async def test_read_timeout_maps_to_timeout_error(
    hass: HomeAssistant, error: Exception
) -> None:
    """Timeout during the probe read becomes base=timeout."""
    unit = create_mock_modbus_unit(connect=True, read_error=False)
    unit.read_holding_registers.side_effect = error
    result = await _start_user_flow(hass)

    with _patch_unit(unit):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "timeout"


async def test_successful_flow(hass: HomeAssistant) -> None:
    """Successful Modbus probe yields a config entry (unit ID defaults to 1)."""
    unit = create_mock_modbus_unit(connect=True, read_error=False)
    result = await _start_user_flow(hass)

    with _patch_unit(unit), patch(_SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "ABB Terra AC (192.168.1.50)"
    assert result["data"] == {
        CONF_HOST: "192.168.1.50",
        CONF_PORT: 502,
        CONF_UNIT_ID: 1,
    }
    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1
    assert entries[0].version == 3
    assert entries[0].options[CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL
    unit.require_timeout.assert_called_once()
    unit.read_holding_registers.assert_awaited_once_with(16384, 1)


async def test_custom_unit_id_is_stored(hass: HomeAssistant) -> None:
    """A non-default Modbus unit ID is kept in the config entry data."""
    unit = create_mock_modbus_unit(connect=True, read_error=False)
    result = await _start_user_flow(hass)

    with _patch_unit(unit), patch(_SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502, CONF_UNIT_ID: 7},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_UNIT_ID] == 7


async def test_already_configured(hass: HomeAssistant) -> None:
    """Abort when unique_id host:port is already registered."""
    MockConfigEntry(
        **mock_config_entry_kwargs(),
        unique_id="192.168.1.50:502",
    ).add_to_hass(hass)

    unit = create_mock_modbus_unit(connect=True, read_error=False)
    result = await _start_user_flow(hass)

    with _patch_unit(unit):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _reconfigure_entry() -> MockConfigEntry:
    return MockConfigEntry(
        **mock_config_entry_kwargs(),
        unique_id="192.168.1.50:502",
        title="ABB Terra AC (192.168.1.50)",
    )


async def test_reconfigure_updates_existing_entry(hass: HomeAssistant) -> None:
    """Reconfigure should update host/port/unit ID, title, and unique_id."""
    entry = _reconfigure_entry()
    entry.add_to_hass(hass)

    unit = create_mock_modbus_unit(connect=True, read_error=False)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with _patch_unit(unit), patch(_SETUP_ENTRY, return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.60", CONF_PORT: 1502, CONF_UNIT_ID: 2},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data == {
        CONF_HOST: "192.168.1.60",
        CONF_PORT: 1502,
        CONF_UNIT_ID: 2,
    }
    assert entry.title == "ABB Terra AC (192.168.1.60)"
    assert entry.unique_id == "192.168.1.60:1502"


async def test_reconfigure_keeps_reconfigure_step_on_validation_error(
    hass: HomeAssistant,
) -> None:
    """Reconfigure errors should keep the flow on the reconfigure step."""
    entry = _reconfigure_entry()
    entry.add_to_hass(hass)

    unit = create_mock_modbus_unit(connect=False, read_error=False)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    with _patch_unit(unit):
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
