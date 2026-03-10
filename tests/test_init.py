"""Tests for the HVAC Control Center integration setup.

Uses the core interface (hass.config_entries.async_setup / async_unload) per
https://developers.home-assistant.io/docs/development_testing/#writing-tests-for-integrations
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.hvac_control_center import DOMAIN


@pytest.mark.asyncio
async def test_setup_and_unload_entry(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """[Happy] Setting up and unloading a config entry via the core config entries interface."""
    await async_setup_component(hass, "http", {})
    await hass.async_block_till_done()
    with (
        patch.object(
            hass.http,
            "async_register_static_paths",
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.frontend.async_register_built_in_panel",
        ),
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert hass.data[DOMAIN].get(mock_config_entry.entry_id) is None


@pytest.mark.asyncio
async def test_unload_when_not_loaded_succeeds(hass: HomeAssistant) -> None:
    """[Unhappy] Unloading an entry that was never set up does not crash and returns True."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.hvac_control_center.config_flow import (
        DEFAULT_ROOMS,
        DEFAULT_SPILL,
        DEFAULT_SYNC_TOLERANCE,
        DEFAULT_TEMP_DEAD_BAND,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Never Setup",
        data={},
        options={
            "room_list": DEFAULT_ROOMS,
            "spill_zones": DEFAULT_SPILL,
            "temp_dead_band": DEFAULT_TEMP_DEAD_BAND,
            "sync_tolerance": DEFAULT_SYNC_TOLERANCE,
        },
        entry_id="never_setup_id",
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_unload(entry.entry_id)
    assert result is True


@pytest.mark.asyncio
async def test_setup_with_empty_options_sets_defaults(hass: HomeAssistant) -> None:
    """[Happy] Setup with empty options updates entry with default options."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="HVAC Control Center",
        data={},
        options={},
        entry_id="test_entry_empty_options",
    )
    entry.add_to_hass(hass)
    await async_setup_component(hass, "http", {})
    await hass.async_block_till_done()
    with (
        patch.object(
            hass.http,
            "async_register_static_paths",
            new_callable=AsyncMock,
            create=True,
        ),
        patch(
            "homeassistant.components.frontend.async_register_built_in_panel",
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    loaded = hass.config_entries.async_get_entry(entry.entry_id)
    assert loaded is not None
    assert loaded.options.get("room_list")
    assert loaded.options.get("spill_zones") == "kitchen"
    assert loaded.options.get("temp_dead_band") == 0.5
    assert loaded.options.get("sync_tolerance") == 0.1
