"""Tests for the HVAC Control Center config sensor.

Assert entity state via hass.states and entity registry per
https://developers.home-assistant.io/docs/development_testing/#writing-tests-for-integrations
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.hvac_control_center.sensor import CONFIG_SENSOR_ID


def _get_config_sensor_entity_id(hass: HomeAssistant, entry_id: str) -> str | None:
    """Return the config sensor entity_id for this config entry."""
    registry = er.async_get(hass)
    for e in registry.entities.get_entries_for_config_entry_id(entry_id):
        if e.domain == SENSOR_DOMAIN and e.unique_id == CONFIG_SENSOR_ID:
            return e.entity_id
    return None


@pytest.mark.asyncio
async def test_sensor_setup_creates_config_entity(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """[Happy] async_setup_entry creates the config sensor."""
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

    entity_id = _get_config_sensor_entity_id(hass, mock_config_entry.entry_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "configured"


@pytest.mark.asyncio
async def test_sensor_attributes(
    hass: HomeAssistant, mock_config_entry: ConfigEntry
) -> None:
    """[Happy] Config sensor exposes room_list, spill_zones, temp_dead_band, sync_tolerance."""
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
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = _get_config_sensor_entity_id(hass, mock_config_entry.entry_id)
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert "room_list" in state.attributes
    assert "spill_zones" in state.attributes
    assert "temp_dead_band" in state.attributes
    assert "sync_tolerance" in state.attributes
    assert state.attributes["room_list"] == mock_config_entry.options["room_list"]
    assert state.attributes["spill_zones"] == mock_config_entry.options["spill_zones"]
    assert (
        state.attributes["temp_dead_band"]
        == mock_config_entry.options["temp_dead_band"]
    )
    assert (
        state.attributes["sync_tolerance"]
        == mock_config_entry.options["sync_tolerance"]
    )
