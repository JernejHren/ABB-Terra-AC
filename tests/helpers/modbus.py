"""Shared Modbus TCP mocks for ABB Terra AC tests."""

from unittest.mock import AsyncMock, MagicMock


def make_holding_registers_37(
    *,
    charging_state_nibble: int = 0,
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
) -> list[int]:
    """Build 37 registers (base 4000h block) matching coordinator decoding.

    Indexes follow ``read_holding_registers(..., count=37)`` → ``registers[0..36]``.
    """
    r = [0] * 37

    def write_u32(idx: int, value: int) -> None:
        r[idx] = (value >> 16) & 0xFFFF
        r[idx + 1] = value & 0xFFFF

    r[8] = error_code & 0xFFFF
    write_u32(6, int(user_max_amps / 0.001))
    write_u32(10, int(socket_lock_raw_32) & 0xFFFFFFFF)
    r[13] = (charging_state_nibble & 0x0F) << 8
    write_u32(14, int(charging_current_limit_amps / 0.001))
    write_u32(16, int(charging_l1_amps / 0.001))
    write_u32(22, int(voltage_l1 / 0.1))
    write_u32(28, active_power_wh)
    write_u32(30, energy_wh)
    write_u32(34, int(charging_current_modbus_amps / 0.001))
    r[36] = fallback_limit & 0xFFFF
    return r


def create_mock_modbus_client(
    *,
    connect: bool = True,
    read_error: bool = False,
    registers: list[int] | None = None,
) -> MagicMock:
    """Return a stand-in for pymodbus AsyncModbusTcpClient.

    The coordinator reads 37 holding registers; config flow probes with count=1.
    A fixed length-37 register list satisfies both call sites.
    """
    client = MagicMock()
    client.connected = False

    async def _connect() -> bool:
        if connect:
            client.connected = True
        return connect

    client.connect = AsyncMock(side_effect=_connect)

    regs = list(registers) if registers is not None else [0] * 37
    if len(regs) != 37:
        msg = "registers must have length 37"
        raise ValueError(msg)

    read_result = MagicMock()
    read_result.isError.return_value = read_error
    read_result.registers = regs
    client.read_holding_registers = AsyncMock(return_value=read_result)

    write_result = MagicMock()
    write_result.isError.return_value = False
    client.write_register = AsyncMock(return_value=write_result)
    client.write_registers = AsyncMock(return_value=write_result)

    def _close() -> None:
        client.connected = False

    client.close = MagicMock(side_effect=_close)
    return client
