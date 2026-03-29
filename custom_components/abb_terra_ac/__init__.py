"""ABB Terra AC charger integration."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException

from .const import (
    CONF_HOST,
    CONF_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    AbbTerraAcData,
)
from .modbus import async_close_client

_LOGGER = logging.getLogger(__name__)

_ISSUE_ID_INVALID_FALLBACK_LIMIT = "invalid_fallback_limit"
_ISSUE_ID_INVALID_CURRENT_LIMIT = "invalid_current_limit"


@dataclass
class AbbTerraAcRuntimeData:
    """Runtime objects stored on the config entry."""

    coordinator: AbbTerraAcDataUpdateCoordinator
    client: AsyncModbusTcpClient


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ABB Terra AC from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    client = AsyncModbusTcpClient(host=host, port=port)
    coordinator = AbbTerraAcDataUpdateCoordinator(hass, client, entry.entry_id)

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = AbbTerraAcRuntimeData(coordinator=coordinator, client=client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        client = entry.runtime_data.client
        if client.connected:
            await async_close_client(client)
        entry.runtime_data = None

    return unload_ok


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow removal of orphaned devices from the UI."""
    return True


class AbbTerraAcDataUpdateCoordinator(DataUpdateCoordinator[AbbTerraAcData]):
    """Coordinator for fetching data from the charger."""

    def __init__(
        self, hass: HomeAssistant, client: AsyncModbusTcpClient, entry_id: str
    ) -> None:
        """Initialize the DataUpdateCoordinator."""
        self.client = client
        self.entry_id = entry_id
        self.serial_number: str | None = None
        self._is_available = True

        # Firmware bug auto-fix: fallback limit
        self._last_valid_fallback_limit: int | None = None
        self._fallback_fix_attempted = False

        # Firmware bug auto-fix: charging current limit
        self._last_valid_current_limit: int | None = None
        self._current_limit_fix_attempted = False

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    def _async_create_limit_issue(
        self,
        issue_id: str,
        limit_name: str,
        current_value: int,
        max_value: int,
    ) -> None:
        """Create a repair issue for an invalid charger limit that could not be restored."""
        ir.async_create_issue(
            self.hass,
            DOMAIN,
            f"{issue_id}_{self.entry_id}",
            is_fixable=False,
            is_persistent=True,
            severity=ir.IssueSeverity.WARNING,
            translation_key="firmware_limit_restore_failed",
            translation_placeholders={
                "limit_name": limit_name,
                "current_value": str(current_value),
                "max_value": str(max_value),
            },
        )

    def _async_delete_limit_issue(self, issue_id: str) -> None:
        """Delete a previously created invalid charger limit issue."""
        ir.async_delete_issue(self.hass, DOMAIN, f"{issue_id}_{self.entry_id}")

    async def _async_update_data(self) -> AbbTerraAcData:
        """Fetch the latest data from the charger."""
        try:
            if not self.client.connected:
                await self.client.connect()

            result = await self.client.read_holding_registers(address=16384, count=37)

            if result.isError():
                self._async_log_unavailable(f"Error reading registers: {result}")
                raise UpdateFailed(f"Error reading registers: {result}")

            data: AbbTerraAcData = {
                "serial_number": "",
                "firmware_version": "",
                "user_settable_max_current": 0.0,
                "error_code": 0,
                "socket_lock_state": 0,
                "charging_state": 0,
                "charging_current_limit": 0.0,
                "charging_current_l1": 0.0,
                "charging_current_l2": 0.0,
                "charging_current_l3": 0.0,
                "voltage_l1": 0.0,
                "voltage_l2": 0.0,
                "voltage_l3": 0.0,
                "active_power": 0.0,
                "energy_delivered": 0.0,
                "communication_timeout": 0,
                "charging_current_limit_modbus": 0.0,
                "fallback_limit": 0,
            }
            registers = result.registers

            # Serial number - read only once
            if self.serial_number is None:
                self.serial_number = self._decode_serial_number(registers[0:4])
            data["serial_number"] = self.serial_number

            data["firmware_version"] = self._decode_firmware_version(registers[4:6])
            data["user_settable_max_current"] = self._decode_32bit_value(registers[6:8], 0.001)
            data["error_code"] = registers[8]
            data["socket_lock_state"] = int(self._decode_32bit_value(registers[10:12]))

            # Charging state: per testing, actual state is in register 400Dh (index 13),
            # encoded in the high byte. Documentation states 400Ch but it always returns 0.
            charging_state_register = registers[13]
            high_byte = (charging_state_register >> 8) & 0xFF
            state_code = high_byte & 0x0F
            data["charging_state"] = state_code

            data["charging_current_limit"] = self._decode_32bit_value(registers[14:16], 0.001)
            data["charging_current_l1"] = self._decode_32bit_value(registers[16:18], 0.001)
            data["charging_current_l2"] = self._decode_32bit_value(registers[18:20], 0.001)
            data["charging_current_l3"] = self._decode_32bit_value(registers[20:22], 0.001)
            data["voltage_l1"] = self._decode_32bit_value(registers[22:24], 0.1)
            data["voltage_l2"] = self._decode_32bit_value(registers[24:26], 0.1)
            data["voltage_l3"] = self._decode_32bit_value(registers[26:28], 0.1)
            data["active_power"] = self._decode_32bit_value(registers[28:30])
            data["energy_delivered"] = self._decode_32bit_value(registers[30:32])
            data["communication_timeout"] = registers[32]
            data["charging_current_limit_modbus"] = self._decode_32bit_value(registers[34:36], 0.001)
            data["fallback_limit"] = registers[36]

            # --- Firmware bug fix: Fallback Limit ---
            # Known firmware bug: fallback limit resets to 256 after unexpected reboot.
            # Restore to last known valid value, or user_settable_max_current as fallback.
            fallback_limit = data["fallback_limit"]
            user_max = int(data["user_settable_max_current"])

            if fallback_limit <= user_max or fallback_limit == 0:
                self._last_valid_fallback_limit = fallback_limit
                self._fallback_fix_attempted = False
                self._async_delete_limit_issue(_ISSUE_ID_INVALID_FALLBACK_LIMIT)
            elif fallback_limit > user_max:
                _LOGGER.warning(
                    "Invalid fallback limit detected: %sA (max allowed: %sA). Attempting to restore.",
                    fallback_limit, user_max
                )
                if not self._fallback_fix_attempted:
                    self._fallback_fix_attempted = True
                    restore_value = self._last_valid_fallback_limit if self._last_valid_fallback_limit is not None else user_max
                    try:
                        write_result = await self.client.write_register(address=16649, value=int(restore_value))
                        if write_result.isError():
                            _LOGGER.error("Failed to write fallback limit: %s", write_result)
                            self._async_create_limit_issue(
                                _ISSUE_ID_INVALID_FALLBACK_LIMIT,
                                "fallback limit",
                                fallback_limit,
                                user_max,
                            )
                        else:
                            _LOGGER.info("Fallback limit restored to %sA.", restore_value)
                            data["fallback_limit"] = restore_value
                            self._async_delete_limit_issue(_ISSUE_ID_INVALID_FALLBACK_LIMIT)
                    except Exception as err:
                        _LOGGER.error("Exception while writing fallback limit: %s", err)
                        self._async_create_limit_issue(
                            _ISSUE_ID_INVALID_FALLBACK_LIMIT,
                            "fallback limit",
                            fallback_limit,
                            user_max,
                        )

            # --- Firmware bug fix: Charging Current Limit ---
            # Known firmware bug: charging current limit resets to 32A after unexpected reboot.
            # Restore to last known valid value, or user_settable_max_current as fallback.
            current_limit = int(data["charging_current_limit_modbus"])

            if user_max > 0 and current_limit <= user_max:
                self._last_valid_current_limit = current_limit
                self._current_limit_fix_attempted = False
                self._async_delete_limit_issue(_ISSUE_ID_INVALID_CURRENT_LIMIT)
            elif user_max > 0 and current_limit > user_max:
                _LOGGER.warning(
                    "Invalid charging current limit detected: %sA (max allowed: %sA). Attempting to restore.",
                    current_limit, user_max
                )
                if not self._current_limit_fix_attempted:
                    self._current_limit_fix_attempted = True
                    restore_value = self._last_valid_current_limit if self._last_valid_current_limit is not None else user_max
                    value_to_send = int(restore_value * 1000)
                    high_word = value_to_send >> 16
                    low_word = value_to_send & 0xFFFF
                    try:
                        write_result = await self.client.write_registers(address=16640, values=[high_word, low_word])
                        if write_result.isError():
                            _LOGGER.error("Failed to write charging current limit: %s", write_result)
                            self._async_create_limit_issue(
                                _ISSUE_ID_INVALID_CURRENT_LIMIT,
                                "charging current limit",
                                current_limit,
                                user_max,
                            )
                        else:
                            _LOGGER.info("Charging current limit restored to %sA.", restore_value)
                            data["charging_current_limit_modbus"] = restore_value
                            self._async_delete_limit_issue(_ISSUE_ID_INVALID_CURRENT_LIMIT)
                    except Exception as err:
                        _LOGGER.error("Exception while writing charging current limit: %s", err)
                        self._async_create_limit_issue(
                            _ISSUE_ID_INVALID_CURRENT_LIMIT,
                            "charging current limit",
                            current_limit,
                            user_max,
                        )

            if not self._is_available:
                _LOGGER.info("ABB Terra AC charger is available again")
            self._is_available = True
            return data

        except (ConnectionException, asyncio.TimeoutError) as err:
            self._async_log_unavailable(f"Connection error: {err}")
            raise UpdateFailed(f"Connection error: {err}")
        except Exception as err:
            self._async_log_unavailable(f"Unexpected error: {err}")
            _LOGGER.error("Unexpected error: %s", err, exc_info=True)
            raise UpdateFailed(err)

    def _async_log_unavailable(self, reason: str) -> None:
        """Log when the charger becomes unavailable without spamming logs."""
        if self._is_available:
            _LOGGER.warning("ABB Terra AC charger became unavailable: %s", reason)
        self._is_available = False

    def _decode_32bit_value(self, regs: list[int], resolution: float = 1) -> float:
        """Decode a 32-bit value from two registers."""
        value = (regs[0] << 16) | regs[1]
        return value * resolution

    def _decode_serial_number(self, regs: list[int]) -> str:
        """Decode serial number from registers."""
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
                ((byte1 >> 4) & 0xF) * 1000 +
                (byte1 & 0xF) * 100 +
                ((byte0 >> 4) & 0xF) * 10 +
                (byte0 & 0xF)
            )

            return f"TACW{rated_power}-{plant_id}-{prod_week:02d}{prod_year:02d}-{connector}{serial_num:04d}"
        except Exception as err:
            _LOGGER.warning("Failed to decode serial number: %s", err)
            return f"Decode error: {regs}"

    def _decode_firmware_version(self, regs: list[int]) -> str:
        """Decode firmware version from registers."""
        try:
            major = (regs[0] >> 8) & 0xFF
            minor = regs[0] & 0xFF
            patch = (regs[1] >> 8) & 0xFF
            patch_bcd = ((patch >> 4) & 0xF) * 10 + (patch & 0xF)
            return f"v{major}.{minor}.{patch_bcd}"
        except Exception as err:
            _LOGGER.warning("Failed to decode firmware version: %s", err)
            return f"Decode error: {regs}"
