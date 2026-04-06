"""Pytest setup for Home Assistant custom component tests."""

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load integrations from the repo's ``custom_components`` folder."""
    return enable_custom_integrations
