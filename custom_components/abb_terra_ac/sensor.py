"""Sensor definitions for ABB Terra AC."""

from __future__ import annotations

from datetime import datetime, timezone
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfPower,
    UnitOfEnergy,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import AbbTerraAcDataUpdateCoordinator, AbbTerraAcRuntimeData
from .const import CHARGING_STATES, DOMAIN, ERROR_CODES, SOCKET_LOCK_STATES

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensors from a config entry."""
    runtime_data: AbbTerraAcRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator

    sensors = [
        AbbTerraAcChargingStateSensor(coordinator, entry),
        AbbTerraAcSerialNumberSensor(coordinator, entry),
        AbbTerraAcFirmwareSensor(coordinator, entry),
        AbbTerraAcErrorCodeSensor(coordinator, entry),
        AbbTerraAcSocketLockStateSensor(coordinator, entry),
        AbbTerraAcActivePowerSensor(coordinator, entry),
        AbbTerraAcEnergyDeliveredSensor(coordinator, entry),
        AbbTerraAcCurrentL1Sensor(coordinator, entry),
        AbbTerraAcCurrentL2Sensor(coordinator, entry),
        AbbTerraAcCurrentL3Sensor(coordinator, entry),
        AbbTerraAcVoltageL1Sensor(coordinator, entry),
        AbbTerraAcVoltageL2Sensor(coordinator, entry),
        AbbTerraAcVoltageL3Sensor(coordinator, entry),
        AbbTerraAcCurrentLimitSensor(coordinator, entry),
    ]
    async_add_entities(sensors, True)


class AbbTerraAcBaseSensor(
    CoordinatorEntity[AbbTerraAcDataUpdateCoordinator], SensorEntity
):
    """Base class for sensors."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._entry_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "ABB Terra AC Charger",
            "manufacturer": "ABB",
            "model": "Terra AC",
        }
        if coordinator.data:
            self._attr_device_info["sw_version"] = coordinator.data.get("firmware_version")
            self._attr_device_info["serial_number"] = coordinator.data.get("serial_number")


class AbbTerraAcChargingStateSensor(AbbTerraAcBaseSensor):
    """Sensor for charging state."""
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(CHARGING_STATES.values())

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "charging_state"
        self._attr_unique_id = f"{self._entry_id}_charging_state"

    @property
    def native_value(self) -> str:
        state_code = self.coordinator.data.get("charging_state")
        return CHARGING_STATES.get(state_code, f"Unknown ({state_code})")


class AbbTerraAcSerialNumberSensor(AbbTerraAcBaseSensor):
    """Sensor for serial number."""
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "serial_number"
        self._attr_unique_id = f"{self._entry_id}_serial_number"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.get("serial_number")


class AbbTerraAcFirmwareSensor(AbbTerraAcBaseSensor):
    """Sensor for firmware version."""
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "firmware_version"
        self._attr_unique_id = f"{self._entry_id}_firmware_version"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.get("firmware_version")


class AbbTerraAcErrorCodeSensor(AbbTerraAcBaseSensor):
    """Sensor for error code."""
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(ERROR_CODES.values())
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "error_code"
        self._attr_unique_id = f"{self._entry_id}_error_code"

    @property
    def native_value(self) -> str:
        error_code = self.coordinator.data.get("error_code")
        return ERROR_CODES.get(error_code, f"Unknown Error ({error_code})")


class AbbTerraAcSocketLockStateSensor(AbbTerraAcBaseSensor):
    """Sensor for socket lock state."""
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(SOCKET_LOCK_STATES.values())

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "socket_lock_state"
        self._attr_unique_id = f"{self._entry_id}_socket_lock_state"

    @property
    def native_value(self) -> str:
        lock_code = self.coordinator.data.get("socket_lock_state")
        return SOCKET_LOCK_STATES.get(lock_code, f"Unknown ({lock_code})")


class AbbTerraAcActivePowerSensor(AbbTerraAcBaseSensor):
    """Sensor for active power."""
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "active_power"
        self._attr_unique_id = f"{self._entry_id}_active_power"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("active_power")


class AbbTerraAcEnergyDeliveredSensor(AbbTerraAcBaseSensor):
    """Sensor for energy delivered in the current session."""
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "energy_delivered"
        self._attr_unique_id = f"{self._entry_id}_energy_delivered"
        self._last_energy_value: float = 0
        self._last_reset: datetime = datetime.now(timezone.utc)

    @property
    def native_value(self) -> float | None:
        value = self.coordinator.data["energy_delivered"]
        # Record reset time when value drops to 0 (end of session)
        if value == 0 and self._last_energy_value > 0:
            self._last_reset = datetime.now(timezone.utc)
        self._last_energy_value = value
        return value

    @property
    def last_reset(self) -> datetime:
        return self._last_reset


class AbbTerraAcCurrentL1Sensor(AbbTerraAcBaseSensor):
    """Sensor for charging current L1."""
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "current_l1"
        self._attr_unique_id = f"{self._entry_id}_current_l1"

    @property
    def native_value(self) -> int | None:
        value = self.coordinator.data.get("charging_current_l1", 0)
        return int(round(value, 0))


class AbbTerraAcCurrentL2Sensor(AbbTerraAcBaseSensor):
    """Sensor for charging current L2."""
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "current_l2"
        self._attr_unique_id = f"{self._entry_id}_current_l2"

    @property
    def native_value(self) -> int | None:
        value = self.coordinator.data.get("charging_current_l2", 0)
        return int(round(value, 0))


class AbbTerraAcCurrentL3Sensor(AbbTerraAcBaseSensor):
    """Sensor for charging current L3."""
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "current_l3"
        self._attr_unique_id = f"{self._entry_id}_current_l3"

    @property
    def native_value(self) -> int | None:
        value = self.coordinator.data.get("charging_current_l3", 0)
        return int(round(value, 0))


class AbbTerraAcVoltageL1Sensor(AbbTerraAcBaseSensor):
    """Sensor for voltage L1."""
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 2

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "voltage_l1"
        self._attr_unique_id = f"{self._entry_id}_voltage_l1"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("voltage_l1")


class AbbTerraAcVoltageL2Sensor(AbbTerraAcBaseSensor):
    """Sensor for voltage L2."""
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 2

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "voltage_l2"
        self._attr_unique_id = f"{self._entry_id}_voltage_l2"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("voltage_l2")


class AbbTerraAcVoltageL3Sensor(AbbTerraAcBaseSensor):
    """Sensor for voltage L3."""
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 2

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "voltage_l3"
        self._attr_unique_id = f"{self._entry_id}_voltage_l3"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("voltage_l3")


class AbbTerraAcCurrentLimitSensor(AbbTerraAcBaseSensor):
    """Sensor for actual current limit chosen by the charger."""
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_suggested_display_precision = 2

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "actual_current_limit"
        self._attr_unique_id = f"{self._entry_id}_actual_current_limit"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.get("charging_current_limit")
