"""Setup / unload tests for the ``abb_terra_ac`` custom integration."""

import logging
from unittest.mock import patch

import pytest
from modbus_connection import (
    ModbusConnectionError,
    ModbusExceptionError,
    ModbusTimeoutError,
)
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.abb_terra_ac import async_migrate_entry
from custom_components.abb_terra_ac import binary_sensor as binary_sensor_platform
from custom_components.abb_terra_ac import button as button_platform
from custom_components.abb_terra_ac import diagnostics
from custom_components.abb_terra_ac import number as number_platform
from custom_components.abb_terra_ac import sensor as sensor_platform
from custom_components.abb_terra_ac import switch as switch_platform
from custom_components.abb_terra_ac.const import (
    CONF_SCAN_INTERVAL,
    CONF_UNIT_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.const import mock_config_entry_kwargs
from tests.helpers.modbus import create_mock_modbus_unit, make_holding_registers_37

_INIT_UNIT = "custom_components.abb_terra_ac.async_get_unit"


async def _async_setup(hass: HomeAssistant, unit) -> MockConfigEntry:
    """Set up a config entry whose Modbus unit is ``unit``."""
    entry = MockConfigEntry(**mock_config_entry_kwargs())
    entry.add_to_hass(hass)
    with patch(_INIT_UNIT, return_value=unit):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_entry_and_unload(hass: HomeAssistant) -> None:
    """Load config entry with a mocked Modbus unit; runtime data is cleared on unload."""
    unit = create_mock_modbus_unit(connect=True, read_error=False)

    with patch(_INIT_UNIT, return_value=unit) as get_unit:
        entry = MockConfigEntry(**mock_config_entry_kwargs())
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    # The shared connection is requested with the stored host/port/unit ID.
    params = get_unit.call_args.args[2]
    assert (params.host, params.port) == ("192.168.1.50", 502)
    assert get_unit.call_args.args[3] == 1
    unit.require_timeout.assert_called()

    assert entry.runtime_data is not None
    assert entry.runtime_data.device is not None

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
    unit = create_mock_modbus_unit(connect=True, read_error=False)
    entry = await _async_setup(hass, unit)

    caplog.set_level(logging.INFO)

    coordinator = entry.runtime_data.coordinator
    success_registers = unit.read_holding_registers.return_value
    unit.read_holding_registers.side_effect = [
        ModbusConnectionError("charger offline"),
        ModbusConnectionError("charger offline"),
        success_registers,
    ]

    # The first failed poll is tolerated, the second one is an outage.
    await coordinator._async_update_data()
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
    unit = create_mock_modbus_unit(
        connect=True,
        read_error=False,
        registers=make_holding_registers_37(),
    )
    entry = await _async_setup(hass, unit)

    coordinator = entry.runtime_data.coordinator
    result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)

    assert result["entry"]["data"][CONF_HOST] == "**REDACTED**"
    assert result["entry"]["data"][CONF_PORT] == 502
    assert result["entry"]["data"][CONF_UNIT_ID] == 1
    assert result["entry"]["version"] == 3
    assert result["entry"]["options"][CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL
    assert result["device"]["host"] == "**REDACTED**"
    assert result["device"]["port"] == 502
    assert result["device"]["unit_id"] == 1
    assert result["coordinator"]["data"]["serial_number"] == "**REDACTED**"
    assert (
        result["coordinator"]["data"]["firmware_version"]
        == coordinator.data["firmware_version"]
    )
    assert result["coordinator"]["serial_number_cached"] is True


async def test_creates_and_clears_repair_issue_for_invalid_fallback_limit(
    hass: HomeAssistant,
) -> None:
    """Failed firmware auto-recovery should create a repair issue that clears later."""
    invalid_registers = make_holding_registers_37(user_max_amps=16, fallback_limit=32)
    valid_registers = make_holding_registers_37(user_max_amps=16, fallback_limit=10)

    unit = create_mock_modbus_unit(
        connect=True, read_error=False, registers=invalid_registers
    )
    unit.read_holding_registers.side_effect = [
        list(invalid_registers),
        list(invalid_registers),
        list(valid_registers),
    ]
    unit.write_register.side_effect = ModbusExceptionError(4)

    entry = await _async_setup(hass, unit)

    issue_reg = ir.async_get(hass)
    issue_id = f"invalid_fallback_limit_{entry.entry_id}"
    issue = issue_reg.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "firmware_limit_restore_failed"

    coordinator = entry.runtime_data.coordinator
    updated_data = await coordinator._async_update_data()
    coordinator.async_set_updated_data(updated_data)

    assert issue_reg.async_get_issue(DOMAIN, issue_id) is None


async def test_migrate_v1_to_current_adds_defaults(hass: HomeAssistant) -> None:
    """Version 1 entries receive default options and unit ID without re-adding."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
        options={},
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    assert entry.version == 3
    assert entry.options[CONF_SCAN_INTERVAL] == DEFAULT_SCAN_INTERVAL
    assert entry.data[CONF_UNIT_ID] == 1


async def test_migrate_v2_adds_unit_id_and_keeps_data(hass: HomeAssistant) -> None:
    """Version 2 entries gain the explicit unit ID; existing values are untouched."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=2,
        data={CONF_HOST: "192.168.1.50", CONF_PORT: 1502},
        options={CONF_SCAN_INTERVAL: 30},
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry) is True
    assert entry.version == 3
    assert entry.data == {CONF_HOST: "192.168.1.50", CONF_PORT: 1502, CONF_UNIT_ID: 1}
    assert entry.options[CONF_SCAN_INTERVAL] == 30


@pytest.mark.parametrize(
    "error",
    [
        ModbusTimeoutError("timed out"),
        ModbusConnectionError("link down"),
        TimeoutError(),
    ],
)
async def test_coordinator_connection_errors_raise_update_failed(
    hass: HomeAssistant, error: Exception
) -> None:
    """Connection problems and timeouts are transient outages, not crashes."""
    unit = create_mock_modbus_unit(connect=True, read_error=False)
    entry = await _async_setup(hass, unit)

    coordinator = entry.runtime_data.coordinator
    unit.read_holding_registers.side_effect = error

    # One missed poll keeps the previous data; a second one is an outage.
    assert await coordinator._async_update_data() is coordinator.data
    with pytest.raises(UpdateFailed, match="Connection error"):
        await coordinator._async_update_data()


async def test_coordinator_modbus_exception_response_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """A Modbus exception response from the charger surfaces as UpdateFailed."""
    unit = create_mock_modbus_unit(connect=True, read_error=False)
    entry = await _async_setup(hass, unit)

    coordinator = entry.runtime_data.coordinator
    unit.read_holding_registers.side_effect = ModbusExceptionError(2)

    with pytest.raises(UpdateFailed, match="Error reading registers"):
        await coordinator._async_update_data()


async def test_setup_retries_when_charger_is_offline(hass: HomeAssistant) -> None:
    """A charger that is down at startup makes the entry retry, not fail."""
    unit = create_mock_modbus_unit(connect=False, read_error=False)

    entry = MockConfigEntry(**mock_config_entry_kwargs())
    entry.add_to_hass(hass)
    with patch(_INIT_UNIT, return_value=unit):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state.value == "setup_retry"


async def _setup_with_scan_interval(
    hass: HomeAssistant, scan_interval: int, communication_timeout: int
) -> MockConfigEntry:
    unit = create_mock_modbus_unit(
        registers=make_holding_registers_37(communication_timeout=communication_timeout)
    )
    kwargs = mock_config_entry_kwargs()
    kwargs["options"] = {CONF_SCAN_INTERVAL: scan_interval}
    entry = MockConfigEntry(**kwargs)
    entry.add_to_hass(hass)
    with patch(_INIT_UNIT, return_value=unit):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.mark.parametrize(("scan_interval", "expect_issue"), [(30, False), (59, False), (60, True), (120, True)])
async def test_scan_interval_vs_communication_timeout_issue(
    hass: HomeAssistant, scan_interval: int, expect_issue: bool
) -> None:
    """A poll interval at or above the charger timeout (60 s) raises a repair issue."""
    entry = await _setup_with_scan_interval(hass, scan_interval, 60)

    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"scan_interval_exceeds_timeout_{entry.entry_id}"
    )
    if expect_issue:
        assert issue is not None
        assert issue.translation_key == "scan_interval_exceeds_timeout"
        assert issue.translation_placeholders == {
            "scan_interval": str(scan_interval),
            "timeout": "60",
        }
    else:
        assert issue is None


async def test_scan_interval_issue_cleared_when_timeout_raised_and_on_unload(
    hass: HomeAssistant,
) -> None:
    """The issue follows the charger's timeout and is removed when the entry unloads."""
    entry = await _setup_with_scan_interval(hass, 120, 60)
    issue_id = f"scan_interval_exceeds_timeout_{entry.entry_id}"
    registry = ir.async_get(hass)
    assert registry.async_get_issue(DOMAIN, issue_id) is not None

    coordinator = entry.runtime_data.coordinator
    unit_registers = make_holding_registers_37(communication_timeout=300)
    coordinator.device._unit.read_holding_registers.return_value = unit_registers
    await coordinator._async_update_data()
    assert registry.async_get_issue(DOMAIN, issue_id) is None

    # Raise it again, then confirm unload removes it.
    coordinator.device._unit.read_holding_registers.return_value = (
        make_holding_registers_37(communication_timeout=60)
    )
    await coordinator._async_update_data()
    assert registry.async_get_issue(DOMAIN, issue_id) is not None
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert registry.async_get_issue(DOMAIN, issue_id) is None


async def test_diagnostics_include_raw_status_block_without_serial(
    hass: HomeAssistant,
) -> None:
    """The raw block is exported as hex, with the serial number registers left out."""
    regs = make_holding_registers_37(charging_state_nibble=4, reduced_current_bit=True)
    regs[0:4] = [0x5422, 0x0400, 0x1922, 0x0001]
    unit = create_mock_modbus_unit(connect=True, read_error=False, registers=regs)
    entry = await _async_setup(hass, unit)

    result = await diagnostics.async_get_config_entry_diagnostics(hass, entry)
    raw = result["coordinator"]["raw_status_block"]

    assert raw["serial_registers"] == "redacted"
    # 4000h + 4 + index: 400Dh is index 13 - 4 = 9 in the exported list.
    assert raw["registers_0x4004_onward"][9] == f"{regs[13]:04X}"
    assert len(raw["registers_0x4004_onward"]) == 33
    assert "5422" not in str(result)


async def test_debug_log_of_status_registers_only_on_change(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """The raw register line is logged when the state or limits change, not each poll."""
    first = make_holding_registers_37(charging_state_nibble=4)
    second = make_holding_registers_37(charging_state_nibble=5)
    unit = create_mock_modbus_unit(connect=True, read_error=False, registers=first)
    entry = await _async_setup(hass, unit)
    coordinator = entry.runtime_data.coordinator

    caplog.set_level(logging.DEBUG, logger="custom_components.abb_terra_ac")
    caplog.clear()
    unit.read_holding_registers.return_value = list(first)
    await coordinator._async_update_data()
    assert not [r for r in caplog.records if "Status registers" in r.getMessage()]

    unit.read_holding_registers.return_value = list(second)
    await coordinator._async_update_data()
    lines = [r.getMessage() for r in caplog.records if "Status registers" in r.getMessage()]
    assert len(lines) == 1
    assert "400C-400D=0000 0500" in lines[0]


async def test_session_state_follows_a_real_pause_by_limit(hass: HomeAssistant) -> None:
    """Sequence from the 12.10 log: B1 -> C2 -> limit 0 A -> B1 (paused) -> B1 after unplug."""
    from custom_components.abb_terra_ac.session_state import SessionState

    def regs(state: int, limit_amps: float) -> list[int]:
        return make_holding_registers_37(
            charging_state_nibble=state,
            reduced_current_bit=True,
            socket_lock_raw_32=0x11,
            charging_current_modbus_amps=limit_amps,
            user_max_amps=20,
            fallback_limit=20,
        )

    unit = create_mock_modbus_unit(
        connect=True, read_error=False, registers=regs(1, 6.0)
    )
    entry = await _async_setup(hass, unit)
    coordinator = entry.runtime_data.coordinator
    assert coordinator.session_state == SessionState.IDLE  # plugged in, waiting

    for state, limit, expected in (
        (4, 6.0, SessionState.ACTIVE),
        (1, 0.0, SessionState.PAUSED_BY_CURRENT),  # limit 0 A while charging
        (4, 6.0, SessionState.ACTIVE),
        (0, 0.0, SessionState.IDLE),  # vehicle gone
        (1, 0.0, SessionState.IDLE),  # plugged in again, nothing charged yet
    ):
        unit.read_holding_registers.return_value = regs(state, limit)
        coordinator.async_set_updated_data(await coordinator._async_update_data())
        assert coordinator.session_state == expected, (state, limit)


async def test_single_missed_poll_keeps_entities_available(
    hass: HomeAssistant,
) -> None:
    """One poll lost to a charger reset does not make entities unavailable."""
    unit = create_mock_modbus_unit(connect=True, read_error=False)
    entry = await _async_setup(hass, unit)
    coordinator = entry.runtime_data.coordinator
    good = unit.read_holding_registers.return_value

    unit.read_holding_registers.side_effect = [ModbusTimeoutError("reset"), good]
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    await coordinator.async_refresh()  # a good poll resets the failure count

    unit.read_holding_registers.side_effect = [
        ModbusTimeoutError("down"),
        ModbusTimeoutError("down"),
        good,
    ]
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
    await coordinator.async_refresh()
    assert coordinator.last_update_success is False
    await coordinator.async_refresh()
    assert coordinator.last_update_success is True
