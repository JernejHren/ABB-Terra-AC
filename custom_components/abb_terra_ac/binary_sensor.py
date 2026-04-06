"""Binary sensor entities for ABB Terra AC."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AbbTerraAcDataUpdateCoordinator, AbbTerraAcRuntimeData
from .entity import AbbTerraAcEntity

PARALLEL_UPDATES = 0

# IEC 61851-1 state C2 — actively delivering charge
_STATE_C2_CHARGING = 4


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities from a config entry."""
    runtime_data: AbbTerraAcRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator

    async_add_entities(
        [AbbTerraAcIsChargingBinarySensor(coordinator, entry)],
        True,
    )


class AbbTerraAcIsChargingBinarySensor(AbbTerraAcEntity, BinarySensorEntity):
    """True when raw charging state is C2 (actively charging)."""

    _attr_has_entity_name = True
    _attr_translation_key = "is_charging"

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        super().__init__(coordinator, entry.entry_id)
        self._attr_unique_id = f"{self._config_entry_id}_is_charging"

    @property
    def is_on(self) -> bool | None:
        """True when charging state register indicates C2."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data["charging_state"] == _STATE_C2_CHARGING
