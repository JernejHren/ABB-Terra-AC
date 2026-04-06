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
