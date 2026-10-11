"""Button entities for ABB Terra AC (start/stop charging session)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AbbTerraAcDataUpdateCoordinator, AbbTerraAcRuntimeData
from .api import AbbTerraAcDevice
from .entity import AbbTerraAcEntity
from .errors import async_run_device_action
from .session_state import LastCommand

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up button entities from a config entry."""
    runtime_data: AbbTerraAcRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator
    device = runtime_data.device

    async_add_entities(
        [
            AbbTerraAcStartChargingButton(coordinator, entry, device),
            AbbTerraAcStopChargingButton(coordinator, entry, device),
        ],
        True,
    )


class AbbTerraAcBaseButton(AbbTerraAcEntity, ButtonEntity):
    """Base class for charger buttons."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        device: AbbTerraAcDevice,
    ) -> None:
        AbbTerraAcEntity.__init__(self, coordinator, entry.entry_id)
        self.device = device


class AbbTerraAcStartChargingButton(AbbTerraAcBaseButton):
    """Start a charging session (register 4105h, value 0)."""

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
        device: AbbTerraAcDevice,
    ) -> None:
        super().__init__(coordinator, entry, device)
        self._attr_translation_key = "start_charging"
        self._attr_unique_id = f"{self._config_entry_id}_start_charging"

    async def async_press(self) -> None:
        """Start charging; retry once with a full refresh between attempts."""
        self.coordinator.last_command = LastCommand.START
        for _ in range(2):
            await async_run_device_action(self.device.async_start_session())
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
        device: AbbTerraAcDevice,
    ) -> None:
        super().__init__(coordinator, entry, device)
        self._attr_translation_key = "stop_charging"
        self._attr_unique_id = f"{self._config_entry_id}_stop_charging"

    async def async_press(self) -> None:
        """Stop charging session."""
        self.coordinator.last_command = LastCommand.STOP
        await async_run_device_action(self.device.async_stop_session())
        await self.coordinator.async_request_refresh()
