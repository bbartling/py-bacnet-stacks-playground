(function () {
  'use strict';

  const DEFAULT_API_PREFIXES = ['/api'];
  const state = {
    apiBase: '/api',
    route: 'overview',
    health: null,
    devices: [],
    points: [],
    pollingConfig: [],
    alarms: [],
    notifications: [],
    selectedPointId: '',
    trends: [],
    lastRefreshTs: null,
    source: 'live',
    discoveryError: '',
    trendError: '',
    discoveryStatus: {
      whois: { state: 'idle', message: 'Idle', ts: '' },
      points: { state: 'idle', message: 'Idle', ts: '' },
    },
    discoveryBusyInstance: null,
    selectedDiscoveryDevices: [],
    user: null,
    alarmRules: [],
    deviceNotes: [],
    layouts: [],
    selectedOverviewDevice: 'all',
    wiresheetRules: [],
    wiresheetStatus: [],
  };

  let mountEl = null;
  function isIntegrator() {
    return String(state.user?.role || '') === 'system_integrator';
  }

  function resolvedPrefixes(options) {
    if (Array.isArray(options.apiPrefixes) && options.apiPrefixes.length) return options.apiPrefixes;
    if (typeof window !== 'undefined' && Array.isArray(window.DIY_BAS_API_PREFIXES) && window.DIY_BAS_API_PREFIXES.length) {
      return window.DIY_BAS_API_PREFIXES;
    }
    return DEFAULT_API_PREFIXES;
  }

  async function fetchJson(url, init) {
    const response = await fetch(url, { ...(init || {}), credentials: 'include' });
    if (!response.ok) {
      let detail = '';
      try {
        const payload = await response.json();
        detail = payload.detail || payload.error || '';
      } catch (_) {}
      if (response.status === 401) throw new Error('Unauthorized - please sign in again.');
      throw new Error(`${response.status}${detail ? `: ${detail}` : ''}`);
    }
    return response.json();
  }

  function escapeHtml(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function formatValue(value, units) {
    if (value === null || value === undefined || value === '') return '—';
    if (units) return `${value} ${units}`;
    return String(value);
  }

  function unixToLabel(unixTs) {
    const d = new Date(Number(unixTs) * 1000);
    if (Number.isNaN(d.getTime())) return '—';
    return d.toLocaleString();
  }

  function unixToIso(unixTs) {
    const d = new Date(Number(unixTs) * 1000);
    if (Number.isNaN(d.getTime())) return '';
    return d.toISOString();
  }

  function nowLabel() {
    return new Date().toLocaleTimeString();
  }

  function selectedDeviceInstances() {
    return new Set((state.selectedDiscoveryDevices || []).map((v) => Number(v)));
  }

  function getDiscoveryDeviceRows() {
    const selected = selectedDeviceInstances();
    return state.devices.map((d) => {
      const instance = d.deviceInstance || d.instance || d.id;
      const instNum = Number(instance);
      const checked = selected.has(instNum);
      return `
      <tr>
        <td><input type="checkbox" data-act="discover-device-check" data-inst="${escapeHtml(String(instance))}" ${checked ? 'checked' : ''} /></td>
        <td>${escapeHtml(String(instance ?? '—'))}</td>
        <td>${escapeHtml(d.name || `Device ${instance}`)}</td>
        <td>${escapeHtml(d.status || 'online')}</td>
        <td>${escapeHtml(String(d.pointCount || 0))}</td>
        <td>${escapeHtml(d.lastSeen || '—')}</td>
      </tr>`;
    }).join('');
  }

  function getPointRows(includePollingActions) {
    return state.points.map((p) => {
      const isEnabled = !!p.pollingEnabled;
      const pollCell = includePollingActions
        ? `<label><input type="checkbox" data-act="poll-toggle" data-point="${escapeHtml(p.pointId)}" ${isEnabled ? 'checked' : ''}/> enabled</label>
           <input class="control" data-act="poll-interval" data-point="${escapeHtml(p.pointId)}" type="number" min="5" max="900" value="${Number(p.intervalSec || 30)}" style="max-width:92px; margin-left:.5rem;" />`
        : escapeHtml(isEnabled ? `enabled (${p.intervalSec || 30}s)` : 'disabled');
      return `
        <tr class="${escapeHtml(`dash-point-${p.valueState || 'fresh'}`)}">
          <td>${escapeHtml(p.deviceId || '')}</td>
          <td>${escapeHtml(p.label || p.objectIdentifier || p.pointId)}</td>
          <td>${escapeHtml(p.objectIdentifier || '')}</td>
          <td>${escapeHtml(formatValue(p.value, p.units))}</td>
          <td>${escapeHtml(p.lastUpdated || '—')}${p.lastError ? `<div class="dash-point-error">${escapeHtml(p.lastError)}</div>` : ''}</td>
          <td>${pollCell}</td>
        </tr>`;
    }).join('');
  }


  function trendPath(items) {
    const nums = items
      .map((i) => Number(i.value))
      .filter((v) => Number.isFinite(v));
    if (nums.length < 2) return '';
    const min = Math.min(...nums);
    const max = Math.max(...nums);
    const range = Math.max(max - min, 0.001);
    const pts = items
      .map((row, idx) => {
        const n = Number(row.value);
        if (!Number.isFinite(n)) return null;
        const x = (idx / Math.max(items.length - 1, 1)) * 100;
        const y = 95 - ((n - min) / range) * 90;
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .filter(Boolean);
    return pts.length > 1 ? `M ${pts.join(' L ')}` : '';
  }

  function viewOverview() {
    const online = state.devices.filter((d) => String(d.status || '').toLowerCase() === 'online').length;
    const polled = state.points.filter((p) => p.pollingEnabled).length;
    const deviceOptions = ['<option value="all">All devices</option>'].concat(
      state.devices.map((d) => `<option value="${escapeHtml(String(d.deviceInstance || ''))}" ${String(d.deviceInstance || '') === String(state.selectedOverviewDevice) ? 'selected' : ''}>${escapeHtml(d.name || d.deviceInstance)}</option>`)
    );
    const notesMap = {};
    (state.deviceNotes || []).forEach((n) => {
      notesMap[String(n.deviceInstance)] = n.note || '';
    });
    const noteCards = state.devices
      .filter((d) => state.selectedOverviewDevice === 'all' || String(d.deviceInstance) === String(state.selectedOverviewDevice))
      .map((d) => `<div class="dash-config-row"><span>${escapeHtml(d.name || d.deviceInstance)}</span><span>${escapeHtml(notesMap[String(d.deviceInstance)] || 'No note')}</span></div>`)
      .join('');
    return `
      <div class="dash-view-inner">
        <section class="dash-grid-two">
          <div class="panel"><div class="dash-config-row"><span>Discovered devices</span><span>${state.devices.length}</span></div></div>
          <div class="panel"><div class="dash-config-row"><span>Online devices</span><span>${online}</span></div></div>
          <div class="panel"><div class="dash-config-row"><span>Discovered points</span><span>${state.points.length}</span></div></div>
          <div class="panel"><div class="dash-config-row"><span>Polling enabled</span><span>${polled}</span></div></div>
        </section>
        <section class="panel">
          <div class="dash-panel-head"><h2>System status</h2><span>${escapeHtml(state.source)}</span></div>
          <div class="dash-config-stack">
            <div class="dash-config-row"><span>Site</span><span>${escapeHtml(state.health?.siteName || '—')}</span></div>
            <div class="dash-config-row"><span>BACnet server URL</span><span>${escapeHtml(state.health?.diy?.baseUrl || '—')}</span></div>
            <div class="dash-config-row"><span>API base</span><span>${escapeHtml(state.apiBase)}</span></div>
            <div class="dash-config-row"><span>Last refresh</span><span>${escapeHtml(state.lastRefreshTs || '—')}</span></div>
          </div>
        </section>
        <section class="panel">
          <div class="dash-panel-head"><h2>Operator Overview</h2><span>Device notes and selected points</span></div>
          <div class="dash-config-row">
            <span>Device Filter</span>
            <span><select class="control" id="overview-device-filter">${deviceOptions.join('')}</select></span>
          </div>
          <div class="dash-config-stack">${noteCards || '<p class="dash-small-note">No devices discovered.</p>'}</div>
        </section>
      </div>`;
  }

  function viewDiscovery() {
    const whoisStatus = state.discoveryStatus?.whois || { state: 'idle', message: 'Idle', ts: '' };
    const pointsStatus = state.discoveryStatus?.points || { state: 'idle', message: 'Idle', ts: '' };
    const whoisRunning = whoisStatus.state === 'running';
    const pointsRunning = pointsStatus.state === 'running';
    const allSelected = state.devices.length > 0 && state.selectedDiscoveryDevices.length === state.devices.length;
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head"><h2>BACnet Discovery</h2><span>Who-Is + point import</span></div>
          ${state.discoveryError ? `<p class="dash-error-banner">${escapeHtml(state.discoveryError)}</p>` : ''}
          <div class="dash-discovery-status-row">
            <div class="dash-discovery-status ${escapeHtml(`dash-discovery-${whoisStatus.state}`)}">
              ${whoisRunning ? '<span class="dash-spinner" aria-hidden="true"></span>' : ''}
              <span><strong>Who-Is:</strong> ${escapeHtml(whoisStatus.message || 'Idle')}</span>
              <span class="dash-discovery-ts">${escapeHtml(whoisStatus.ts || '')}</span>
            </div>
            <div class="dash-discovery-status ${escapeHtml(`dash-discovery-${pointsStatus.state}`)}">
              ${pointsRunning ? '<span class="dash-spinner" aria-hidden="true"></span>' : ''}
              <span><strong>Points:</strong> ${escapeHtml(pointsStatus.message || 'Idle')}</span>
              <span class="dash-discovery-ts">${escapeHtml(pointsStatus.ts || '')}</span>
            </div>
          </div>
          <div class="dash-config-row">
            <span>
              <input class="control" id="whois-start" type="number" placeholder="start instance" value="1" style="max-width:180px" />
              <input class="control" id="whois-end" type="number" placeholder="end instance" value="4194303" style="max-width:180px; margin-left:.5rem;" />
            </span>
            <span><button class="btn primary" data-act="run-whois" ${whoisRunning ? 'disabled' : ''}>Run Who-Is discovery</button></span>
          </div>
        </section>
        <section class="panel">
          <div class="dash-panel-head"><h2>Discovered Devices</h2><span>${state.devices.length} found</span></div>
          <div class="dash-config-row">
            <span><label><input type="checkbox" data-act="discover-select-all" ${allSelected ? 'checked' : ''}/> Select all devices</label></span>
            <span><button class="btn" data-act="discover-points-selected" ${pointsRunning || state.selectedDiscoveryDevices.length === 0 ? 'disabled' : ''}>Discover points for selected (${state.selectedDiscoveryDevices.length})</button></span>
          </div>
          <div class="dash-table-wrap">
            <table class="dash-table">
              <thead><tr><th></th><th>Instance</th><th>Name</th><th>Status</th><th>Points</th><th>Last seen</th></tr></thead>
              <tbody>${getDiscoveryDeviceRows()}</tbody>
            </table>
          </div>
        </section>
      </div>`;
  }

  function viewPolling() {
    const enabledCount = state.points.filter((p) => p.pollingEnabled).length;
    const allChecked = state.points.length > 0 && enabledCount === state.points.length;
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head"><h2>Polling Configuration</h2><span>${state.points.length} points</span></div>
          <div class="dash-config-row">
            <span>Polling selection</span>
            <span><label><input type="checkbox" data-act="poll-toggle-all" ${allChecked ? 'checked' : ''}/> Select all points</label></span>
          </div>
          <p class="dash-small-note">Enable points and set interval seconds. Click save to persist settings for the polling loop.</p>
          <div class="dash-table-wrap">
            <table class="dash-table">
              <thead><tr><th>Device</th><th>Point</th><th>Object</th><th>Value</th><th>Updated</th><th>Polling</th></tr></thead>
              <tbody>${getPointRows(true)}</tbody>
            </table>
          </div>
          <div style="margin-top:.75rem;"><button class="btn primary" data-act="save-polling">Save polling config</button></div>
        </section>
      </div>`;
  }

  function viewPoints() {
    const treeHtml = window.DiyBasPointsTree ? window.DiyBasPointsTree.renderTree(state.points) : '<p class="dash-small-note">Points tree unavailable.</p>';
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head"><h2>Points Tree</h2><span>${state.points.length} total</span></div>
          ${treeHtml}
        </section>
      </div>`;
  }

  function viewBuilder() {
    const rows = (state.layouts || [])
      .map((l) => `<div class="dash-config-row"><span>${escapeHtml(l.name || l.id)}</span><span>${escapeHtml(l.roleScope || 'all')}</span></div>`)
      .join('');
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head"><h2>Custom Dashboard Builder</h2><span>System Integrator only</span></div>
          <p class="dash-small-note">Create simple widget cards by selecting point IDs and save layout for operators.</p>
          <div class="dash-config-row">
            <span><input id="builder-name" class="control" placeholder="Layout name" /></span>
            <span><button class="btn primary" data-act="builder-save">Save layout</button></span>
          </div>
          <div class="dash-config-row">
            <span><textarea id="builder-layout-json" class="control" rows="6" style="min-width:500px">{ "widgets": [] }</textarea></span>
            <span></span>
          </div>
          <div class="dash-config-stack">${rows || '<p class="dash-small-note">No saved layouts yet.</p>'}</div>
        </section>
      </div>`;
  }


  function viewTrends() {
    const options = state.points
      .map((p) => `<option value="${escapeHtml(p.pointId)}" ${p.pointId === state.selectedPointId ? 'selected' : ''}>${escapeHtml(p.label || p.pointId)}</option>`)
      .join('');
    const path = trendPath(state.trends);
    const trendRows = state.trends
      .slice(-20)
      .reverse()
      .map((i) => `<div class="dash-config-row"><span>${escapeHtml(unixToLabel(i.ts))}</span><span>${escapeHtml(String(i.value))}</span></div>`)
      .join('');
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head"><h2>Trend Explorer</h2><span>SQLite retention + Plotly zoom/export</span></div>
          ${state.trendError ? `<p class="dash-error-banner">${escapeHtml(state.trendError)}</p>` : ''}
          <div class="dash-config-row">
            <span>
              <select class="control" id="trend-point" style="min-width:340px">${options}</select>
              <select class="control" id="trend-range" style="max-width:160px; margin-left:.5rem;">
                <option value="3600">1h</option><option value="21600">6h</option><option value="86400" selected>24h</option>
                <option value="604800">7d</option><option value="1209600">14d</option>
              </select>
            </span>
            <span><button class="btn" data-act="load-trend">Load trend</button></span>
          </div>
          <div class="dash-chart-wrap">
            <div id="plotly-trend" class="dash-plotly-trend"></div>
            <svg viewBox="0 0 100 100" preserveAspectRatio="none" class="dash-chart-svg" ${path ? 'hidden' : ''}>
              <path d="" class="dash-chart-line"></path>
            </svg>
          </div>
          <div class="dash-trend-list">${trendRows || '<p class="dash-small-note">No trend samples in selected range.</p>'}</div>
        </section>
      </div>`;
  }

  function viewDevices() {
    const notesByDevice = {};
    (state.deviceNotes || []).forEach((n) => {
      notesByDevice[String(n.deviceInstance)] = n.note || '';
    });
    return `
      <div class="dash-view-inner"><section class="panel"><div class="dash-panel-head"><h2>Devices</h2><span>${state.devices.length} total</span></div>
      <p class="dash-small-note">${isIntegrator() ? 'Right-click a device row to remove it and its discovered points.' : 'Operator view is read-only.'}</p>
      <div class="dash-table-wrap"><table class="dash-table"><thead><tr><th>Instance</th><th>Name</th><th>Status</th><th>Points</th><th>Last seen</th><th>Overview Note</th></tr></thead>
      <tbody>${state.devices.map((d) => `<tr data-device-inst="${escapeHtml(String(d.deviceInstance || ''))}" class="dash-device-row"><td>${escapeHtml(String(d.deviceInstance || '—'))}</td><td>${escapeHtml(d.name || '')}</td><td>${escapeHtml(d.status || '')}</td><td>${escapeHtml(String(d.pointCount || 0))}</td><td>${escapeHtml(d.lastSeen || '—')}</td><td>${isIntegrator() ? `<input class="control" data-act="device-note" data-device-inst="${escapeHtml(String(d.deviceInstance || ''))}" value="${escapeHtml(notesByDevice[String(d.deviceInstance)] || '')}" placeholder="Room / Area description" />` : escapeHtml(notesByDevice[String(d.deviceInstance)] || '—')}</td></tr>`).join('')}</tbody>
      </table></div></section></div>`;
  }

  function viewAlarms() {
    const cards = state.alarms.length
      ? state.alarms.map((a) => `<div class="dash-alarm-card"><div><strong>${escapeHtml(a.message || a.detail || 'Alarm')}</strong><p>${escapeHtml(a.state || 'active')}</p></div><div class="dash-alarm-meta">${escapeHtml(a.triggeredAt || a.ts || '')}</div></div>`).join('')
      : '<p class="dash-small-note">No active alarms.</p>';
    return `<div class="dash-view-inner"><section class="panel"><div class="dash-panel-head"><h2>Alarms</h2><span>${state.alarms.length}</span></div><div class="dash-alarm-list">${cards}</div></section></div>`;
  }

  function viewNotifications() {
    const rows = state.notifications.length
      ? state.notifications.map((n) => `<div class="dash-config-row"><span>${escapeHtml(n.ts || '')}</span><span>${escapeHtml([n.channel, n.detail].filter(Boolean).join(' · '))}</span></div>`).join('')
      : '<p class="dash-small-note">No notification entries.</p>';
    return `<div class="dash-view-inner"><section class="panel"><div class="dash-panel-head"><h2>Notifications</h2><span>${state.notifications.length}</span></div><div class="dash-config-stack">${rows}</div></section></div>`;
  }

  function paint() {
    if (!mountEl) return;
    const viewMap = {
      overview: viewOverview,
      discovery: viewDiscovery,
      polling: viewPolling,
      devices: viewDevices,
      points: viewPoints,
      wiresheet: () => (window.DiyBasWiresheet ? window.DiyBasWiresheet.render(state) : '<p class="dash-small-note">Wire Sheet module unavailable.</p>'),
      builder: viewBuilder,
      trends: viewTrends,
      alarms: viewAlarms,
      notifications: viewNotifications,
    };
    const fn = viewMap[state.route] || viewOverview;
    mountEl.innerHTML = fn();
    renderTrendPlotly();
    bindEvents();
    bindPointsTree();
    bindDevicesContextMenu();
  }

  function bindPointsTree() {
    if (!mountEl || state.route !== 'points' || !window.DiyBasPointsTree) return;
    window.DiyBasPointsTree.bindContextMenu(mountEl, {
      onSetPolling: async (pointId, enabled) => {
        const row = state.points.find((p) => p.pointId === pointId);
        if (row) row.pollingEnabled = !!enabled;
        const items = state.points.map((p) => ({
          pointId: p.pointId,
          enabled: !!p.pollingEnabled,
          intervalSec: Number(p.intervalSec || 30),
          deviceInstance: Number(p.deviceInstance || 0),
          objectIdentifier: p.objectIdentifier || '',
          propertyIdentifier: p.propertyIdentifier || 'present-value',
          label: p.label || '',
        }));
        await fetchJson(`${state.apiBase}/polling/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items }),
        });
        await refresh();
        state.route = 'points';
        paint();
      },
      onSetPollingPreset: async (pointId, intervalSec) => {
        const row = state.points.find((p) => p.pointId === pointId);
        if (row) {
          row.pollingEnabled = true;
          row.intervalSec = Number(intervalSec || 30);
        }
        const items = state.points.map((p) => ({
          pointId: p.pointId,
          enabled: !!p.pollingEnabled,
          intervalSec: Number(p.intervalSec || 30),
          deviceInstance: Number(p.deviceInstance || 0),
          objectIdentifier: p.objectIdentifier || '',
          propertyIdentifier: p.propertyIdentifier || 'present-value',
          label: p.label || '',
        }));
        await fetchJson(`${state.apiBase}/polling/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items }),
        });
        await refresh();
        state.route = 'points';
        paint();
      },
      onConfigureAlarm: async (pointId) => {
        const row = state.points.find((p) => p.pointId === pointId);
        if (!row) return;
        const detectedType = typeof row.value === 'boolean' ? 'bool' : 'numeric';
        if (detectedType === 'numeric') {
          const low = prompt('Numeric low threshold (blank for none):', '');
          const high = prompt('Numeric high threshold (blank for none):', '');
          await fetchJson(`${state.apiBase}/alarm-rules`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              pointId,
              pointType: 'numeric',
              enabled: true,
              lowThreshold: low === '' ? null : Number(low),
              highThreshold: high === '' ? null : Number(high),
              deadband: 0,
            }),
          });
        } else {
          const expected = confirm('For boolean alarm: should normal state be TRUE? Click Cancel for FALSE.');
          const delay = Number(prompt('Boolean mismatch delay seconds:', '0') || 0);
          await fetchJson(`${state.apiBase}/alarm-rules`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              pointId,
              pointType: 'bool',
              enabled: true,
              expectedBool: expected,
              boolDelaySec: delay,
            }),
          });
        }
        await refresh();
        state.route = 'points';
        paint();
      },
      onDeletePoint: async (pointId) => {
        if (!isIntegrator()) return;
        await fetchJson(`${state.apiBase}/points/${encodeURIComponent(pointId)}`, { method: 'DELETE' });
        await refresh();
        state.route = 'points';
        paint();
      },
    });
  }

  function bindDevicesContextMenu() {
    if (!mountEl || state.route !== 'devices' || !isIntegrator()) return;
    mountEl.querySelectorAll('.dash-device-row').forEach((row) => {
      row.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        const inst = Number(row.getAttribute('data-device-inst') || 0);
        if (!inst) return;
        showDeviceMenu(e.clientX, e.clientY, inst);
      });
    });
  }

  function showDeviceMenu(x, y, deviceInstance) {
    closeDeviceMenu();
    const m = document.createElement('div');
    m.className = 'points-menu';
    m.innerHTML = '<button data-act="delete-device">Delete device and points</button>';
    m.style.left = `${x}px`;
    m.style.top = `${y}px`;
    m.addEventListener('click', async (e) => {
      const act = e.target && e.target.getAttribute ? e.target.getAttribute('data-act') : '';
      closeDeviceMenu();
      if (act !== 'delete-device') return;
      if (!isIntegrator()) return;
      await fetchJson(`${state.apiBase}/devices/${deviceInstance}`, { method: 'DELETE' });
      await refresh();
      state.route = 'devices';
      paint();
    });
    document.body.appendChild(m);
    setTimeout(() => document.addEventListener('click', closeDeviceMenu, { once: true }), 0);
  }

  function closeDeviceMenu() {
    const old = document.querySelector('.points-menu');
    if (old) old.remove();
  }

  function renderTrendPlotly() {
    if (!mountEl || state.route !== 'trends') return;
    const el = mountEl.querySelector('#plotly-trend');
    if (!el) return;
    if (!window.Plotly) {
      el.innerHTML = '<p class="dash-small-note">Plotly failed to load; trend table still available.</p>';
      return;
    }
    const rows = (state.trends || []).filter((r) => r && r.ts !== undefined && r.value !== undefined);
    const trace = [
      {
        x: rows.map((r) => unixToIso(r.ts)),
        y: rows.map((r) => Number(r.value)),
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: '#0d7a5f', width: 2 },
        marker: { size: 5 },
        name: 'Value',
      },
    ];
    const layout = {
      margin: { l: 42, r: 16, t: 12, b: 42 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      xaxis: { title: 'Time', type: 'date' },
      yaxis: { title: 'Value' },
      showlegend: false,
    };
    const config = {
      responsive: true,
      displaylogo: false,
      toImageButtonOptions: { format: 'png', filename: `trend-${state.selectedPointId || 'point'}`, height: 600, width: 1000, scale: 1 },
    };
    window.Plotly.react(el, trace, layout, config);
  }

  function bindEvents() {
    if (!mountEl) return;
    mountEl.querySelectorAll('[data-act="run-whois"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!isIntegrator()) return;
        try {
          state.discoveryError = '';
          state.discoveryStatus.whois = { state: 'running', message: 'Running discovery...', ts: nowLabel() };
          paint();
          const start = Number(mountEl.querySelector('#whois-start')?.value || 1);
          const end = Number(mountEl.querySelector('#whois-end')?.value || 4194303);
          const payload = await fetchJson(`${state.apiBase}/discovery/whois`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ startInstance: start, endInstance: end }),
          });
          state.discoveryStatus.whois = { state: 'success', message: `OK (${Number(payload?.count || 0)} devices)`, ts: nowLabel() };
          await refresh();
          state.selectedDiscoveryDevices = (state.devices || [])
            .map((d) => Number(d.deviceInstance || d.instance || d.id))
            .filter((n) => Number.isFinite(n));
          state.route = 'discovery';
          paint();
        } catch (err) {
          const msg = String(err && err.message ? err.message : err);
          state.discoveryError = msg;
          state.discoveryStatus.whois = { state: 'error', message: msg, ts: nowLabel() };
          paint();
        }
      });
    });
    mountEl.querySelectorAll('[data-act="discover-device-check"]').forEach((el) => {
      el.addEventListener('change', () => {
        const inst = Number(el.getAttribute('data-inst'));
        const current = selectedDeviceInstances();
        if (el.checked) current.add(inst);
        else current.delete(inst);
        state.selectedDiscoveryDevices = Array.from(current.values());
        paint();
      });
    });
    mountEl.querySelectorAll('[data-act="discover-select-all"]').forEach((el) => {
      el.addEventListener('change', () => {
        if (el.checked) {
          state.selectedDiscoveryDevices = (state.devices || [])
            .map((d) => Number(d.deviceInstance || d.instance || d.id))
            .filter((n) => Number.isFinite(n));
        } else {
          state.selectedDiscoveryDevices = [];
        }
        paint();
      });
    });
    mountEl.querySelectorAll('[data-act="discover-points-selected"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!isIntegrator()) return;
        const selected = Array.from(selectedDeviceInstances().values());
        if (!selected.length) return;
        let totalPoints = 0;
        try {
          state.discoveryError = '';
          for (const inst of selected) {
            state.discoveryBusyInstance = inst;
            state.discoveryStatus.points = { state: 'running', message: `Discovering points for ${inst}...`, ts: nowLabel() };
            paint();
            const payload = await fetchJson(`${state.apiBase}/discovery/device-points`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ deviceInstance: inst }),
            });
            totalPoints += Number(payload?.count || 0);
          }
          state.discoveryStatus.points = { state: 'success', message: `OK (${totalPoints} points from ${selected.length} device(s))`, ts: nowLabel() };
          state.discoveryBusyInstance = null;
          await refresh();
          state.route = 'discovery';
          paint();
        } catch (err) {
          const msg = String(err && err.message ? err.message : err);
          state.discoveryError = msg;
          state.discoveryStatus.points = { state: 'error', message: msg, ts: nowLabel() };
          state.discoveryBusyInstance = null;
          state.route = 'discovery';
          paint();
        }
      });
    });
    mountEl.querySelectorAll('[data-act="poll-toggle"]').forEach((el) => {
      el.addEventListener('change', () => {
        const pointId = el.getAttribute('data-point');
        const row = state.points.find((p) => p.pointId === pointId);
        if (row) row.pollingEnabled = el.checked;
      });
    });
    mountEl.querySelectorAll('[data-act="poll-toggle-all"]').forEach((el) => {
      el.addEventListener('change', () => {
        const checked = !!el.checked;
        state.points = state.points.map((p) => ({ ...p, pollingEnabled: checked }));
        paint();
      });
    });
    mountEl.querySelectorAll('[data-act="poll-interval"]').forEach((el) => {
      el.addEventListener('change', () => {
        const pointId = el.getAttribute('data-point');
        const row = state.points.find((p) => p.pointId === pointId);
        if (row) row.intervalSec = Math.max(5, Math.min(900, Number(el.value || 30)));
      });
    });
    mountEl.querySelectorAll('[data-act="save-polling"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!isIntegrator()) return;
        const items = state.points.map((p) => ({
          pointId: p.pointId,
          enabled: !!p.pollingEnabled,
          intervalSec: Number(p.intervalSec || 30),
          deviceInstance: Number(p.deviceInstance || 0),
          objectIdentifier: p.objectIdentifier || '',
          propertyIdentifier: p.propertyIdentifier || 'present-value',
          label: p.label || '',
        }));
        await fetchJson(`${state.apiBase}/polling/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items }),
        });
        await refresh();
      });
    });
    mountEl.querySelectorAll('[data-act="load-trend"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        try {
          state.trendError = '';
          const pointId = mountEl.querySelector('#trend-point')?.value || state.selectedPointId;
          const seconds = Number(mountEl.querySelector('#trend-range')?.value || 86400);
          await loadTrend(pointId, seconds);
          paint();
        } catch (err) {
          state.trendError = String(err && err.message ? err.message : err);
          paint();
        }
      });
    });
    mountEl.querySelectorAll('[data-act="builder-save"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        const name = mountEl.querySelector('#builder-name')?.value || 'Overview';
        let layout = {};
        try {
          layout = JSON.parse(mountEl.querySelector('#builder-layout-json')?.value || '{}');
        } catch (err) {
          state.trendError = `Invalid JSON: ${String(err?.message || err)}`;
          paint();
          return;
        }
        await fetchJson(`${state.apiBase}/dashboard-layouts`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, roleScope: 'all', layout }),
        });
        await refresh();
        state.route = 'builder';
        paint();
      });
    });
    mountEl.querySelectorAll('#overview-device-filter').forEach((el) => {
      el.addEventListener('change', () => {
        state.selectedOverviewDevice = el.value;
        paint();
      });
    });
    mountEl.querySelectorAll('[data-act="device-note"]').forEach((el) => {
      el.addEventListener('change', async () => {
        if (!isIntegrator()) return;
        const deviceInstance = Number(el.getAttribute('data-device-inst') || 0);
        if (!deviceInstance) return;
        await fetchJson(`${state.apiBase}/device-notes`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ deviceInstance, note: el.value || '' }),
        });
        await refresh();
        state.route = 'devices';
        paint();
      });
    });
    if (state.route === 'wiresheet' && window.DiyBasWiresheet) {
      window.DiyBasWiresheet.bind({
        mountEl,
        state,
        isIntegrator,
        fetchJson,
        refresh,
        setRoute: (route) => {
          state.route = route;
        },
        paint,
        apiBase: state.apiBase,
      });
    }
  }

  async function loadTrend(pointId, secondsBack) {
    if (!pointId) return;
    const endTs = Math.floor(Date.now() / 1000);
    const startTs = endTs - Number(secondsBack || 86400);
    const trend = await fetchJson(`${state.apiBase}/trends/query?pointId=${encodeURIComponent(pointId)}&startTs=${startTs}&endTs=${endTs}&limit=3000`);
    state.selectedPointId = pointId;
    state.trends = Array.isArray(trend.items) ? trend.items : [];
  }

  async function loadLiveBundle(prefixes) {
    const list = prefixes.length ? prefixes : DEFAULT_API_PREFIXES;
    for (const raw of list) {
      const base = raw.replace(/\/$/, '');
      try {
        const [health, devices, points, alarms, notificationLogs, pollingConfig, alarmRules, deviceNotes, layouts, wiresheetRules, wiresheetStatus] = await Promise.all([
          fetchJson(`${base}/health`),
          fetchJson(`${base}/discovery/devices`),
          fetchJson(`${base}/points`),
          fetchJson(`${base}/alarms/events`),
          fetchJson(`${base}/notifications/logs`),
          fetchJson(`${base}/polling/config`),
          fetchJson(`${base}/alarm-rules`),
          fetchJson(`${base}/device-notes`),
          fetchJson(`${base}/dashboard-layouts`),
          fetchJson(`${base}/wiresheet/config`),
          fetchJson(`${base}/wiresheet/status`),
        ]);
        return { ok: true, base, health, devices, points, alarms, notificationLogs, pollingConfig, alarmRules, deviceNotes, layouts, wiresheetRules, wiresheetStatus };
      } catch (_) {}
    }
    return { ok: false };
  }

  function mergePollingConfig() {
    const byPoint = {};
    (state.pollingConfig || []).forEach((r) => {
      if (r && r.pointId) byPoint[r.pointId] = r;
    });
    state.points = state.points.map((p) => {
      const cfg = byPoint[p.pointId];
      return cfg
        ? { ...p, pollingEnabled: !!cfg.enabled, intervalSec: Number(cfg.intervalSec || 30) }
        : { ...p, pollingEnabled: !!p.pollingEnabled, intervalSec: Number(p.intervalSec || 30) };
    });
  }

  async function init(el, options = {}) {
    if (!(el instanceof HTMLElement)) return;
    mountEl = el;
    await refresh(options);
  }

  function setRoute(route) {
    state.route = route;
    paint();
  }

  async function refresh(options = {}) {
    const result = await loadLiveBundle(resolvedPrefixes(options));
    if (!result.ok) {
      state.source = 'offline';
      paint();
      return;
    }
    state.apiBase = result.base;
    state.health = result.health || null;
    state.devices = Array.isArray(result.devices?.items) ? result.devices.items : [];
    state.points = Array.isArray(result.points?.items) ? result.points.items : [];
    state.pollingConfig = Array.isArray(result.pollingConfig?.items) ? result.pollingConfig.items : [];
    state.alarms = Array.isArray(result.alarms?.items) ? result.alarms.items : [];
    state.notifications = Array.isArray(result.notificationLogs?.items) ? result.notificationLogs.items : [];
    state.alarmRules = Array.isArray(result.alarmRules?.items) ? result.alarmRules.items : [];
    state.deviceNotes = Array.isArray(result.deviceNotes?.items) ? result.deviceNotes.items : [];
    state.layouts = Array.isArray(result.layouts?.items) ? result.layouts.items : [];
    state.wiresheetRules = Array.isArray(result.wiresheetRules?.items) ? result.wiresheetRules.items : [];
    state.wiresheetStatus = Array.isArray(result.wiresheetStatus?.items) ? result.wiresheetStatus.items : [];
    state.lastRefreshTs = new Date().toLocaleTimeString();
    state.source = 'live';
    const validInstances = new Set(
      (state.devices || [])
        .map((d) => Number(d.deviceInstance || d.instance || d.id))
        .filter((n) => Number.isFinite(n))
    );
    state.selectedDiscoveryDevices = (state.selectedDiscoveryDevices || []).filter((n) => validInstances.has(Number(n)));
    mergePollingConfig();
    if (!state.selectedPointId && state.points.length) state.selectedPointId = state.points[0].pointId;
    if (state.selectedPointId) {
      try {
        state.trendError = '';
        await loadTrend(state.selectedPointId, 86400);
      } catch (err) {
        state.trends = [];
        state.trendError = String(err && err.message ? err.message : err);
      }
    }
    paint();
  }

  function getTopbarMeta() {
    if (!state.health) {
      return { title: 'Dashboard', subtitle: 'Loading…', pill: '…', pillTone: 'neutral' };
    }
    const h = state.health;
    const source = state.source === 'live' ? 'Live API' : 'Offline';
    const titles = {
      overview: 'Overview',
      discovery: 'Discovery',
      polling: 'Polling',
      devices: 'Devices',
      points: 'Points',
      wiresheet: 'Wire Sheet',
      trends: 'Trends',
      alarms: 'Alarms',
      notifications: 'Notifications',
    };
    return {
      title: `${h.appTitle || 'diy-bas'} — ${titles[state.route] || 'Overview'}`,
      subtitle: `${h.siteName || 'site'} · ${source} (${state.apiBase})`,
      pill: h.diy?.reachable ? 'BACnet OK' : source,
      pillTone: h.diy?.reachable ? 'ok' : 'bad',
    };
  }

  window.DiyBasDashboard = {
    init,
    setRoute,
    refresh,
    getTopbarMeta,
    setAuthContext: (user) => {
      state.user = user || null;
    },
  };
})();
