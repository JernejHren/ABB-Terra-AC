"""Definicija senzorjev za ABB Terra AC."""
from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfPower,
    UnitOfEnergy,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CHARGING_STATES

async def async_setup_entry(hass, entry, async_add_entities):
    """Nastavi senzorje iz konfiguracijskega vnosa."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    sensors = [
        AbbTerraAcChargingStateSensor(coordinator, entry),
        AbbTerraAcSerialNumberSensor(coordinator, entry),
        AbbTerraAcFirmwareSensor(coordinator, entry),
        AbbTerraAcErrorCodeSensor(coordinator, entry),
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

class AbbTerraAcBaseSensor(CoordinatorEntity, SensorEntity):
    """Osnovni razred za senzorje."""
    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        serial = coordinator.data.get('serial_number') if coordinator.data else entry.entry_id
        self._entry_id = entry.entry_id
        self._attr_device_info = {
            "identifiers": {(DOMAIN, serial)},
            "name": "ABB Terra AC Charger",
            "manufacturer": "ABB",
            "model": "Terra AC",
        }
        if coordinator.data:
            self._attr_device_info["sw_version"] = coordinator.data.get('firmware_version')

class AbbTerraAcChargingStateSensor(AbbTerraAcBaseSensor):
    """Senzor za stanje polnjenja."""
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(CHARGING_STATES.values())
    
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Charging State"
        self._attr_unique_id = f"{self._entry_id}_charging_state"
        self._attr_icon = "mdi:ev-station"

    @property
    def state(self):
        """Vrne trenutno stanje iz slovarja CHARGING_STATES."""
        state_code = self.coordinator.data.get("charging_state")
        return CHARGING_STATES.get(state_code, f"Unknown ({state_code})")

class AbbTerraAcSerialNumberSensor(AbbTerraAcBaseSensor):
    _attr_entity_registry_enabled_default = False
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Serial Number"
        self._attr_unique_id = f"{self._entry_id}_serial_number"
        self._attr_icon = "mdi:numeric"

    @property
    def state(self):
        return self.coordinator.data.get("serial_number")

class AbbTerraAcFirmwareSensor(AbbTerraAcBaseSensor):
    _attr_entity_registry_enabled_default = False
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Firmware Version"
        self._attr_unique_id = f"{self._entry_id}_firmware_version"
        self._attr_icon = "mdi:chip"

    @property
    def state(self):
        return self.coordinator.data.get("firmware_version")

class AbbTerraAcErrorCodeSensor(AbbTerraAcBaseSensor):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Error Code"
        self._attr_unique_id = f"{self._entry_id}_error_code"
        self._attr_icon = "mdi:alert-circle-outline"

    @property
    def state(self):
        error_code = self.coordinator.data.get("error_code")
        return "No error" if error_code == 0 else str(error_code)

class AbbTerraAcActivePowerSensor(AbbTerraAcBaseSensor):
    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Active Power"
        self._attr_unique_id = f"{self._entry_id}_active_power"

    @property
    def native_value(self):
        return self.coordinator.data.get("active_power")

class AbbTerraAcEnergyDeliveredSensor(AbbTerraAcBaseSensor):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Energy Delivered"
        self._attr_unique_id = f"{self._entry_id}_energy_delivered"

    @property
    def native_value(self):
        return self.coordinator.data.get("energy_delivered")

class AbbTerraAcCurrentL1Sensor(AbbTerraAcBaseSensor):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Current L1"
        self._attr_unique_id = f"{self._entry_id}_current_l1"

    @property
    def native_value(self):
        value = self.coordinator.data.get("charging_current_l1", 0)
        return int(round(value, 0))

class AbbTerraAcCurrentL2Sensor(AbbTerraAcBaseSensor):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Current L2"
        self._attr_unique_id = f"{self._entry_id}_current_l2"

    @property
    def native_value(self):
        value = self.coordinator.data.get("charging_current_l2", 0)
        return int(round(value, 0))

class AbbTerraAcCurrentL3Sensor(AbbTerraAcBaseSensor):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Current L3"
        self._attr_unique_id = f"{self._entry_id}_current_l3"

    @property
    def native_value(self):
        value = self.coordinator.data.get("charging_current_l3", 0)
        return int(round(value, 0))

class AbbTerraAcVoltageL1Sensor(AbbTerraAcBaseSensor):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 2
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Voltage L1"
        self._attr_unique_id = f"{self._entry_id}_voltage_l1"

    @property
    def native_value(self):
        return self.coordinator.data.get("voltage_l1")

class AbbTerraAcVoltageL2Sensor(AbbTerraAcBaseSensor):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 2
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Voltage L2"
        self._attr_unique_id = f"{self._entry_id}_voltage_l2"

    @property
    def native_value(self):
        return self.coordinator.data.get("voltage_l2")

class AbbTerraAcVoltageL3Sensor(AbbTerraAcBaseSensor):
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_suggested_display_precision = 2
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Voltage L3"
        self._attr_unique_id = f"{self._entry_id}_voltage_l3"

    @property
    def native_value(self):
        return self.coordinator.data.get("voltage_l3")

class AbbTerraAcCurrentLimitSensor(AbbTerraAcBaseSensor):
    _attr_device_class = SensorDeviceClass.CURRENT
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_suggested_display_precision = 2
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry)
        self._attr_name = "ABB Actual Current Limit"
        self._attr_unique_id = f"{self._entry_id}_actual_current_limit"
        self._attr_icon = "mdi:current-ac"
        
    @property
    def native_value(self):
        return self.coordinator.data.get("charging_current_limit")