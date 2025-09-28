"""Definicija stikal za ABB Terra AC."""
import asyncio
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Nastavi stikala iz konfiguracijskega vnosa."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]
    
    switches = [
        AbbTerraAcChargingSwitch(coordinator, entry, client),
        AbbTerraAcLockSwitch(coordinator, entry, client),
    ]
    async_add_entities(switches, True)

class AbbTerraAcBaseSwitch(CoordinatorEntity, SwitchEntity):
    """Osnovni razred za stikala."""
    def __init__(self, coordinator, entry, client):
        super().__init__(coordinator)
        self.client = client
        serial = coordinator.data.get('serial_number') if coordinator.data else entry.entry_id
        self._entry_id = entry.entry_id
        self._attr_device_info = { "identifiers": {(DOMAIN, serial)} }

class AbbTerraAcChargingSwitch(AbbTerraAcBaseSwitch):
    """Stikalo za začetek/ustavitev polnjenja."""
    def __init__(self, coordinator, entry, client):
        super().__init__(coordinator, entry, client)
        self._attr_name = "ABB Start/Stop Charging"
        self._attr_unique_id = f"{self._entry_id}_charging"
        self._attr_icon = "mdi:flash"
        self._attr_device_class = SwitchDeviceClass.SWITCH
        
    @property
    def is_on(self):
        """Vrne True, če je polnilna seja aktivna (stanje B2, C1 ali C2)."""
        charging_state = self.coordinator.data.get("charging_state")
        # Seznam stanj, ki predstavljajo aktivno polnilno sejo
        active_session_states = [2, 3, 4]
        return charging_state in active_session_states

    async def async_turn_on(self, **kwargs):
        """Začne sejo polnjenja in počaka pred osvežitvijo."""
        await self.client.write_register(address=16645, value=0)
        await asyncio.sleep(7)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Ustavi sejo polnjenja in počaka pred osvežitvijo."""
        await self.client.write_register(address=16645, value=1)
        await asyncio.sleep(7)
        await self.coordinator.async_request_refresh()

class AbbTerraAcLockSwitch(AbbTerraAcBaseSwitch):
    """Stikalo za zaklepanje/odklepanje kabla."""
    def __init__(self, coordinator, entry, client):
        super().__init__(coordinator, entry, client)
        self._attr_name = "ABB Lock Cable"
        self._attr_unique_id = f"{self._entry_id}_lock"
        self._attr_icon = "mdi:lock"
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self):
        """Vrne True, če je kabel zaklenjen."""
        lock_state = self.coordinator.data.get("socket_lock_state")
        return lock_state == 273

    async def async_turn_on(self, **kwargs):
        """Zaklene kabel in počaka pred osvežitvijo."""
        await self.client.write_register(address=16643, value=1)
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Odklene kabel in počaka pred osvežitvijo."""
        await self.client.write_register(address=16643, value=0)
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()
