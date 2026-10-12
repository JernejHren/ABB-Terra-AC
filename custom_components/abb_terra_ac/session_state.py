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

# Minimum current per IEC 61851-1: a commanded limit below this pauses the session
# (the integration pauses with 0 A).
_PAUSE_CURRENT_THRESHOLD_A = 6.0

# State 5 with a limit of at least 6 A is seen for a few seconds while a session
# starts (B1 -> C2). Beyond this many consecutive polls it is no longer a transition.
STATE_5_TRANSITION_POLLS = 2


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
    state_5_polls: int = 1,
) -> SessionState:
    """Map raw charger state + limits + last command to SessionState.

    Deterministic: only inputs from the latest poll, ``last_command`` and the
    number of consecutive polls that reported state 5 (``state_5_polls``).
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
        # A commanded limit below 6 A pauses the session (the charger also zeroes
        # the limit after a stop command, so without last_command the two look
        # the same).
        if current_limit_modbus < _PAUSE_CURRENT_THRESHOLD_A:
            return SessionState.PAUSED_BY_CURRENT
        if max_phase > _PAUSE_CURRENT_THRESHOLD_A:
            return SessionState.UNKNOWN
        # Limit is high enough to charge and nothing is drawn: the short
        # transition while a session starts. Only trust it for a poll or two.
        if state_5_polls <= STATE_5_TRANSITION_POLLS:
            return SessionState.ACTIVE
        return SessionState.UNKNOWN

    return SessionState.UNKNOWN
