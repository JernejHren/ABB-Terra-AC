"""Tests for decoding the charger error register (manual section 10.2)."""

import pytest

from custom_components.abb_terra_ac.const import ERROR_CODES, decode_error_bits
from homeassistant.core import HomeAssistant

from tests.test_entities import _async_setup_with_registers, _entity_id_for
from tests.helpers.modbus import make_holding_registers_37

# Codes from the Terra AC installation manual, troubleshooting table (IEC).
_MANUAL_CODES = {
    0x0002: "residual_current_detected",
    0x0004: "pe_missing_or_swap_neutral_phase",
    0x0008: "over_voltage",
    0x0010: "under_voltage",
    0x0020: "over_current",
    0x0040: "severe_over_current",
    0x0080: "over_temperature",
    0x0400: "power_relay_fault",
    0x0800: "internal_communication_failure",
    0x1000: "e_lock_failure",
    0x2000: "missing_phase",
    0x4000: "modbus_communication_lost",
}


def test_error_codes_match_manual() -> None:
    """Every documented code maps to its translation key, plus 0 = no error."""
    assert ERROR_CODES == {0: "no_error", **_MANUAL_CODES}


def test_decode_no_error() -> None:
    assert decode_error_bits(0) == (["no_error"], 0)


@pytest.mark.parametrize(("code", "key"), list(_MANUAL_CODES.items()))
def test_decode_single_bit(code: int, key: str) -> None:
    assert decode_error_bits(code) == ([key], 0)


def test_decode_combined_errors_lowest_bit_first() -> None:
    keys, unknown = decode_error_bits(0x0006)
    assert keys == ["residual_current_detected", "pe_missing_or_swap_neutral_phase"]
    assert unknown == 0


def test_decode_reports_undocumented_bits() -> None:
    """Bits without a documented meaning are returned as a mask, not dropped."""
    keys, unknown = decode_error_bits(0x0100)
    assert keys == []
    assert unknown == 0x0100

    keys, unknown = decode_error_bits(0x0100 | 0x0020)
    assert keys == ["over_current"]
    assert unknown == 0x0100


async def test_sensor_single_error(hass: HomeAssistant) -> None:
    registers = make_holding_registers_37(error_code=0x0010)
    entry, _ = await _async_setup_with_registers(hass, registers)

    state = hass.states.get(_entity_id_for(hass, entry.entry_id, "error_code"))
    assert state.state == "under_voltage"
    assert state.attributes["raw_code"] == "0x0010"
    assert state.attributes["active_errors"] == ["under_voltage"]
    assert "unknown_bits" not in state.attributes


async def test_sensor_combined_errors(hass: HomeAssistant) -> None:
    registers = make_holding_registers_37(error_code=0x0006)
    entry, _ = await _async_setup_with_registers(hass, registers)

    state = hass.states.get(_entity_id_for(hass, entry.entry_id, "error_code"))
    assert state.state == "residual_current_detected"
    assert state.attributes["raw_code"] == "0x0006"
    assert state.attributes["active_errors"] == [
        "residual_current_detected",
        "pe_missing_or_swap_neutral_phase",
    ]


async def test_sensor_undocumented_bit_is_unknown(hass: HomeAssistant) -> None:
    registers = make_holding_registers_37(error_code=0x0100)
    entry, _ = await _async_setup_with_registers(hass, registers)

    state = hass.states.get(_entity_id_for(hass, entry.entry_id, "error_code"))
    assert state.state == "unknown"
    assert state.attributes["unknown_bits"] == "0x0100"
