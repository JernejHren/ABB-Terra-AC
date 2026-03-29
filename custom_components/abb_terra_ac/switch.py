"""Switch entity definitions for ABB Terra AC."""
from __future__ import annotations

import asyncio
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
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
    """Set up switches from a config entry."""
    runtime_data: AbbTerraAcRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    switches = [
        AbbTerraAcChargingSwitch(coordinator, entry, client),
        AbbTerraAcLockSwitch(coordinator, entry, client),
    ]
    async_add_entities(switches, True)


class AbbTerraAcBaseSwitch(
    CoordinatorEntity[AbbTerraAcDataUpdateCoordinator], SwitchEntity
):
    """Base class for switches."""

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
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ABB Terra AC Charger",
            "manufacturer": "ABB",
            "model": "Terra AC",
        }

    async def _async_write_register(self, address: int, value: int) -> None:
        """Write a single Modbus register with translated HA exceptions."""
        try:
            result = await self.client.write_register(address=address, value=value)
        except Exception as err:
            raise build_service_error("charger_unavailable") from err

        if result.isError():
            raise build_service_error("write_failed")


class AbbTerraAcChargingSwitch(AbbTerraAcBaseSwitch):
    """Switch for starting/stopping a charging session."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_translation_key = "charging"
        self._attr_unique_id = f"{self._entry_id}_charging"
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Start charging session (register 4105h, value 0)."""
        await self._async_write_register(address=16645, value=0)
        await asyncio.sleep(7)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop charging session (register 4105h, value 1)."""
        await self._async_write_register(address=16645, value=1)
        await asyncio.sleep(7)
        await self.coordinator.async_request_refresh()


class AbbTerraAcLockSwitch(AbbTerraAcBaseSwitch):
    """Switch for locking/unlocking the cable."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_translation_key = "lock"
        self._attr_unique_id = f"{self._entry_id}_lock"
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

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Lock cable (register 4103h, value 1)."""
        await self._async_write_register(address=16643, value=1)
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlock cable (register 4103h, value 0)."""
        await self._async_write_register(address=16643, value=0)
        await asyncio.sleep(3)
        await self.coordinator.async_request_refresh()
