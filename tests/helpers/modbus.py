"""Shared Modbus TCP mocks for ABB Terra AC tests."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

from modbus_connection import ModbusConnectionError, ModbusExceptionError


def make_holding_registers_37(
    *,
    charging_state_nibble: int = 0,
    reduced_current_bit: bool = False,
    socket_lock_raw_32: int = 0,
    error_code: int = 0,
    user_max_amps: float = 16.0,
    charging_current_limit_amps: float = 0.0,
    charging_l1_amps: float = 0.0,
    charging_current_modbus_amps: float = 0.0,
    fallback_limit: int = 0,
    voltage_l1: float = 0.0,
    active_power_wh: int = 0,
    energy_wh: int = 0,
    communication_timeout: int = 60,
) -> list[int]:
    """Build 37 registers (base 4000h block) matching coordinator decoding.

    Indexes follow ``read_holding_registers(..., count=37)`` → ``registers[0..36]``.
    """
    r = [0] * 37

    def write_u32(idx: int, value: int) -> None:
        r[idx] = (value >> 16) & 0xFFFF
        r[idx + 1] = value & 0xFFFF

    write_u32(6, int(user_max_amps / 0.001))
    write_u32(8, error_code & 0xFFFFFFFF)
    write_u32(10, int(socket_lock_raw_32) & 0xFFFFFFFF)

    high_byte = (charging_state_nibble & 0x0F)
    if reduced_current_bit:
        high_byte |= 0x80
    r[13] = high_byte << 8

    write_u32(14, int(charging_current_limit_amps / 0.001))
    write_u32(16, int(charging_l1_amps / 0.001))
    write_u32(22, int(voltage_l1 / 0.1))
    write_u32(28, active_power_wh)
    write_u32(30, energy_wh)
    r[32] = communication_timeout & 0xFFFF
    write_u32(34, int(charging_current_modbus_amps / 0.001))
    r[36] = fallback_limit & 0xFFFF
    return r


def create_mock_modbus_unit(
    *,
    connect: bool = True,
    read_error: bool = False,
    registers: list[int] | None = None,
) -> MagicMock:
    """Return a stand-in for a ``modbus_connection.ModbusUnit``.

    ``read_holding_registers`` returns the register list directly (as the real
    unit does). ``connect=False`` makes reads raise ``ModbusConnectionError``;
    ``read_error=True`` makes them raise a Modbus exception response.

    The coordinator reads 37 holding registers; the config flow probes with
    count=1. A fixed length-37 register list satisfies both call sites.
    """
    regs = list(registers) if registers is not None else [0] * 37
    if len(regs) != 37:
        msg = "registers must have length 37"
        raise ValueError(msg)

    unit = MagicMock()
    unit.connected = connect
    unit.require_timeout = MagicMock()

    if not connect:
        unit.read_holding_registers = AsyncMock(
            side_effect=ModbusConnectionError("not connected")
        )
    elif read_error:
        unit.read_holding_registers = AsyncMock(side_effect=ModbusExceptionError(2))
    else:
        unit.read_holding_registers = AsyncMock(return_value=regs)

    unit.write_register = AsyncMock(return_value=None)
    unit.write_registers = AsyncMock(return_value=None)
    return unit


def temporary_unit_factory(unit: MagicMock):
    """Return a replacement for ``async_get_temporary_unit`` yielding ``unit``."""

    @asynccontextmanager
    async def _factory(hass, params, unit_id):
        yield unit

    return _factory
