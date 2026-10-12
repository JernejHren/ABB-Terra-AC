"""Constants for the ABB Terra AC integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

from .session_state import LastCommand, SessionState

LAST_COMMAND_OPTIONS: Final[list[str]] = [c.value for c in LastCommand]
SESSION_STATE_OPTIONS: Final[list[str]] = [s.value for s in SessionState]

DOMAIN: Final = "abb_terra_ac"
DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1
DEFAULT_SCAN_INTERVAL: Final = 15
MIN_SCAN_INTERVAL: Final = 5
MAX_SCAN_INTERVAL: Final = 300
MODBUS_READ_TIMEOUT: Final = 3.0

PLATFORMS: Final[list[Platform]] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.BINARY_SENSOR,
]

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_UNIT_ID: Final = "unit_id"

# Charging states per IEC 61851-1
CHARGING_STATES: Final[dict[int, str]] = {
    0: "State A - Idle",
    1: "State B1 - EV Plug in, pending authorization",
    2: "State B2 - EV Plug in, charging complete",
    3: "State C1 - EV Ready for charge",
    4: "State C2 - Charging",
    5: "State D/F - Paused / Fault",
}

# Socket lock states (enum values = translation keys under entity.sensor.socket_lock_state.state)
SOCKET_LOCK_STATES: Final[dict[int, str]] = {
    0: "no_cable_plugged",
    1: "cable_connected_unlocked",
    17: "cable_connected_locked",
    257: "cable_ev_connected_unlocked",
    273: "cable_ev_connected_locked",
}

# Error codes (enum values = translation keys under entity.sensor.error_code.state)
ERROR_CODES: Final[dict[int, str]] = {
    0: "no_error",
    2: "residual_current_detected",
    4: "pe_missing_or_swap_neutral_phase",
    8: "over_voltage",
    16: "under_voltage",
    32: "over_current",
    64: "severe_over_current",
    128: "over_temperature",
    1024: "power_relay_fault",
    2048: "internal_communication_failure",
    4096: "e_lock_failure",
    8192: "missing_phase",
    16384: "modbus_communication_lost",
}


def decode_error_bits(code: int) -> tuple[list[str], int]:
    """Split an error register value into known error keys and unknown bits.

    The manual lists every error as a single bit (0x0002, 0x0004, ... 0x4000),
    so several faults can in principle be reported at once (e.g. 0x0006).
    Returns ``(keys, unknown_mask)``: the keys of all known bits set, lowest
    bit first, and a mask of the set bits that have no documented meaning.
    ``code == 0`` (no error) returns ``(["no_error"], 0)``.
    """
    code = int(code) & 0xFFFFFFFF
    if code == 0:
        return [ERROR_CODES[0]], 0
    keys: list[str] = []
    known_mask = 0
    for value, key in ERROR_CODES.items():
        if value and code & value == value:
            keys.append(key)
            known_mask |= value
    return keys, code & ~known_mask
