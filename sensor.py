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

from . import AbbTerraAcDataUpdateCoordinator, AbbTerraAcRuntimeData
from .const import (
    CHARGING_STATES,
    ERROR_CODES,
    LAST_COMMAND_OPTIONS,
    SESSION_STATE_OPTIONS,
    SOCKET_LOCK_STATES,
)
from .entity import AbbTerraAcEntity
from .session_state import SESSION_STATE_ICONS, vehicle_connected_from_socket_lock

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
        AbbTerraAcChargingStateRawSensor(coordinator, entry),
        AbbTerraAcChargingStateSensor(coordinator, entry),
        AbbTerraAcSessionStateSensor(coordinator, entry),
        AbbTerraAcLastCommandSensor(coordinator, entry),
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


class AbbTerraAcBaseSensor(AbbTerraAcEntity, SensorEntity):
    """Base class for sensors."""

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry.entry_id)
        self._entry_id = entry.entry_id


class AbbTerraAcChargingStateRawSensor(AbbTerraAcBaseSensor):
    """Raw charging state nibble from the ABB register (IEC 61851-1)."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "charging_state_raw"

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_charging_state_raw"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("charging_state")


class AbbTerraAcChargingStateSensor(AbbTerraAcBaseSensor):
    """Charging state decoded per IEC 61851-1."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_translation_key = "charging_state"
    _attr_options = list(dict.fromkeys([*CHARGING_STATES.values(), "Unknown"]))

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_charging_state"

    @property
    def native_value(self) -> str | None:
        charging_state = self.coordinator.data.get("charging_state")
        if charging_state is None:
            return "Unknown"
        return CHARGING_STATES.get(int(charging_state), "Unknown")


class AbbTerraAcSessionStateSensor(AbbTerraAcBaseSensor):
    """Derived session state (idle, active, paused by current vs command, etc.)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(SESSION_STATE_OPTIONS)
    _attr_translation_key = "session_state"

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_session_state"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.session_state.value

    @property
    def icon(self) -> str | None:
        return SESSION_STATE_ICONS.get(self.coordinator.session_state)

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Debug-friendly context: raw register, limits, and connection."""
        d = self.coordinator.data
        if not d:
            return {}
        return {
            "charging_state_raw": d["charging_state"],
            "current_limit": d["charging_current_limit_modbus"],
            "last_command": self.coordinator.last_command,
            "vehicle_connected": vehicle_connected_from_socket_lock(
                int(d["socket_lock_state"])
            ),
        }


class AbbTerraAcLastCommandSensor(AbbTerraAcBaseSensor):
    """Last start/stop command issued from Home Assistant (not mixed into session state)."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(LAST_COMMAND_OPTIONS)
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "last_command"

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{self._entry_id}_last_command"

    @property
    def native_value(self) -> str | None:
        return self.coordinator.last_command


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
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "error_code"
        self._attr_unique_id = f"{self._entry_id}_error_code"
        opts = list(dict.fromkeys([*ERROR_CODES.values(), "unknown"]))
        self._attr_options = opts

    @property
    def native_value(self) -> str:
        error_code = self.coordinator.data.get("error_code")
        if error_code is None:
            return "unknown"
        return ERROR_CODES.get(int(error_code), "unknown")


class AbbTerraAcSocketLockStateSensor(AbbTerraAcBaseSensor):
    """Sensor for socket lock state."""
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(
        self, coordinator: AbbTerraAcDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator, entry)
        self._attr_translation_key = "socket_lock_state"
        self._attr_unique_id = f"{self._entry_id}_socket_lock_state"
        opts = list(dict.fromkeys([*SOCKET_LOCK_STATES.values(), "unknown"]))
        self._attr_options = opts

    @property
    def native_value(self) -> str:
        lock_code = self.coordinator.data.get("socket_lock_state")
        if lock_code is None:
            return "unknown"
        return SOCKET_LOCK_STATES.get(int(lock_code), "unknown")


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
        self._last_energy_value: float = 0.0
        self._last_reset: datetime = datetime.now(timezone.utc)

    def _handle_coordinator_update(self) -> None:
        """Track session boundary when energy resets to 0 (avoid side effects in native_value)."""
        super()._handle_coordinator_update()
        if not self.coordinator.data:
            return
        value = float(self.coordinator.data["energy_delivered"])
        if value == 0.0 and self._last_energy_value > 0.0:
            self._last_reset = datetime.now(timezone.utc)
        self._last_energy_value = value

    @property
    def native_value(self) -> float | None:
        if not self.coordinator.data:
            return None
        return self.coordinator.data["energy_delivered"]

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
