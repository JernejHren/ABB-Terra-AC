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
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": "ABB Terra AC Charger",
            "manufacturer": "ABB",
            "model": "Terra AC",
        }

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
        """
        Vrne True, če je polnilna seja aktivna.
        Register 4105h je 'Write Only', zato stanje sklepamo iz Charging State.
        Stanja (IEC 61851-1 in ABB implementacija):
        2 = B2 (Authorized, EVSE Ready)
        3 = C1 (EV Ready)
        4 = C2 (Charging)
        5 = D/F (Paused/Fault) - Vključeno, ker <6A sproži pavzo, a seja ostane aktivna.
        """
        charging_state = self.coordinator.data.get("charging_state")
        # Dodano stanje 5, da stikalo ostane vklopljeno tudi med pavzo (npr. solarno polnjenje)
        return charging_state in [2, 3, 4, 5]

    async def async_turn_on(self, **kwargs):
        """Začne sejo polnjenja (Start Session - value 0)."""
        # Register 4105h (16645 decimal)
        await self.client.write_register(address=16645, value=0)
        # Vrnjeno na 7 sekund za zanesljivo osvežitev
        await asyncio.sleep(7) 
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Ustavi sejo polnjenja (Stop Session - value 1)."""
        # Register 4105h (16645 decimal)
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
        """
        Vrne True, če je kabel zaklenjen.
        Preverjamo obe stanji zaklepa iz registra 400Ah:
        17  (0x0011) = Cable connected, locked
        273 (0x0111) = Cable & EV connected, locked
        """
        lock_state = self.coordinator.data.get("socket_lock_state")
        return lock_state in [17, 273]

    async def async_turn_on(self, **kwargs):
        """Zaklene kabel (Lock - value 1)."""
        # Register 4103h (16643 decimal)
        await self.client.write_register(address=16643, value=1)
        # Vrnjeno na 3 sekunde, kot v vaši originalni datoteki
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        """Odklene kabel (Unlock - value 0)."""
        # Register 4103h (16643 decimal)
        await self.client.write_register(address=16643, value=0)
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()
