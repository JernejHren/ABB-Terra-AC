"""Constants for the ABB Terra AC integration."""

from __future__ import annotations

from typing import Final, TypedDict

from homeassistant.const import Platform

DOMAIN: Final = "abb_terra_ac"
DEFAULT_PORT: Final = 502
DEFAULT_SCAN_INTERVAL: Final = 15

PLATFORMS: Final[list[Platform]] = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_SCAN_INTERVAL: Final = "scan_interval"


class AbbTerraAcData(TypedDict):
    """Coordinator data for one charger update."""

    serial_number: str
    firmware_version: str
    user_settable_max_current: float
    error_code: int
    socket_lock_state: int
    charging_state: int
    charging_current_limit: float
    charging_current_l1: float
    charging_current_l2: float
    charging_current_l3: float
    voltage_l1: float
    voltage_l2: float
    voltage_l3: float
    active_power: float
    energy_delivered: float
    communication_timeout: int
    charging_current_limit_modbus: float
    fallback_limit: int

# Charging states per IEC 61851-1
CHARGING_STATES: Final[dict[int, str]] = {
    0: "State A - Idle",
    1: "State B1 - EV Plug in, pending authorization",
    2: "State B2 - EV Plug in, charging complete",
    3: "State C1 - EV Ready for charge",
    4: "State C2 - Charging",
    5: "State D/F - Paused / Fault",
}

# Socket lock states
SOCKET_LOCK_STATES: Final[dict[int, str]] = {
    0: "No cable plugged",
    1: "Cable connected, unlocked",
    17: "Cable connected, locked",
    257: "Cable & EV connected, unlocked",
    273: "Cable & EV connected, locked",
}

# Error codes
ERROR_CODES: Final[dict[int, str]] = {
    0: "No Error",
    2: "Residual Current Detected",
    4: "PE Missing or Swap Neutral/Phase",
    8: "Over Voltage",
    16: "Under Voltage",
    32: "Over Current",
    64: "Severe Over Current",
    128: "Over Temperature",
    1024: "Power Relay Fault",
    2048: "Internal Communication Failure",
    4096: "E-Lock Failure",
    8192: "Missing Phase",
    16384: "Modbus Communication Lost",
}
