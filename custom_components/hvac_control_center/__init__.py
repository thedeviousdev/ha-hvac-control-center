"""HVAC Control Center integration - all logic in one place, no YAML scripts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from homeassistant.components import frontend
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .config_flow import (
    DEFAULT_ROOMS,
    DEFAULT_SPILL,
    DEFAULT_SYNC_TOLERANCE,
    DEFAULT_TEMP_DEAD_BAND,
)
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
MAIN_UNIT_TOGGLE = "input_boolean.hvac_main_unit_turn_on"
MAIN_MODE = "input_select.hvac_main_unit_set_mode"

DAMPER_OPEN_PCT = 90
DAMPER_CLOSED_PCT = 10
CLIMATE_RUNNING_STATES = ("fan_only", "cool", "heat", "auto", "dry")

PANEL_URL_PATH = "hvac-control-center"
PANEL_MODULE_URL = "/hac_static/hvac_control_center/hvac-panel.js"
FRONTEND_DIR = "frontend"


async def _async_noop_update() -> dict[str, Any]:
    """Trivial coordinator update to satisfy Home Assistant's expectations."""
    return {}


def _get_options(hass: HomeAssistant) -> dict[str, Any]:
    """Get current options from the config entry."""
    if DOMAIN not in hass.data:
        return {}
    entry_id = hass.data[DOMAIN].get("entry_id")
    if not entry_id:
        return {}
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or not entry.options:
        return {}
    return entry.options


def _get_rooms(hass: HomeAssistant) -> list[str]:
    opts = _get_options(hass)
    s = (opts.get("room_list") or DEFAULT_ROOMS).strip()
    if not s:
        return [
            "bathroom",
            "guest",
            "hobby",
            "kitchen",
            "lounge_kitch",
            "lounge_yard",
            "master",
            "office",
        ]
    return [r.strip() for r in s.split(",") if r.strip()]


def _get_spill_zones(hass: HomeAssistant) -> list[str]:
    opts = _get_options(hass)
    s = (opts.get("spill_zones") or DEFAULT_SPILL).strip()
    if not s:
        return ["kitchen"]
    return [x.strip() for x in s.split(",") if x.strip()]


def _get_temp_dead_band(hass: HomeAssistant) -> float:
    opts = _get_options(hass)
    try:
        return float(opts.get("temp_dead_band", DEFAULT_TEMP_DEAD_BAND))
    except (TypeError, ValueError):
        return DEFAULT_TEMP_DEAD_BAND


def _get_sync_tolerance(hass: HomeAssistant) -> float:
    opts = _get_options(hass)
    try:
        return float(opts.get("sync_tolerance", DEFAULT_SYNC_TOLERANCE))
    except (TypeError, ValueError):
        return DEFAULT_SYNC_TOLERANCE


def _climate_entity(room: str) -> str:
    return f"climate.{room}"


def _toggle_entity(room: str) -> str:
    return f"input_boolean.hvac_toggle_{room}"


def _damper_entity(room: str) -> str:
    return f"cover.{room}_damper"


def _target_temp_entity(room: str) -> str:
    return f"input_number.hvac_set_target_temperature_{room}"


def _boost_entity(room: str) -> str:
    return f"input_boolean.hvac_boost_{room}"


async def _process_room_damper(hass: HomeAssistant, room_name: str) -> None:
    climate_entity = _climate_entity(room_name)
    toggle_entity = _toggle_entity(room_name)
    damper_entity = _damper_entity(room_name)

    climate_state = hass.states.get(climate_entity)
    toggle_state = hass.states.get(toggle_entity)
    if not climate_state or climate_state.state in ("unknown", "unavailable"):
        return
    if not toggle_state or toggle_state.state in ("unknown", "unavailable"):
        return

    hvac_state = climate_state.state
    toggle_on = toggle_state.state == "on"
    damper_state = hass.states.get(damper_entity)
    position = 0
    if damper_state and damper_state.attributes.get("current_position") is not None:
        try:
            position = int(damper_state.attributes["current_position"])
        except (TypeError, ValueError):
            pass

    spill_zones = _get_spill_zones(hass)
    is_spill = room_name in spill_zones
    main_on = hass.states.is_state(MAIN_UNIT_TOGGLE, "on")
    climate_running = hvac_state in CLIMATE_RUNNING_STATES
    should_be_open = (is_spill and main_on) or (toggle_on and climate_running)
    is_open = position >= DAMPER_OPEN_PCT
    is_closed = position <= DAMPER_CLOSED_PCT

    if should_be_open and not is_open:
        await hass.services.async_call(
            "cover", "set_cover_position", {"entity_id": damper_entity, "position": 100}
        )
        await hass.services.async_call(
            "logbook",
            "log",
            {
                "name": f"HVAC - {room_name.title()}",
                "message": f"Damper opened - spill: {is_spill}, main: {main_on}, toggle: {toggle_state.state}, climate: {hvac_state}",
            },
        )
    elif not should_be_open and not is_closed:
        await hass.services.async_call(
            "cover", "set_cover_position", {"entity_id": damper_entity, "position": 0}
        )
        await hass.services.async_call(
            "logbook",
            "log",
            {
                "name": f"HVAC - {room_name.title()}",
                "message": f"Damper closed - toggle: {toggle_state.state}, climate: {hvac_state}",
            },
        )


async def _process_room_temperature(hass: HomeAssistant, room_name: str) -> None:
    climate_entity = _climate_entity(room_name)
    toggle_entity = _toggle_entity(room_name)
    target_temp_entity = _target_temp_entity(room_name)

    climate_state = hass.states.get(climate_entity)
    target_state = hass.states.get(target_temp_entity)
    if not climate_state or climate_state.state in ("unknown", "unavailable"):
        return
    if not target_state or target_state.state in ("unknown", "unavailable"):
        return

    try:
        target_temp = float(target_state.state)
    except (TypeError, ValueError):
        target_temp = 20.0
    current_temp = climate_state.attributes.get("current_temperature")
    if current_temp is None:
        return
    try:
        current_temp = float(current_temp)
    except (TypeError, ValueError):
        return

    system_mode_state = hass.states.get(MAIN_MODE)
    system_mode = (system_mode_state.state or "cool").lower()
    hvac_state = climate_state.state
    system_enabled = hass.states.is_state(MAIN_UNIT_TOGGLE, "on")
    toggle_on = hass.states.is_state(toggle_entity, "on")
    dead_band = _get_temp_dead_band(hass)
    temp_diff = abs(current_temp - target_temp)

    needs_cooling = system_mode == "cool" and current_temp > target_temp
    needs_heating = system_mode == "heat" and current_temp < target_temp
    should_turn_on = (
        system_enabled
        and toggle_on
        and (needs_cooling or needs_heating)
        and temp_diff >= dead_band
        and hvac_state == "off"
    )
    cooling_satisfied = system_mode == "cool" and current_temp <= target_temp
    heating_satisfied = system_mode == "heat" and current_temp >= target_temp
    wrong_mode_cooling = system_mode == "cool" and current_temp < target_temp
    wrong_mode_heating = system_mode == "heat" and current_temp > target_temp
    should_turn_off = (
        cooling_satisfied
        or heating_satisfied
        or wrong_mode_cooling
        or wrong_mode_heating
    ) and hvac_state != "off"

    if should_turn_on:
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": climate_entity, "hvac_mode": "fan_only"},
        )
        await hass.services.async_call(
            "logbook",
            "log",
            {
                "name": f"HVAC - {room_name.title()}",
                "message": f"Turned on - {system_mode} mode, Δ{temp_diff:.1f}°C (target: {target_temp}°C, current: {current_temp}°C)",
            },
        )
    elif should_turn_off:
        await hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {"entity_id": climate_entity, "hvac_mode": "off"},
        )
        reason = (
            "target reached"
            if (cooling_satisfied or heating_satisfied)
            else "wrong mode"
        )
        await hass.services.async_call(
            "logbook",
            "log",
            {
                "name": f"HVAC - {room_name.title()}",
                "message": f"Turned off - {reason} (target: {target_temp}°C, current: {current_temp}°C)",
            },
        )


async def _sync_helper_to_climate(
    hass: HomeAssistant,
    target_temp_entity: str,
    climate_entity: str,
    room_name: str | None = None,
) -> None:
    target_state = hass.states.get(target_temp_entity)
    if not target_state or target_state.state in ("unknown", "unavailable"):
        return
    try:
        target_temp = float(target_state.state)
    except (TypeError, ValueError):
        return
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": climate_entity, "temperature": target_temp},
    )
    name = (room_name or climate_entity.replace("climate.", "")).title()
    await hass.services.async_call(
        "logbook",
        "log",
        {
            "name": f"HVAC - {name}",
            "message": f"HVAC - {name} temperature set to {target_temp}°C",
        },
    )


async def _sync_climate_to_helper(
    hass: HomeAssistant, climate_entity: str, target_helper: str
) -> None:
    climate_state = hass.states.get(climate_entity)
    helper_state = hass.states.get(target_helper)
    if not climate_state:
        return
    temp_attr = climate_state.attributes.get("temperature")
    if temp_attr is None:
        return
    try:
        new_temp = float(temp_attr)
    except (TypeError, ValueError):
        return
    tolerance = _get_sync_tolerance(hass)
    if helper_state and helper_state.state not in ("unknown", "unavailable"):
        try:
            helper_temp = float(helper_state.state)
            if abs(new_temp - helper_temp) <= tolerance:
                return
        except (TypeError, ValueError):
            pass
    await hass.services.async_call(
        "input_number", "set_value", {"entity_id": target_helper, "value": new_temp}
    )
    await hass.services.async_call(
        "logbook",
        "log",
        {
            "name": "HVAC Sync",
            "message": f"Synced {climate_entity} temperature {new_temp}°C to {target_helper}",
        },
    )


async def _diagnose_kitchen(hass: HomeAssistant) -> None:
    climate_state = hass.states.get("climate.kitchen")
    toggle_state = hass.states.get("input_boolean.hvac_toggle_kitchen")
    damper_state = hass.states.get("cover.kitchen_damper")
    main_on = hass.states.is_state(MAIN_UNIT_TOGGLE, "on")
    current_temp = 0.0
    target_temp = 0.0
    if climate_state:
        t = climate_state.attributes.get("current_temperature")
        if t is not None:
            try:
                current_temp = float(t)
            except (TypeError, ValueError):
                pass
    target_s = hass.states.get("input_number.hvac_set_target_temperature_kitchen")
    if target_s and target_s.state not in ("unknown", "unavailable"):
        try:
            target_temp = float(target_s.state)
        except (TypeError, ValueError):
            pass
    system_mode = (hass.states.get(MAIN_MODE) or hass.states.Entity()).state or "—"
    expected = (
        "Climate should be OFF (toggle is off)"
        if (toggle_state and toggle_state.state == "off")
        else f"Climate may run if temp needs adjustment ({system_mode} mode)"
    )
    msg = (
        f"Climate: {climate_state.state if climate_state else '—'} | Toggle: {toggle_state.state if toggle_state else '—'} | "
        f"Damper: {damper_state.attributes.get('current_position', 0) if damper_state else 0}% | "
        f"Main: {main_on} | Temp: {current_temp}°C / {target_temp}°C | Expected: {expected}"
    )
    await hass.services.async_call(
        "logbook", "log", {"name": "HVAC - Kitchen Diagnostic", "message": msg}
    )


async def _set_all_rooms_target_temperature(
    hass: HomeAssistant, temperature: float
) -> None:
    rooms = _get_rooms(hass)
    for room in rooms:
        helper = _target_temp_entity(room)
        await hass.services.async_call(
            "input_number", "set_value", {"entity_id": helper, "value": temperature}
        )
    await hass.services.async_call(
        "logbook",
        "log",
        {"name": "HVAC Automation", "message": f"Set all rooms to {temperature}°C"},
    )


async def _handle_boost(hass: HomeAssistant, room: str) -> None:
    boost_entity = _boost_entity(room)
    boost_on = hass.states.is_state(boost_entity, "on")
    await hass.services.async_call(
        "logbook",
        "log",
        {
            "name": f"HVAC - {room.title()}",
            "message": f"Boost turned {'on' if boost_on else 'off'} for {room}",
        },
    )


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up HVAC Control Center from a config entry."""
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_async_noop_update,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {
        "coordinator": coordinator,
    }
    hass.data[DOMAIN]["entry_id"] = config_entry.entry_id

    # Ensure options exist with defaults
    if not config_entry.options:
        hass.config_entries.async_update_entry(
            config_entry,
            options={
                "room_list": DEFAULT_ROOMS,
                "spill_zones": DEFAULT_SPILL,
                "temp_dead_band": DEFAULT_TEMP_DEAD_BAND,
                "sync_tolerance": DEFAULT_SYNC_TOLERANCE,
            },
        )

    # Register static path for panel JS (served from integration folder)
    frontend_path = Path(__file__).parent / FRONTEND_DIR
    if frontend_path.is_dir():
        try:
            # Newer Home Assistant: async_register_static_paths + StaticPathConfig
            from homeassistant.components.http import (  # type: ignore[import-not-found]
                StaticPathConfig,
            )

            register = getattr(hass.http, "async_register_static_paths", None)
            if register is not None:
                await register(
                    [
                        StaticPathConfig(
                            "/hac_static/hvac_control_center",
                            frontend_path,
                            False,
                        )
                    ]
                )
            else:
                # Older Home Assistant: synchronous register_static_path
                hass.http.register_static_path(
                    "/hac_static/hvac_control_center",
                    str(frontend_path),
                    cache=True,
                )
        except Exception as e:  # pragma: no cover - defensive, logged for debugging
            _LOGGER.warning("Could not register static path for HVAC panel: %s", e)

    # Register the panel
    try:
        frontend.async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title="HVAC Control Center",
            sidebar_icon="mdi:thermostat",
            frontend_url_path=PANEL_URL_PATH,
            config={
                "_panel_custom": {
                    "name": "hvac-control-center",
                    "embed_iframe": False,
                    "trust_external": False,
                    "module_url": PANEL_MODULE_URL,
                }
            },
            require_admin=False,
        )
    except Exception as e:
        _LOGGER.warning("Could not register HVAC panel: %s", e)

    # Set up sensor platform (config sensor)
    await hass.config_entries.async_forward_entry_setup(config_entry, "sensor")

    async def process_room_damper(call: ServiceCall) -> None:
        room_name = call.data.get("room_name", "").strip()
        if room_name:
            await _process_room_damper(hass, room_name)

    async def process_room_temperature(call: ServiceCall) -> None:
        room_name = call.data.get("room_name", "").strip()
        if room_name:
            await _process_room_temperature(hass, room_name)

    async def process_all_rooms(call: ServiceCall) -> None:
        for room in _get_rooms(hass):
            if hass.states.is_state(_toggle_entity(room), "on"):
                await _process_room_temperature(hass, room)

    async def process_all_dampers(call: ServiceCall) -> None:
        for room in _get_rooms(hass):
            await _process_room_damper(hass, room)

    async def sync_helper_to_climate(call: ServiceCall) -> None:
        target_temp_entity = call.data.get("target_temp_entity")
        climate_entity = call.data.get("climate_entity")
        room_name = call.data.get("room_name")
        if target_temp_entity and climate_entity:
            await _sync_helper_to_climate(
                hass, target_temp_entity, climate_entity, room_name
            )

    async def sync_climate_to_helper(call: ServiceCall) -> None:
        climate_entity = call.data.get("climate_entity")
        target_helper = call.data.get("target_helper")
        if climate_entity and target_helper:
            await _sync_climate_to_helper(hass, climate_entity, target_helper)

    async def diagnose_kitchen(call: ServiceCall) -> None:
        await _diagnose_kitchen(hass)

    async def set_all_rooms_target_temperature(call: ServiceCall) -> None:
        temp = call.data.get("temperature")
        if temp is not None:
            try:
                t = float(temp)
                await _set_all_rooms_target_temperature(hass, t)
            except (TypeError, ValueError):
                pass

    async def handle_boost(call: ServiceCall) -> None:
        room = call.data.get("room", "").strip()
        if room:
            await _handle_boost(hass, room)

    async def set_config(call: ServiceCall) -> None:
        entry = hass.config_entries.async_get_entry(hass.data[DOMAIN]["entry_id"])
        if not entry:
            return
        opts = dict(entry.options or {})
        if "room_list" in call.data:
            opts["room_list"] = str(call.data["room_list"]).strip()
        if "spill_zones" in call.data:
            opts["spill_zones"] = str(call.data["spill_zones"]).strip()
        if "temp_dead_band" in call.data:
            try:
                opts["temp_dead_band"] = float(call.data["temp_dead_band"])
            except (TypeError, ValueError):
                pass
        if "sync_tolerance" in call.data:
            try:
                opts["sync_tolerance"] = float(call.data["sync_tolerance"])
            except (TypeError, ValueError):
                pass
        hass.config_entries.async_update_entry(entry, options=opts)
        coordinator.async_set_updated_data({})

    hass.services.async_register(DOMAIN, "process_room_damper", process_room_damper)
    hass.services.async_register(
        DOMAIN, "process_room_temperature", process_room_temperature
    )
    hass.services.async_register(DOMAIN, "process_all_rooms", process_all_rooms)
    hass.services.async_register(DOMAIN, "process_all_dampers", process_all_dampers)
    hass.services.async_register(
        DOMAIN, "sync_helper_to_climate", sync_helper_to_climate
    )
    hass.services.async_register(
        DOMAIN, "sync_climate_to_helper", sync_climate_to_helper
    )
    hass.services.async_register(DOMAIN, "diagnose_kitchen", diagnose_kitchen)
    hass.services.async_register(
        DOMAIN, "set_all_rooms_target_temperature", set_all_rooms_target_temperature
    )
    hass.services.async_register(DOMAIN, "handle_boost", handle_boost)
    hass.services.async_register(DOMAIN, "set_config", set_config)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    await hass.config_entries.async_forward_entry_unload(config_entry, "sensor")
    hass.data[DOMAIN].pop(config_entry.entry_id, None)
    if hass.data[DOMAIN].get("entry_id") == config_entry.entry_id:
        hass.data[DOMAIN].pop("entry_id", None)
    return True
