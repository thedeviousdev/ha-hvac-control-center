"""Tests for the HVAC Control Center config flow.

Config flow tests verify form steps, validation, and create/options flows per
https://developers.home-assistant.io/docs/development_testing/
"""

from __future__ import annotations

import pytest
from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.hvac_control_center import DOMAIN
from custom_components.hvac_control_center.config_flow import (
    DEFAULT_ROOMS,
    DEFAULT_SPILL,
    DEFAULT_SYNC_TOLERANCE,
    DEFAULT_TEMP_DEAD_BAND,
)


@pytest.mark.asyncio
async def test_user_flow_show_form(hass: HomeAssistant) -> None:
    """[Happy] Initial user step shows the form with room_list, spill_zones, tolerances."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"
    schema = result.get("data_schema")
    assert schema is not None
    keys = set(schema.schema)
    assert "room_list" in keys
    assert "spill_zones" in keys
    assert "temp_dead_band" in keys
    assert "sync_tolerance" in keys


@pytest.mark.asyncio
async def test_user_flow_skip_with_defaults_creates_entry(hass: HomeAssistant) -> None:
    """[Happy] Submitting form with defaults creates entry with options."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is data_entry_flow.FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "room_list": DEFAULT_ROOMS,
            "spill_zones": DEFAULT_SPILL,
            "temp_dead_band": DEFAULT_TEMP_DEAD_BAND,
            "sync_tolerance": DEFAULT_SYNC_TOLERANCE,
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "HVAC Control Center"
    assert result["data"] == {}
    assert result["options"]["room_list"] == DEFAULT_ROOMS
    assert result["options"]["spill_zones"] == DEFAULT_SPILL
    assert result["options"]["temp_dead_band"] == DEFAULT_TEMP_DEAD_BAND
    assert result["options"]["sync_tolerance"] == DEFAULT_SYNC_TOLERANCE


@pytest.mark.asyncio
async def test_user_flow_custom_values_creates_entry(hass: HomeAssistant) -> None:
    """[Happy] Submitting form with custom rooms and tolerances creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "room_list": "living_room,bedroom",
            "spill_zones": "living_room",
            "temp_dead_band": 0.3,
            "sync_tolerance": 0.2,
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["options"]["room_list"] == "living_room,bedroom"
    assert result["options"]["spill_zones"] == "living_room"
    assert result["options"]["temp_dead_band"] == 0.3
    assert result["options"]["sync_tolerance"] == 0.2


@pytest.mark.asyncio
async def test_options_flow_show_form(
    hass: HomeAssistant, mock_config_entry: config_entries.ConfigEntry
) -> None:
    """[Happy] Options flow shows form with current options."""
    opts_result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    assert opts_result["type"] is data_entry_flow.FlowResultType.FORM
    assert opts_result["step_id"] == "init"
    schema = opts_result.get("data_schema")
    assert schema is not None
    keys = set(schema.schema)
    assert "room_list" in keys
    assert "spill_zones" in keys
    assert "temp_dead_band" in keys
    assert "sync_tolerance" in keys


@pytest.mark.asyncio
async def test_options_flow_update_options(
    hass: HomeAssistant, mock_config_entry: config_entries.ConfigEntry
) -> None:
    """[Happy] Options flow submit updates entry options."""
    opts_result = await hass.config_entries.options.async_init(
        mock_config_entry.entry_id
    )
    result = await hass.config_entries.options.async_configure(
        opts_result["flow_id"],
        {
            "room_list": "room_a,room_b",
            "spill_zones": "room_a",
            "temp_dead_band": 0.4,
            "sync_tolerance": 0.15,
        },
    )
    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_get_entry(mock_config_entry.entry_id)
    assert entry is not None
    assert entry.options["room_list"] == "room_a,room_b"
    assert entry.options["spill_zones"] == "room_a"
    assert entry.options["temp_dead_band"] == 0.4
    assert entry.options["sync_tolerance"] == 0.15
