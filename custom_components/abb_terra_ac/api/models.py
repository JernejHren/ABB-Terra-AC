"""Data models for the ABB Terra AC device library."""

from __future__ import annotations

from typing import TypedDict


class AbbTerraAcData(TypedDict):
    """Decoded charger state from one poll."""

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
    charging_at_reduced_current: bool
