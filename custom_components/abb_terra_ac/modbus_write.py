"""Shared Modbus write helpers with translated Home Assistant errors."""

from __future__ import annotations

from pymodbus.client import AsyncModbusTcpClient

from .errors import build_service_error


async def async_write_register(
    client: AsyncModbusTcpClient, address: int, value: int
) -> None:
    """Write a single holding register; raise translated errors on failure."""
    try:
        result = await client.write_register(address=address, value=value)
    except Exception as err:
        raise build_service_error("charger_unavailable") from err

    if result.isError():
        raise build_service_error("write_failed")


async def async_write_registers(
    client: AsyncModbusTcpClient, address: int, values: list[int]
) -> None:
    """Write multiple holding registers; raise translated errors on failure."""
    try:
        result = await client.write_registers(address=address, values=values)
    except Exception as err:
        raise build_service_error("charger_unavailable") from err

    if result.isError():
        raise build_service_error("write_failed")
