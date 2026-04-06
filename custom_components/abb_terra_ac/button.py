"""Button entities for ABB Terra AC (start/stop charging session)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from pymodbus.client import AsyncModbusTcpClient

from . import AbbTerraAcDataUpdateCoordinator, AbbTerraAcRuntimeData
from .entity import AbbTerraAcEntity
from .modbus_write import async_write_register
from .session_state import LastCommand

PARALLEL_UPDATES = 0

REG_START_STOP_SESSION = 16645
VAL_START_SESSION = 0
VAL_STOP_SESSION = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    runtime_data: AbbTerraAcRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator
    client = runtime_data.client

    async_add_entities(
        [
            AbbTerraAcStartChargingButton(coordinator, entry, client),
            AbbTerraAcStopChargingButton(coordinator, entry, client),
        ],
        True,
    )


class AbbTerraAcBaseButton(AbbTerraAcEntity, ButtonEntity):
    """Base class for charger buttons."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient,
    ) -> None:
        AbbTerraAcEntity.__init__(self, coordinator, entry.entry_id)
        self.client = client


class AbbTerraAcStartChargingButton(AbbTerraAcBaseButton):
    """Start a charging session (register 4105h, value 0)."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient,
    ) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_translation_key = "start_charging"
        self._attr_unique_id = f"{self._config_entry_id}_start_charging"

    async def async_press(self) -> None:
        """Start charging; retry once with a full refresh between attempts."""
        self.coordinator.last_command = LastCommand.START
        for _ in range(2):
            await async_write_register(self.client, REG_START_STOP_SESSION, VAL_START_SESSION)
            await self.coordinator.async_request_refresh()
            data = self.coordinator.data
            if not data or data["charging_state"] not in (0, 1):
                break


class AbbTerraAcStopChargingButton(AbbTerraAcBaseButton):
    """Stop the charging session (register 4105h, value 1)."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        client: AsyncModbusTcpClient,
    ) -> None:
        super().__init__(coordinator, entry, client)
        self._attr_translation_key = "stop_charging"
        self._attr_unique_id = f"{self._config_entry_id}_stop_charging"

    async def async_press(self) -> None:
        """Stop charging session."""
        self.coordinator.last_command = LastCommand.STOP
        await async_write_register(self.client, REG_START_STOP_SESSION, VAL_STOP_SESSION)
        await self.coordinator.async_request_refresh()
