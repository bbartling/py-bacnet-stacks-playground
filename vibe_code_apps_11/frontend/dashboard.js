(function () {
  'use strict';

  const DEFAULT_API_PREFIXES = ['/api'];
  const state = {
    apiBase: '/api',
    route: 'overview',
    health: null,
    /** idle = before first check; loading = refresh in flight; ready = last health applied */
    bacnetLink: { phase: 'idle', reachable: null, detail: '', statusLabel: '' },
    devices: [],
    points: [],
    pollingConfig: [],
    alarms: [],
    alarmHistory: [],
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
    /** From GET /api/alarm-settings (device offline threshold seconds). */
    alarmSettings: { deviceOfflineSec: 300 },
    deviceNotes: [],
    layouts: [],
    selectedOverviewDevice: 'all',
    wiresheetRules: [],
    wiresheetStatus: [],
    /** Inline banner after refresh / actions (cleared on tab change). */
    feedbackMessage: '',
    feedbackTone: '',
    /** Non-fatal issues from last refresh (e.g. one endpoint failed). */
    bundleErrors: [],
    dockerLogs: {
      container: 'diy-bas',
      lines: 400,
      text: '',
      error: '',
      loading: false,
      containers: [],
      containersFetched: false,
    },
    /** Last trend query window (seconds) for sliding-window live updates. */
    trendsRangeSec: 86400,
    trendsWindowStartTs: 0,
    trendsLive: false,
    trendStreamStatus: '',
    /** Up to 8 point IDs selected in Trend Explorer (checkboxes). */
    trendSelectedIds: [],
    /** Per-point sample rows for chart: { [pointId]: [{ ts, value, ... }] } */
    trendByPoint: {},
    trendOrder: [],
    /** Last multiline diagnostics for Trend Explorer (also mirrored to #trend-diag-pre). */
    trendDiagText: '',
    /** Points tab: session hint for priority-8 override (blue row) until Release. */
    pointPri8OverrideIds: {},
  };

  let mountEl = null;
  let trendsEventSource = null;
  let trendsStreamReconnectTimer = null;
  /** Ring buffer of trend troubleshooting lines (max ~40). */
  let trendDiagBuf = [];

  function trendPushDiag(line) {
    const ts = new Date().toISOString().slice(11, 23);
    const full = `[${ts}] ${String(line)}`;
    trendDiagBuf.push(full);
    while (trendDiagBuf.length > 40) trendDiagBuf.shift();
    state.trendDiagText = trendDiagBuf.join('\n');
    if (typeof console !== 'undefined' && console.info) {
      console.info('[diy-bas][trends-diag]', line);
    }
    const pre = mountEl && mountEl.querySelector('#trend-diag-pre');
    if (pre) pre.textContent = state.trendDiagText;
  }

  function logTab(action, detail) {
    if (typeof console !== 'undefined' && console.info) {
      console.info('[diy-bas][tab]', state.route, action, detail !== undefined ? detail : '');
    }
  }

  function setFeedback(message, tone) {
    state.feedbackMessage = String(message || '');
    state.feedbackTone = tone === 'ok' ? 'ok' : tone === 'err' ? 'err' : '';
  }

  function clearFeedback() {
    state.feedbackMessage = '';
    state.feedbackTone = '';
  }

  function feedbackBannerHtml() {
    if (!state.feedbackMessage) return '';
    const cls = state.feedbackTone === 'ok' ? 'dash-ok-banner' : 'dash-error-banner';
    return `<div class="dash-feedback-strip"><p class="${cls}" role="status">${escapeHtml(state.feedbackMessage)}</p></div>`;
  }

  function isIntegrator() {
    return String(state.user?.role || '') === 'system_integrator';
  }

  function canBulkPoints() {
    const br = String(state.user?.basRole || '');
    return isIntegrator() || br === 'maintenance';
  }

  function resolvedPrefixes(options) {
    if (Array.isArray(options.apiPrefixes) && options.apiPrefixes.length) return options.apiPrefixes;
    if (typeof window !== 'undefined' && Array.isArray(window.DIY_BAS_API_PREFIXES) && window.DIY_BAS_API_PREFIXES.length) {
      return window.DIY_BAS_API_PREFIXES;
    }
    return DEFAULT_API_PREFIXES;
  }

  async function pollReadNowApi(pointIds) {
    const body = pointIds && pointIds.length ? { pointIds } : {};
    return fetchJson(`${state.apiBase}/polling/read-now`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  async function fetchJson(url, init) {
    const method = (init && init.method) || 'GET';
    if (typeof console !== 'undefined' && console.debug) {
      console.debug('[diy-bas][api] →', method, url);
    }
    const response = await fetch(url, { ...(init || {}), credentials: 'include' });
    if (!response.ok) {
      let detail = '';
      try {
        const payload = await response.json();
        detail = payload.detail || payload.error || '';
      } catch (_) {}
      if (response.status === 401) throw new Error('Unauthorized - please sign in again.');
      const err = new Error(`${response.status}${detail ? `: ${detail}` : ''}`);
      if (typeof console !== 'undefined' && console.warn) {
        console.warn('[diy-bas][api] ✗', method, url, err.message);
      }
      throw err;
    }
    const json = await response.json();
    if (method !== 'GET' && typeof console !== 'undefined' && console.info) {
      console.info('[diy-bas][api] ✓', method, url);
    }
    return json;
  }

  function escapeHtml(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function formatNumericForDisplay(value) {
    if (value === null || value === undefined || value === '') return null;
    if (typeof value === 'boolean') return String(value);
    const n = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(n)) return String(value);
    if (typeof value === 'string' && value.trim() !== '' && !/^[-+]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][-+]?\d+)?$/.test(value.trim())) {
      return String(value);
    }
    return n.toFixed(2);
  }

  function formatValue(value, units) {
    const core = formatNumericForDisplay(value);
    if (core === null) return '—';
    if (units) return `${core} ${units}`;
    return core;
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
      const trCls = d.deviceOfflineAlarm ? 'dash-device-row--offline-warn' : '';
      return `
      <tr${trCls ? ` class="${trCls}"` : ''}>
        <td><input type="checkbox" data-act="discover-device-check" data-inst="${escapeHtml(String(instance))}" ${checked ? 'checked' : ''} /></td>
        <td>${escapeHtml(String(instance ?? '—'))}</td>
        <td>${escapeHtml(d.name || `Device ${instance}`)}</td>
        <td>${escapeHtml(d.status || 'online')}</td>
        <td>${escapeHtml(String(d.pointCount || 0))}</td>
        <td>${escapeHtml(d.lastSeen || '—')}</td>
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

  function bacnetStatusBannerHtml() {
    const link = state.bacnetLink || { phase: 'idle', reachable: null, detail: '', statusLabel: '' };
    let mod = 'pending';
    let line = 'Waiting for status…';
    if (link.phase === 'idle') {
      mod = 'pending';
      line = 'Waiting for first BACnet check…';
    } else if (link.phase === 'loading') {
      mod = 'pending';
      line = 'Checking BACnet gateway…';
    } else if (link.phase === 'ready') {
      if (link.reachable) {
        mod = 'online';
        line = link.statusLabel ? String(link.statusLabel) : 'Gateway online';
      } else {
        mod = 'offline';
        line = link.detail ? String(link.detail) : 'Gateway offline or unreachable';
      }
    }
    return `
      <section class="panel bas-bacnet-status-panel" aria-live="polite">
        <div class="bas-bacnet-status bas-bacnet-status--${mod}">
          <span class="bas-bacnet-led" aria-hidden="true"></span>
          <div class="bas-bacnet-status-text">
            <strong>BACnet gateway</strong>
            <span class="bas-bacnet-status-line">${escapeHtml(line)}</span>
          </div>
        </div>
      </section>`;
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
        ${bacnetStatusBannerHtml()}
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

  function viewPoints() {
    const treeHtml = window.DiyBasPointsTree
      ? window.DiyBasPointsTree.renderTree(state.points, { pointOverrideIds: state.pointPri8OverrideIds || {} })
      : '<p class="dash-small-note">Points tree unavailable.</p>';
    const bulkBar = canBulkPoints()
      ? `<div class="points-toolbar" id="points-bulk-toolbar">
          <span><strong>Bulk</strong></span>
          <button type="button" class="btn btn-sm" id="points-select-all">Select all</button>
          <button type="button" class="btn btn-sm" id="points-select-none">Clear</button>
          <label>Interval <select class="control" id="points-bulk-interval">
            <option value="10">10s</option>
            <option value="30" selected>30s</option>
            <option value="60">60s</option>
            <option value="120">120s</option>
            <option value="300">300s</option>
          </select></label>
          <button type="button" class="btn primary btn-sm" id="points-bulk-apply-selected">Apply interval to selected</button>
          <button type="button" class="btn btn-sm" id="points-bulk-apply-all">Apply interval to all points</button>
          <button type="button" class="btn btn-sm" id="points-read-selected">Read BACnet (selected)</button>
          <button type="button" class="btn btn-sm" id="points-read-all-polling">Read BACnet (all polling-on)</button>
        </div>`
      : '';
    const alarmBar = isIntegrator()
      ? `<div class="points-toolbar points-toolbar--alarms" id="points-alarm-toolbar">
          <span><strong>Alarms</strong></span>
          <button type="button" class="btn primary btn-sm" id="points-bulk-alarm-threshold">High / low (selected)…</button>
          <button type="button" class="btn primary btn-sm" id="points-bulk-alarm-cross">Motor status vs command (selected)…</button>
          <button type="button" class="btn btn-sm" id="points-bulk-alarm-runtime">Device offline timing…</button>
          <button type="button" class="btn btn-sm" id="points-bulk-alarm-clear">Turn off alarms (selected)</button>
          <span class="dash-small-note" style="margin:0">Rows highlight <strong class="points-alarm-hint">red</strong> when a point (or its device) has an active alarm.</span>
        </div>`
      : '';
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head"><h2>Points</h2><span>${state.points.length} total</span></div>
          <p class="dash-small-note">The <strong>Poll</strong> column shows saved interval (from server). Right-click for off / interval presets / one-shot read. Integrators and maintenance can use bulk actions below.</p>
          ${bulkBar}
          ${alarmBar}
          ${treeHtml}
        </section>
      </div>`;
  }

  function viewDockerLogs() {
    const dl = state.dockerLogs || {};
    const opts = (dl.containers || [])
      .map((o) => `<option value="${escapeHtml(o.id)}" ${String(o.id) === String(dl.container) ? 'selected' : ''}>${escapeHtml(o.label || o.id)}</option>`)
      .join('');
    const loading = dl.loading ? '<p class="dash-small-note">Loading…</p>' : '';
    const err = dl.error ? `<p class="dash-error-banner">${escapeHtml(dl.error)}</p>` : '';
    const hint =
      '<p class="dash-small-note">Runs <code>docker logs</code> on the host where this app runs. If you see “Docker CLI not available”, the container has no <code>docker</code> binary (common on minimal Pi images) or no socket mount—mount <code>/var/run/docker.sock</code> read-only or run on a host with Docker; moving to a current Ubuntu + Compose host usually fixes it.</p>';
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head"><h2>Docker logs</h2><span>Containers</span></div>
          ${hint}
          <div class="dash-docker-toolbar">
            <label>Container <select class="control" id="docker-container" style="min-width:220px">${opts || '<option value="diy-bas">diy-bas</option>'}</select></label>
            <label>Lines <input class="control" id="docker-lines" type="number" min="50" max="5000" value="${Number(dl.lines) || 400}" style="max-width:100px" /></label>
            <button type="button" class="btn primary" id="docker-refresh">${dl.loading ? 'Loading…' : 'Load logs'}</button>
          </div>
          ${err}
          ${loading}
          <pre class="dash-docker-pre" id="docker-log-pre">${escapeHtml(dl.text || '')}</pre>
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
    const rangeSec = Number(state.trendsRangeSec) || 86400;
    const rangeLabels = { 3600: '1h', 21600: '6h', 86400: '24h', 604800: '7d', 1209600: '14d' };
    const rangeOpts = [3600, 21600, 86400, 604800, 1209600]
      .map((v) => `<option value="${v}" ${v === rangeSec ? 'selected' : ''}>${rangeLabels[v] || v + 's'}</option>`)
      .join('');
    const nSel = (state.trendSelectedIds || []).length;
    const nSelId = 'trend-selected-count';
    const treeHtml = window.DiyBasPointsTree
      ? window.DiyBasPointsTree.renderTree(state.points, {
          variant: 'trends',
          pointOverrideIds: state.pointPri8OverrideIds || {},
        })
      : '<p class="dash-small-note">Points tree unavailable.</p>';
    const path = trendPath(state.trends);
    const trendRows = (state.trends || [])
      .slice(-24)
      .reverse()
      .map((i) => {
        const pid = i.pointId ? `<span class="dash-small-note">${escapeHtml(String(i.pointId))}</span> · ` : '';
        return `<div class="dash-config-row"><span>${pid}${escapeHtml(unixToLabel(i.ts))}</span><span>${escapeHtml(
          formatNumericForDisplay(i.value) ?? '—'
        )}</span></div>`;
      })
      .join('');
    const liveNote =
      '<p class="dash-small-note" style="margin-top:.35rem">Select up to <strong>8</strong> points. <strong>Load trend</strong> reads SQLite history. <strong>Important:</strong> samples are written only after a <strong>successful BACnet read</strong> (Points tab → <em>Read value now</em> / bulk read, or <em>Read BACnet &amp; reload</em> below). Polling interval alone does not fill the trend DB.</p>';
    const streamStatus = state.trendStreamStatus
      ? `<p class="dash-small-note" id="trend-live-status">${escapeHtml(state.trendStreamStatus)}</p>`
      : '<p class="dash-small-note" id="trend-live-status" hidden></p>';
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head"><h2>Trend Explorer</h2><span>SQLite retention + Plotly zoom/export</span></div>
          ${state.trendError ? `<p class="dash-error-banner">${escapeHtml(state.trendError)}</p>` : ''}
          <div class="points-toolbar points-toolbar--alarms" id="trend-points-toolbar">
            <span><strong>Points for chart</strong></span>
            <button type="button" class="btn btn-sm" id="trend-pick-all">Select all</button>
            <button type="button" class="btn btn-sm" id="trend-pick-none">Clear</button>
            <span class="dash-small-note" style="margin:0"><span id="${nSelId}">${nSel}</span> selected (max 8)</span>
          </div>
          <div class="dash-trend-picker-wrap" style="max-height:240px;overflow:auto;margin-bottom:.75rem;border:1px solid var(--border);border-radius:10px">
            ${treeHtml}
          </div>
          <div class="dash-config-row">
            <span>
              <label>Window <select class="control" id="trend-range" style="max-width:160px">${rangeOpts}</select></label>
            </span>
            <span>
              <button class="btn primary" data-act="load-trend">Load trend</button>
              <button type="button" class="btn btn-sm" data-act="trend-read-bacnet" title="POST /api/polling/read-now for selected points, then reload chart">Read BACnet &amp; reload</button>
              <label class="dash-trend-live-label"><input type="checkbox" id="trend-live" ${state.trendsLive ? 'checked' : ''} /> Live stream</label>
            </span>
          </div>
          ${liveNote}
          ${streamStatus}
          <details class="dash-trend-diag-wrap" style="margin:.5rem 0">
            <summary>Trend diagnostics (server logs + API hints)</summary>
            <p class="dash-small-note" style="margin:.35rem 0">Server: Django logger <code>bas.views</code> at INFO logs each <code>/api/trends/query</code> and stream batches. Client lines below update as you use this tab.</p>
            <pre id="trend-diag-pre" class="dash-trend-diag"></pre>
          </details>
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
      <tbody>${state.devices
        .map((d) => {
          const di = String(d.deviceInstance || '');
          const devOff = !!d.deviceOfflineAlarm;
          const rowCls = `dash-device-row${devOff ? ' dash-device-row--offline-warn' : ''}`;
          return `<tr data-device-inst="${escapeHtml(di)}" class="${rowCls}"><td>${escapeHtml(String(d.deviceInstance || '—'))}</td><td>${escapeHtml(d.name || '')}</td><td>${escapeHtml(d.status || '')}</td><td>${escapeHtml(String(d.pointCount || 0))}</td><td>${escapeHtml(d.lastSeen || '—')}</td><td>${isIntegrator() ? `<input class="control" data-act="device-note" data-device-inst="${escapeHtml(di)}" value="${escapeHtml(notesByDevice[di] || '')}" placeholder="Room / Area description" />` : escapeHtml(notesByDevice[di] || '—')}</td></tr>`;
        })
        .join('')}</tbody>
      </table></div></section></div>`;
  }

  function viewAlarms() {
    const activeCards = state.alarms.length
      ? state.alarms
          .map(
            (a) => `
        <div class="dash-alarm-card dash-alarm-card--active">
          <div>
            <strong>${escapeHtml(a.message || a.detail || 'Alarm')}</strong>
            <p class="dash-small-note">${escapeHtml(a.pointId || '')} · ${escapeHtml(a.kind || '')}</p>
          </div>
          <div class="dash-alarm-meta">${escapeHtml(a.triggeredAt || a.ts || '')}<br /><span class="dash-small-note">value: ${escapeHtml(String(a.valueAtOpen ?? ''))}</span></div>
        </div>`
          )
          .join('')
      : '<p class="dash-small-note">No active alarms.</p>';

    const hist = state.alarmHistory || [];
    const byPoint = new Map();
    hist.forEach((h) => {
      const pid = h.pointId || '';
      if (!byPoint.has(pid)) byPoint.set(pid, []);
      byPoint.get(pid).push(h);
    });
    const pointLabel = (pid) => {
      const s = String(pid || '');
      if (s.startsWith('device:')) {
        const n = s.slice('device:'.length);
        return `Device ${n} (BACnet)`;
      }
      const p = state.points.find((x) => String(x.pointId) === String(pid));
      return p ? p.label || pid : pid;
    };
    const auditBlocks = Array.from(byPoint.entries())
      .sort((a, b) => {
        const ta = Math.max(...(a[1] || []).map((x) => Number(x.openedTs) || 0));
        const tb = Math.max(...(b[1] || []).map((x) => Number(x.openedTs) || 0));
        return tb - ta;
      })
      .map(([pid, rows]) => {
        const sorted = [...rows].sort((x, y) => Number(y.openedTs) - Number(x.openedTs));
        const inner = sorted
          .map((r) => {
            const out = r.clearedAt ? escapeHtml(r.clearedAt) : '— still active —';
            const dur = r.durationSec != null ? `${r.durationSec}s` : '—';
            return `<tr><td>${escapeHtml(r.kind || '')}</td><td>${escapeHtml(r.message || '')}</td><td>${escapeHtml(
              r.openedAt || ''
            )}</td><td>${out}</td><td>${escapeHtml(dur)}</td><td>${escapeHtml(String(r.valueOpen ?? ''))}</td><td>${escapeHtml(
              String(r.valueClear ?? '')
            )}</td></tr>`;
          })
          .join('');
        return `<details class="dash-alarm-audit-group" open>
          <summary class="dash-alarm-audit-summary"><strong>${escapeHtml(pointLabel(pid))}</strong> <span class="dash-small-note">${escapeHtml(
          pid
        )}</span> · ${sorted.length} event(s)</summary>
          <div class="dash-table-wrap dash-alarm-audit-table">
            <table class="dash-table dash-table--compact">
              <thead><tr><th>Kind</th><th>Message</th><th>In alarm</th><th>Cleared</th><th>Duration</th><th>Value @ in</th><th>Value @ clear</th></tr></thead>
              <tbody>${inner}</tbody>
            </table>
          </div>
        </details>`;
      })
      .join('');

    return `<div class="dash-view-inner">
      <section class="panel">
        <div class="dash-panel-head"><h2>Active alarms</h2><span>${state.alarms.length}</span></div>
        <p class="dash-small-note">Conditions are evaluated when BACnet values refresh (polling read-now / read paths). Device-offline uses the supervisory “no successful response” timer. History is stored in SQLite (<code>alarm_events</code>).</p>
        <div class="dash-alarm-list">${activeCards}</div>
      </section>
      <section class="panel" style="margin-top:1rem">
        <div class="dash-panel-head"><h2>Alarm audit trail</h2><span>${hist.length} segment(s)</span></div>
        <p class="dash-small-note">Grouped by point: each row is one in-alarm segment (cleared timestamp when the condition returned to normal).</p>
        ${auditBlocks || '<p class="dash-small-note">No alarm history yet.</p>'}
      </section>
    </div>`;
  }

  function viewNotifications() {
    const rows = state.notifications.length
      ? state.notifications.map((n) => `<div class="dash-config-row"><span>${escapeHtml(n.ts || '')}</span><span>${escapeHtml([n.channel, n.detail].filter(Boolean).join(' · '))}</span></div>`).join('')
      : '<p class="dash-small-note">No notification entries.</p>';
    return `<div class="dash-view-inner"><section class="panel"><div class="dash-panel-head"><h2>Notifications</h2><span>${state.notifications.length}</span></div><div class="dash-config-stack">${rows}</div></section></div>`;
  }

  function viewSchedulePlaceholder() {
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head"><h2>Schedule</h2><span>Editor panel</span></div>
          <p class="dash-small-note">The weekly schedule grid is in the main <strong>Schedule</strong> workspace (sidebar). This placeholder keeps the dashboard route in sync when that panel is open so navigation logs and refresh stay consistent.</p>
        </section>
      </div>`;
  }

  function paint() {
    if (!mountEl) return;
    const viewMap = {
      overview: viewOverview,
      discovery: viewDiscovery,
      devices: viewDevices,
      points: viewPoints,
      wiresheet: () => (window.DiyBasWiresheet ? window.DiyBasWiresheet.render(state) : '<p class="dash-small-note">Wire Sheet module unavailable.</p>'),
      builder: viewBuilder,
      trends: viewTrends,
      alarms: viewAlarms,
      notifications: viewNotifications,
      dockerlogs: viewDockerLogs,
      schedule: viewSchedulePlaceholder,
    };
    const fn = viewMap[state.route] || viewOverview;
    if (typeof console !== 'undefined' && console.info) {
      console.info('[diy-bas][dash] paint', {
        route: state.route,
        devices: state.devices?.length ?? 0,
        points: state.points?.length ?? 0,
        wiresheetLoaded: typeof window !== 'undefined' && !!window.DiyBasWiresheet,
        pointsTreeLoaded: typeof window !== 'undefined' && !!window.DiyBasPointsTree,
      });
    }
    mountEl.innerHTML = feedbackBannerHtml() + fn();
    renderTrendPlotly();
    const trendPre = mountEl.querySelector('#trend-diag-pre');
    if (trendPre) trendPre.textContent = state.trendDiagText || trendDiagBuf.join('\n');
    bindEvents();
    bindPointsTree();
    bindPointsToolbar();
    bindPointsAlarmToolbar();
    bindDockerLogs();
    bindTrendLive();
    bindTrendExplorer();
    bindDevicesContextMenu();
  }

  function bindPointsTree() {
    if (!mountEl || state.route !== 'points' || !window.DiyBasPointsTree) return;
    window.DiyBasPointsTree.bindContextMenu(mountEl, {
      canConfigureAlarms: isIntegrator(),
      canBacnetWrite: canBulkPoints(),
      pointOverrideIds: state.pointPri8OverrideIds || {},
      getPoint: (pointId) => state.points.find((p) => String(p.pointId) === String(pointId)) || null,
      onReadPointNow: async (pointId) => {
        try {
          const r = await pollReadNowApi([pointId]);
          logTab('read one point', { pointId, read: r.read, errors: (r.errors && r.errors.length) || 0 });
          await refresh();
          setFeedback(`Read ${pointId}: ${r.read} ok, ${(r.errors && r.errors.length) || 0} error(s).`, r.errors && r.errors.length ? 'err' : 'ok');
        } catch (err) {
          const msg = String(err && err.message ? err.message : err);
          if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][points]', msg);
          setFeedback(`Read failed: ${msg}`, 'err');
        }
        state.route = 'points';
        paint();
      },
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
        try {
          await fetchJson(`${state.apiBase}/polling/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items }),
          });
          logTab('polling saved', { pointId, enabled });
          await refresh();
          setFeedback(enabled ? 'Polling updated.' : 'Polling off; saved.', 'ok');
        } catch (err) {
          const msg = String(err && err.message ? err.message : err);
          logTab('polling save failed', msg);
          if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][points]', msg);
          setFeedback(`Polling save failed: ${msg}`, 'err');
        }
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
        try {
          await fetchJson(`${state.apiBase}/polling/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items }),
          });
          logTab('polling preset saved', { pointId, intervalSec });
          let readLine = '';
          try {
            const r = await pollReadNowApi([pointId]);
            readLine = ` Read BACnet: ${r.read}/${r.attempted} (${(r.errors && r.errors.length) || 0} errors).`;
          } catch (re) {
            readLine = ` Instant read failed: ${String(re && re.message ? re.message : re)}.`;
          }
          await refresh();
          setFeedback(`Polling ${intervalSec}s saved.${readLine}`, 'ok');
        } catch (err) {
          const msg = String(err && err.message ? err.message : err);
          logTab('polling preset failed', msg);
          if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][points]', msg);
          setFeedback(`Polling save failed: ${msg}`, 'err');
        }
        state.route = 'points';
        paint();
      },
      onConfigureAlarm: async (pointId) => {
        if (!isIntegrator()) return;
        const p = state.points.find((x) => String(x.pointId) === String(pointId));
        if (p && inferPointAlarmKind(p) === 'bool') {
          setFeedback(
            'Status vs command: select an even number of points in order (status, command, …), then use **Motor status vs command** on the toolbar.',
            'err'
          );
          state.route = 'points';
          paint();
          return;
        }
        openAlarmThresholdModal([pointId]);
      },
      onDeletePoint: async (pointId) => {
        if (!isIntegrator()) return;
        try {
          await fetchJson(`${state.apiBase}/points/${encodeURIComponent(pointId)}`, { method: 'DELETE' });
          logTab('point deleted', { pointId });
          await refresh();
          setFeedback('Point removed.', 'ok');
        } catch (err) {
          const msg = String(err && err.message ? err.message : err);
          logTab('point delete failed', msg);
          if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][points]', msg);
          setFeedback(`Delete failed: ${msg}`, 'err');
        }
        state.route = 'points';
        paint();
      },
      onBacnetOverride: async (pointId) => {
        if (!canBulkPoints()) return;
        const raw = window.prompt('Override at priority 8 — present-value (number, true/false, or text):', '');
        if (raw === null) return;
        let value = raw.trim();
        try {
          if (/^(true|false|null)$/i.test(value)) value = JSON.parse(value.toLowerCase());
          else if (/^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(value)) value = Number(value);
        } catch (_) {}
        try {
          await fetchJson(`${state.apiBase}/points/write`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pointId, action: 'override', value }),
          });
          state.pointPri8OverrideIds = { ...(state.pointPri8OverrideIds || {}), [pointId]: true };
          logTab('bacnet override', { pointId });
          await refresh();
          setFeedback('Override written at priority 8.', 'ok');
        } catch (err) {
          setFeedback(String(err && err.message ? err.message : err), 'err');
        }
        state.route = 'points';
        paint();
      },
      onBacnetSet: async (pointId) => {
        if (!canBulkPoints()) return;
        const raw = window.prompt('Set present-value (default priority — number, true/false, or text):', '');
        if (raw === null) return;
        let value = raw.trim();
        try {
          if (/^(true|false|null)$/i.test(value)) value = JSON.parse(value.toLowerCase());
          else if (/^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(value)) value = Number(value);
        } catch (_) {}
        try {
          await fetchJson(`${state.apiBase}/points/write`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pointId, action: 'set', value }),
          });
          logTab('bacnet set', { pointId });
          await refresh();
          setFeedback('Set (default priority) written.', 'ok');
        } catch (err) {
          setFeedback(String(err && err.message ? err.message : err), 'err');
        }
        state.route = 'points';
        paint();
      },
      onBacnetRelease: async (pointId) => {
        if (!canBulkPoints()) return;
        if (!window.confirm('Release priority 8 (write null at priority 8)?')) return;
        try {
          await fetchJson(`${state.apiBase}/points/write`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pointId, action: 'release' }),
          });
          const next = { ...(state.pointPri8OverrideIds || {}) };
          delete next[pointId];
          state.pointPri8OverrideIds = next;
          logTab('bacnet release p8', { pointId });
          await refresh();
          setFeedback('Priority 8 released.', 'ok');
        } catch (err) {
          setFeedback(String(err && err.message ? err.message : err), 'err');
        }
        state.route = 'points';
        paint();
      },
    });
    mountEl.querySelectorAll('.points-tree-alarm-info').forEach((btn) => {
      btn.addEventListener('click', (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        const pid = btn.getAttribute('data-point-id');
        if (pid) openPointAlarmDetailModal(pid);
      });
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
      try {
        await fetchJson(`${state.apiBase}/devices/${deviceInstance}`, { method: 'DELETE' });
        logTab('device deleted', { deviceInstance });
        await refresh();
        setFeedback(`Device ${deviceInstance} and its points removed.`, 'ok');
      } catch (err) {
        const msg = String(err && err.message ? err.message : err);
        logTab('device delete failed', msg);
        if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][devices]', msg);
        setFeedback(`Delete failed: ${msg}`, 'err');
      }
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

  function pointsPollingItemsPayload() {
    return state.points.map((p) => ({
      pointId: p.pointId,
      enabled: !!p.pollingEnabled,
      intervalSec: Number(p.intervalSec || 30),
      deviceInstance: Number(p.deviceInstance || 0),
      objectIdentifier: p.objectIdentifier || '',
      propertyIdentifier: p.propertyIdentifier || 'present-value',
      label: p.label || '',
    }));
  }

  function inferPointAlarmKind(p) {
    const oi = String(p.objectIdentifier || '').toLowerCase();
    if (
      /^(binary-input|binary-output|binary-value|multi-state-input|multi-state-value|multi-state-output)/.test(oi)
    ) {
      return 'bool';
    }
    if (/^(analog-input|analog-output|analog-value|integer-value|integer-input|integer-output)/.test(oi)) {
      return 'numeric';
    }
    if (typeof p.value === 'boolean') return 'bool';
    return 'numeric';
  }

  function closeAlarmModals() {
    if (closeAlarmModals._esc) {
      document.removeEventListener('keydown', closeAlarmModals._esc);
      closeAlarmModals._esc = null;
    }
    [
      'points-alarm-threshold-overlay',
      'points-alarm-cross-overlay',
      'points-alarm-runtime-overlay',
      'points-alarm-modal-overlay',
      'points-alarm-point-detail-overlay',
    ].forEach((id) => {
      document.getElementById(id)?.remove();
    });
  }

  function alarmKindUiLabel(kind) {
    const k = String(kind || '');
    const m = {
      threshold_low: 'Low limit',
      threshold_high: 'High limit',
      bool_mismatch: 'Binary mismatch',
      cross_mismatch: 'Status vs command',
      device_offline: 'Device offline',
    };
    return m[k] || k || 'Alarm';
  }

  function openPointAlarmDetailModal(pointId) {
    closeAlarmModals();
    const p = state.points.find((x) => String(x.pointId) === String(pointId));
    if (!p || !p.inAlarm) {
      setFeedback('No active alarm on this point (try refreshing).', 'err');
      return;
    }
    const title = escapeHtml(p.label || p.objectIdentifier || pointId);
    const details = Array.isArray(p.alarmDetails) ? p.alarmDetails : [];
    const body =
      details.length > 0
        ? `<ul style="margin:0;padding:0">${details
            .map((d) => {
              const lbl = escapeHtml(alarmKindUiLabel(d.kind));
              const msg = escapeHtml(d.message || '—');
              const opened = d.openedAt
                ? `<div class="dash-small-note">Opened: ${escapeHtml(d.openedAt)}</div>`
                : '';
              const vv = d.valueAtOpen
                ? `<div class="dash-small-note">Snapshot: <code>${escapeHtml(d.valueAtOpen)}</code></div>`
                : '';
              return `<li class="point-alarm-detail-item"><div><strong>${lbl}</strong><span class="point-alarm-detail-state">active</span></div><div>${msg}</div>${opened}${vv}</li>`;
            })
            .join('')}</ul>`
        : `<p class="dash-small-note">${escapeHtml(p.alarmSummary || 'In alarm')}</p>`;
    const overlay = document.createElement('div');
    overlay.id = 'points-alarm-point-detail-overlay';
    overlay.className = 'dash-modal-overlay';
    overlay.innerHTML = `
      <div class="dash-modal" role="dialog" aria-modal="true" aria-labelledby="point-alarm-detail-title">
        <div class="dash-modal-head">
          <h2 id="point-alarm-detail-title">Alarm on point</h2>
          <button type="button" class="btn btn-sm" data-act="alarm-modal-close" aria-label="Close">✕</button>
        </div>
        <div class="dash-modal-body">
          <p><strong>${title}</strong> <span class="dash-small-note">(${escapeHtml(String(pointId))})</span></p>
          ${body}
          <p class="dash-small-note" style="margin-top:.75rem">Open alarms clear automatically when the condition clears. Use the Alarms tab for history.</p>
          <div class="dash-modal-actions">
            <button type="button" class="btn primary" data-act="alarm-modal-close">Close</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const finish = () => closeAlarmModals();
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) finish();
    });
    overlay.querySelectorAll('[data-act="alarm-modal-close"]').forEach((b) => {
      b.addEventListener('click', finish);
    });
    closeAlarmModals._esc = (ev) => {
      if (ev.key === 'Escape') finish();
    };
    document.addEventListener('keydown', closeAlarmModals._esc);
  }

  function _alarmRuleBaseDisabled(p) {
    const pt = p && p.objectIdentifier != null && inferPointAlarmKind(p) === 'bool' ? 'bool' : 'numeric';
    return {
      pointId: p.pointId,
      pointType: pt,
      enabled: false,
      ruleKind: 'threshold',
      comparePointId: '',
      compareOperator: 'eq',
      lowThreshold: null,
      highThreshold: null,
      expectedBool: null,
      boolDelaySec: 0,
      delaySec: 0,
      deadband: 0,
      notes: 'disabled (bulk)',
    };
  }

  function openAlarmThresholdModal(pointIds) {
    closeAlarmModals();
    const ids = [...new Set((pointIds || []).map(String).filter(Boolean))];
    const rows = ids
      .map((id) => state.points.find((p) => String(p.pointId) === id))
      .filter(Boolean);
    if (!rows.length) {
      setFeedback('No matching points for alarm setup.', 'err');
      paint();
      return;
    }
    const preview = rows
      .map((p) => {
        const k = inferPointAlarmKind(p);
        return `<tr><td>${escapeHtml(p.label || p.pointId)}</td><td class="dash-small-note">${escapeHtml(p.pointId)}</td><td>${escapeHtml(
          k
        )}</td><td>${escapeHtml(formatNumericForDisplay(p.value) ?? String(p.value ?? '—'))}</td></tr>`;
      })
      .join('');
    const overlay = document.createElement('div');
    overlay.id = 'points-alarm-threshold-overlay';
    overlay.className = 'dash-modal-overlay';
    overlay.innerHTML = `
      <div class="dash-modal" role="dialog" aria-modal="true" aria-labelledby="points-alarm-threshold-title">
        <div class="dash-modal-head">
          <h2 id="points-alarm-threshold-title">High / low alarms</h2>
          <button type="button" class="btn btn-sm" data-act="alarm-modal-close" aria-label="Close">✕</button>
        </div>
        <div class="dash-modal-body">
          <p class="dash-small-note">${rows.length} point(s). <strong>Analog limits only</strong> (numeric BACnet types). Use <strong>Motor status vs command</strong> for binary vs normal or status vs command cross-checks.</p>
          <div class="dash-table-wrap" style="max-height:180px;overflow:auto;margin-bottom:.75rem">
            <table class="dash-table dash-table--compact"><thead><tr><th>Label</th><th>Point ID</th><th>Inferred</th><th>Current value</th></tr></thead><tbody>${preview}</tbody></table>
          </div>
          <fieldset class="dash-modal-fieldset">
            <legend class="dash-small-note">Rule type</legend>
            <label><input type="radio" name="alarm-threshold-mode" value="numeric" checked /> High / low thresholds</label>
            <label style="margin-left:.75rem"><input type="radio" name="alarm-threshold-mode" value="off" /> Turn off alarm rules</label>
          </fieldset>
          <div id="alarm-threshold-numeric-fields" class="dash-modal-grid">
            <label>Low limit <input class="control" id="alarm-threshold-low" type="text" placeholder="blank = none" /></label>
            <label>High limit <input class="control" id="alarm-threshold-high" type="text" placeholder="blank = none" /></label>
            <label>Deadband <input class="control" id="alarm-threshold-dead" type="number" step="0.01" value="1" /></label>
          </div>
          <label class="dash-modal-grid" style="margin-top:.5rem">Alarm delay (seconds)
            <input class="control" id="alarm-threshold-delay" type="number" min="0" max="86400" value="30" />
          </label>
          <p class="dash-small-note">Default 30s: condition must hold before a low/high alarm opens.</p>
          <p class="dash-small-note" id="alarm-threshold-skip-note"></p>
          <div class="dash-modal-actions">
            <button type="button" class="btn" data-act="alarm-modal-close">Cancel</button>
            <button type="button" class="btn primary" data-act="alarm-threshold-apply">Save rules</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const syncMode = () => {
      const mode = overlay.querySelector('input[name="alarm-threshold-mode"]:checked')?.value || 'numeric';
      const num = overlay.querySelector('#alarm-threshold-numeric-fields');
      if (num) num.hidden = mode !== 'numeric';
    };
    overlay.querySelectorAll('input[name="alarm-threshold-mode"]').forEach((r) => {
      r.addEventListener('change', syncMode);
    });
    syncMode();

    const finish = () => closeAlarmModals();
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) finish();
    });
    overlay.querySelectorAll('[data-act="alarm-modal-close"]').forEach((b) => {
      b.addEventListener('click', finish);
    });

    overlay.querySelector('[data-act="alarm-threshold-apply"]')?.addEventListener('click', async () => {
      const mode = overlay.querySelector('input[name="alarm-threshold-mode"]:checked')?.value || 'numeric';
      const delaySec = Math.max(0, Math.min(86400, Number(overlay.querySelector('#alarm-threshold-delay')?.value || 30)));
      const items = [];
      let skipped = 0;
      if (mode === 'off') {
        rows.forEach((p) => {
          items.push(_alarmRuleBaseDisabled(p));
        });
      } else {
        const lowRaw = overlay.querySelector('#alarm-threshold-low')?.value?.trim() || '';
        const highRaw = overlay.querySelector('#alarm-threshold-high')?.value?.trim() || '';
        const dead = Number(overlay.querySelector('#alarm-threshold-dead')?.value || 1);
        const low = lowRaw === '' ? null : Number(lowRaw);
        const high = highRaw === '' ? null : Number(highRaw);
        if (low == null && high == null) {
          setFeedback('Set at least one of low or high threshold.', 'err');
          return;
        }
        rows.forEach((p) => {
          if (inferPointAlarmKind(p) !== 'numeric') {
            skipped += 1;
            return;
          }
          items.push({
            pointId: p.pointId,
            pointType: 'numeric',
            enabled: true,
            ruleKind: 'threshold',
            comparePointId: '',
            compareOperator: 'eq',
            lowThreshold: low,
            highThreshold: high,
            expectedBool: null,
            boolDelaySec: delaySec,
            delaySec,
            deadband: dead,
            notes: 'bulk numeric',
          });
        });
      }
      if (!items.length) {
        setFeedback('Nothing to save (all points skipped as incompatible with this rule type).', 'err');
        return;
      }
      const msg = `Save alarm rules for ${items.length} point(s)?${skipped ? ` (${skipped} skipped as wrong type for this mode.)` : ''}`;
      if (!window.confirm(msg)) return;
      try {
        await fetchJson(`${state.apiBase}/alarm-rules`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items }),
        });
        logTab('alarm threshold bulk saved', { count: items.length, skipped });
        finish();
        await refresh();
        setFeedback(`Saved alarm rules for ${items.length} point(s).`, 'ok');
        state.route = 'points';
        paint();
      } catch (err) {
        setFeedback(String(err && err.message ? err.message : err), 'err');
      }
    });

    closeAlarmModals._esc = (ev) => {
      if (ev.key === 'Escape') finish();
    };
    document.addEventListener('keydown', closeAlarmModals._esc);
  }

  /** Checkbox order on Points tab: status, command, status, command, … */
  function openAlarmMotorStatusCommandModal(orderedPointIds) {
    closeAlarmModals();
    const ids = Array.isArray(orderedPointIds)
      ? orderedPointIds.map(String).filter(Boolean)
      : [];
    const rows = ids
      .map((id) => state.points.find((p) => String(p.pointId) === id))
      .filter(Boolean);
    if (!rows.length) {
      setFeedback('No matching points for alarm setup.', 'err');
      paint();
      return;
    }
    const preview = ids
      .map((id, idx) => {
        const p = state.points.find((x) => String(x.pointId) === id);
        if (!p) return '';
        const role = idx % 2 === 0 ? 'Status' : 'Command';
        const pair = Math.floor(idx / 2) + 1;
        const k = inferPointAlarmKind(p);
        return `<tr><td>${escapeHtml(role)} (pair ${pair})</td><td>${escapeHtml(p.label || p.pointId)}</td><td class="dash-small-note">${escapeHtml(
          p.pointId
        )}</td><td>${escapeHtml(k)}</td></tr>`;
      })
      .filter(Boolean)
      .join('');
    const overlay = document.createElement('div');
    overlay.id = 'points-alarm-cross-overlay';
    overlay.className = 'dash-modal-overlay';
    overlay.innerHTML = `
      <div class="dash-modal" role="dialog" aria-modal="true" aria-labelledby="points-alarm-motor-title">
        <div class="dash-modal-head">
          <h2 id="points-alarm-motor-title">Motor status vs command</h2>
          <button type="button" class="btn btn-sm" data-act="alarm-modal-close" aria-label="Close">✕</button>
        </div>
        <div class="dash-modal-body">
          <p class="dash-small-note">Use the same <strong>checkbox column</strong> as bulk alarms. Tick points in <strong>order</strong>: <strong>status</strong>, <strong>command</strong>, <strong>status</strong>, <strong>command</strong>, … (an <strong>even</strong> count). The rule is: alarm if <strong>status ≠ command</strong> after values stay mismatched for the hold time below (default 300&nbsp;s).</p>
          <div class="dash-table-wrap" style="max-height:200px;overflow:auto;margin-bottom:.75rem">
            <table class="dash-table dash-table--compact"><thead><tr><th>Role</th><th>Label</th><th>Point ID</th><th>Inferred</th></tr></thead><tbody>${preview}</tbody></table>
          </div>
          <label style="display:block;margin-bottom:.75rem">Mismatch hold time (seconds)
            <input class="control" id="alarm-motor-mismatch-sec" type="number" min="10" max="86400" value="300" style="max-width:10rem;margin-top:.25rem" />
          </label>
          <p class="dash-small-note" style="margin-top:-0.35rem;margin-bottom:.75rem">Allowed range 10–86400 (saved per rule; engine clamps).</p>
          <fieldset class="dash-modal-fieldset">
            <label><input type="radio" name="alarm-cross-mode" value="apply" checked /> Apply status vs command pairs</label>
            <label style="margin-left:.75rem"><input type="radio" name="alarm-cross-mode" value="off" /> Turn off rules for these points</label>
          </fieldset>
          <div class="dash-modal-actions">
            <button type="button" class="btn" data-act="alarm-modal-close">Cancel</button>
            <button type="button" class="btn primary" data-act="alarm-cross-apply">Save</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);

    const finish = () => closeAlarmModals();
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) finish();
    });
    overlay.querySelectorAll('[data-act="alarm-modal-close"]').forEach((b) => {
      b.addEventListener('click', finish);
    });
    overlay.querySelector('[data-act="alarm-cross-apply"]')?.addEventListener('click', async () => {
      const sub = overlay.querySelector('input[name="alarm-cross-mode"]:checked')?.value || 'apply';
      const items = [];
      if (sub === 'off') {
        const seen = new Set();
        ids.forEach((id) => {
          const p = state.points.find((x) => String(x.pointId) === id);
          if (p && !seen.has(p.pointId)) {
            seen.add(p.pointId);
            items.push(_alarmRuleBaseDisabled(p));
          }
        });
      } else {
        if (ids.length < 2 || ids.length % 2 !== 0) {
          setFeedback('Select an even number of points in checkbox order: status, command, status, command, …', 'err');
          return;
        }
        const rawHold = Number(overlay.querySelector('#alarm-motor-mismatch-sec')?.value);
        const delaySec = Math.max(10, Math.min(86400, Number.isFinite(rawHold) ? Math.floor(rawHold) : 300));
        let skipped = 0;
        for (let i = 0; i < ids.length; i += 2) {
          const statusPid = ids[i];
          const commandPid = ids[i + 1];
          if (!statusPid || !commandPid || statusPid === commandPid) {
            skipped += 1;
            continue;
          }
          const p = state.points.find((x) => String(x.pointId) === statusPid);
          if (!p) {
            skipped += 1;
            continue;
          }
          items.push({
            pointId: statusPid,
            pointType: inferPointAlarmKind(p),
            enabled: true,
            ruleKind: 'cross_compare',
            comparePointId: commandPid,
            compareOperator: 'eq',
            lowThreshold: null,
            highThreshold: null,
            expectedBool: null,
            boolDelaySec: delaySec,
            delaySec,
            deadband: 0,
            notes: 'status vs command',
          });
        }
      }
      if (!items.length) {
        setFeedback('Nothing to save (check pair count and point order).', 'err');
        return;
      }
      const hold =
        sub === 'off'
          ? 0
          : Math.max(10, Math.min(86400, Math.floor(Number(overlay.querySelector('#alarm-motor-mismatch-sec')?.value) || 300)));
      const msg =
        sub === 'off'
          ? `Turn off alarm rules for ${items.length} point(s)?`
          : `Save ${items.length} status-vs-command rule(s) (${hold}s mismatch hold, alarm when status ≠ command)?`;
      if (!window.confirm(msg)) return;
      try {
        await fetchJson(`${state.apiBase}/alarm-rules`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items }),
        });
        logTab('alarm motor pairs saved', { count: items.length });
        finish();
        await refresh();
        setFeedback(sub === 'off' ? `Rules cleared for ${items.length} point(s).` : `Saved ${items.length} status vs command rule(s).`, 'ok');
        state.route = 'points';
        paint();
      } catch (err) {
        setFeedback(String(err && err.message ? err.message : err), 'err');
      }
    });
    closeAlarmModals._esc = (ev) => {
      if (ev.key === 'Escape') finish();
    };
    document.addEventListener('keydown', closeAlarmModals._esc);
  }

  function openAlarmRuntimeModal() {
    closeAlarmModals();
    const sec = Math.max(60, Math.min(86400, Number(state.alarmSettings?.deviceOfflineSec || 300)));
    const overlay = document.createElement('div');
    overlay.id = 'points-alarm-runtime-overlay';
    overlay.className = 'dash-modal-overlay';
    overlay.innerHTML = `
      <div class="dash-modal" role="dialog" aria-modal="true" aria-labelledby="points-alarm-runtime-title">
        <div class="dash-modal-head">
          <h2 id="points-alarm-runtime-title">Device offline timing</h2>
          <button type="button" class="btn btn-sm" data-act="alarm-modal-close" aria-label="Close">✕</button>
        </div>
        <div class="dash-modal-body">
          <p class="dash-small-note">If a BACnet device has polling-enabled points and no successful read for this many seconds, a <code>device_offline</code> alarm is raised for that device. Timer resets on any successful read for that device instance.</p>
          <label>Device offline after (seconds)
            <input class="control" id="alarm-runtime-offline-sec" type="number" min="60" max="86400" value="${sec}" />
          </label>
          <p class="dash-small-note">Allowed range 60–86400 (clamped on save).</p>
          <div class="dash-modal-actions">
            <button type="button" class="btn" data-act="alarm-modal-close">Cancel</button>
            <button type="button" class="btn primary" data-act="alarm-runtime-apply">Save</button>
          </div>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    const finish = () => closeAlarmModals();
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) finish();
    });
    overlay.querySelectorAll('[data-act="alarm-modal-close"]').forEach((b) => {
      b.addEventListener('click', finish);
    });
    overlay.querySelector('[data-act="alarm-runtime-apply"]')?.addEventListener('click', async () => {
      const raw = Number(overlay.querySelector('#alarm-runtime-offline-sec')?.value || 300);
      const deviceOfflineSec = Math.max(60, Math.min(86400, raw));
      try {
        await fetchJson(`${state.apiBase}/alarm-settings`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ deviceOfflineSec }),
        });
        state.alarmSettings = { ...state.alarmSettings, deviceOfflineSec };
        logTab('alarm runtime saved', { deviceOfflineSec });
        finish();
        setFeedback(`Device offline threshold saved (${deviceOfflineSec}s).`, 'ok');
        state.route = 'points';
        paint();
      } catch (err) {
        setFeedback(String(err && err.message ? err.message : err), 'err');
      }
    });
    closeAlarmModals._esc = (ev) => {
      if (ev.key === 'Escape') finish();
    };
    document.addEventListener('keydown', closeAlarmModals._esc);
  }

  function pickPointsTreeIdsDomOrder() {
    if (!mountEl) return [];
    return Array.from(mountEl.querySelectorAll('.points-tree-pick:checked'))
      .map((c) => c.getAttribute('data-point-id'))
      .filter(Boolean);
  }

  function bindPointsAlarmToolbar() {
    if (!mountEl || state.route !== 'points' || !isIntegrator()) return;
    const pickIds = () => {
      const seen = new Set();
      const out = [];
      pickPointsTreeIdsDomOrder().forEach((id) => {
        if (id && !seen.has(id)) {
          seen.add(id);
          out.push(id);
        }
      });
      return out;
    };
    const th = mountEl.querySelector('#points-bulk-alarm-threshold');
    if (th) {
      th.onclick = () => {
        const ids = pickIds();
        if (!ids.length) {
          setFeedback('Select at least one point (checkbox column) for alarm setup.', 'err');
          paint();
          return;
        }
        openAlarmThresholdModal(ids);
      };
    }
    const cr = mountEl.querySelector('#points-bulk-alarm-cross');
    if (cr) {
      cr.onclick = () => {
        const ids = pickPointsTreeIdsDomOrder();
        if (ids.length < 2) {
          setFeedback('Select at least two points in order: status, then command (repeat for more pairs).', 'err');
          paint();
          return;
        }
        if (ids.length % 2 !== 0) {
          setFeedback('Select an even number of points (pairs: status, command, …) in checkbox list order.', 'err');
          paint();
          return;
        }
        openAlarmMotorStatusCommandModal(ids);
      };
    }
    const rt = mountEl.querySelector('#points-bulk-alarm-runtime');
    if (rt) {
      rt.onclick = () => {
        openAlarmRuntimeModal();
      };
    }
    const clr = mountEl.querySelector('#points-bulk-alarm-clear');
    if (clr) {
      clr.onclick = async () => {
        const ids = pickIds();
        if (!ids.length) {
          setFeedback('Select points to clear alarm rules.', 'err');
          paint();
          return;
        }
        if (!window.confirm(`Turn off alarm rules for ${ids.length} point(s)?`)) return;
        const items = ids.map((id) => {
          const p = state.points.find((x) => String(x.pointId) === String(id));
          return _alarmRuleBaseDisabled(p || { pointId: id });
        });
        try {
          await fetchJson(`${state.apiBase}/alarm-rules`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ items }),
          });
          await refresh();
          setFeedback(`Alarm rules disabled for ${ids.length} point(s).`, 'ok');
        } catch (err) {
          setFeedback(String(err && err.message ? err.message : err), 'err');
        }
        state.route = 'points';
        paint();
      };
    }
  }

  function bindPointsToolbar() {
    if (!mountEl || state.route !== 'points' || !canBulkPoints()) return;
    const readIv = () => Number(mountEl.querySelector('#points-bulk-interval')?.value || 30);

    mountEl.querySelector('#points-select-all')?.addEventListener('click', () => {
      mountEl.querySelectorAll('.points-tree-pick').forEach((c) => {
        c.checked = true;
      });
    });
    mountEl.querySelector('#points-select-none')?.addEventListener('click', () => {
      mountEl.querySelectorAll('.points-tree-pick').forEach((c) => {
        c.checked = false;
      });
    });

    mountEl.querySelector('#points-bulk-apply-selected')?.addEventListener('click', async () => {
      const ids = Array.from(mountEl.querySelectorAll('.points-tree-pick:checked'))
        .map((c) => c.getAttribute('data-point-id'))
        .filter(Boolean);
      if (!ids.length) {
        setFeedback('Select at least one point (checkbox column).', 'err');
        paint();
        return;
      }
      const sec = readIv();
      state.points.forEach((p) => {
        if (ids.includes(p.pointId)) {
          p.pollingEnabled = true;
          p.intervalSec = sec;
        }
      });
      try {
        await fetchJson(`${state.apiBase}/polling/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items: pointsPollingItemsPayload() }),
        });
        const r = await pollReadNowApi(ids);
        logTab('bulk polling selected', { count: ids.length, sec, read: r.read });
        await refresh();
        setFeedback(
          `Bulk: ${ids.length} point(s) at ${sec}s. BACnet read ${r.read}/${r.attempted} (${(r.errors && r.errors.length) || 0} errors).`,
          r.errors && r.errors.length ? 'err' : 'ok',
        );
      } catch (err) {
        const msg = String(err && err.message ? err.message : err);
        if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][points]', msg);
        setFeedback(msg, 'err');
      }
      state.route = 'points';
      paint();
    });

    mountEl.querySelector('#points-bulk-apply-all')?.addEventListener('click', async () => {
      if (!state.points.length) return;
      const sec = readIv();
      if (!window.confirm(`Enable polling at ${sec}s for all ${state.points.length} points?`)) return;
      state.points = state.points.map((p) => ({ ...p, pollingEnabled: true, intervalSec: sec }));
      try {
        await fetchJson(`${state.apiBase}/polling/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ items: pointsPollingItemsPayload() }),
        });
        const r = await pollReadNowApi([]);
        logTab('bulk polling all', { sec, read: r.read, attempted: r.attempted });
        await refresh();
        setFeedback(`All ${state.points.length} point(s) set to ${sec}s. Read ${r.read} BACnet value(s) for polling-on rows.`, 'ok');
      } catch (err) {
        const msg = String(err && err.message ? err.message : err);
        setFeedback(msg, 'err');
      }
      state.route = 'points';
      paint();
    });

    mountEl.querySelector('#points-read-selected')?.addEventListener('click', async () => {
      const ids = Array.from(mountEl.querySelectorAll('.points-tree-pick:checked'))
        .map((c) => c.getAttribute('data-point-id'))
        .filter(Boolean);
      if (!ids.length) {
        setFeedback('Select points to read (checkboxes).', 'err');
        paint();
        return;
      }
      try {
        const r = await pollReadNowApi(ids);
        logTab('read selected', r);
        await refresh();
        setFeedback(`BACnet read: ${r.read}/${r.attempted} ok (${(r.errors && r.errors.length) || 0} errors).`, r.errors && r.errors.length ? 'err' : 'ok');
      } catch (err) {
        setFeedback(String(err && err.message ? err.message : err), 'err');
      }
      state.route = 'points';
      paint();
    });

    mountEl.querySelector('#points-read-all-polling')?.addEventListener('click', async () => {
      try {
        const r = await pollReadNowApi([]);
        logTab('read all polling', r);
        await refresh();
        setFeedback(`BACnet read (polling-on): ${r.read}/${r.attempted} (${(r.errors && r.errors.length) || 0} errors).`, r.errors && r.errors.length ? 'err' : 'ok');
      } catch (err) {
        setFeedback(String(err && err.message ? err.message : err), 'err');
      }
      state.route = 'points';
      paint();
    });
  }

  async function refreshDockerContainersIfNeeded() {
    if (state.dockerLogs.containers && state.dockerLogs.containers.length) return;
    try {
      const d = await fetchJson(`${state.apiBase}/docker/containers`);
      state.dockerLogs.containers = Array.isArray(d.items) ? d.items : [];
      state.dockerLogs.error = '';
    } catch (err) {
      state.dockerLogs.containers = [
        { id: 'diy-bas', label: 'diy-bas' },
        { id: 'diy-bas-caddy', label: 'diy-bas-caddy' },
        { id: 'diy-bacnet-server', label: 'diy-bacnet-server' },
      ];
      state.dockerLogs.error = `Container list fallback (${String(err && err.message ? err.message : err)}).`;
    }
  }

  async function loadDockerLogsDisplay() {
    const sel = mountEl?.querySelector('#docker-container');
    const linesEl = mountEl?.querySelector('#docker-lines');
    if (!sel) return;
    state.dockerLogs.container = sel.value || 'diy-bas';
    state.dockerLogs.lines = Math.max(50, Math.min(Number(linesEl?.value || 400), 5000));
    state.dockerLogs.loading = true;
    state.dockerLogs.error = '';
    paint();
    try {
      const u = `${state.apiBase}/docker/logs?container=${encodeURIComponent(state.dockerLogs.container)}&lines=${state.dockerLogs.lines}`;
      const data = await fetchJson(u);
      state.dockerLogs.text = typeof data.text === 'string' ? data.text : '';
    } catch (err) {
      let msg = String(err && err.message ? err.message : err);
      if (/503/.test(msg) && /docker/i.test(msg)) {
        msg =
          'Docker CLI is not available in this container (common without docker.sock or on a minimal Pi image). Mount the Docker socket read-only or run where docker is installed; a current Ubuntu + Compose host usually resolves this.';
      }
      state.dockerLogs.error = msg;
      state.dockerLogs.text = '';
    } finally {
      state.dockerLogs.loading = false;
      paint();
    }
  }

  function bindDockerLogs() {
    if (!mountEl || state.route !== 'dockerlogs') return;
    mountEl.querySelector('#docker-refresh')?.addEventListener('click', () => void loadDockerLogsDisplay());
    mountEl.querySelector('#docker-container')?.addEventListener('change', (e) => {
      const t = e.target;
      state.dockerLogs.container = (t && t.value) || 'diy-bas';
    });
    if (!state.dockerLogs.containersFetched) {
      void refreshDockerContainersIfNeeded().then(() => {
        state.dockerLogs.containersFetched = true;
        paint();
      });
    }
  }

  function closeTrendEventSource() {
    if (trendsStreamReconnectTimer) {
      clearTimeout(trendsStreamReconnectTimer);
      trendsStreamReconnectTimer = null;
    }
    if (trendsEventSource) {
      trendsEventSource.close();
      trendsEventSource = null;
    }
  }

  function stopTrendLive() {
    closeTrendEventSource();
    state.trendsLive = false;
    state.trendStreamStatus = '';
  }

  function trendPointLabelFromId(pid) {
    const p = state.points.find((x) => String(x.pointId) === String(pid));
    return p ? p.label || pid : pid;
  }

  function rebuildTrendsFlatten() {
    const rows = [];
    (state.trendOrder || []).forEach((pid) => {
      (state.trendByPoint[pid] || []).forEach((r) => {
        rows.push({ ...r, pointId: pid });
      });
    });
    rows.sort((a, b) => Number(a.ts) - Number(b.ts));
    state.trends = rows;
  }

  function mergeTrendSamplesForPid(pid, newItems) {
    if (!pid || !Array.isArray(newItems) || !newItems.length) return;
    const cur = state.trendByPoint[pid] || [];
    const byKey = new Map(cur.map((r) => [`${r.ts}:${pid}`, { ...r, pointId: pid }]));
    newItems.forEach((row) => {
      if (!row || row.ts === undefined) return;
      byKey.set(`${row.ts}:${pid}`, { ...row, pointId: pid });
    });
    const now = Math.floor(Date.now() / 1000);
    const win = Number(state.trendsRangeSec) || 86400;
    const minTs = now - win;
    let merged = Array.from(byKey.values())
      .filter((r) => Number(r.ts) >= minTs)
      .sort((a, b) => Number(a.ts) - Number(b.ts));
    const cap = 3500;
    if (merged.length > cap) merged = merged.slice(-cap);
    state.trendByPoint[pid] = merged;
    rebuildTrendsFlatten();
  }

  function maxTrendSampleTs() {
    let m = 0;
    const order = state.trendOrder && state.trendOrder.length ? state.trendOrder : Object.keys(state.trendByPoint || {});
    order.forEach((pid) => {
      (state.trendByPoint[pid] || []).forEach((r) => {
        if (r && Number.isFinite(Number(r.ts)) && Number(r.ts) > m) m = Number(r.ts);
      });
    });
    (state.trends || []).forEach((r) => {
      if (r && Number.isFinite(Number(r.ts)) && Number(r.ts) > m) m = Number(r.ts);
    });
    return m;
  }

  function trendStreamSinceTsParam() {
    const m = maxTrendSampleTs();
    if (m > 0) return m;
    const end = Math.floor(Date.now() / 1000);
    return end - (Number(state.trendsRangeSec) || 86400);
  }

  /** @param {unknown[] | { type?: string, items?: unknown[], series?: Record<string, unknown[]>, pointId?: string }} arg */
  function mergeTrendLiveSamples(arg) {
    if (arg && typeof arg === 'object' && !Array.isArray(arg)) {
      const msg = arg;
      if (msg.type === 'samples' && msg.series && typeof msg.series === 'object') {
        Object.entries(msg.series).forEach(([pid, arr]) => mergeTrendSamplesForPid(pid, arr));
        return;
      }
      if (msg.type === 'samples' && Array.isArray(msg.items) && msg.items.length) {
        const pid = msg.pointId || (state.trendOrder && state.trendOrder[0]) || state.selectedPointId;
        mergeTrendSamplesForPid(pid, msg.items);
        return;
      }
    }
    const items = Array.isArray(arg) ? arg : [];
    if (!items.length) return;
    const pid = (state.trendOrder && state.trendOrder[0]) || state.selectedPointId;
    mergeTrendSamplesForPid(pid, items);
  }

  function updateTrendSampleListDom() {
    const wrap = mountEl?.querySelector('.dash-trend-list');
    if (!wrap) return;
    const trendRows = (state.trends || [])
      .slice(-24)
      .reverse()
      .map((i) => {
        const pid = i.pointId ? `<span class="dash-small-note">${escapeHtml(String(i.pointId))}</span> · ` : '';
        return `<div class="dash-config-row"><span>${pid}${escapeHtml(unixToLabel(i.ts))}</span><span>${escapeHtml(
          formatNumericForDisplay(i.value) ?? '—'
        )}</span></div>`;
      })
      .join('');
    wrap.innerHTML = trendRows || '<p class="dash-small-note">No trend samples in selected range.</p>';
  }

  function setTrendStreamStatus(text) {
    state.trendStreamStatus = String(text || '');
    const el = mountEl?.querySelector('#trend-live-status');
    if (el) {
      el.textContent = state.trendStreamStatus;
      el.hidden = !state.trendStreamStatus;
    }
  }

  function scheduleTrendStreamReconnect(delayMs) {
    if (trendsStreamReconnectTimer) clearTimeout(trendsStreamReconnectTimer);
    trendsStreamReconnectTimer = setTimeout(() => {
      trendsStreamReconnectTimer = null;
      if (state.trendsLive && state.route === 'trends' && mountEl) openTrendEventSource();
    }, delayMs);
  }

  function openTrendEventSource() {
    if (!mountEl || state.route !== 'trends' || !state.trendsLive) return;
    syncTrendSelectedFromDom();
    const ids = (state.trendSelectedIds || []).filter(Boolean).slice(0, 8);
    if (!ids.length) {
      setTrendStreamStatus('Select at least one point to stream.');
      return;
    }
    closeTrendEventSource();
    state.trendOrder = [...ids];
    state.selectedPointId = ids[0];
    const sinceTs = trendStreamSinceTsParam();
    const interval = 3;
    const url =
      ids.length === 1
        ? `${state.apiBase}/trends/stream?pointId=${encodeURIComponent(ids[0])}&interval=${interval}&sinceTs=${sinceTs}`
        : `${state.apiBase}/trends/stream?pointIds=${encodeURIComponent(ids.join(','))}&interval=${interval}&sinceTs=${sinceTs}`;
    setTrendStreamStatus('Live: connecting…');
    trendPushDiag(`SSE open ${url}`);
    const es = new EventSource(url);
    trendsEventSource = es;
    es.addEventListener('message', (ev) => {
      try {
        const msg = JSON.parse(ev.data || '{}');
        if (msg.type === 'hello') {
          trendPushDiag(`SSE hello pointIds=${(msg.pointIds || []).join(',')} sinceTs=${msg.sinceTs}`);
          setTrendStreamStatus(ids.length > 1 ? `Live: watching ${ids.length} series…` : 'Live: watching for new samples…');
          return;
        }
        if (msg.type === 'done') {
          setTrendStreamStatus('Live: segment ended, reconnecting…');
          closeTrendEventSource();
          if (state.trendsLive && state.route === 'trends') scheduleTrendStreamReconnect(400);
          return;
        }
        if (msg.type === 'samples') {
          if (msg.series && typeof msg.series === 'object' && Object.keys(msg.series).length) {
            const sizes = Object.fromEntries(Object.entries(msg.series).map(([k, v]) => [k, Array.isArray(v) ? v.length : 0]));
            trendPushDiag(`SSE samples (multi): ${JSON.stringify(sizes)}`);
            mergeTrendLiveSamples(msg);
          } else if (Array.isArray(msg.items) && msg.items.length) {
            trendPushDiag(`SSE samples (single): pointId=${msg.pointId || ''} n=${msg.items.length}`);
            mergeTrendLiveSamples(msg);
          } else {
            trendPushDiag('SSE samples event with empty payload (no new rows in this poll)');
          }
          renderTrendPlotly();
          updateTrendSampleListDom();
          setTrendStreamStatus(`Live: ${state.trends.length} samples in window`);
        }
      } catch (e) {
        if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][trends-stream]', e);
      }
    });
    es.addEventListener('error', () => {
      trendPushDiag('SSE error event (network, 401, or proxy closed stream) — retrying');
      setTrendStreamStatus('Live: connection error, retrying…');
      closeTrendEventSource();
      if (state.trendsLive && state.route === 'trends') scheduleTrendStreamReconnect(2500);
    });
  }

  function bindTrendLive() {
    if (!mountEl || state.route !== 'trends') return;
    const liveEl = mountEl.querySelector('#trend-live');
    if (liveEl) {
      liveEl.checked = !!state.trendsLive;
      liveEl.onchange = () => {
        state.trendsLive = !!liveEl.checked;
        if (state.trendsLive) {
          openTrendEventSource();
        } else {
          stopTrendLive();
          paint();
        }
      };
    }
    const rangeSel = mountEl.querySelector('#trend-range');
    if (rangeSel) {
      rangeSel.onchange = () => {
        state.trendsRangeSec = Math.max(60, Number(rangeSel.value) || 86400);
      };
    }
    if (state.trendsLive) openTrendEventSource();
  }

  function syncTrendSelectedFromDom() {
    if (!mountEl) return;
    state.trendSelectedIds = Array.from(mountEl.querySelectorAll('.points-trend-pick:checked'))
      .map((c) => c.getAttribute('data-point-id'))
      .filter(Boolean)
      .slice(0, 8);
    const cEl = mountEl.querySelector('#trend-selected-count');
    if (cEl) cEl.textContent = String(state.trendSelectedIds.length);
  }

  function restoreTrendPickerChecks() {
    let ids = (state.trendSelectedIds || []).filter(Boolean).slice(0, 8);
    if (!ids.length && state.selectedPointId) ids = [state.selectedPointId];
    if (!ids.length && state.points && state.points.length) ids = [state.points[0].pointId];
    const want = new Set(ids);
    mountEl?.querySelectorAll('.points-trend-pick').forEach((cb) => {
      cb.checked = want.has(cb.getAttribute('data-point-id'));
    });
    syncTrendSelectedFromDom();
  }

  function bindTrendExplorer() {
    if (!mountEl || state.route !== 'trends') return;
    const pa = mountEl.querySelector('#trend-pick-all');
    if (pa) {
      pa.onclick = () => {
        mountEl.querySelectorAll('.points-trend-pick').forEach((c) => {
          c.checked = true;
        });
        syncTrendSelectedFromDom();
        paint();
      };
    }
    const pn = mountEl.querySelector('#trend-pick-none');
    if (pn) {
      pn.onclick = () => {
        mountEl.querySelectorAll('.points-trend-pick').forEach((c) => {
          c.checked = false;
        });
        syncTrendSelectedFromDom();
        paint();
      };
    }
    mountEl.querySelectorAll('.points-trend-pick').forEach((cb) => {
      cb.addEventListener('change', () => {
        syncTrendSelectedFromDom();
        paint();
      });
    });
    restoreTrendPickerChecks();
  }

  function renderTrendPlotly() {
    if (!mountEl || state.route !== 'trends') return;
    const el = mountEl.querySelector('#plotly-trend');
    if (!el) return;
    if (!window.Plotly) {
      el.innerHTML = '<p class="dash-small-note">Plotly failed to load; trend table still available.</p>';
      trendPushDiag('plotly: window.Plotly missing (check script CDN / network)');
      return;
    }
    const order =
      state.trendOrder && state.trendOrder.length
        ? state.trendOrder
        : Object.keys(state.trendByPoint || {}).filter((k) => (state.trendByPoint[k] || []).length);
    const palette = ['#0d7a5f', '#2563eb', '#b45309', '#9333ea', '#dc2626', '#0891b2', '#4d7c0f', '#92400e'];
    let rawTotal = 0;
    let skippedVal = 0;
    const traces = order.map((pid, i) => {
      const all = state.trendByPoint[pid] || [];
      rawTotal += all.length;
      const rows = all.filter((r) => {
        if (!r || r.ts === undefined) return false;
        if (r.value === undefined) {
          skippedVal += 1;
          return false;
        }
        return true;
      });
      return {
        x: rows.map((r) => unixToIso(r.ts)),
        y: rows.map((r) => {
          const n = Number(r.value);
          return Number.isFinite(n) ? n : null;
        }),
        type: 'scatter',
        mode: 'lines+markers',
        line: { color: palette[i % palette.length], width: 2 },
        marker: { size: 4 },
        name: trendPointLabelFromId(pid),
      };
    });
    const plotted = traces.reduce((n, t) => n + (t.x && t.x.length ? t.x.length : 0), 0);
    const finiteY = traces.reduce((n, t) => n + (t.y || []).filter((v) => v !== null && Number.isFinite(v)).length, 0);
    trendPushDiag(
      `plotly: series=${order.length} rawRows=${rawTotal} plottedRows=${plotted} finiteY=${finiteY} skippedMissingValue=${skippedVal}`
    );
    if (plotted === 0 && rawTotal === 0 && order.length) {
      try {
        window.Plotly.purge(el);
      } catch (e) {
        el.innerHTML = '';
      }
      el.innerHTML =
        '<p class="dash-small-note">No trend samples in SQLite for this time window. Run <strong>Read BACnet &amp; reload</strong> (or Points tab reads) while the BACnet gateway is online so values are recorded, then widen the window if needed.</p>';
      return;
    }
    if (!traces.length) {
      try {
        window.Plotly.purge(el);
      } catch (e) {
        el.innerHTML = '';
      }
      el.innerHTML =
        '<p class="dash-small-note">No series to plot. Select points and click <strong>Load trend</strong>, or use <strong>Read BACnet &amp; reload</strong> to capture samples first.</p>';
      return;
    }
    if (plotted === 0 && rawTotal > 0) {
      try {
        window.Plotly.purge(el);
      } catch (e) {
        el.innerHTML = '';
      }
      el.innerHTML =
        '<p class="dash-small-note">Samples exist but none are plottable on a numeric Y axis (e.g. only non-numeric / enum values). See the table below; check diagnostics for raw counts.</p>';
      return;
    }
    if (finiteY === 0 && plotted > 0) {
      try {
        window.Plotly.purge(el);
      } catch (e) {
        el.innerHTML = '';
      }
      el.innerHTML =
        '<p class="dash-small-note">All sample values are non-numeric in this window (Plotly line chart needs numbers). Boolean points plot as 0/1; pure strings need another chart type later.</p>';
      return;
    }
    const layout = {
      margin: { l: 42, r: 16, t: 12, b: 42 },
      paper_bgcolor: 'transparent',
      plot_bgcolor: 'transparent',
      xaxis: { title: 'Time', type: 'date' },
      yaxis: { title: traces.length > 1 ? 'Value (multi-series)' : 'Value' },
      showlegend: traces.length > 1,
    };
    const safe = (state.trendOrder && state.trendOrder[0]) || state.selectedPointId || 'point';
    const config = {
      responsive: true,
      displaylogo: false,
      toImageButtonOptions: { format: 'png', filename: `trend-${safe}`, height: 600, width: 1000, scale: 1 },
    };
    window.Plotly.react(el, traces, layout, config);
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
          logTab('who-is ok', { count: payload?.count });
          await refresh();
          setFeedback(`Who-Is complete: ${Number(payload?.count || 0)} device(s).`, 'ok');
          state.selectedDiscoveryDevices = (state.devices || [])
            .map((d) => Number(d.deviceInstance || d.instance || d.id))
            .filter((n) => Number.isFinite(n));
          state.route = 'discovery';
          paint();
        } catch (err) {
          const msg = String(err && err.message ? err.message : err);
          state.discoveryError = msg;
          state.discoveryStatus.whois = { state: 'error', message: msg, ts: nowLabel() };
          logTab('who-is failed', msg);
          if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][discovery]', msg);
          setFeedback(`Who-Is failed: ${msg}`, 'err');
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
          logTab('point discovery ok', { totalPoints, devices: selected.length });
          await refresh();
          setFeedback(`Point discovery done: ${totalPoints} point(s).`, 'ok');
          state.route = 'discovery';
          paint();
        } catch (err) {
          const msg = String(err && err.message ? err.message : err);
          state.discoveryError = msg;
          state.discoveryStatus.points = { state: 'error', message: msg, ts: nowLabel() };
          state.discoveryBusyInstance = null;
          logTab('point discovery failed', msg);
          if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][discovery]', msg);
          setFeedback(`Point discovery failed: ${msg}`, 'err');
          state.route = 'discovery';
          paint();
        }
      });
    });
    mountEl.querySelectorAll('[data-act="load-trend"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        try {
          state.trendError = '';
          stopTrendLive();
          syncTrendSelectedFromDom();
          const ids = (state.trendSelectedIds || []).filter(Boolean).slice(0, 8);
          if (!ids.length) {
            setFeedback('Select one or more points in the list above (max 8).', 'err');
            paint();
            return;
          }
          const seconds = Number(mountEl.querySelector('#trend-range')?.value || 86400);
          state.trendsRangeSec = seconds;
          logTab('trend load', { pointIds: ids, seconds });
          await loadTrend(ids, seconds);
          if (typeof console !== 'undefined' && console.info) {
            console.info('[diy-bas][trends]', 'loaded', ids, state.trends?.length || 0, 'samples');
          }
          trendPushDiag(`Load trend button: done series=${ids.length} flatSamples=${state.trends?.length || 0}`);
          setFeedback(`Trend loaded (${ids.length} series, ${state.trends?.length || 0} samples).`, 'ok');
          paint();
        } catch (err) {
          state.trendError = String(err && err.message ? err.message : err);
          if (typeof console !== 'undefined' && console.warn) {
            console.warn('[diy-bas][trends]', state.trendError);
          }
          setFeedback(`Trend load failed: ${state.trendError}`, 'err');
          paint();
        }
      });
    });
    mountEl.querySelectorAll('[data-act="trend-read-bacnet"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        try {
          state.trendError = '';
          stopTrendLive();
          syncTrendSelectedFromDom();
          const ids = (state.trendSelectedIds || []).filter(Boolean).slice(0, 8);
          if (!ids.length) {
            setFeedback('Select one or more points first (checkboxes in the tree).', 'err');
            paint();
            return;
          }
          const seconds = Number(mountEl.querySelector('#trend-range')?.value || 86400);
          state.trendsRangeSec = seconds;
          trendPushDiag(`Read BACnet & reload: POST read-now for ${ids.length} point(s)`);
          const r = await pollReadNowApi(ids);
          trendPushDiag(
            `read-now result read=${r.read} attempted=${r.attempted || ids.length} errors=${(r.errors && r.errors.length) || 0}`
          );
          await loadTrend(ids, seconds);
          setFeedback(
            `BACnet read ${r.read}/${r.attempted || ids.length} ok, trend reloaded (${state.trends?.length || 0} samples in window).`,
            r.errors && r.errors.length ? 'err' : 'ok'
          );
          paint();
        } catch (err) {
          state.trendError = String(err && err.message ? err.message : err);
          trendPushDiag(`Read BACnet & reload FAILED ${state.trendError}`);
          setFeedback(state.trendError, 'err');
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
          logTab('builder invalid json', state.trendError);
          if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][builder]', state.trendError);
          paint();
          return;
        }
        try {
          await fetchJson(`${state.apiBase}/dashboard-layouts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, roleScope: 'all', layout }),
          });
          logTab('layout saved', { name });
          await refresh();
          setFeedback('Dashboard layout saved.', 'ok');
        } catch (err) {
          const msg = String(err && err.message ? err.message : err);
          logTab('layout save failed', msg);
          if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][builder]', msg);
          setFeedback(`Layout save failed: ${msg}`, 'err');
        }
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
        try {
          await fetchJson(`${state.apiBase}/device-notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ deviceInstance, note: el.value || '' }),
          });
          logTab('device note saved', { deviceInstance });
          await refresh();
          setFeedback('Device note saved.', 'ok');
        } catch (err) {
          const msg = String(err && err.message ? err.message : err);
          logTab('device note failed', msg);
          if (typeof console !== 'undefined' && console.warn) console.warn('[diy-bas][devices]', msg);
          setFeedback(`Note save failed: ${msg}`, 'err');
        }
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
          logTab('wiresheet navigate', route);
          state.route = route;
          paint();
        },
        paint,
        apiBase: state.apiBase,
        setFeedback,
      });
    }
  }

  async function loadTrend(pointIds, secondsBack) {
    const raw = Array.isArray(pointIds) ? pointIds : [pointIds];
    const ids = [...new Set(raw.map(String).filter(Boolean))].slice(0, 8);
    if (!ids.length) return;
    const sec = Number(secondsBack || 86400);
    state.trendsRangeSec = sec;
    const endTs = Math.floor(Date.now() / 1000);
    const startTs = endTs - sec;
    state.trendsWindowStartTs = startTs;
    state.trendOrder = [...ids];
    state.trendSelectedIds = [...ids];
    state.selectedPointId = ids[0];
    state.trendByPoint = {};
    trendPushDiag(`GET /trends/query startTs=${startTs} endTs=${endTs} windowSec=${sec} pointIds=${ids.join(',')}`);
    if (ids.length === 1) {
      const qUrl = `${state.apiBase}/trends/query?pointId=${encodeURIComponent(ids[0])}&startTs=${startTs}&endTs=${endTs}&limit=3000`;
      const trend = await fetchJson(qUrl);
      const items = Array.isArray(trend.items) ? trend.items : [];
      state.trendByPoint[ids[0]] = items.map((r) => ({ ...r, pointId: ids[0] }));
      trendPushDiag(
        `trends/query single: returned items=${items.length} diagnostic=${JSON.stringify(trend.diagnostic || {})}`
      );
    } else {
      const qp = encodeURIComponent(ids.join(','));
      const qUrl = `${state.apiBase}/trends/query?pointIds=${qp}&startTs=${startTs}&endTs=${endTs}&limit=4000`;
      const trend = await fetchJson(qUrl);
      const ser = Array.isArray(trend.series) ? trend.series : [];
      ser.forEach((s) => {
        const pid = s.pointId;
        if (!pid) return;
        state.trendByPoint[pid] = (Array.isArray(s.items) ? s.items : []).map((r) => ({ ...r, pointId: pid }));
      });
      trendPushDiag(
        `trends/query multi: series=${ser.length} diagnostic=${JSON.stringify(trend.diagnostic || {})} perSeries=${ser
          .map((s) => `${s.pointId}:${(s.items || []).length}`)
          .join(';')}`
      );
    }
    rebuildTrendsFlatten();
    trendPushDiag(`rebuildTrendsFlatten: total flat rows=${(state.trends || []).length}`);
  }

  async function loadLiveBundle(prefixes) {
    const list = prefixes.length ? prefixes : DEFAULT_API_PREFIXES;
    const emptyList = { items: [] };
    for (const raw of list) {
      const base = raw.replace(/\/$/, '');
      const specs = [
        ['health', `${base}/health`],
        ['devices', `${base}/discovery/devices`],
        ['points', `${base}/points`],
        ['alarms', `${base}/alarms/events`],
        ['notificationLogs', `${base}/notifications/logs`],
        ['pollingConfig', `${base}/polling/config`],
        ['alarmRules', `${base}/alarm-rules`],
        ['alarmSettings', `${base}/alarm-settings`],
        ['deviceNotes', `${base}/device-notes`],
        ['layouts', `${base}/dashboard-layouts`],
        ['wiresheetRules', `${base}/wiresheet/config`],
        ['wiresheetStatus', `${base}/wiresheet/status`],
      ];
      const settled = await Promise.allSettled(specs.map(([, url]) => fetchJson(url)));
      const bundleErrors = [];
      const vals = {};
      settled.forEach((r, i) => {
        const key = specs[i][0];
        if (r.status === 'fulfilled') {
          vals[key] = r.value;
        } else {
          const msg = String(r.reason?.message || r.reason);
          bundleErrors.push(`${key}: ${msg}`);
          if (typeof console !== 'undefined' && console.warn) {
            console.warn('[diy-bas][bundle]', base, key, msg);
          }
        }
      });
      if (!vals.health) {
        if (typeof console !== 'undefined' && console.warn) {
          console.warn('[diy-bas][bundle] no health for prefix', base, bundleErrors);
        }
        continue;
      }
      return {
        ok: true,
        base,
        health: vals.health,
        devices: vals.devices || emptyList,
        points: vals.points || emptyList,
        alarms: vals.alarms || { items: [], history: [] },
        notificationLogs: vals.notificationLogs || emptyList,
        pollingConfig: vals.pollingConfig || emptyList,
        alarmRules: vals.alarmRules || emptyList,
        alarmSettings: vals.alarmSettings || { deviceOfflineSec: 300 },
        deviceNotes: vals.deviceNotes || emptyList,
        layouts: vals.layouts || emptyList,
        wiresheetRules: vals.wiresheetRules || emptyList,
        wiresheetStatus: vals.wiresheetStatus || emptyList,
        bundleErrors,
      };
    }
    return {
      ok: false,
      humanError: 'Could not reach supervisory API (health check failed).',
    };
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
    const prev = state.route;
    if (route !== prev) {
      if (prev === 'trends' && route !== 'trends') {
        closeTrendEventSource();
        state.trendsLive = false;
        state.trendStreamStatus = '';
      }
      clearFeedback();
      if (typeof console !== 'undefined' && console.info) {
        console.info('[diy-bas][tab]', 'navigate', { from: prev, to: route });
      }
    }
    state.route = route;
    paint();
  }

  async function refresh(options = {}) {
    const prefixes = resolvedPrefixes(options);
    logTab('refresh start', { prefixes });
    clearFeedback();
    state.bundleErrors = [];
    state.bacnetLink = { ...(state.bacnetLink || {}), phase: 'loading' };
    paint();
    const result = await loadLiveBundle(prefixes);
    if (!result.ok) {
      state.source = 'offline';
      state.bacnetLink = {
        phase: 'ready',
        reachable: false,
        detail: String(result.humanError || 'Could not reach supervisory API (refresh failed).'),
        statusLabel: '',
      };
      setFeedback(String(result.humanError || 'Refresh failed.'), 'err');
      if (typeof console !== 'undefined' && console.warn) {
        console.warn('[diy-bas][refresh] aborted', result);
      }
      paint();
      return;
    }
    state.apiBase = result.base;
    state.health = result.health || null;
    const diy = (result.health && result.health.diy) || {};
    state.bacnetLink = {
      phase: 'ready',
      reachable: !!diy.reachable,
      detail: String(diy.detail || ''),
      statusLabel: String(diy.status || ''),
    };
    state.devices = Array.isArray(result.devices?.items) ? result.devices.items : [];
    state.points = Array.isArray(result.points?.items) ? result.points.items : [];
    state.pollingConfig = Array.isArray(result.pollingConfig?.items) ? result.pollingConfig.items : [];
    state.alarms = Array.isArray(result.alarms?.items) ? result.alarms.items : [];
    state.alarmHistory = Array.isArray(result.alarms?.history) ? result.alarms.history : [];
    state.notifications = Array.isArray(result.notificationLogs?.items) ? result.notificationLogs.items : [];
    state.alarmRules = Array.isArray(result.alarmRules?.items) ? result.alarmRules.items : [];
    state.alarmSettings = result.alarmSettings && typeof result.alarmSettings.deviceOfflineSec === 'number'
      ? { deviceOfflineSec: result.alarmSettings.deviceOfflineSec }
      : { deviceOfflineSec: 300 };
    state.deviceNotes = Array.isArray(result.deviceNotes?.items) ? result.deviceNotes.items : [];
    state.layouts = Array.isArray(result.layouts?.items) ? result.layouts.items : [];
    state.wiresheetRules = Array.isArray(result.wiresheetRules?.items) ? result.wiresheetRules.items : [];
    state.wiresheetStatus = Array.isArray(result.wiresheetStatus?.items) ? result.wiresheetStatus.items : [];
    state.bundleErrors = Array.isArray(result.bundleErrors) ? result.bundleErrors : [];
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
    if (state.selectedPointId && !state.trendsLive) {
      try {
        state.trendError = '';
        const tids = (state.trendSelectedIds || []).filter(Boolean).length
          ? state.trendSelectedIds.slice(0, 8)
          : [state.selectedPointId];
        trendPushDiag(`refresh: auto loadTrend route=${state.route} ids=${tids.join(',')}`);
        await loadTrend(tids, state.trendsRangeSec || 86400);
      } catch (err) {
        state.trends = [];
        state.trendByPoint = {};
        state.trendOrder = [];
        state.trendError = String(err && err.message ? err.message : err);
        trendPushDiag(`refresh: loadTrend FAILED ${state.trendError}`);
        if (typeof console !== 'undefined' && console.warn) {
          console.warn('[diy-bas][trends] initial load failed', state.trendError);
        }
      }
    }
    if (state.bundleErrors.length) {
      setFeedback(`Partial refresh: ${state.bundleErrors.join(' · ')}`, 'err');
    }
    if (typeof console !== 'undefined' && console.info) {
      console.info('[diy-bas][refresh] ok', {
        apiBase: state.apiBase,
        devices: state.devices.length,
        points: state.points.length,
        bacnetReachable: !!diy.reachable,
        bundleWarnings: state.bundleErrors.length,
      });
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
      devices: 'Devices',
      points: 'Points',
      wiresheet: 'Wire Sheet',
      builder: 'Custom Dashboard',
      trends: 'Trends',
      alarms: 'Alarms',
      notifications: 'Notifications',
      schedule: 'Schedule',
      dockerlogs: 'Docker logs',
    };
    const partial = state.bundleErrors?.length ? ` · ${state.bundleErrors.length} API warning(s)` : '';
    return {
      title: `${h.appTitle || 'diy-bas'} — ${titles[state.route] || 'Overview'}`,
      subtitle: `${h.siteName || 'site'} · ${source} (${state.apiBase}) · last ${state.lastRefreshTs || '—'}${partial}`,
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
