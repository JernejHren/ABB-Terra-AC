"""Derive high-level session state from raw Modbus charging state and limits."""

from __future__ import annotations

from enum import StrEnum


class SessionState(StrEnum):
    """Logical charging session state (derived, not a single register)."""

    IDLE = "idle"
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED_BY_CURRENT = "paused_by_current"
    PAUSED_BY_COMMAND = "paused_by_command"
    UNKNOWN = "unknown"


class LastCommand(StrEnum):
    """Last user command affecting the charging session (separate from session state)."""

    NONE = "none"
    START = "start"
    STOP = "stop"


# Icons for session_state (UX); entity may override via extra_state_attributes if needed.
SESSION_STATE_ICONS: dict[SessionState, str] = {
    SessionState.IDLE: "mdi:power-plug-off",
    SessionState.ACTIVE: "mdi:ev-station",
    SessionState.COMPLETED: "mdi:battery-check",
    SessionState.PAUSED_BY_CURRENT: "mdi:pause-circle",
    SessionState.PAUSED_BY_COMMAND: "mdi:stop-circle",
    SessionState.UNKNOWN: "mdi:help-circle-outline",
}

# Minimum current per IEC 61851-1 before pause (integration uses 0 A = pause).
_PAUSE_CURRENT_THRESHOLD_A = 6.0


def vehicle_connected_from_socket_lock(socket_lock_state: int) -> bool:
    """True when a cable or vehicle connection is present (not unplugged)."""
    return socket_lock_state != 0


def derive_session_state(
    *,
    charging_state_raw: int,
    current_limit_modbus: float,
    last_command: str,
    charging_current_l1: float,
    charging_current_l2: float,
    charging_current_l3: float,
) -> SessionState:
    """Map raw charger state + limits + last command to SessionState.

    Deterministic: no delays, only inputs from the latest poll (and last_command).
    """
    max_phase = max(
        charging_current_l1,
        charging_current_l2,
        charging_current_l3,
    )

    if charging_state_raw in (0, 1):
        return SessionState.IDLE

    if charging_state_raw == 2:
        return SessionState.COMPLETED

    if charging_state_raw in (3, 4):
        return SessionState.ACTIVE

    if charging_state_raw == 5:
        if last_command == LastCommand.STOP:
            return SessionState.PAUSED_BY_COMMAND
        if current_limit_modbus <= 0.0:
            return SessionState.PAUSED_BY_CURRENT
        # Paused register state but meaningful limit and no stop command: edge case.
        if max_phase > _PAUSE_CURRENT_THRESHOLD_A:
            return SessionState.UNKNOWN
        return SessionState.PAUSED_BY_CURRENT

    return SessionState.UNKNOWN
