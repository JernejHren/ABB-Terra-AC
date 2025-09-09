"""Definicija številčnih entitet za ABB Terra AC."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Nastavi številčne entitete iz konfiguracijskega vnosa."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    
    numbers = [
        AbbTerraAcChargingCurrentLimit(coordinator, entry, client),
        AbbTerraAcFallbackLimit(coordinator, entry, client),
    ]
    async_add_entities(numbers, True)

class AbbTerraAcBaseNumber(CoordinatorEntity, NumberEntity):
    """Osnovni razred za števila."""
    def __init__(self, coordinator, entry, client):
        super().__init__(coordinator)
        self.client = client
        serial = coordinator.data.get('serial_number') if coordinator.data else entry.entry_id
        self._entry_id = entry.entry_id
        self._attr_device_info = { "identifiers": {(DOMAIN, serial)} }

class AbbTerraAcChargingCurrentLimit(AbbTerraAcBaseNumber):
    """Entiteta za nastavitev omejitve polnilnega toka."""
    def __init__(self, coordinator, entry, client):
        super().__init__(coordinator, entry, client)
        self._attr_name = "ABB Charging Current Limit"
        self._attr_unique_id = f"{self._entry_id}_current_limit"
        self._attr_icon = "mdi:current-ac"
        self._attr_native_unit_of_measurement = "A"
        self._attr_native_min_value = 0  # Spremenjeno na 0
        self._attr_native_max_value = 32
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data.get("charging_current_limit_modbus")
        return int(value) if value is not None else None

    async def async_set_native_value(self, value: float) -> None:
        value_to_send = int(value * 1000)
        high_word = value_to_send >> 16
        low_word = value_to_send & 0xFFFF
        await self.client.write_registers(address=16640, values=[high_word, low_word])
        await self.coordinator.async_request_refresh()

class AbbTerraAcFallbackLimit(AbbTerraAcBaseNumber):
    """Entiteta za nastavitev fallback limita."""
    def __init__(self, coordinator, entry, client):
        super().__init__(coordinator, entry, client)
        self._attr_name = "ABB Fallback Limit"
        self._attr_unique_id = f"{self._entry_id}_fallback_limit"
        self._attr_icon = "mdi:current-ac"
        self._attr_native_unit_of_measurement = "A"
        self._attr_native_min_value = 6
        self._attr_native_max_value = 32
        self._attr_native_step = 1
        self._attr_mode = NumberMode.SLIDER
    
    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("fallback_limit")

    async def async_set_native_value(self, value: float) -> None:
        int_value = int(value)
        await self.client.write_register(address=16649, value=int_value)
        await self.coordinator.async_request_refresh()