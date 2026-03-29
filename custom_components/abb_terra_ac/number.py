"""Number entity definitions for ABB Terra AC."""
from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pymodbus.client import AsyncModbusTcpClient

from . import AbbTerraAcDataUpdateCoordinator, AbbTerraAcRuntimeData
from .const import DOMAIN
from .errors import build_service_error

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number entities from a config entry."""
    runtime_data: AbbTerraAcRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    numbers = [
        AbbTerraAcChargingCurrentLimit(coordinator, entry, client),
        AbbTerraAcFallbackLimit(coordinator, entry, client),
    ]
    async_add_entities(numbers, True)


class AbbTerraAcBaseNumber(
    CoordinatorEntity[AbbTerraAcDataUpdateCoordinator], NumberEntity
):
    """Base class for number entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator)
        self.client = client
        self._entry_id = entry.entry_id
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    async def _async_write_register(self, address: int, value: int) -> None:
        """Write a single Modbus register with translated HA exceptions."""
        try:
            result = await self.client.write_register(address=address, value=value)
        except Exception as err:
            raise build_service_error("charger_unavailable") from err

        if result.isError():
            raise build_service_error("write_failed")

    async def _async_write_registers(self, address: int, values: list[int]) -> None:
        """Write multiple Modbus registers with translated HA exceptions."""
        try:
            result = await self.client.write_registers(address=address, values=values)
        except Exception as err:
            raise build_service_error("charger_unavailable") from err

        if result.isError():
            raise build_service_error("write_failed")


class AbbTerraAcChargingCurrentLimit(AbbTerraAcBaseNumber):
    """Number entity for setting the charging current limit."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_translation_key = "current_limit"
        self._attr_unique_id = f"{self._entry_id}_current_limit"
        self._attr_native_unit_of_measurement = "A"
        self._attr_native_min_value = 0  # 0 triggers pause state (< 6A per IEC 61851-1)
        self._attr_native_max_value = 32
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER

    @property
    def native_max_value(self) -> float:
        """Dynamically set maximum based on user_settable_max_current."""
        max_current = self.coordinator.data.get("user_settable_max_current") if self.coordinator.data else None
        return int(max_current) if max_current else 32

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.get("charging_current_limit_modbus")
        return int(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set new charging current limit."""
        value_to_send = int(value * 1000)
        high_word = value_to_send >> 16
        low_word = value_to_send & 0xFFFF
        await self._async_write_registers(address=16640, values=[high_word, low_word])
        await self.coordinator.async_request_refresh()


class AbbTerraAcFallbackLimit(AbbTerraAcBaseNumber):
    """Number entity for setting the fallback current limit."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_translation_key = "fallback_limit"
        self._attr_unique_id = f"{self._entry_id}_fallback_limit"
        self._attr_native_unit_of_measurement = "A"
        self._attr_native_min_value = 0  # 0 triggers pause state on communication loss
        self._attr_native_max_value = 32
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER

    @property
    def native_max_value(self) -> float:
        """Dynamically set maximum based on user_settable_max_current."""
        max_current = self.coordinator.data.get("user_settable_max_current") if self.coordinator.data else None
        return int(max_current) if max_current else 32

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("fallback_limit")

    async def async_set_native_value(self, value: float) -> None:
        """Set new fallback limit."""
        await self._async_write_register(address=16649, value=int(value))
        await self.coordinator.async_request_refresh()
