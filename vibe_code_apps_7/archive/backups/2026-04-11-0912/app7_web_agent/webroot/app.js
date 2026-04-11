async function getJson(path) {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json()
}

function formatValue(value, units) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return units && units !== 'bool' ? `${value} ${units}` : `${value}`
}

function renderDeviceCards(devices, routePrefix) {
  return devices.map(device => `
    <div class="device-card ${device.status}">
      <div class="device-title-row">
        <strong>${device.name}</strong>
        <span class="status-dot ${device.status}">${device.status}</span>
      </div>
      <ul>
        <li><span>points</span><span>${device.pointCount}</span></li>
        <li><span>last seen</span><span>${device.lastSeen || '—'}</span></li>
        <li><span>polling</span><span>${device.pollingEnabled ? 'enabled' : 'disabled'}</span></li>
        <li><span>route</span><span>${routePrefix}</span></li>
      </ul>
    </div>
  `).join('')
}

function renderPointRows(points) {
  return points.map(point => `
    <tr class="${point.alarmState === 'alarm' ? 'row-alarm' : ''}">
      <td>${point.deviceId}</td>
      <td>${point.label}</td>
      <td>${formatValue(point.value, point.units)}</td>
      <td>${point.lastUpdated || '—'}</td>
      <td>${point.alarmState}</td>
    </tr>
  `).join('')
}

function renderAlarmCards(alarms) {
  if (!alarms.length) {
    return '<div class="small-note">No active alarms right now.</div>'
  }
  return alarms.map(alarm => `
    <div class="alarm-card">
      <div>
        <strong>${alarm.message}</strong>
        <p>${alarm.state}</p>
      </div>
      <div class="alarm-meta">
        <span class="severity">${alarm.severity}</span>
        <span>${alarm.triggeredAt}</span>
      </div>
    </div>
  `).join('')
}

function renderTrendRows(trendItems) {
  if (!trendItems.length) return '<div class="small-note">No trend samples collected yet.</div>'
  const recent = trendItems.slice(-8).reverse()
  return `
    <div class="trend-list">
      ${recent.map(item => `<div class="config-row"><span>${item.ts}</span><span>${item.value}</span></div>`).join('')}
    </div>
  `
}

async function render() {
  const app = document.getElementById('app')
  app.innerHTML = '<div style="padding:24px">Loading App 7 from VOLTTRON...</div>'

  try {
    const [health, devices, points, alarms, trends, notificationLogs] = await Promise.all([
      getJson('/app7/api/health'),
      getJson('/app7/api/devices'),
      getJson('/app7/api/points'),
      getJson('/app7/api/alarms/events'),
      getJson('/app7/api/trends?pointId=Zone1VAV::ZoneTemp'),
      getJson('/app7/api/notifications/logs')
    ])

    app.innerHTML = `
      <div class="app-shell">
        <aside class="sidebar">
          <div class="brand">
            <h1>App 7</h1>
            <p>BAS / BMS Lite</p>
          </div>
          <nav>
            <div class="nav-item active">Overview</div>
            <div class="nav-item">Devices</div>
            <div class="nav-item">Points</div>
            <div class="nav-item">Trends</div>
            <div class="nav-item">Alarms</div>
            <div class="nav-item">Notifications</div>
          </nav>
        </aside>

        <main class="main">
          <header class="topbar">
            <div>
              <h2>${health.appTitle}</h2>
              <p>VOLTTRON-hosted frontend reading real platform-driver data from ${health.siteName}.</p>
            </div>
            <div class="status-pill">${health.volttron.status}</div>
          </header>

          <section class="grid two-up">
            <div class="panel">
              <div class="panel-header">
                <h3>Device Tree</h3>
                <span>${devices.items.length} devices</span>
              </div>
              <div class="device-list">${renderDeviceCards(devices.items, health.routePrefix)}</div>
            </div>

            <div class="panel">
              <div class="panel-header">
                <h3>Active Alarms</h3>
                <span>${alarms.items.length} active</span>
              </div>
              <div class="alarm-list">${renderAlarmCards(alarms.items)}</div>
            </div>
          </section>

          <section class="panel">
            <div class="panel-header">
              <h3>Point Table</h3>
              <span>${points.items.length} points</span>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Device</th>
                    <th>Point</th>
                    <th>Value</th>
                    <th>Last Updated</th>
                    <th>Alarm</th>
                  </tr>
                </thead>
                <tbody>
                  ${renderPointRows(points.items)}
                </tbody>
              </table>
            </div>
          </section>

          <section class="grid two-up">
            <div class="panel">
              <div class="panel-header">
                <h3>Trend View</h3>
                <span>${trends.pointId}</span>
              </div>
              ${renderTrendRows(trends.items)}
            </div>

            <div class="panel">
              <div class="panel-header">
                <h3>Alarm / SMTP Config View</h3>
                <span>draft</span>
              </div>
              <div class="config-stack">
                <div class="config-row"><span>Alarm definitions</span><span>${health.counts.activeAlarms ? 'active present' : 'configured'}</span></div>
                <div class="config-row"><span>Notification logs</span><span>${notificationLogs.items.length}</span></div>
                <div class="config-row"><span>Polling control</span><span>API stubbed</span></div>
                <div class="config-row"><span>Live source</span><span>platform.driver publishes</span></div>
              </div>
              <p class="small-note">This option-1 pass keeps the UI/API shape visible while VOLTTRON handles BACnet Proxy, Platform Driver, polling, and supervisory agents underneath.</p>
            </div>
          </section>
        </main>
      </div>
    `
  } catch (error) {
    app.innerHTML = `
      <div style="padding:24px; color:#ffb4ae; font-family:Segoe UI, sans-serif;">
        <h2>App 7 failed to load</h2>
        <p>${error.message}</p>
        <p>Check whether the VOLTTRON web agent is installed and whether <code>/app7/api/health</code> is reachable.</p>
      </div>
    `
  }
}

render()
