"""Translation files stay complete and in step with ``strings.json``."""

import json
from pathlib import Path

import pytest

_BASE = Path(__file__).parent.parent / "custom_components" / "abb_terra_ac"


def _load(name: str) -> dict:
    return json.loads((_BASE / name).read_text(encoding="utf-8"))


def _leaves(data: dict, prefix: str = "") -> set[str]:
    out: set[str] = set()
    for key, value in data.items():
        if isinstance(value, dict):
            out |= _leaves(value, f"{prefix}/{key}")
        else:
            out.add(f"{prefix}/{key}")
    return out


@pytest.mark.parametrize("language", ["en", "sl"])
def test_translation_has_every_string(language: str) -> None:
    """Every key in strings.json is translated, and nothing else is."""
    strings = _leaves(_load("strings.json"))
    translated = _leaves(_load(f"translations/{language}.json"))

    assert strings - translated == set()
    assert translated - strings == set()


def test_every_entity_has_an_icon_or_a_device_class_icon() -> None:
    """Entities without a device class provide an icon in icons.json."""
    entities = _load("strings.json")["entity"]
    icons = _load("icons.json")["entity"]
    # These sensors get their icon from their device class.
    device_class_icons = {
        "active_power",
        "current_l1",
        "current_l2",
        "current_l3",
        "energy_delivered",
        "voltage_l1",
        "voltage_l2",
        "voltage_l3",
    }
    missing = {
        f"{platform}/{key}"
        for platform, keys in entities.items()
        for key in keys
        if key not in device_class_icons and key not in icons.get(platform, {})
    }
    assert missing == set()
