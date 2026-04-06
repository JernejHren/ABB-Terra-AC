"""Helpers for working with the Modbus client."""
from __future__ import annotations

import inspect
import logging

from pymodbus.client import AsyncModbusTcpClient

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
