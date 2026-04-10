"""Helpers for working with the Modbus client."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import inspect
import logging
from typing import Any

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException, ModbusIOException

from .const import MODBUS_CONNECT_TIMEOUT

_LOGGER = logging.getLogger(__name__)


async def async_close_client(client: AsyncModbusTcpClient) -> None:
    """Safely close the Modbus client for both sync and async pymodbus APIs."""
    try:
        close = getattr(client, "close", None)
        if not callable(close):
            return

        close_result = close()
        if inspect.isawaitable(close_result):
            await close_result
    except Exception:
        _LOGGER.debug("Failed to close Modbus client", exc_info=True)


@asynccontextmanager
async def _async_null_lock():
    """Provide a no-op async context manager when no shared lock is supplied."""
    yield


async def async_ensure_client_connected(client: AsyncModbusTcpClient) -> None:
    """Open the TCP connection if needed."""
    if client.connected:
        return

    connected = await asyncio.wait_for(
        client.connect(),
        timeout=MODBUS_CONNECT_TIMEOUT,
    )
    if not connected:
        msg = "connect() returned False"
        raise ConnectionException(msg)


async def async_reset_client(client: AsyncModbusTcpClient) -> None:
    """Close the current socket so the next request gets a clean reconnect."""
    await async_close_client(client)
    if hasattr(client, "connected"):
        client.connected = False


async def async_modbus_call(
    client: AsyncModbusTcpClient,
    method_name: str,
    *,
    lock: asyncio.Lock | None = None,
    retry: bool = False,
    **kwargs: Any,
) -> Any:
    """Run one Modbus call under a shared lock with optional reconnect+retry."""
    async with lock or _async_null_lock():
        await async_ensure_client_connected(client)
        method = getattr(client, method_name)

        try:
            return await method(**kwargs)
        except (ConnectionException, ModbusIOException, asyncio.TimeoutError):
            await async_reset_client(client)
            if not retry:
                raise

        await async_ensure_client_connected(client)
        method = getattr(client, method_name)
        return await method(**kwargs)
