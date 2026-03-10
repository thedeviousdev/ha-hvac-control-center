/**
 * HVAC Control Center - Home Assistant custom panel
 * Reads config from sensor.hvac_control_config; saves via hvac_control.set_config. No configuration.yaml required.
 */

const CONFIG_ENTITY = 'sensor.hvac_control_config';
const MAIN_UNIT_TOGGLE = 'input_boolean.hvac_main_unit_turn_on';
const MAIN_MODE = 'input_select.hvac_main_unit_set_mode';
const DOMAIN = 'hvac_control';
const DEFAULT_ROOMS = 'bathroom,guest,hobby,kitchen,lounge_kitch,lounge_yard,master,office';
const DEFAULT_SPILL = 'kitchen';

function roomIdToName(roomId) {
  return roomId.split('_').map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' ');
}

function getConfig(hass) {
  const state = hass?.states?.[CONFIG_ENTITY];
  const attrs = state?.attributes || {};
  return {
    room_list: (attrs.room_list || DEFAULT_ROOMS).trim(),
    spill_zones: (attrs.spill_zones || DEFAULT_SPILL).trim(),
    temp_dead_band: attrs.temp_dead_band != null ? Number(attrs.temp_dead_band) : 0.5,
    sync_tolerance: attrs.sync_tolerance != null ? Number(attrs.sync_tolerance) : 0.1,
  };
}

function getRooms(hass) {
  const cfg = getConfig(hass);
  if (!cfg.room_list) return ['bathroom', 'guest', 'hobby', 'kitchen', 'lounge_kitch', 'lounge_yard', 'master', 'office'];
  return cfg.room_list.split(',').map(s => s.trim()).filter(Boolean);
}

function getSpillZones(hass) {
  const cfg = getConfig(hass);
  if (!cfg.spill_zones) return ['kitchen'];
  return cfg.spill_zones.split(',').map(s => s.trim()).filter(Boolean);
}

function getState(hass, entityId) {
  const s = hass?.states?.[entityId];
  return s?.state ?? '—';
}

function getAttr(hass, entityId, attr) {
  const s = hass?.states?.[entityId];
  return s?.attributes?.[attr];
}

function escapeHtml(s) {
  if (s == null) return '';
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
}

class HvacControlPanel extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this.attachShadow({ mode: 'open' });
  }

  set hass(value) {
    this._hass = value;
    this._render();
  }

  _callService(domain, service, data = {}) {
    if (!this._hass) return;
    this._hass.callService(domain, service, data);
  }

  _render() {
    if (!this._hass) {
      this.shadowRoot.innerHTML = '<p style="padding:16px">Loading…</p>';
      return;
    }
    const cfg = getConfig(this._hass);
    const rooms = getRooms(this._hass);
    const spillZones = getSpillZones(this._hass);
    const mainOn = getState(this._hass, MAIN_UNIT_TOGGLE) === 'on';
    const mainMode = getState(this._hass, MAIN_MODE) || '—';
    const roomListValue = cfg.room_list;
    const spillListValue = cfg.spill_zones;
    const tempDeadBand = cfg.temp_dead_band;
    const syncTolerance = cfg.sync_tolerance;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; padding: 16px; box-sizing: border-box; }
        * { box-sizing: border-box; }
        .header { margin-bottom: 20px; }
        .header h1 { margin: 0; font-size: 1.5rem; }
        .card { background: var(--ha-card-background, #1c1c1c); border-radius: 8px; padding: 16px; margin-bottom: 16px; border: 1px solid var(--divider-color, #333); }
        .card h2 { margin: 0 0 12px 0; font-size: 1.1rem; }
        .main-row { display: flex; align-items: center; gap: 16px; flex-wrap: wrap; }
        .main-row label { display: flex; align-items: center; gap: 8px; cursor: pointer; }
        .main-row input[type="checkbox"] { width: 18px; height: 18px; }
        .room-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
        .room-card { background: var(--ha-card-background, #1c1c1c); border-radius: 8px; padding: 12px; border: 1px solid var(--divider-color, #333); }
        .room-card.spill { border-left: 3px solid var(--info-color, #039be5); }
        .room-name { font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
        .room-name .badge { font-size: 0.7rem; background: var(--info-color, #039be5); color: #fff; padding: 2px 6px; border-radius: 4px; }
        .row { display: flex; justify-content: space-between; align-items: center; margin: 6px 0; font-size: 0.9rem; }
        .row .label { color: var(--secondary-text-color, #8a8a8a); }
        button { background: var(--primary-color, #03a9f4); color: var(--text-primary-color, #fff); border: none; padding: 8px 14px; border-radius: 6px; cursor: pointer; font-size: 0.9rem; }
        button:hover { opacity: 0.9; }
        button.secondary { background: var(--secondary-background-color, #4a4a4a); }
        .actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
        input[type="number"], input[type="text"] { padding: 4px 8px; border-radius: 4px; border: 1px solid var(--divider-color, #333); background: var(--input-background, #2a2a2a); color: var(--primary-text-color); }
        input[type="number"] { width: 56px; }
        input[type="text"].full { width: 100%; max-width: 320px; }
        .toggle-wrap { display: flex; align-items: center; gap: 8px; }
        .toggle-wrap input[type="checkbox"] { width: 40px; height: 22px; cursor: pointer; }
        .settings-grid { display: grid; gap: 8px; max-width: 400px; }
        .settings-grid label { display: flex; align-items: center; gap: 8px; }
        .settings-grid input { flex: 1; min-width: 0; }
      </style>
      <div class="header">
        <h1>HVAC Control Center</h1>
      </div>

      <div class="card">
        <h2>Settings</h2>
        <div class="settings-grid">
          <label>Room list (comma-separated) <input type="text" class="full" id="room-list-input" value="${escapeHtml(roomListValue)}" placeholder="bathroom,guest,..."></label>
          <label>Spill zones (comma-separated) <input type="text" class="full" id="spill-list-input" value="${escapeHtml(spillListValue)}" placeholder="kitchen"></label>
          <label>Temp dead band (°C) <input type="number" id="temp-dead-band" step="0.1" min="0.1" max="2" value="${escapeHtml(String(tempDeadBand))}"></label>
          <label>Sync tolerance (°C) <input type="number" id="sync-tolerance" step="0.05" min="0.05" max="1" value="${escapeHtml(String(syncTolerance))}"></label>
          <label><button type="button" id="save-config-btn" class="secondary">Save settings</button></label>
        </div>
      </div>

      <div class="card">
        <h2>Main unit</h2>
        <div class="main-row">
          <label>
            <input type="checkbox" id="main-toggle" ${mainOn ? 'checked' : ''}>
            <span>Main unit on</span>
          </label>
          <span class="row"><span class="label">Mode</span> ${mainMode}</span>
        </div>
        <div class="actions">
          <button data-service="process_all_rooms">Process all rooms</button>
          <button data-service="process_all_dampers">Process all dampers</button>
          <button data-service="diagnose_kitchen" class="secondary">Diagnose kitchen</button>
          <label style="display:inline-flex;align-items:center;gap:8px;">
            Set all to <input type="number" id="all-target-temp" step="0.5" min="5" max="40" value="20"> °C
            <button type="button" id="set-all-temp-btn" class="secondary">Apply</button>
          </label>
        </div>
      </div>

      <div class="card">
        <h2>Rooms</h2>
        <div class="room-grid" id="room-grid"></div>
      </div>
    `;

    const mainToggle = this.shadowRoot.getElementById('main-toggle');
    if (mainToggle) {
      mainToggle.addEventListener('change', () => {
        this._callService('input_boolean', mainToggle.checked ? 'turn_on' : 'turn_off', { entity_id: MAIN_UNIT_TOGGLE });
      });
    }

    this.shadowRoot.querySelectorAll('button[data-service]').forEach(btn => {
      btn.addEventListener('click', () => {
        const svc = btn.dataset.service;
        this._callService(DOMAIN, svc, {});
      });
    });

    const setAllTempBtn = this.shadowRoot.getElementById('set-all-temp-btn');
    const allTargetInput = this.shadowRoot.getElementById('all-target-temp');
    if (setAllTempBtn && allTargetInput) {
      setAllTempBtn.addEventListener('click', () => {
        const temp = parseFloat(allTargetInput.value);
        if (!isNaN(temp)) {
          this._callService(DOMAIN, 'set_all_rooms_target_temperature', { temperature: temp });
        }
      });
    }

    const saveConfigBtn = this.shadowRoot.getElementById('save-config-btn');
    const roomListInput = this.shadowRoot.getElementById('room-list-input');
    const spillListInput = this.shadowRoot.getElementById('spill-list-input');
    const tempDeadBandInput = this.shadowRoot.getElementById('temp-dead-band');
    const syncToleranceInput = this.shadowRoot.getElementById('sync-tolerance');
    if (saveConfigBtn && roomListInput && spillListInput && tempDeadBandInput && syncToleranceInput) {
      saveConfigBtn.addEventListener('click', () => {
        const data = {
          room_list: roomListInput.value.trim(),
          spill_zones: spillListInput.value.trim(),
        };
        const t = parseFloat(tempDeadBandInput.value);
        const s = parseFloat(syncToleranceInput.value);
        if (!isNaN(t)) data.temp_dead_band = t;
        if (!isNaN(s)) data.sync_tolerance = s;
        this._callService(DOMAIN, 'set_config', data);
      });
    }

    const grid = this.shadowRoot.getElementById('room-grid');
    if (!grid) return;

    rooms.forEach(room => {
      const isSpill = spillZones.includes(room);
      const climateId = `climate.${room}`;
      const toggleId = `input_boolean.hvac_toggle_${room}`;
      const damperId = `cover.${room}_damper`;
      const targetTempId = `input_number.hvac_set_target_temperature_${room}`;
      const boostId = `input_boolean.hvac_boost_${room}`;

      const climateState = getState(this._hass, climateId);
      const toggleOn = getState(this._hass, toggleId) === 'on';
      const currentTemp = getAttr(this._hass, climateId, 'current_temperature');
      const targetTemp = getState(this._hass, targetTempId);
      const damperPos = getAttr(this._hass, damperId, 'current_position');
      const boostOn = getState(this._hass, boostId) === 'on';

      const card = document.createElement('div');
      card.className = 'room-card' + (isSpill ? ' spill' : '');
      card.innerHTML = `
        <div class="room-name">
          ${roomIdToName(room)}
          ${isSpill ? '<span class="badge">Spill</span>' : ''}
        </div>
        <div class="toggle-wrap row">
          <span class="label">Toggle</span>
          <input type="checkbox" class="room-toggle" data-room="${room}" data-toggle-id="${toggleId}" ${toggleOn ? 'checked' : ''}>
        </div>
        <div class="row"><span class="label">Climate</span> ${climateState}</div>
        <div class="row"><span class="label">Current</span> ${currentTemp != null ? currentTemp + ' °C' : '—'}</div>
        <div class="row"><span class="label">Target</span>
          <input type="number" class="room-target-temp" data-room="${room}" step="0.5" min="5" max="40" value="${targetTemp || ''}" placeholder="—">
        </div>
        <div class="row"><span class="label">Damper</span> ${damperPos != null ? damperPos + '%' : '—'}</div>
        <div class="row"><span class="label">Boost</span>
          <input type="checkbox" class="room-boost" data-room="${room}" data-boost-id="${boostId}" ${boostOn ? 'checked' : ''}>
        </div>
        <div class="actions">
          <button type="button" class="secondary room-temp" data-room="${room}">Set temp</button>
          <button type="button" class="secondary room-damper" data-room="${room}">Set damper</button>
        </div>
      `;

      card.querySelector('.room-toggle').addEventListener('change', (e) => {
        this._callService('input_boolean', e.target.checked ? 'turn_on' : 'turn_off', { entity_id: e.target.dataset.toggleId });
      });
      card.querySelector('.room-boost').addEventListener('change', (e) => {
        this._callService('input_boolean', e.target.checked ? 'turn_on' : 'turn_off', { entity_id: e.target.dataset.boostId });
      });
      card.querySelector('.room-temp').addEventListener('click', () => {
        const input = card.querySelector('.room-target-temp');
        const temp = input ? parseFloat(input.value) : 20;
        if (!isNaN(temp)) {
          this._callService('input_number', 'set_value', { entity_id: targetTempId, value: temp });
          this._callService(DOMAIN, 'sync_helper_to_climate', {
            target_temp_entity: targetTempId,
            climate_entity: climateId,
            room_name: room
          });
          this._callService(DOMAIN, 'process_room_temperature', { room_name: room });
        }
      });
      card.querySelector('.room-damper').addEventListener('click', () => {
        this._callService(DOMAIN, 'process_room_damper', { room_name: room });
      });

      grid.appendChild(card);
    });
  }
}

customElements.define('hvac-control', HvacControlPanel);
export default HvacControlPanel;
