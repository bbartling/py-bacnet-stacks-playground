(function () {
  'use strict';

  /** Default API roots to try (Flask can serve `/api/...`; VOLTTRON used `/app7/api/...`). */
  const DEFAULT_API_PREFIXES = ['/api', '/app7/api'];

  function resolvedPrefixes(options) {
    if (Array.isArray(options.apiPrefixes) && options.apiPrefixes.length) {
      return options.apiPrefixes;
    }
    if (
      typeof window !== 'undefined' &&
      Array.isArray(window.BAS8_API_PREFIXES) &&
      window.BAS8_API_PREFIXES.length
    ) {
      return window.BAS8_API_PREFIXES;
    }
    return DEFAULT_API_PREFIXES;
  }

  const MOCK = {
    health: {
      appTitle: 'BAS Lite dashboard',
      siteName: 'Demo site (mock)',
      routePrefix: '/api',
      volttron: { status: 'mock — connect Flask later' },
      counts: { activeAlarms: 2 },
    },
    devices: {
      items: [
        {
          name: 'AHU-1',
          status: 'online',
          pointCount: 48,
          lastSeen: '3s ago',
          pollingEnabled: true,
        },
        {
          name: 'VAV-101',
          status: 'online',
          pointCount: 12,
          lastSeen: '5s ago',
          pollingEnabled: true,
        },
        {
          name: 'CHW-Plant',
          status: 'unknown',
          pointCount: 24,
          lastSeen: '—',
          pollingEnabled: false,
        },
      ],
    },
    points: {
      items: [
        {
          deviceId: 'AHU-1',
          label: 'Supply air temp',
          value: 55.2,
          units: '°F',
          lastUpdated: '3s ago',
          alarmState: 'normal',
        },
        {
          deviceId: 'VAV-101',
          label: 'Zone temp',
          value: 72.1,
          units: '°F',
          lastUpdated: '5s ago',
          alarmState: 'normal',
        },
        {
          deviceId: 'VAV-101',
          label: 'Airflow',
          value: 850,
          units: 'CFM',
          lastUpdated: '5s ago',
          alarmState: 'alarm',
        },
        {
          deviceId: 'CHW-Plant',
          label: 'Leaving CHW temp',
          value: null,
          units: '°F',
          lastUpdated: '—',
          alarmState: 'unknown',
        },
      ],
    },
    alarms: {
      items: [
        {
          message: 'VAV-101 airflow below minimum',
          state: 'active',
          severity: 'warning',
          triggeredAt: '2026-04-18 08:12',
        },
        {
          message: 'CHW-Plant comm loss',
          state: 'active',
          severity: 'critical',
          triggeredAt: '2026-04-17 22:40',
        },
      ],
    },
    trends: {
      pointId: 'VAV-101::ZoneTemp',
      items: [
        { ts: '08:10', value: 71.8 },
        { ts: '08:15', value: 72.0 },
        { ts: '08:20', value: 72.1 },
        { ts: '08:25', value: 72.4 },
        { ts: '08:30', value: 72.1 },
      ],
    },
    notificationLogs: {
      items: [
        { ts: '2026-04-18 08:12', channel: 'email', detail: 'Alarm: VAV-101 airflow' },
        { ts: '2026-04-17 22:41', channel: 'smtp stub', detail: 'Alarm: CHW-Plant comm' },
        { ts: '2026-04-16 06:00', channel: 'log', detail: 'Daily heartbeat OK' },
      ],
    },
  };

  /** @type {HTMLElement | null} */
  let mountEl = null;
  /** @type {string} */
  let currentRoute = 'overview';
  /** @type {object | null} */
  let bundle = null;

  async function fetchJson(url) {
    const response = await fetch(url);
    if (!response.ok) throw new Error(`${response.status}`);
    return response.json();
  }

  /**
   * @param {string[]} prefixes
   */
  async function loadLiveBundle(prefixes) {
    const list = prefixes.length ? prefixes : DEFAULT_API_PREFIXES;
    for (const raw of list) {
      const base = raw.replace(/\/$/, '');
      try {
        const [health, devices, points, alarms, trends, notificationLogs] =
          await Promise.all([
            fetchJson(`${base}/health`),
            fetchJson(`${base}/devices`),
            fetchJson(`${base}/points`),
            fetchJson(`${base}/alarms/events`),
            fetchJson(`${base}/trends?pointId=Zone1VAV::ZoneTemp`),
            fetchJson(`${base}/notifications/logs`),
          ]);
        return {
          health,
          devices,
          points,
          alarms,
          trends,
          notificationLogs,
          _source: 'live',
          _apiBase: base,
        };
      } catch {
        /* try next prefix */
      }
    }
    return null;
  }

  function formatValue(value, units) {
    if (value === null || value === undefined) return '—';
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    return units && units !== 'bool' ? `${value} ${units}` : `${value}`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function renderDeviceCards(devices, routePrefix) {
    return devices
      .map(
        (device) => `
    <div class="dash-device-card dash-device-${escapeHtml(device.status)}">
      <div class="dash-device-title-row">
        <strong>${escapeHtml(device.name)}</strong>
        <span class="dash-status-dot dash-status-${escapeHtml(device.status)}">${escapeHtml(device.status)}</span>
      </div>
      <ul class="dash-device-meta">
        <li><span>Points</span><span>${device.pointCount}</span></li>
        <li><span>Last seen</span><span>${escapeHtml(device.lastSeen || '—')}</span></li>
        <li><span>Polling</span><span>${device.pollingEnabled ? 'enabled' : 'disabled'}</span></li>
        <li><span>Route</span><span>${escapeHtml(routePrefix)}</span></li>
      </ul>
    </div>`
      )
      .join('');
  }

  function renderPointRows(points) {
    return points
      .map(
        (point) => `
    <tr class="${point.alarmState === 'alarm' ? 'dash-row-alarm' : ''}">
      <td>${escapeHtml(point.deviceId)}</td>
      <td>${escapeHtml(point.label)}</td>
      <td>${escapeHtml(formatValue(point.value, point.units))}</td>
      <td>${escapeHtml(point.lastUpdated || '—')}</td>
      <td>${escapeHtml(point.alarmState)}</td>
    </tr>`
      )
      .join('');
  }

  function renderAlarmCards(alarms) {
    if (!alarms.length) {
      return '<p class="dash-small-note">No active alarms right now.</p>';
    }
    return alarms
      .map(
        (alarm) => `
    <div class="dash-alarm-card dash-sev-${escapeHtml(alarm.severity)}">
      <div>
        <strong>${escapeHtml(alarm.message)}</strong>
        <p>${escapeHtml(alarm.state)}</p>
      </div>
      <div class="dash-alarm-meta">
        <span class="dash-severity">${escapeHtml(alarm.severity)}</span>
        <span>${escapeHtml(alarm.triggeredAt)}</span>
      </div>
    </div>`
      )
      .join('');
  }

  function renderTrendRows(trendItems) {
    if (!trendItems.length) {
      return '<p class="dash-small-note">No trend samples yet.</p>';
    }
    const recent = trendItems.slice(-12).reverse();
    return `
    <div class="dash-trend-list">
      ${recent
        .map(
          (item) =>
            `<div class="dash-config-row"><span>${escapeHtml(item.ts)}</span><span>${escapeHtml(String(item.value))}</span></div>`
        )
        .join('')}
    </div>`;
  }

  function renderNotificationRows(items) {
    if (!items.length) {
      return '<p class="dash-small-note">No notification log entries.</p>';
    }
    return `
    <div class="dash-trend-list">
      ${items
        .map((row) => {
          const right = [row.channel, row.detail].filter(Boolean).join(' · ');
          return `<div class="dash-config-row"><span>${escapeHtml(row.ts)}</span><span>${escapeHtml(right)}</span></div>`;
        })
        .join('')}
    </div>`;
  }

  function viewOverview(b) {
    const { health, devices, points, alarms, trends, notificationLogs } = b;
    return `
      <div class="dash-view-inner">
        <section class="dash-grid-two">
          <div class="panel">
            <div class="dash-panel-head">
              <h2>Device tree</h2>
              <span>${devices.items.length} devices</span>
            </div>
            <div class="dash-device-list">${renderDeviceCards(devices.items, health.routePrefix)}</div>
          </div>
          <div class="panel">
            <div class="dash-panel-head">
              <h2>Active alarms</h2>
              <span>${alarms.items.length} active</span>
            </div>
            <div class="dash-alarm-list">${renderAlarmCards(alarms.items)}</div>
          </div>
        </section>

        <section class="panel">
          <div class="dash-panel-head">
            <h2>Point table</h2>
            <span>${points.items.length} points</span>
          </div>
          <div class="dash-table-wrap">
            <table class="dash-table">
              <thead>
                <tr>
                  <th>Device</th>
                  <th>Point</th>
                  <th>Value</th>
                  <th>Last updated</th>
                  <th>Alarm</th>
                </tr>
              </thead>
              <tbody>${renderPointRows(points.items)}</tbody>
            </table>
          </div>
        </section>

        <section class="dash-grid-two">
          <div class="panel">
            <div class="dash-panel-head">
              <h2>Trend view</h2>
              <span>${escapeHtml(trends.pointId || '—')}</span>
            </div>
            ${renderTrendRows(trends.items || [])}
          </div>
          <div class="panel">
            <div class="dash-panel-head">
              <h2>Supervisory / config</h2>
              <span>draft</span>
            </div>
            <div class="dash-config-stack">
              <div class="dash-config-row"><span>Alarm definitions</span><span>${health.counts?.activeAlarms ? 'Active present' : 'OK'}</span></div>
              <div class="dash-config-row"><span>Notification logs</span><span>${notificationLogs.items.length} entries</span></div>
              <div class="dash-config-row"><span>Polling</span><span>API when wired</span></div>
              <div class="dash-config-row"><span>Live source</span><span>BACnet / Flask (future)</span></div>
            </div>
            <p class="dash-small-note">Same layout as the legacy VOLTTRON App&nbsp;7 web agent: devices, points, alarms, trends, and logs. Data here is mock until your Flask service implements these JSON routes.</p>
          </div>
        </section>
      </div>`;
  }

  function viewDevices(b) {
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head">
            <h2>Devices</h2>
            <span>${b.devices.items.length} total</span>
          </div>
          <div class="dash-device-list">${renderDeviceCards(b.devices.items, b.health.routePrefix)}</div>
        </section>
      </div>`;
  }

  function viewPoints(b) {
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head">
            <h2>Points</h2>
            <span>${b.points.items.length} total</span>
          </div>
          <div class="dash-table-wrap">
            <table class="dash-table">
              <thead>
                <tr>
                  <th>Device</th>
                  <th>Point</th>
                  <th>Value</th>
                  <th>Last updated</th>
                  <th>Alarm</th>
                </tr>
              </thead>
              <tbody>${renderPointRows(b.points.items)}</tbody>
            </table>
          </div>
        </section>
      </div>`;
  }

  function viewTrends(b) {
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head">
            <h2>Trends</h2>
            <span>${escapeHtml(b.trends.pointId || '')}</span>
          </div>
          ${renderTrendRows(b.trends.items || [])}
          <p class="dash-small-note">Plotly (or Chart.js) can mount here when the Flask API returns time-series arrays.</p>
        </section>
      </div>`;
  }

  function viewAlarms(b) {
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head">
            <h2>Alarms</h2>
            <span>${b.alarms.items.length} active</span>
          </div>
          <div class="dash-alarm-list">${renderAlarmCards(b.alarms.items)}</div>
        </section>
      </div>`;
  }

  function viewNotifications(b) {
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head">
            <h2>Notification log</h2>
            <span>${b.notificationLogs.items.length} entries</span>
          </div>
          ${renderNotificationRows(b.notificationLogs.items)}
        </section>
      </div>`;
  }

  function paint() {
    if (!mountEl || !bundle) return;
    const b = bundle;
    let html = '';
    switch (currentRoute) {
      case 'overview':
        html = viewOverview(b);
        break;
      case 'devices':
        html = viewDevices(b);
        break;
      case 'points':
        html = viewPoints(b);
        break;
      case 'trends':
        html = viewTrends(b);
        break;
      case 'alarms':
        html = viewAlarms(b);
        break;
      case 'notifications':
        html = viewNotifications(b);
        break;
      default:
        html = viewOverview(b);
    }
    mountEl.innerHTML = html;
  }

  /**
   * @param {object} options
   * @param {string[]=} options.apiPrefixes — e.g. `['/api']` for Flask; tries each until one works.
   */
  async function init(el, options = {}) {
    if (!(el instanceof HTMLElement)) return;
    mountEl = el;
    const prefixes = resolvedPrefixes(options);
    const live = await loadLiveBundle(prefixes);
    if (live) {
      bundle = live;
    } else {
      bundle = {
        health: MOCK.health,
        devices: MOCK.devices,
        points: MOCK.points,
        alarms: MOCK.alarms,
        trends: MOCK.trends,
        notificationLogs: MOCK.notificationLogs,
        _source: 'mock',
        _apiBase: '',
      };
    }
    paint();
  }

  /**
   * @param {string} route overview|devices|points|trends|alarms|notifications
   */
  function setRoute(route) {
    currentRoute = route;
    paint();
  }

  async function refresh(options = {}) {
    const prefixes = resolvedPrefixes(options);
    const live = await loadLiveBundle(prefixes);
    if (live) {
      bundle = live;
    } else {
      bundle = {
        health: MOCK.health,
        devices: MOCK.devices,
        points: MOCK.points,
        alarms: MOCK.alarms,
        trends: MOCK.trends,
        notificationLogs: MOCK.notificationLogs,
        _source: 'mock',
        _apiBase: '',
      };
    }
    paint();
  }

  function getTopbarMeta() {
    if (!bundle) {
      return { title: 'Dashboard', subtitle: 'Loading…', pill: '…' };
    }
    const h = bundle.health;
    const source = bundle._source === 'live' ? 'Live API' : 'Mock data';
    const titles = {
      overview: 'Overview',
      devices: 'Devices',
      points: 'Points',
      trends: 'Trends',
      alarms: 'Alarms',
      notifications: 'Notifications',
    };
    return {
      title: `${h.appTitle} — ${titles[currentRoute] || 'Overview'}`,
      subtitle: `${h.siteName} · ${source}${bundle._apiBase ? ` (${bundle._apiBase})` : ''}`,
      pill: h.volttron?.status || source,
    };
  }

  window.Bas8Dashboard = {
    init,
    setRoute,
    refresh,
    getTopbarMeta,
  };
})();
