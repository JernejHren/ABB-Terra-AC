"""Modbus device library for the ABB Terra AC charger.

This module deliberately has no Home Assistant imports. It talks to the charger
through a ``modbus_connection.ModbusUnit`` handed in by the caller, so the
caller owns (and shares) the connection.

Register map: ABB Terra AC Modbus Communication v1.11.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .models import AbbTerraAcData

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit

_LOGGER = logging.getLogger(__name__)

# Base of the polled block (4000h) and its length.
REG_STATUS_BLOCK = 16384
STATUS_BLOCK_LENGTH = 37

# Writable registers.
REG_CURRENT_LIMIT = 16640  # 4100h, 32-bit, mA
REG_CABLE_LOCK = 16643  # 4103h
REG_START_STOP_SESSION = 16645  # 4105h
REG_COMMUNICATION_TIMEOUT = 16646  # 4106h
REG_FALLBACK_LIMIT = 16649  # 4109h

VAL_START_SESSION = 0
VAL_STOP_SESSION = 1

# Largest value the 32-bit current-limit register (4100h) can hold.
MAX_CURRENT_LIMIT_MA = 0xFFFFFFFF


def decode_32bit_value(regs: list[int], resolution: float = 1) -> float:
    """Decode a 32-bit value from two registers (high word first)."""
    return ((regs[0] << 16) | regs[1]) * resolution


def decode_serial_number(regs: list[int]) -> str:
    """Decode the serial number from four registers."""
    try:
        connector_type = {0x47: "G", 0x50: "P", 0x53: "S", 0x54: "T"}
        rated_power_map = {0x07: "7", 0x11: "11", 0x22: "22"}

        byte7 = (regs[0] >> 8) & 0xFF
        byte6 = regs[0] & 0xFF
        byte5 = (regs[1] >> 8) & 0xFF
        byte3 = (regs[2] >> 8) & 0xFF
        byte2 = regs[2] & 0xFF
        byte1 = (regs[3] >> 8) & 0xFF
        byte0 = regs[3] & 0xFF

        connector = connector_type.get(byte7, f"Unknown (0x{byte7:02X})")
        rated_power = rated_power_map.get(byte6, str(byte6))
        plant_id = byte5
        prod_week = ((byte3 >> 4) & 0xF) * 10 + (byte3 & 0xF)
        prod_year = ((byte2 >> 4) & 0xF) * 10 + (byte2 & 0xF)
        serial_num = (
            ((byte1 >> 4) & 0xF) * 1000
            + (byte1 & 0xF) * 100
            + ((byte0 >> 4) & 0xF) * 10
            + (byte0 & 0xF)
        )

        return (
            f"TACW{rated_power}-{plant_id}-{prod_week:02d}{prod_year:02d}"
            f"-{connector}{serial_num:04d}"
        )
    except Exception as err:  # noqa: BLE001 - decoding must never break polling
        _LOGGER.warning("Failed to decode serial number: %s", err)
        return f"Decode error: {regs}"


def decode_firmware_version(regs: list[int]) -> str:
    """Decode the firmware version from two registers."""
    try:
        major = (regs[0] >> 8) & 0xFF
        minor = regs[0] & 0xFF
        patch = (regs[1] >> 8) & 0xFF
        patch_bcd = ((patch >> 4) & 0xF) * 10 + (patch & 0xF)
        return f"v{major}.{minor}.{patch_bcd}"
    except Exception as err:  # noqa: BLE001 - decoding must never break polling
        _LOGGER.warning("Failed to decode firmware version: %s", err)
        return f"Decode error: {regs}"


def decode_status_block(
    registers: list[int], serial_number: str | None = None
) -> AbbTerraAcData:
    """Decode the 37-register status block into typed charger data.

    ``serial_number`` lets the caller pass a cached value; the serial is
    decoded from the block only when it is ``None``.
    """
    if serial_number is None:
        serial_number = decode_serial_number(registers[0:4])

    # Charging state (manual section 5.6): a 32-bit value spanning 400Ch-400Dh
    # whose byte 1 holds the state. Byte 1 is the high byte of the second
    # register, 400Dh (index 13); 400Ch itself is spare and reads 0.
    # Bit 7 = charging below the value commanded via 4100h (reduced current),
    # bits 6..0 = state.
    high_byte = (registers[13] >> 8) & 0xFF

    return {
        "serial_number": serial_number,
        "firmware_version": decode_firmware_version(registers[4:6]),
        "user_settable_max_current": decode_32bit_value(registers[6:8], 0.001),
        "error_code": int(decode_32bit_value(registers[8:10])),
        "socket_lock_state": int(decode_32bit_value(registers[10:12])),
        "charging_state": high_byte & 0x7F,
        "charging_at_reduced_current": bool(high_byte & 0x80),
        "charging_current_limit": decode_32bit_value(registers[14:16], 0.001),
        "charging_current_l1": decode_32bit_value(registers[16:18], 0.001),
        "charging_current_l2": decode_32bit_value(registers[18:20], 0.001),
        "charging_current_l3": decode_32bit_value(registers[20:22], 0.001),
        "voltage_l1": decode_32bit_value(registers[22:24], 0.1),
        "voltage_l2": decode_32bit_value(registers[24:26], 0.1),
        "voltage_l3": decode_32bit_value(registers[26:28], 0.1),
        "active_power": decode_32bit_value(registers[28:30]),
        "energy_delivered": decode_32bit_value(registers[30:32]),
        "communication_timeout": registers[32],
        "charging_current_limit_modbus": decode_32bit_value(registers[34:36], 0.001),
        "fallback_limit": registers[36],
    }


class AbbTerraAcDevice:
    """One ABB Terra AC charger reachable through a Modbus unit."""

    def __init__(self, unit: ModbusUnit) -> None:
        """Wrap a unit. The caller owns the connection behind it."""
        self._unit = unit
        self._serial_number: str | None = None
        self._last_registers: list[int] | None = None

    @property
    def last_registers(self) -> list[int] | None:
        """Raw 37-register status block from the latest successful read."""
        return self._last_registers

    @property
    def connected(self) -> bool:
        """Whether the underlying link is currently open."""
        return self._unit.connected

    @property
    def serial_number(self) -> str | None:
        """Serial number, once a status read has decoded it."""
        return self._serial_number

    async def async_probe(self) -> None:
        """Read one register to check the charger answers.

        Raises the ``modbus_connection`` errors on failure.
        """
        await self._unit.read_holding_registers(REG_STATUS_BLOCK, 1)

    async def async_read_status(self) -> AbbTerraAcData:
        """Read and decode the whole status block in a single request.

        The serial number is read only once and cached.
        """
        registers = await self._unit.read_holding_registers(
            REG_STATUS_BLOCK, STATUS_BLOCK_LENGTH
        )
        self._last_registers = list(registers)
        data = decode_status_block(registers, self._serial_number)
        self._serial_number = data["serial_number"]
        return data

    async def async_start_session(self) -> None:
        """Start a charging session (register 4105h, value 0)."""
        await self._unit.write_register(REG_START_STOP_SESSION, VAL_START_SESSION)

    async def async_stop_session(self) -> None:
        """Stop the charging session (register 4105h, value 1)."""
        await self._unit.write_register(REG_START_STOP_SESSION, VAL_STOP_SESSION)

    async def async_set_cable_lock(self, locked: bool) -> None:
        """Lock or unlock the cable (register 4103h)."""
        await self._unit.write_register(REG_CABLE_LOCK, 1 if locked else 0)

    async def async_set_current_limit(self, amps: float) -> None:
        """Set the charging current limit (32-bit write to 4100h, in mA).

        ``round`` avoids floating point truncation (``1.005 * 1000`` is
        ``1004.9999...``). A negative or oversized value is rejected rather than
        wrapped into the register.
        """
        value = round(amps * 1000)
        if not 0 <= value <= MAX_CURRENT_LIMIT_MA:
            msg = f"Current limit {amps} A is outside the 32-bit register range"
            raise ValueError(msg)
        await self._unit.write_registers(
            REG_CURRENT_LIMIT, [value >> 16, value & 0xFFFF]
        )

    async def async_set_fallback_limit(self, amps: int) -> None:
        """Set the fallback current limit (register 4109h)."""
        await self._unit.write_register(REG_FALLBACK_LIMIT, int(amps))

    async def async_set_communication_timeout(self, seconds: int) -> None:
        """Set the Modbus communication timeout (register 4106h)."""
        await self._unit.write_register(REG_COMMUNICATION_TIMEOUT, int(seconds))
