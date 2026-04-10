"""Setup / unload tests for the ``abb_terra_ac`` custom integration."""
import logging
from unittest.mock import MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.abb_terra_ac import binary_sensor as binary_sensor_platform
from custom_components.abb_terra_ac import button as button_platform
from custom_components.abb_terra_ac import diagnostics
from custom_components.abb_terra_ac import number as number_platform
from custom_components.abb_terra_ac import sensor as sensor_platform
from custom_components.abb_terra_ac import switch as switch_platform
from custom_components.abb_terra_ac import async_migrate_entry
from custom_components.abb_terra_ac.const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed
from pymodbus.exceptions import ConnectionException, ModbusIOException

from tests.const import mock_config_entry_kwargs
from tests.helpers.modbus import create_mock_modbus_client
from tests.helpers.modbus import make_holding_registers_37

_INIT_MODBUS = "custom_components.abb_terra_ac.AsyncModbusTcpClient"


def _read_result_with_registers(registers: list[int]) -> MagicMock:
    """Build one mocked Modbus read result object."""
    result = MagicMock()
    result.isError.return_value = False
    result.registers = list(registers)
    return result


async def test_setup_entry_and_unload(hass: HomeAssistant) -> None:
    """Load config entry with mocked Modbus; unload closes client."""
    entry = MockConfigEntry(**mock_config_entry_kwargs())
    entry.add_to_hass(hass)

    mock_client = create_mock_modbus_client(connect=True, read_error=False)

    with patch(_INIT_MODBUS, return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    assert entry.runtime_data is not None
    assert entry.runtime_data.client is mock_client

    coordinator = entry.runtime_data.coordinator
    assert coordinator.data is not None
    assert "serial_number" in coordinator.data

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert not hasattr(entry, "runtime_data") or entry.runtime_data is None


async def test_logs_when_unavailable_and_when_available_again(
    hass: HomeAssistant, caplog
) -> None:
    """Coordinator logs one transition to unavailable and one recovery message."""
    entry = MockConfigEntry(**mock_config_entry_kwargs())
    entry.add_to_hass(hass)

    mock_client = create_mock_modbus_client(connect=True, read_error=False)

    caplog.set_level(logging.INFO)

    with patch(_INIT_MODBUS, return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    success_result = mock_client.read_holding_registers.return_value
    mock_client.read_holding_registers.side_effect = [
        ConnectionException("charger offline"),
        success_result,
    ]

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    await coordinator._async_update_data()

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "ABB Terra AC charger became unavailable: Connection error:" in message
        and "charger offline" in message
        for message in messages
    )
    assert "ABB Terra AC charger is available again" in messages


def test_platforms_define_parallel_updates() -> None:
    """Platforms explicitly opt into coordinator-safe serialized updates."""
    assert sensor_platform.PARALLEL_UPDATES == 0
    assert switch_platform.PARALLEL_UPDATES == 0
    assert number_platform.PARALLEL_UPDATES == 0
    assert button_platform.PARALLEL_UPDATES == 0
    assert binary_sensor_platform.PARALLEL_UPDATES == 0


async def test_config_entry_diagnostics_redact_sensitive_data(
    hass: HomeAssistant,
) -> None:
    """Diagnostics should include useful state while redacting sensitive values."""
    entry = MockConfigEntry(**mock_config_entry_kwargs())
    entry.add_to_hass(hass)

    mock_client = create_mock_modbus_client(
        connect=True,
        read_error=False,
        registers=make_holding_registers_37(),
    )

    with patch(_INIT_MODBUS, return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["data"][CONF_HOST] == "**REDACTED**"
    assert result["entry"]["data"][CONF_PORT] == 502
    assert result["entry"]["version"] == 2
    assert result["entry"]["options"][CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL
    assert result["client"]["host"] == "**REDACTED**"
    assert result["client"]["port"] == 502
    assert result["coordinator"]["data"]["serial_number"] == "**REDACTED**"
    assert result["coordinator"]["data"]["firmware_version"] == coordinator.data["firmware_version"]
    assert result["coordinator"]["serial_number_cached"] is True


async def test_creates_and_clears_repair_issue_for_invalid_fallback_limit(
    hass: HomeAssistant,
) -> None:
    """Failed firmware auto-recovery should create a repair issue that clears later."""
    entry = MockConfigEntry(**mock_config_entry_kwargs())
    entry.add_to_hass(hass)

    invalid_registers = make_holding_registers_37(
        user_max_amps=16,
        fallback_limit=32,
    )
    valid_registers = make_holding_registers_37(
        user_max_amps=16,
        fallback_limit=10,
    )

    mock_client = create_mock_modbus_client(
        connect=True,
        read_error=False,
        registers=invalid_registers,
    )
    mock_client.read_holding_registers.side_effect = [
        _read_result_with_registers(invalid_registers),
        _read_result_with_registers(invalid_registers),
        _read_result_with_registers(valid_registers),
    ]
    failed_write = mock_client.write_register.return_value
    failed_write.isError.return_value = True

    with patch(_INIT_MODBUS, return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    issue_reg = ir.async_get(hass)
    issue_id = f"invalid_fallback_limit_{entry.entry_id}"
    issue = issue_reg.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "firmware_limit_restore_failed"

    coordinator = entry.runtime_data.coordinator
    updated_data = await coordinator._async_update_data()
    coordinator.async_set_updated_data(updated_data)

    assert issue_reg.async_get_issue(DOMAIN, issue_id) is None


async def test_migrate_v1_adds_default_scan_interval(hass: HomeAssistant) -> None:
    """Version 1 entries receive default options without re-adding the integration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        options={},
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    assert entry.version == 2
    assert entry.options[CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL


async def test_coordinator_connect_timeout_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """Connect timeout should surface as UpdateFailed instead of hanging setup."""
    entry = MockConfigEntry(**mock_config_entry_kwargs())
    entry.add_to_hass(hass)

    mock_client = create_mock_modbus_client(connect=True, read_error=False)

    with patch(_INIT_MODBUS, return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    mock_client.connected = False

    async def _timeout_connect():
        raise TimeoutError

    mock_client.connect.side_effect = _timeout_connect

    with pytest.raises(UpdateFailed, match="Connection error"):
        await coordinator._async_update_data()


async def test_coordinator_modbus_io_exception_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """Pymodbus I/O cancellation errors should be treated as transient outages."""
    entry = MockConfigEntry(**mock_config_entry_kwargs())
    entry.add_to_hass(hass)

    mock_client = create_mock_modbus_client(connect=True, read_error=False)

    with patch(_INIT_MODBUS, return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    mock_client.read_holding_registers.side_effect = ModbusIOException(
        "Request cancelled outside pymodbus."
    )

    with pytest.raises(UpdateFailed, match="Connection error"):
        await coordinator._async_update_data()


async def test_coordinator_reconnects_and_retries_read_once(
    hass: HomeAssistant,
) -> None:
    """One transient Modbus I/O failure should trigger a clean reconnect and retry."""
    entry = MockConfigEntry(**mock_config_entry_kwargs())
    entry.add_to_hass(hass)

    good_registers = make_holding_registers_37()
    mock_client = create_mock_modbus_client(
        connect=True,
        read_error=False,
        registers=good_registers,
    )

    with patch(_INIT_MODBUS, return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)

    await hass.async_block_till_done()

    coordinator = entry.runtime_data.coordinator
    mock_client.read_holding_registers.side_effect = [
        ModbusIOException("Request cancelled outside pymodbus."),
        _read_result_with_registers(good_registers),
    ]

    updated_data = await coordinator._async_update_data()

    assert updated_data["fallback_limit"] == 0
    assert mock_client.connect.await_count >= 2
    assert mock_client.close.call_count >= 1
