"""Entity platform tests (sensor / switch / number) for ``abb_terra_ac``."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.abb_terra_ac.const import DOMAIN, CHARGING_STATES, ERROR_CODES, SOCKET_LOCK_STATES
from custom_components.abb_terra_ac.number import AbbTerraAcFallbackLimit
from custom_components.abb_terra_ac.switch import AbbTerraAcChargingSwitch
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from tests.helpers.modbus import (
    create_mock_modbus_client,
    make_holding_registers_37,
)

_INIT_MODBUS = "custom_components.abb_terra_ac.AsyncModbusTcpClient"

_EXPECTED_ENTITY_SUFFIXES = frozenset(
    {
        "charging_state",
        "serial_number",
        "firmware_version",
        "error_code",
        "socket_lock_state",
        "active_power",
        "energy_delivered",
        "current_l1",
        "current_l2",
        "current_l3",
        "voltage_l1",
        "voltage_l2",
        "voltage_l3",
        "actual_current_limit",
        "charging",
        "lock",
        "current_limit",
        "fallback_limit",
    }
)


def _suffix(registry_entry: er.RegistryEntry, entry_id: str) -> str:
    prefix = f"{entry_id}_"
    if not registry_entry.unique_id.startswith(prefix):
        msg = f"unexpected unique_id {registry_entry.unique_id!r}"
        raise AssertionError(msg)
    return registry_entry.unique_id.removeprefix(prefix)


def _write_register_address_value(call) -> tuple[int, int]:
    """Normalize one ``write_register`` mock call (positional or keyword)."""
    if call.args and len(call.args) >= 2:
        return int(call.args[0]), int(call.args[1])
    return int(call.kwargs["address"]), int(call.kwargs["value"])


def _write_registers_address_values(call) -> tuple[int, list[int]]:
    """Normalize one ``write_registers`` mock call."""
    if call.args and len(call.args) >= 2:
        return int(call.args[0]), list(call.args[1])
    return int(call.kwargs["address"]), list(call.kwargs["values"])


def _read_result_with_registers(registers: list[int]) -> MagicMock:
    """Build one mocked Modbus read result object."""
    result = MagicMock()
    result.isError.return_value = False
    result.registers = list(registers)
    return result


def _entity_id_for(
    hass: HomeAssistant, config_entry_id: str, suffix: str
) -> str:
    """Resolve entity_id from config entry id and unique_id suffix."""
    registry = er.async_get(hass)
    prefix = f"{config_entry_id}_{suffix}"
    for e in er.async_entries_for_config_entry(registry, config_entry_id):
        if e.unique_id == prefix:
            return e.entity_id
    msg = f"No entity with unique_id {prefix!r}"
    raise AssertionError(msg)


def _with_identity_registers(registers: list[int], *, firmware_patch_bcd: int = 3) -> list[int]:
    """Populate serial number and firmware registers with deterministic values."""
    updated = list(registers)
    updated[0] = 0x4711
    updated[1] = 0x2A00
    updated[2] = 0x1224
    updated[3] = 0x3456
    updated[4] = 0x0102
    updated[5] = (firmware_patch_bcd << 8) & 0xFFFF
    return updated


async def _async_setup_with_registers(
    hass: HomeAssistant, registers: list[int]
) -> tuple[MockConfigEntry, object]:
    """Set up config entry with mocked Modbus returning ``registers``."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.50", CONF_PORT: 502},
    )
    entry.add_to_hass(hass)
    mock_client = create_mock_modbus_client(
        connect=True, read_error=False, registers=registers
    )
    with patch(_INIT_MODBUS, return_value=mock_client):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry, mock_client


async def test_entity_registry_matches_integration(hass: HomeAssistant) -> None:
    """Exactly the expected set of entities is created for one config entry."""
    registers = make_holding_registers_37()
    entry, _ = await _async_setup_with_registers(hass, registers)

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    found = frozenset(_suffix(e, entry.entry_id) for e in entries)

    assert found == _EXPECTED_ENTITY_SUFFIXES
    assert len(entries) == len(_EXPECTED_ENTITY_SUFFIXES)

    by_suffix = {_suffix(e, entry.entry_id): e for e in entries}
    for suffix, ent in by_suffix.items():
        assert ent.platform == DOMAIN, suffix
        if suffix in ("charging", "lock"):
            assert ent.domain == "switch", suffix
        elif suffix in ("current_limit", "fallback_limit"):
            assert ent.domain == "number", suffix
        else:
            assert ent.domain == "sensor", suffix


async def test_single_device_for_config_entry(hass: HomeAssistant) -> None:
    """Device registry contains one device tied to the config entry."""
    registers = make_holding_registers_37()
    entry, _ = await _async_setup_with_registers(hass, registers)

    dev_reg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(dev_reg, entry.entry_id)
    assert len(devices) == 1
    assert devices[0].name == "ABB Terra AC Charger"


async def test_entities_use_has_entity_name(hass: HomeAssistant) -> None:
    """Entity registry names should omit the device prefix."""
    registers = make_holding_registers_37()
    entry, _ = await _async_setup_with_registers(hass, registers)

    charging_state_id = _entity_id_for(hass, entry.entry_id, "charging_state")
    charging_switch_id = _entity_id_for(hass, entry.entry_id, "charging")
    current_limit_id = _entity_id_for(hass, entry.entry_id, "current_limit")

    assert hass.states.get(charging_state_id).attributes["friendly_name"] == "ABB Terra AC Charger Charging State"
    assert hass.states.get(charging_switch_id).attributes["friendly_name"] == "ABB Terra AC Charger Start/Stop Charging"
    assert hass.states.get(current_limit_id).attributes["friendly_name"] == "ABB Terra AC Charger Charging Current Limit"


async def test_entities_use_expected_entity_categories(hass: HomeAssistant) -> None:
    """Diagnostic entities should be categorized for the UI."""
    registers = make_holding_registers_37()
    entry, _ = await _async_setup_with_registers(hass, registers)

    registry = er.async_get(hass)

    assert registry.async_get(_entity_id_for(hass, entry.entry_id, "serial_number")).entity_category == "diagnostic"
    assert registry.async_get(_entity_id_for(hass, entry.entry_id, "firmware_version")).entity_category == "diagnostic"
    assert registry.async_get(_entity_id_for(hass, entry.entry_id, "error_code")).entity_category == "diagnostic"
    assert registry.async_get(_entity_id_for(hass, entry.entry_id, "current_limit")).entity_category is None
    assert registry.async_get(_entity_id_for(hass, entry.entry_id, "fallback_limit")).entity_category is None


async def test_entities_use_expected_device_classes(hass: HomeAssistant) -> None:
    """Entities should expose appropriate Home Assistant device classes."""
    registers = make_holding_registers_37()
    entry, _ = await _async_setup_with_registers(hass, registers)

    charging_state_id = _entity_id_for(hass, entry.entry_id, "charging_state")
    error_code_id = _entity_id_for(hass, entry.entry_id, "error_code")
    socket_lock_id = _entity_id_for(hass, entry.entry_id, "socket_lock_state")
    active_power_id = _entity_id_for(hass, entry.entry_id, "active_power")
    energy_id = _entity_id_for(hass, entry.entry_id, "energy_delivered")
    current_id = _entity_id_for(hass, entry.entry_id, "current_l1")
    voltage_id = _entity_id_for(hass, entry.entry_id, "voltage_l1")
    actual_limit_id = _entity_id_for(hass, entry.entry_id, "actual_current_limit")
    charging_switch_id = _entity_id_for(hass, entry.entry_id, "charging")
    lock_switch_id = _entity_id_for(hass, entry.entry_id, "lock")

    assert hass.states.get(charging_state_id).attributes["device_class"] == "enum"
    assert hass.states.get(error_code_id).attributes["device_class"] == "enum"
    assert hass.states.get(socket_lock_id).attributes["device_class"] == "enum"
    assert hass.states.get(active_power_id).attributes["device_class"] == "power"
    assert hass.states.get(energy_id).attributes["device_class"] == "energy"
    assert hass.states.get(current_id).attributes["device_class"] == "current"
    assert hass.states.get(voltage_id).attributes["device_class"] == "voltage"
    assert hass.states.get(actual_limit_id).attributes["device_class"] == "current"
    assert hass.states.get(charging_switch_id).attributes["device_class"] == "switch"
    assert hass.states.get(lock_switch_id).attributes["device_class"] == "switch"


async def test_sensor_states_reflect_registers(hass: HomeAssistant) -> None:
    """Several sensors expose decoded Modbus values (enabled entities)."""
    registers = make_holding_registers_37(
        charging_state_nibble=4,
        socket_lock_raw_32=17,
        error_code=0,
        user_max_amps=16.0,
        charging_current_limit_amps=11.0,
        charging_l1_amps=10.0,
        charging_current_modbus_amps=11.0,
        fallback_limit=8,
        voltage_l1=230.0,
        active_power_wh=5000,
        energy_wh=12345,
    )
    entry, _ = await _async_setup_with_registers(hass, registers)

    charging_id = _entity_id_for(hass, entry.entry_id, "charging_state")
    assert hass.states.get(charging_id).state == CHARGING_STATES[4]

    err_id = _entity_id_for(hass, entry.entry_id, "error_code")
    assert hass.states.get(err_id).state == ERROR_CODES[0]

    lock_id = _entity_id_for(hass, entry.entry_id, "socket_lock_state")
    assert hass.states.get(lock_id).state == SOCKET_LOCK_STATES[17]

    lim_id = _entity_id_for(hass, entry.entry_id, "actual_current_limit")
    assert float(hass.states.get(lim_id).state) == pytest.approx(11.0)

    cur1_id = _entity_id_for(hass, entry.entry_id, "current_l1")
    assert float(hass.states.get(cur1_id).state) == pytest.approx(10.0)

    v1_id = _entity_id_for(hass, entry.entry_id, "voltage_l1")
    assert float(hass.states.get(v1_id).state) == pytest.approx(230.0)

    p_id = _entity_id_for(hass, entry.entry_id, "active_power")
    assert float(hass.states.get(p_id).state) == pytest.approx(5000.0)

    e_id = _entity_id_for(hass, entry.entry_id, "energy_delivered")
    assert float(hass.states.get(e_id).state) == pytest.approx(12345.0)


async def test_switch_charging_turn_on_writes_modbus(hass: HomeAssistant) -> None:
    """Starting charging issues Modbus write to register 4105h."""
    registers = make_holding_registers_37(charging_state_nibble=0)
    entry, mock_client = await _async_setup_with_registers(hass, registers)

    entity_id = _entity_id_for(hass, entry.entry_id, "charging")
    assert hass.states.get(entity_id).state == "off"

    with patch(
        "custom_components.abb_terra_ac.switch.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert mock_client.write_register.await_count >= 1
    match = [
        _write_register_address_value(c)
        for c in mock_client.write_register.await_args_list
        if _write_register_address_value(c) == (16645, 0)
    ]
    assert match


async def test_switch_charging_turn_off_writes_modbus(hass: HomeAssistant) -> None:
    """Stopping charging issues Modbus write to register 4105h."""
    registers = make_holding_registers_37(charging_state_nibble=4)
    entry, mock_client = await _async_setup_with_registers(hass, registers)

    entity_id = _entity_id_for(hass, entry.entry_id, "charging")
    assert hass.states.get(entity_id).state == "on"

    with patch(
        "custom_components.abb_terra_ac.switch.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert mock_client.write_register.await_count >= 1
    match = [
        _write_register_address_value(c)
        for c in mock_client.write_register.await_args_list
        if _write_register_address_value(c) == (16645, 1)
    ]
    assert match


async def test_switch_lock_turn_on_and_turn_off_write_modbus(hass: HomeAssistant) -> None:
    """Cable lock switch maps on/off to the expected Modbus register."""
    registers = make_holding_registers_37(socket_lock_raw_32=1)
    entry, mock_client = await _async_setup_with_registers(hass, registers)

    entity_id = _entity_id_for(hass, entry.entry_id, "lock")
    assert hass.states.get(entity_id).state == "off"

    with patch(
        "custom_components.abb_terra_ac.switch.asyncio.sleep",
        new_callable=AsyncMock,
    ):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        await hass.services.async_call(
            "switch",
            "turn_off",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    writes = {
        _write_register_address_value(c)
        for c in mock_client.write_register.await_args_list
    }
    assert (16643, 1) in writes
    assert (16643, 0) in writes


async def test_number_charging_limit_set_value_writes_registers(hass: HomeAssistant) -> None:
    """Charging current limit number uses 32-bit write to 4100h."""
    registers = make_holding_registers_37(
        user_max_amps=32.0,
        charging_current_modbus_amps=16.0,
    )
    entry, mock_client = await _async_setup_with_registers(hass, registers)

    entity_id = _entity_id_for(hass, entry.entry_id, "current_limit")

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 15.0},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_client.write_registers.await_count >= 1
    found = False
    for c in mock_client.write_registers.await_args_list:
        addr, vals = _write_registers_address_values(c)
        if addr == 16640 and vals == [0, 15000]:
            found = True
            break
    assert found


async def test_number_fallback_set_value_writes_register(hass: HomeAssistant) -> None:
    """Fallback limit number writes single register 4111h."""
    registers = make_holding_registers_37(user_max_amps=32.0, fallback_limit=6)
    entry, mock_client = await _async_setup_with_registers(hass, registers)

    entity_id = _entity_id_for(hass, entry.entry_id, "fallback_limit")

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 9.0},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert mock_client.write_register.await_count >= 1
    match = [
        _write_register_address_value(c)
        for c in mock_client.write_register.await_args_list
        if _write_register_address_value(c) == (16649, 9)
    ]
    assert match


async def test_number_entities_use_dynamic_max_value(hass: HomeAssistant) -> None:
    """Number entities derive their max value from user_settable_max_current."""
    registers = make_holding_registers_37(user_max_amps=20.0)
    entry, _ = await _async_setup_with_registers(hass, registers)

    current_limit_id = _entity_id_for(hass, entry.entry_id, "current_limit")
    fallback_limit_id = _entity_id_for(hass, entry.entry_id, "fallback_limit")

    assert float(hass.states.get(current_limit_id).attributes["max"]) == pytest.approx(20.0)
    assert float(hass.states.get(fallback_limit_id).attributes["max"]) == pytest.approx(20.0)


async def test_disabled_identity_sensors_can_be_enabled_and_updated(
    hass: HomeAssistant,
) -> None:
    """Default-disabled serial/firmware sensors can be enabled and refreshed."""
    initial_registers = _with_identity_registers(make_holding_registers_37(), firmware_patch_bcd=3)
    updated_registers = _with_identity_registers(make_holding_registers_37(), firmware_patch_bcd=4)
    entry, mock_client = await _async_setup_with_registers(hass, initial_registers)

    serial_id = _entity_id_for(hass, entry.entry_id, "serial_number")
    firmware_id = _entity_id_for(hass, entry.entry_id, "firmware_version")
    registry = er.async_get(hass)

    assert hass.states.get(serial_id) is None
    assert hass.states.get(firmware_id) is None
    assert registry.async_get(serial_id).disabled_by is not None
    assert registry.async_get(firmware_id).disabled_by is not None

    registry.async_update_entity(serial_id, disabled_by=None)
    registry.async_update_entity(firmware_id, disabled_by=None)
    await hass.async_block_till_done()

    assert hass.states.get(serial_id) is None
    assert hass.states.get(firmware_id) is None

    with patch(_INIT_MODBUS, return_value=mock_client):
        assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(serial_id).state == "TACW11-42-1224-G3456"
    assert hass.states.get(firmware_id).state == "v1.2.3"

    mock_client.read_holding_registers.return_value.registers = updated_registers
    with patch(_INIT_MODBUS, return_value=mock_client):
        assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(serial_id).state == "TACW11-42-1224-G3456"
    assert hass.states.get(firmware_id).state == "v1.2.4"


async def test_coordinator_restores_invalid_fallback_limit(hass: HomeAssistant) -> None:
    """Invalid fallback limit is restored to the last known valid value."""
    valid_registers = make_holding_registers_37(
        user_max_amps=16.0,
        fallback_limit=10,
    )
    invalid_registers = make_holding_registers_37(
        user_max_amps=16.0,
        fallback_limit=32,
    )
    entry, mock_client = await _async_setup_with_registers(hass, valid_registers)

    coordinator = entry.runtime_data.coordinator
    assert coordinator.data["fallback_limit"] == 10

    mock_client.read_holding_registers.side_effect = [
        _read_result_with_registers(invalid_registers),
    ]
    updated_data = await coordinator._async_update_data()
    coordinator.async_set_updated_data(updated_data)
    await hass.async_block_till_done()

    writes = {
        _write_register_address_value(c)
        for c in mock_client.write_register.await_args_list
    }
    assert (16649, 10) in writes
    assert coordinator.data["fallback_limit"] == 10


async def test_coordinator_restores_invalid_current_limit(hass: HomeAssistant) -> None:
    """Invalid charging current limit is restored to the last known valid value."""
    valid_registers = make_holding_registers_37(
        user_max_amps=16.0,
        charging_current_modbus_amps=12.0,
    )
    invalid_registers = make_holding_registers_37(
        user_max_amps=16.0,
        charging_current_modbus_amps=32.0,
    )
    entry, mock_client = await _async_setup_with_registers(hass, valid_registers)

    coordinator = entry.runtime_data.coordinator
    assert coordinator.data["charging_current_limit_modbus"] == 12

    mock_client.read_holding_registers.side_effect = [
        _read_result_with_registers(invalid_registers),
    ]
    updated_data = await coordinator._async_update_data()
    coordinator.async_set_updated_data(updated_data)
    await hass.async_block_till_done()

    found = False
    for c in mock_client.write_registers.await_args_list:
        addr, vals = _write_registers_address_values(c)
        if addr == 16640 and vals == [0, 12000]:
            found = True
            break
    assert found


async def test_switch_write_exception_raises_translated_error() -> None:
    """Entity actions should raise translated HA errors on connection failure."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.50", CONF_PORT: 502})
    coordinator = MagicMock()
    coordinator.data = {"charging_state": 0}
    coordinator.async_request_refresh = AsyncMock()
    client = MagicMock()
    client.write_register = AsyncMock(side_effect=RuntimeError("boom"))

    entity = AbbTerraAcChargingSwitch(coordinator, entry, client)

    with patch("custom_components.abb_terra_ac.switch.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(HomeAssistantError) as err:
            await entity.async_turn_on()

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "charger_unavailable"


async def test_number_write_error_result_raises_translated_error() -> None:
    """Modbus error responses should raise translated HA errors."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "192.168.1.50", CONF_PORT: 502})
    coordinator = MagicMock()
    coordinator.data = {"fallback_limit": 0, "user_settable_max_current": 16}
    coordinator.async_request_refresh = AsyncMock()
    client = MagicMock()
    write_result = MagicMock()
    write_result.isError.return_value = True
    client.write_register = AsyncMock(return_value=write_result)

    entity = AbbTerraAcFallbackLimit(coordinator, entry, client)

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_set_native_value(8)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "write_failed"
