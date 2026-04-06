"""Switch entity definitions for ABB Terra AC (cable lock only)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymodbus.client import AsyncModbusTcpClient

from . import AbbTerraAcDataUpdateCoordinator, AbbTerraAcRuntimeData
from .entity import AbbTerraAcEntity
from .modbus_write import async_write_register

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
        AbbTerraAcLockSwitch(coordinator, entry, client),
    ]
    async_add_entities(switches, True)


class AbbTerraAcBaseSwitch(AbbTerraAcEntity, SwitchEntity):
    """Base class for switches."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient
    ) -> None:
        AbbTerraAcEntity.__init__(self, coordinator, entry.entry_id)
        self.client = client


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
        self._attr_unique_id = f"{self._config_entry_id}_lock"
        # HA ``SwitchDeviceClass`` has no ``lock``; use generic switch for cable lock.
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
        await async_write_register(self.client, 16643, 1)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Unlock cable (register 4103h, value 0)."""
        await async_write_register(self.client, 16643, 0)
        await self.coordinator.async_request_refresh()
