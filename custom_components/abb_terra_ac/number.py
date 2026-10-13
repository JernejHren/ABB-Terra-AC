"""Number entity definitions for ABB Terra AC."""
from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AbbTerraAcDataUpdateCoordinator, AbbTerraAcRuntimeData
from .api import AbbTerraAcDevice
from .entity import AbbTerraAcEntity
from .errors import async_run_device_action

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number entities from a config entry."""
    runtime_data: AbbTerraAcRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator
    device = runtime_data.device

    numbers = [
        AbbTerraAcChargingCurrentLimit(coordinator, entry, device),
        AbbTerraAcFallbackLimit(coordinator, entry, device),
        AbbTerraAcCommunicationTimeout(coordinator, entry, device),
    ]
    async_add_entities(numbers, True)


class AbbTerraAcBaseNumber(AbbTerraAcEntity, NumberEntity):
    """Base class for number entities."""

    _attr_entity_category: EntityCategory | None = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        device: AbbTerraAcDevice
    ) -> None:
        AbbTerraAcEntity.__init__(self, coordinator, entry.entry_id)
        self.device = device


class AbbTerraAcChargingCurrentLimit(AbbTerraAcBaseNumber):
    """Number entity for setting the charging current limit."""

    _attr_entity_category = None

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        device: AbbTerraAcDevice
    ) -> None:
        super().__init__(coordinator, entry, device)
        self._attr_translation_key = "current_limit"
        self._attr_unique_id = f"{self._config_entry_id}_current_limit"
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
        await async_run_device_action(self.device.async_set_current_limit(value))
        await self.coordinator.async_request_refresh()


class AbbTerraAcFallbackLimit(AbbTerraAcBaseNumber):
    """Number entity for setting the fallback current limit."""

    _attr_entity_category = None

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        device: AbbTerraAcDevice
    ) -> None:
        super().__init__(coordinator, entry, device)
        self._attr_translation_key = "fallback_limit"
        self._attr_unique_id = f"{self._config_entry_id}_fallback_limit"
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
        await async_run_device_action(self.device.async_set_fallback_limit(int(value)))
        await self.coordinator.async_request_refresh()


class AbbTerraAcCommunicationTimeout(AbbTerraAcBaseNumber):
    """Number entity for setting the Modbus communication timeout."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        device: AbbTerraAcDevice
    ) -> None:
        super().__init__(coordinator, entry, device)
        self._attr_translation_key = "communication_timeout"
        self._attr_unique_id = f"{self._config_entry_id}_communication_timeout"
        self._attr_native_unit_of_measurement = "s"
        self._attr_native_min_value = 10
        self._attr_native_max_value = 65535
        self._attr_native_step = 1
        self._attr_mode = NumberMode.BOX

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("communication_timeout")

    async def async_set_native_value(self, value: float) -> None:
        """Set new communication timeout."""
        await async_run_device_action(
            self.device.async_set_communication_timeout(int(value))
        )
        await self.coordinator.async_request_refresh()
