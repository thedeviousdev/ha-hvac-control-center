# HVAC System Overview - What You're Building

## System Purpose
You have a **zoned HVAC system** with individual climate controls and dampers for 8 rooms (bathroom, guest, hobby, kitchen, lounge_kitch, lounge_yard, master, office). You're automating the coordination between:
- Room-level climate entities (thermostats)
- Room dampers (motorized vents)
- A main HVAC unit
- User toggle switches for each room
- Temperature setpoints

---

## Core Functionality

### 1. **Room-by-Room Control**
- Each room has a toggle (on/off switch)
- When toggle is ON: Climate entity turns on/off based on temperature needs
- When toggle is OFF: Climate entity should stay OFF
- Dampers open when climate is running, close when off

### 2. **Spill Zone (Kitchen)**
- Kitchen is a "spill zone" - acts as pressure relief for the HVAC system
- Kitchen damper stays OPEN whenever main unit is ON (regardless of kitchen toggle state) // TODO: This kitchen damper should not stay open if it has been turned off, however, if the HVAC system has opened the damper on its own, and the room toggle is "off", do not modify the damper opening.  
- Kitchen climate should still respect toggle (only run if toggle is ON)

### 3. **Temperature Control Logic**
- **Cool mode**: Turn on when current > target, turn off when current ≤ target
- **Heat mode**: Turn on when current < target, turn off when current ≥ target
- 0.5°C dead band to prevent rapid cycling
- Only operate when main unit is enabled

### 4. **Main Unit Auto-Control**
- Main unit turns ON when any room climate activates
- Main unit turns OFF when all room climates are off
- Coordinates with dampers to maintain system pressure

### 5. **Bidirectional Sync**
- Temperature helpers ↔ Climate entities (prevents feedback loops with tolerance checks)
- Main unit controls ↔ Helper switches
- Mode and fan settings sync both ways

---

## System Architecture

```
User Toggles → Automations → Scripts → Climate Entities → Physical HVAC
                    ↓           ↓            ↓
                Dampers ←  Temperature ← Sensors
                              Logic
```

### Key Scripts

#### `hvac_room_set_damper`
Controls individual damper position based on:
- Room toggle state
- Climate running state
- Spill zone status
- Main unit status

**Logic**:
- Open if: (Spill zone AND main unit ON) OR (Toggle ON AND climate running)
- Close if: Toggle OFF AND climate OFF (unless spill zone with main unit ON)
- Tolerance: 90% = open, 10% = closed (prevents micro-adjustments)

#### `hvac_room_set_temperature_2`
Temperature-based climate control with:
- 0.5°C dead band
- Cool/heat mode logic
- System enable check
- Toggle verification

**Logic**:
- Turn ON if: System enabled AND toggle ON AND (needs cooling OR needs heating) AND temp difference ≥ 0.5°C
- Turn OFF if: Target reached OR wrong mode OR system disabled

#### `hvac_process_all_rooms`
Batch processes all rooms with toggles ON
- Iterates through room list
- Skips rooms with toggles OFF
- Calls temperature script for each enabled room

#### `hvac_process_all_dampers`
Updates all damper positions
- Iterates through all rooms
- Calls damper script for each room

#### `hvac_sync_*`
Bidirectional sync scripts:
- `hvac_sync_climate_to_helper` - Climate → Helper
- `hvac_sync_helper_to_climate` - Helper → Climate

### Key Automations

#### HVAC - Sync - All Rooms - Dampers
**Triggers**: Toggle or climate state changes
**Action**: Updates damper position for the specific room that changed
**Mode**: restart

#### HVAC - All Rooms - Set Mode
**Triggers**: Toggle changes, temperature changes, target temp changes, main unit changes
**Action**: Calls `hvac_process_all_rooms`
**Mode**: restart

#### HVAC - All Rooms - Set Temperature
**Triggers**: Helper temperature changes
**Action**: Updates climate device temperature
**Mode**: restart

#### HVAC - Sync - All Rooms - Target Temperature
**Triggers**: Climate temperature attribute changes
**Conditions**: Only if difference > 0.1°C (prevents loops)
**Action**: Updates helper temperature
**Mode**: queued

#### HVAC - Main Unit - Auto Control
**Triggers**: Any climate state change
**Action**: 
- Turn ON main unit if any room is running
- Turn OFF main unit if all rooms are off
**Mode**: restart

#### HVAC - Safeguard - Enforce Toggle State
**Triggers**: Any climate or toggle state change
**Conditions**: Toggle OFF but climate running
**Action**: Force climate to OFF, log event
**Mode**: queued

---

## Design Principles

### 1. **Toggle is King**
- The toggle is user-controlled only—the system must NEVER turn it off when climate turns off
- Toggle = "monitor and control this room" (dampers, climate on/off). It persists as the user set it
- If toggle is OFF, climate should NEVER run (except spill zone damper can be open)

### 2. **Spill Zone Exception**
Kitchen damper can be open even with toggle OFF (for pressure balancing)

### 3. **Prevent Loops**
- Use tolerance checks (0.1°C for temps, 90%/10% for dampers)
- Add rate limiting with `for: seconds: 2`
- Proper condition checks

### 4. **Error Handling**
Check for unavailable entities before operating:
```yaml
{{ states(entity) not in ['unknown', 'unavailable'] }}
```

### 5. **Clear Logging**
Track what's happening for debugging:
- Log damper opens/closes with reason
- Log temperature changes with context
- Log safeguard interventions

### 6. **Idempotent Operations**
Only act when change is needed:
- Check current position before moving damper
- Check current state before changing climate
- Use "unchanged" logging for no-ops

---

## Configuration

### Room List
```yaml
input_text.hvac_room_list:
  bathroom,guest,hobby,kitchen,lounge_kitch,lounge_yard,master,office
```

### Spill Zones
```yaml
input_text.hvac_spill_zone_list:
  kitchen
```

### Entity Naming Convention
- Climate: `climate.{room}`
- Toggle: `input_boolean.hvac_toggle_{room}`
- Damper: `cover.{room}_damper`
- Target Temp: `input_number.hvac_set_target_temperature_{room}`
- Boost: `input_boolean.hvac_boost_{room}`

---

## Flow Diagrams

### Temperature Control Flow
```
Temperature Sensor → Current Temp
                          ↓
Target Helper → Target Temp
                          ↓
                  Compare with 0.5°C dead band
                          ↓
              ┌───────────┴───────────┐
              ↓                       ↓
        Needs Heating           Needs Cooling
              ↓                       ↓
        Check Toggle ON         Check Toggle ON
              ↓                       ↓
        Turn ON Climate         Turn ON Climate
              ↓                       ↓
        Open Damper             Open Damper
```

### Damper Control Flow
```
Trigger (Toggle/Climate Change)
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
Is Spill Zone?      Toggle ON?
    ↓                   ↓
Main Unit ON?      Climate Running?
    ↓                   ↓
    └─────────┬─────────┘
              ↓
      Should Be Open?
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
  YES                  NO
    ↓                   ↓
Position < 90%?    Position > 10%?
    ↓                   ↓
  Open to 100%      Close to 0%
```

### Main Unit Control Flow
```
Any Room Climate Changes
              ↓
    Check All Room States
              ↓
    ┌─────────┴─────────┐
    ↓                   ↓
All OFF?          Any Running?
    ↓                   ↓
Turn Main OFF    Turn Main ON
    ↓                   ↓
Close All        Set to Mode
Dampers          from Helper
```

---

## Troubleshooting Guide

### Problem: Toggle turns back off immediately
**Check**:
1. Temperature script - does it turn OFF climate when system disabled?
2. Auto-off automation - is it triggering?
3. Main unit status - is it OFF?

**Solution**: Remove system_enabled check from turn-off conditions

---

### Problem: Dampers open for disabled rooms
**Check**:
1. Multiple damper automations running?
2. Damper position tolerance too tight?
3. Climate entity state (might be 'idle' not 'off')

**Solution**: Disable duplicate automations, increase tolerance

---

### Problem: Temperature constantly changing
**Check**:
1. Sync automations creating feedback loop?
2. No tolerance check in sync?

**Solution**: Add 0.1°C tolerance check before syncing

---

### Problem: Spill zone damper cycling
**Check**:
1. Damper position bouncing around threshold?
2. Conflicting automations?

**Solution**: Use 90%/10% tolerance instead of exact values

---

### Problem: Room turns on with toggle OFF
**Check**:
1. External control (physical thermostat, other integration)?
2. Temperature script checking toggle?
3. Safeguard automation enabled?

**Solution**: 
1. Add toggle check to temperature script
2. Enable safeguard automation
3. Check logbook for what's triggering it
4. Run diagnostic script

---

## Recent Refactoring Improvements

### Code Quality
- **Before**: ~200 lines of duplicated room mappings
- **After**: Template-based entity name construction
- **Benefit**: Add new room in minutes instead of hours

### Automation Count
- **Before**: 17 HVAC automations (with duplicates)
- **After**: 15 clean automations
- **Removed**: Duplicate boost automations, conflicting damper automation

### Logic Clarity
- **Before**: 4 complex temperature conditions
- **After**: 2 clear conditions with computed variables
- **Benefit**: Much easier to understand and debug

### Safety
- **Before**: No error handling
- **After**: Entity availability checks, safeguard automation
- **Benefit**: Robust operation, survives restarts

---

## Diagnostic Tools

### Kitchen Diagnostic Script
Run `script.hvac_diagnose_kitchen` to see:
- Current climate state
- Toggle state
- Damper position
- Main unit status
- Temperature info
- Expected vs actual behavior

### Logbook Messages to Watch For
- `"Damper opened"` - Shows why damper opened
- `"Damper closed"` - Shows why damper closed
- `"Turned on"` - Shows temperature control activation
- `"Turned off"` - Shows why climate turned off
- `"FORCED OFF"` - **CRITICAL** - Safeguard intervened

### States to Monitor
```yaml
# Kitchen-specific
climate.kitchen
input_boolean.hvac_toggle_kitchen
cover.kitchen_damper
input_number.hvac_set_target_temperature_kitchen

# System-wide
climate.hvac (main unit)
input_boolean.hvac_main_unit_turn_on
input_select.hvac_main_unit_set_mode
```

---

## HVAC Control Plugin (no YAML scripts)

All HVAC logic lives in the **HVAC Control** plugin. There are no HVAC scripts in `scripts.yaml`; automations call the integration's services instead.

### What it is
- **Custom integration** (`custom_components/hvac_control`): Python code that implements damper, temperature, batch, sync, diagnose, set-all, and config. Exposes services under the `hvac_control` domain. Stores room list, spill zones, and tolerances in the config entry (no `configuration.yaml` required).
- **Custom panel**: Served from the integration at `/hac_static/hvac_control/hvac-panel.js`. Reads config from `sensor.hvac_control_config` and saves via `hvac_control.set_config`. No dashboard cards required.

### Install

**Option A – HACS (easiest)**  
1. Install [HACS](https://hacs.xyz) if you haven’t already.  
2. Push this repo to GitHub (or use your existing fork).  
3. In Home Assistant: **HACS → Integrations → ⋮ (top right) → Custom repositories**.  
4. Add your repo URL (e.g. `https://github.com/yourusername/ha-hvac-control-center`), set **Category** to **Integration**, then **Add**.  
5. In **HACS → Integrations**, search for **HVAC Control**, then **Download**.  
6. Restart Home Assistant, then **Settings → Devices & services → Add Integration** and add **HVAC Control**.

**Option B – Manual**  
1. Copy the whole **`custom_components/hvac_control/`** folder (including **`frontend/`**) into your Home Assistant **config** directory.  
2. Restart Home Assistant, then **Settings → Devices & services → Add Integration** and add **HVAC Control**.  
3. The **HVAC** entry appears in the sidebar (thermostat icon). No `panel_custom`, `input_text`, or `input_number` entries are needed in `configuration.yaml`.

### Configurable in the panel
- **Rooms**: Editable room list and spill zone list (comma-separated). Saved via `hvac_control.set_config` (stored in the integration config entry).
- **Tolerances**: Temp dead band (°C) and sync tolerance (°C), also saved via `set_config`. Defaults: 0.5°C and 0.1°C. Damper open/closed (90%/10%) are fixed in the integration.

### Integration services (`hvac_control` domain)
| Service | Parameters | Description |
|--------|------------|-------------|
| `process_room_damper` | `room_name` | Run damper logic for one room (open/close by spill zone, toggle, climate). |
| `process_room_temperature` | `room_name` | Run temperature logic for one room (turn climate on/off by dead band, mode, toggle). |
| `process_all_rooms` | — | Run temperature logic for all rooms with toggle ON. |
| `process_all_dampers` | — | Run damper logic for all rooms. |
| `sync_helper_to_climate` | `target_temp_entity`, `climate_entity`, `room_name` (optional) | Set climate temperature from the target helper. |
| `sync_climate_to_helper` | `climate_entity`, `target_helper` | Set helper from climate (only if diff > sync tolerance). |
| `diagnose_kitchen` | — | Log kitchen state to logbook. |
| `set_all_rooms_target_temperature` | `temperature` | Set all rooms' target temp helper to the given value. |
| `handle_boost` | `room` | Called when a room's boost toggle changes. |
| `set_config` | `room_list`, `spill_zones`, `temp_dead_band`, `sync_tolerance` (all optional) | Update integration config (rooms, spill zones, tolerances). Panel uses this to save settings. |

---

## Future Enhancements

### Potential Additions
1. **Schedule support** - Different temps at different times
2. **Weather integration** - Adjust based on outside temperature
3. **Zone grouping** - Treat multiple rooms as one zone

---

## Summary

You're building a **smart HVAC coordinator** that:
- ✅ Provides room-by-room climate control
- ✅ Respects user toggle preferences
- ✅ Manages dampers for proper airflow
- ✅ Handles spill zones for system pressure
- ✅ Prevents feedback loops and conflicts
- ✅ Recovers from errors gracefully
- ✅ Logs everything for debugging

**The goal**: Make your physical HVAC system operate intelligently while maintaining system integrity and user control.

**Current status**: HVAC logic moved into the HVAC Control plugin (custom integration + sidebar panel). No YAML scripts; automations call `hvac_control.*` services.
