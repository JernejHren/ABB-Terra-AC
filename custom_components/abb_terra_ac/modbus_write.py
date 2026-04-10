"""Shared Modbus write helpers with translated Home Assistant errors."""

from __future__ import annotations

import asyncio

from pymodbus.client import AsyncModbusTcpClient

from .errors import build_service_error
from .modbus import async_modbus_call


async def async_write_register(
    client: AsyncModbusTcpClient,
    address: int,
    value: int,
    *,
    lock: asyncio.Lock | None = None,
) -> None:
    """Write a single holding register; raise translated errors on failure."""
    try:
        result = await async_modbus_call(
            client,
            "write_register",
            lock=lock,
            address=address,
            value=value,
        )
    except Exception as err:
        raise build_service_error("charger_unavailable") from err

    if result.isError():
        raise build_service_error("write_failed")


async def async_write_registers(
    client: AsyncModbusTcpClient,
    address: int,
    values: list[int],
    *,
    lock: asyncio.Lock | None = None,
) -> None:
    """Write multiple holding registers; raise translated errors on failure."""
    try:
        result = await async_modbus_call(
            client,
            "write_registers",
            lock=lock,
            address=address,
            values=values,
        )
    except Exception as err:
        raise build_service_error("charger_unavailable") from err

    if result.isError():
        raise build_service_error("write_failed")
