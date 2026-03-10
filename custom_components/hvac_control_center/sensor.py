"""Sensor that exposes HVAC Control Center config for the frontend panel."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import DOMAIN
from .config_flow import (
    DEFAULT_ROOMS,
    DEFAULT_SPILL,
    DEFAULT_SYNC_TOLERANCE,
    DEFAULT_TEMP_DEAD_BAND,
)

CONFIG_SENSOR_ID = "hvac_control_center_config"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HVAC config sensor from a config entry."""
    if config_entry.entry_id not in (hass.data.get(DOMAIN) or {}):
        return
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([HvacControlConfigSensor(coordinator, config_entry)])


class HvacControlConfigSensor(SensorEntity):
    """Sensor exposing room_list, spill_zones, temp_dead_band, sync_tolerance as attributes."""

    _attr_has_entity_name = True
    _attr_name = "Config"
    _attr_unique_id = CONFIG_SENSOR_ID

    def __init__(self, coordinator: DataUpdateCoordinator, entry: ConfigEntry) -> None:
        self.coordinator = coordinator
        self._entry = entry
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}}

    @property
    def state(self) -> str:
        return "configured"

    @property
    def extra_state_attributes(self) -> dict:
        opts = self._entry.options or {}
        return {
            "room_list": opts.get("room_list", DEFAULT_ROOMS),
            "spill_zones": opts.get("spill_zones", DEFAULT_SPILL),
            "temp_dead_band": opts.get("temp_dead_band", DEFAULT_TEMP_DEAD_BAND),
            "sync_tolerance": opts.get("sync_tolerance", DEFAULT_SYNC_TOLERANCE),
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_update))

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
