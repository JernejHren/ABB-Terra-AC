"""Unit tests for derived session state logic."""

from __future__ import annotations

import pytest

from custom_components.abb_terra_ac.session_state import (
    SessionState,
    derive_session_state,
    vehicle_connected_from_socket_lock,
)


def test_vehicle_connected_from_socket_lock() -> None:
    """No cable means not connected; any non-zero lock code means a cable is present."""
    assert vehicle_connected_from_socket_lock(0) is False
    assert vehicle_connected_from_socket_lock(1) is True
    assert vehicle_connected_from_socket_lock(273) is True


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, SessionState.IDLE),
        (1, SessionState.IDLE),
        (2, SessionState.COMPLETED),
        (3, SessionState.ACTIVE),
        (4, SessionState.ACTIVE),
    ],
)
def test_derive_session_state_basic_mapping(raw: int, expected: SessionState) -> None:
    """Idle / completed / active branches do not depend on last_command."""
    assert (
        derive_session_state(
            charging_state_raw=raw,
            current_limit_modbus=16.0,
            last_command="none",
            charging_current_l1=0.0,
            charging_current_l2=0.0,
            charging_current_l3=0.0,
        )
        == expected
    )


def test_paused_by_current_vs_command() -> None:
    """State 5 distinguishes pause by 0 A limit vs explicit stop command."""
    base_kw = dict(
        charging_state_raw=5,
        charging_current_l1=0.0,
        charging_current_l2=0.0,
        charging_current_l3=0.0,
    )
    assert (
        derive_session_state(
            **base_kw,
            current_limit_modbus=0.0,
            last_command="none",
        )
        == SessionState.PAUSED_BY_CURRENT
    )
    assert (
        derive_session_state(
            **base_kw,
            current_limit_modbus=16.0,
            last_command="stop",
        )
        == SessionState.PAUSED_BY_COMMAND
    )


def test_state_5_high_phase_current_unknown() -> None:
    """Paused/fault register state with meaningful limit but high phase current is unknown."""
    assert (
        derive_session_state(
            charging_state_raw=5,
            current_limit_modbus=16.0,
            last_command="none",
            charging_current_l1=10.0,
            charging_current_l2=0.0,
            charging_current_l3=0.0,
        )
        == SessionState.UNKNOWN
    )


def test_unknown_raw_state() -> None:
    """Unexpected raw codes map to UNKNOWN."""
    assert (
        derive_session_state(
            charging_state_raw=99,
            current_limit_modbus=0.0,
            last_command="none",
            charging_current_l1=0.0,
            charging_current_l2=0.0,
            charging_current_l3=0.0,
        )
        == SessionState.UNKNOWN
    )


_NO_CURRENT = dict(
    charging_current_l1=0.0, charging_current_l2=0.0, charging_current_l3=0.0
)


def test_state_5_with_limit_below_6a_is_paused_by_current() -> None:
    """Real log 11.10 13:51:46: stop left the limit at 0 A, state 5 (paused).

    Anything below 6 A pauses the session (IEC 61851-1), not only 0 A.
    """
    for limit in (0.0, 3.0, 5.9):
        assert (
            derive_session_state(
                charging_state_raw=5,
                current_limit_modbus=limit,
                last_command="none",
                **_NO_CURRENT,
            )
            == SessionState.PAUSED_BY_CURRENT
        )


def test_state_5_after_stop_command_is_paused_by_command() -> None:
    """Real log 11.10 09:28:32: the charger zeroed the limit after stop."""
    assert (
        derive_session_state(
            charging_state_raw=5,
            current_limit_modbus=0.0,
            last_command="stop",
            **_NO_CURRENT,
        )
        == SessionState.PAUSED_BY_COMMAND
    )


def test_state_5_with_6a_limit_is_a_start_transition() -> None:
    """Real log 11.10 09:18:06: state 5 with 6 A commanded, C2 followed 10 s later.

    That is not a pause by current; it must not be reported as one.
    """
    assert (
        derive_session_state(
            charging_state_raw=5,
            current_limit_modbus=6.0,
            last_command="none",
            state_5_polls=1,
            **_NO_CURRENT,
        )
        == SessionState.ACTIVE
    )


def test_state_5_transition_does_not_last() -> None:
    """After a few polls in state 5 with a sufficient limit the state is unknown."""
    assert (
        derive_session_state(
            charging_state_raw=5,
            current_limit_modbus=6.0,
            last_command="none",
            state_5_polls=3,
            **_NO_CURRENT,
        )
        == SessionState.UNKNOWN
    )
