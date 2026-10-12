"""Tests for the Home Assistant-independent ABB Terra AC device library.

Expected values come from the ABB Terra AC Modbus communication manual v1.11
(sections 5.1 to 5.19).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.abb_terra_ac.api import AbbTerraAcDevice
from custom_components.abb_terra_ac.api.device import (
    REG_CABLE_LOCK,
    REG_COMMUNICATION_TIMEOUT,
    REG_CURRENT_LIMIT,
    REG_FALLBACK_LIMIT,
    REG_START_STOP_SESSION,
    REG_STATUS_BLOCK,
    STATUS_BLOCK_LENGTH,
    decode_32bit_value,
    decode_firmware_version,
    decode_serial_number,
    decode_status_block,
)

from tests.helpers.modbus import create_mock_modbus_unit, make_holding_registers_37


def test_register_addresses_match_manual() -> None:
    """Addresses from the manual's register table (4000h, 4100h, ...)."""
    assert REG_STATUS_BLOCK == 0x4000
    assert STATUS_BLOCK_LENGTH == 0x24 + 1  # 4000h..4024h inclusive
    assert REG_CURRENT_LIMIT == 0x4100
    assert REG_CABLE_LOCK == 0x4103
    assert REG_START_STOP_SESSION == 0x4105
    assert REG_COMMUNICATION_TIMEOUT == 0x4106
    assert REG_FALLBACK_LIMIT == 0x4109


def test_decode_serial_number_manual_example() -> None:
    """Manual 5.1: 0x54 0x22 0x04 0x00 0x49 0x20 0x00 0x25 -> TACW22-4-4920-T0025."""
    assert decode_serial_number([0x5422, 0x0400, 0x4920, 0x0025]) == (
        "TACW22-4-4920-T0025"
    )


@pytest.mark.parametrize(
    ("connector_byte", "letter"),
    [(0x47, "G"), (0x50, "P"), (0x53, "S"), (0x54, "T")],
)
def test_decode_serial_number_connector_types(connector_byte: int, letter: str) -> None:
    """Each documented connector type maps to its letter."""
    result = decode_serial_number([(connector_byte << 8) | 0x07, 0x0400, 0x0120, 0x0001])
    assert result == f"TACW7-4-0120-{letter}0001"


def test_decode_serial_number_bad_input_does_not_raise() -> None:
    """Decoding must never break polling."""
    assert decode_serial_number([]).startswith("Decode error")


def test_decode_firmware_version_manual_example() -> None:
    """Manual 5.2: 0x01 0x02 0x13 0x00 -> v1.2.13 (last byte reserved)."""
    assert decode_firmware_version([0x0102, 0x1300]) == "v1.2.13"


def test_decode_32bit_value_is_high_word_first() -> None:
    """32-bit values are two registers, high word first."""
    assert decode_32bit_value([0x0001, 0x0000]) == 65536
    assert decode_32bit_value([0x0000, 0x3E80], 0.001) == pytest.approx(16.0)


def test_decode_status_block_scales_and_layout() -> None:
    """Offsets and resolutions follow the register table."""
    regs = make_holding_registers_37(
        user_max_amps=16.0,
        charging_current_limit_amps=10.0,
        charging_l1_amps=9.5,
        charging_current_modbus_amps=8.0,
        fallback_limit=6,
        voltage_l1=230.5,
        active_power_wh=2200,
        energy_wh=1234,
        communication_timeout=60,
    )
    data = decode_status_block(regs)

    assert data["user_settable_max_current"] == pytest.approx(16.0)
    assert data["charging_current_limit"] == pytest.approx(10.0)
    assert data["charging_current_l1"] == pytest.approx(9.5)
    assert data["charging_current_limit_modbus"] == pytest.approx(8.0)
    assert data["fallback_limit"] == 6
    assert data["voltage_l1"] == pytest.approx(230.5)
    assert data["active_power"] == 2200
    assert data["energy_delivered"] == 1234
    assert data["communication_timeout"] == 60


@pytest.mark.parametrize("state", [0, 1, 2, 3, 4, 5])
def test_decode_charging_state_uses_byte_1_of_400d(state: int) -> None:
    """Manual 5.6: bits 6..0 of byte 1 (high byte of 400Dh) hold the state."""
    regs = make_holding_registers_37(charging_state_nibble=state)
    data = decode_status_block(regs)
    assert data["charging_state"] == state
    assert data["charging_at_reduced_current"] is False


def test_decode_charging_state_reduced_current_bit() -> None:
    """Manual 5.6: bit 7 set means charging below the value commanded via 4100h."""
    regs = make_holding_registers_37(charging_state_nibble=4, reduced_current_bit=True)
    data = decode_status_block(regs)
    assert data["charging_state"] == 4
    assert data["charging_at_reduced_current"] is True


def test_decode_status_block_uses_cached_serial() -> None:
    """A cached serial skips decoding it again."""
    regs = make_holding_registers_37()
    assert decode_status_block(regs, "CACHED")["serial_number"] == "CACHED"


async def test_read_status_reads_one_block_and_caches_serial() -> None:
    """One 37-register read; the serial is cached after the first poll."""
    regs = make_holding_registers_37()
    unit = create_mock_modbus_unit(registers=regs)
    device = AbbTerraAcDevice(unit)

    assert device.serial_number is None
    first = await device.async_read_status()
    unit.read_holding_registers.assert_awaited_once_with(0x4000, 37)
    assert device.serial_number == first["serial_number"]

    # Corrupt the serial words: the cached value must still be reported.
    changed = list(regs)
    changed[0:4] = [0xFFFF] * 4
    unit.read_holding_registers.return_value = changed
    second = await device.async_read_status()
    assert second["serial_number"] == first["serial_number"]


async def test_probe_reads_one_register() -> None:
    """The config flow probe is a single register read at 4000h."""
    unit = create_mock_modbus_unit()
    await AbbTerraAcDevice(unit).async_probe()
    unit.read_holding_registers.assert_awaited_once_with(0x4000, 1)


def _device() -> tuple[AbbTerraAcDevice, MagicMock]:
    unit = create_mock_modbus_unit()
    return AbbTerraAcDevice(unit), unit


async def test_start_and_stop_session_values() -> None:
    """Manual 5.17: 0 starts, 1 stops a session (register 4105h)."""
    device, unit = _device()
    await device.async_start_session()
    unit.write_register.assert_awaited_with(0x4105, 0)
    await device.async_stop_session()
    unit.write_register.assert_awaited_with(0x4105, 1)


async def test_cable_lock_values() -> None:
    """Manual 5.16: 1 locks, 0 unlocks (register 4103h)."""
    device, unit = _device()
    await device.async_set_cable_lock(True)
    unit.write_register.assert_awaited_with(0x4103, 1)
    await device.async_set_cable_lock(False)
    unit.write_register.assert_awaited_with(0x4103, 0)


async def test_set_fallback_and_timeout_registers() -> None:
    """Fallback limit goes to 4109h and the timeout to 4106h."""
    device, unit = _device()
    await device.async_set_fallback_limit(16)
    unit.write_register.assert_awaited_with(0x4109, 16)
    await device.async_set_communication_timeout(120)
    unit.write_register.assert_awaited_with(0x4106, 120)


@pytest.mark.parametrize(
    ("amps", "words"),
    [
        (16, [0x0000, 0x3E80]),  # 16000 mA
        (6, [0x0000, 0x1770]),  # 6000 mA
        (0, [0x0000, 0x0000]),
        (32.5, [0x0000, 0x7EF4]),  # 32500 mA
        (1.005, [0x0000, 0x03ED]),  # 1005 mA, not 1004 from float truncation
    ],
)
async def test_set_current_limit_writes_milliamps_as_32_bit(
    amps: float, words: list[int]
) -> None:
    """Manual 5.15: 32-bit value at 4100h, resolution 0.001 A, high word first."""
    device, unit = _device()
    await device.async_set_current_limit(amps)
    unit.write_registers.assert_awaited_once_with(0x4100, words)


@pytest.mark.parametrize("amps", [-1, 5_000_000])
async def test_set_current_limit_rejects_out_of_range(amps: float) -> None:
    """A value that does not fit 32 bits is rejected, never wrapped."""
    device, unit = _device()
    unit.write_registers = AsyncMock()
    with pytest.raises(ValueError, match="outside the 32-bit register range"):
        await device.async_set_current_limit(amps)
    unit.write_registers.assert_not_awaited()
