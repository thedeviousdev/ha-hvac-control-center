"""Pytest configuration and shared fixtures for HVAC Control Center tests.

Follows the Home Assistant testing framework:
https://developers.homeassistant.io/docs/development_testing/

- Use hass.config_entries.async_setup(entry_id) to set up the integration.
- Assert entity state via hass.states; assert registry via entity_registry.
- Mock config entries via the mock_config_entry fixture (uses MockConfigEntry from the pytest plugin).
"""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hvac_control_center import DOMAIN
from custom_components.hvac_control_center.config_flow import (
    DEFAULT_ROOMS,
    DEFAULT_SPILL,
    DEFAULT_SYNC_TOLERANCE,
    DEFAULT_TEMP_DEAD_BAND,
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests (required for custom component tests)."""
    yield


@pytest.fixture
def mock_config_entry_options() -> dict:
    """Default config entry options (rooms, spill zones, tolerances)."""
    return {
        "room_list": DEFAULT_ROOMS,
        "spill_zones": DEFAULT_SPILL,
        "temp_dead_band": DEFAULT_TEMP_DEAD_BAND,
        "sync_tolerance": DEFAULT_SYNC_TOLERANCE,
    }


@pytest.fixture
def mock_config_entry(
    hass: HomeAssistant, mock_config_entry_options: dict
) -> ConfigEntry:
    """Create and add a config entry for testing."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HVAC Control Center",
        data={},
        options=mock_config_entry_options,
        entry_id="test_entry_id",
    )
    entry.add_to_hass(hass)
    return entry
