"""Switch entity definitions for ABB Terra AC."""
import asyncio
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
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
    """Set up switches from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    client = hass.data[DOMAIN][entry.entry_id]["client"]

    switches = [
        AbbTerraAcChargingSwitch(coordinator, entry, client),
        AbbTerraAcLockSwitch(coordinator, entry, client),
    ]
    async_add_entities(switches, True)


class AbbTerraAcBaseSwitch(CoordinatorEntity, SwitchEntity):
    """Base class for switches."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator)
        self.client = client
        self._entry_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ABB Terra AC Charger",
            "manufacturer": "ABB",
            "model": "Terra AC",
        }


class AbbTerraAcChargingSwitch(AbbTerraAcBaseSwitch):
    """Switch for starting/stopping a charging session."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_name = "ABB Start/Stop Charging"
        self._attr_unique_id = f"{self._entry_id}_charging"
        self._attr_icon = "mdi:flash"
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool:
        """Return True if a charging session is active.
        
        Register 4105h is Write Only, so state is inferred from Charging State.
        States 2-5 indicate an active session:
        2 = B2 (Authorized, EVSE Ready)
        3 = C1 (EV Ready)
        4 = C2 (Charging)
        5 = D/F (Paused) - included so switch stays on during pause (e.g. solar charging)
        """
        charging_state = self.coordinator.data.get("charging_state")
        return charging_state in [2, 3, 4, 5]

    async def async_turn_on(self, **kwargs) -> None:
        """Start charging session (register 4105h, value 0)."""
        await self.client.write_register(address=16645, value=0)
        await asyncio.sleep(7)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Stop charging session (register 4105h, value 1)."""
        await self.client.write_register(address=16645, value=1)
        await asyncio.sleep(7)
        await self.coordinator.async_request_refresh()


class AbbTerraAcLockSwitch(AbbTerraAcBaseSwitch):
    """Switch for locking/unlocking the cable."""

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_name = "ABB Lock Cable"
        self._attr_unique_id = f"{self._entry_id}_lock"
        self._attr_icon = "mdi:lock"
        self._attr_device_class = SwitchDeviceClass.SWITCH

    @property
    def is_on(self) -> bool:
        """Return True if cable is locked.
        
        Lock states from register 400Ah:
        17  (0x0011) = Cable connected, locked
        273 (0x0111) = Cable & EV connected, locked
        """
        lock_state = self.coordinator.data.get("socket_lock_state")
        return lock_state in [17, 273]

    async def async_turn_on(self, **kwargs) -> None:
        """Lock cable (register 4103h, value 1)."""
        await self.client.write_register(address=16643, value=1)
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Unlock cable (register 4103h, value 0)."""
        await self.client.write_register(address=16643, value=0)
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()
