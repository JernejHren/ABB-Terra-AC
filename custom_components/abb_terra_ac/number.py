"""Number entity definitions for ABB Terra AC."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pymodbus.client import AsyncModbusTcpClient

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number entities from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]

    numbers = [
        AbbTerraAcChargingCurrentLimit(coordinator, entry, client),
        AbbTerraAcFallbackLimit(coordinator, entry, client),
    ]
    async_add_entities(numbers, True)


class AbbTerraAcBaseNumber(CoordinatorEntity, NumberEntity):
    """Base class for number entities."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator)
        self.client = client
        self._entry_id = entry.entry_id
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}


class AbbTerraAcChargingCurrentLimit(AbbTerraAcBaseNumber):
    """Number entity for setting the charging current limit."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_name = "ABB Charging Current Limit"
        self._attr_unique_id = f"{self._entry_id}_current_limit"
        self._attr_icon = "mdi:current-ac"
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
        await self.client.write_registers(address=16640, values=[high_word, low_word])
        await self.coordinator.async_request_refresh()


class AbbTerraAcFallbackLimit(AbbTerraAcBaseNumber):
    """Number entity for setting the fallback current limit."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_name = "ABB Fallback Limit"
        self._attr_unique_id = f"{self._entry_id}_fallback_limit"
        self._attr_icon = "mdi:current-ac"
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
        await self.client.write_register(address=16649, value=int(value))
        await self.coordinator.async_request_refresh()
