"""Config flow for HVAC Control Center."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv

from . import DOMAIN

DEFAULT_ROOMS = "bathroom,guest,hobby,kitchen,lounge_kitch,lounge_yard,master,office"
DEFAULT_SPILL = "kitchen"
DEFAULT_TEMP_DEAD_BAND = 0.5
DEFAULT_SYNC_TOLERANCE = 0.1


async def validate_input(_hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate and return validated config."""
    return {
        "room_list": (data.get("room_list") or DEFAULT_ROOMS).strip(),
        "spill_zones": (data.get("spill_zones") or DEFAULT_SPILL).strip(),
        "temp_dead_band": float(data.get("temp_dead_band", DEFAULT_TEMP_DEAD_BAND)),
        "sync_tolerance": float(data.get("sync_tolerance", DEFAULT_SYNC_TOLERANCE)),
    }


class HvacControlConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HVAC Control Center."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step (optional settings)."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                validated = await validate_input(self.hass, user_input)
                return self.async_create_entry(
                    title="HVAC Control Center", data={}, options=validated
                )
            except (ValueError, KeyError):
                errors["base"] = "invalid_values"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional("room_list", default=DEFAULT_ROOMS): cv.string,
                    vol.Optional("spill_zones", default=DEFAULT_SPILL): cv.string,
                    vol.Optional(
                        "temp_dead_band", default=DEFAULT_TEMP_DEAD_BAND
                    ): vol.Coerce(float),
                    vol.Optional(
                        "sync_tolerance", default=DEFAULT_SYNC_TOLERANCE
                    ): vol.Coerce(float),
                }
            ),
            errors=errors,
            description_placeholders={
                "msg": "You can change these later in the HVAC panel."
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get the options flow for this handler."""
        return HvacControlOptionsFlow(config_entry)


class HvacControlOptionsFlow(config_entries.OptionsFlow):
    """Handle HVAC Control Center options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        opts = self.config_entry.options or {}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "room_list", default=opts.get("room_list", DEFAULT_ROOMS)
                    ): cv.string,
                    vol.Optional(
                        "spill_zones", default=opts.get("spill_zones", DEFAULT_SPILL)
                    ): cv.string,
                    vol.Optional(
                        "temp_dead_band",
                        default=opts.get("temp_dead_band", DEFAULT_TEMP_DEAD_BAND),
                    ): vol.Coerce(float),
                    vol.Optional(
                        "sync_tolerance",
                        default=opts.get("sync_tolerance", DEFAULT_SYNC_TOLERANCE),
                    ): vol.Coerce(float),
                }
            ),
        )
