"""Shared entity base with dynamic device info from coordinator data."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from . import AbbTerraAcDataUpdateCoordinator


def abb_terra_ac_device_info_static(entry_id: str) -> dict[str, Any]:
    """Static device registry fields (identity); sw/serial added at runtime."""
    return {
        "identifiers": {(DOMAIN, entry_id)},
        "name": "ABB Terra AC Charger",
        "manufacturer": "ABB",
        "model": "Terra AC",
    }


class AbbTerraAcEntity(CoordinatorEntity["AbbTerraAcDataUpdateCoordinator"]):
    """Coordinator entity with device_info updated when firmware or identity changes."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AbbTerraAcDataUpdateCoordinator,
        entry_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._config_entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Device info including current firmware and serial from the latest poll."""
        info = DeviceInfo(**abb_terra_ac_device_info_static(self._config_entry_id))  # type: ignore[typeddict-item]
        data = self.coordinator.data
        if data:
            info["sw_version"] = data.get("firmware_version")
            info["serial_number"] = data.get("serial_number")
        return info  # type: ignore[no-any-return]
