const state = {
  theme: localStorage.getItem('app7-theme') || 'dark',
  selectedDeviceId: 'BensFakeAHU',
  selectedPointId: 'BensFakeAHU::SA_T',
  writeMessage: '',
  plotFullscreen: false,
  initialized: false,
  cache: {
    devices: [],
    allPoints: [],
    alarms: [],
    notificationConfig: null,
    graphics: null,
    setpointsByDevice: {},
    trendsByPoint: {},
    health: null
  }
}

let refreshTimer = null

async function getJson(path) {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json()
}

async function postJson(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  if (!response.ok) throw new Error(`Request failed: ${response.status}`)
  return response.json()
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function formatValue(value, units) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (typeof value === 'number') return units && units !== 'bool' ? `${value.toFixed(1)} ${units}` : `${value.toFixed(1)}`
  return units && units !== 'bool' ? `${value} ${units}` : `${value}`
}

function setTheme(theme) {
  state.theme = theme
  document.documentElement.setAttribute('data-theme', theme)
  localStorage.setItem('app7-theme', theme)
}

function statusClass(status) {
  return status === 'alarm' ? 'alarm' : status === 'online' ? 'online' : 'unknown'
}

function getSelectedDevice() {
  return state.cache.devices.find(d => d.id === state.selectedDeviceId) || state.cache.devices[0]
}

function getDevicePoints(deviceId) {
  return state.cache.allPoints.filter(point => point.deviceId === deviceId)
}

function getCurrentTrend() {
  const trend = state.cache.trendsByPoint[state.selectedPointId]
  if (trend && typeof trend.then !== 'function') return trend
  return { pointId: state.selectedPointId, label: state.selectedPointId, units: '', items: [] }
}

async function fetchInitialData() {
  const [health, devicesRes, allPointsRes, alarmsRes, notificationConfig, graphics] = await Promise.all([
    getJson('/app7/api/health'),
    getJson('/app7/api/devices'),
    getJson('/app7/api/points'),
    getJson('/app7/api/alarms/events'),
    getJson('/app7/api/notifications/config'),
    getJson('/app7/api/graphics/overview')
  ])

  state.cache.health = health
  state.cache.devices = devicesRes.items || []
  state.cache.allPoints = allPointsRes.items || []
  state.cache.alarms = alarmsRes.items || []
  state.cache.notificationConfig = notificationConfig
  state.cache.graphics = graphics

  if (!state.cache.devices.find(d => d.id === state.selectedDeviceId) && state.cache.devices[0]) {
    state.selectedDeviceId = state.cache.devices[0].id
  }

  const selectedDevice = getSelectedDevice()
  const devicePoints = getDevicePoints(selectedDevice.id)
  if (!devicePoints.find(p => p.id === state.selectedPointId) && devicePoints[0]) {
    state.selectedPointId = devicePoints[0].id
  }

  await Promise.all([
    ensureTrend(state.selectedPointId),
    ensureSetpoints(selectedDevice.id)
  ])
}

async function refreshLiveData() {
  const selectedDevice = getSelectedDevice()
  const [health, allPointsRes, alarmsRes, trend] = await Promise.all([
    getJson('/app7/api/health'),
    getJson('/app7/api/points'),
    getJson('/app7/api/alarms/events'),
    getJson(`/app7/api/trends?pointId=${encodeURIComponent(state.selectedPointId)}`)
  ])

  state.cache.health = health
  state.cache.allPoints = allPointsRes.items || []
  state.cache.alarms = alarmsRes.items || []
  state.cache.trendsByPoint[state.selectedPointId] = trend

  const refreshedPoints = getDevicePoints(selectedDevice.id)
  if (!refreshedPoints.find(p => p.id === state.selectedPointId) && refreshedPoints[0]) {
    state.selectedPointId = refreshedPoints[0].id
    await ensureTrend(state.selectedPointId)
  }
}

async function ensureTrend(pointId) {
  if (!state.cache.trendsByPoint[pointId]) {
    state.cache.trendsByPoint[pointId] = await getJson(`/app7/api/trends?pointId=${encodeURIComponent(pointId)}`)
  }
}

async function ensureSetpoints(deviceId) {
  if (!state.cache.setpointsByDevice[deviceId]) {
    const result = await getJson(`/app7/api/setpoints?deviceId=${encodeURIComponent(deviceId)}`)
    state.cache.setpointsByDevice[deviceId] = result.items || []
  }
}

function renderDeviceTree(devices) {
  return devices.map(device => `
    <button class="device-tree-item ${state.selectedDeviceId === device.id ? 'selected' : ''} ${statusClass(device.status)}" data-device-id="${device.id}">
      <div>
        <strong>${escapeHtml(device.displayName || device.name)}</strong>
        <div class="muted">${escapeHtml(device.kind.toUpperCase())}</div>
      </div>
      <div class="tree-meta">
        <span class="status-dot ${statusClass(device.status)}">${escapeHtml(device.status)}</span>
        <span>${device.pointCount}</span>
      </div>
    </button>
  `).join('')
}

function renderEquipmentSummary(device, alarms, graphicsPoints) {
  const activeAlarms = alarms.filter(alarm => alarm.deviceId === device.id)
  const cards = (graphicsPoints || []).slice(0, 4).map(point => `
    <button class="graphic-tile ${state.selectedPointId === point.id ? 'selected' : ''} ${point.alarmState === 'alarm' ? 'alarm' : ''}" data-point-id="${point.id}">
      <span class="graphic-label">${escapeHtml(point.label)}</span>
      <strong>${escapeHtml(formatValue(point.value, point.units))}</strong>
      <span class="muted">${point.adjustable ? 'writable setpoint' : 'read only'}</span>
    </button>
  `).join('')

  return `
    <section class="hero-grid">
      <div class="panel hero-panel">
        <div class="panel-header">
          <h3>${escapeHtml(device.displayName || device.name)}</h3>
          <span>${escapeHtml(device.address)}</span>
        </div>
        <div class="hero-metrics">
          <div class="metric-card"><span>Status</span><strong class="${statusClass(device.status)}-text">${escapeHtml(device.status)}</strong></div>
          <div class="metric-card"><span>Points</span><strong>${device.pointCount}</strong></div>
          <div class="metric-card"><span>Polling</span><strong>${device.pollingEnabled ? 'enabled' : 'disabled'}</strong></div>
          <div class="metric-card"><span>Active alarms</span><strong>${activeAlarms.length}</strong></div>
        </div>
        <div class="graphics-grid">${cards}</div>
      </div>
      <div class="panel hero-panel">
        <div class="panel-header">
          <h3>Alarm State</h3>
          <span>${activeAlarms.length ? 'attention needed' : 'quiet'}</span>
        </div>
        <div class="alarm-list">${renderAlarmCards(activeAlarms)}</div>
      </div>
    </section>
  `
}

function renderPointRows(points) {
  return points.map(point => `
    <tr class="${point.alarmState === 'alarm' ? 'row-alarm' : ''} ${state.selectedPointId === point.id ? 'row-selected' : ''}" data-point-id="${point.id}">
      <td>${escapeHtml(point.label)}</td>
      <td>${escapeHtml(formatValue(point.value, point.units))}</td>
      <td>${escapeHtml(point.lastUpdated || '—')}</td>
      <td>${point.adjustable ? 'yes' : 'no'}</td>
      <td>${escapeHtml(point.alarmState)}</td>
    </tr>
  `).join('')
}

function renderAlarmCards(alarms) {
  if (!alarms.length) return '<div class="small-note">No active alarms for this equipment.</div>'
  return alarms.map(alarm => `
    <div class="alarm-card ${alarm.severity}">
      <div>
        <strong>${escapeHtml(alarm.message)}</strong>
        <p>${escapeHtml(alarm.state)}</p>
      </div>
      <div class="alarm-meta">
        <span class="severity">${escapeHtml(alarm.severity)}</span>
        <span>${escapeHtml(alarm.triggeredAt)}</span>
      </div>
    </div>
  `).join('')
}

function renderPlotlyMount() {
  return '<div id="plotly-trend" class="plotly-trend"></div>'
}

function renderPlotlyFullscreenShell() {
  if (!state.plotFullscreen) return ''
  return `
    <div class="plotly-modal-backdrop" data-close-plotly="true">
      <div class="plotly-modal" onclick="event.stopPropagation()">
        <div class="panel-header">
          <h3>Full Screen Trend</h3>
          <button class="theme-btn" data-close-plotly="true">Close</button>
        </div>
        <div id="plotly-trend-fullscreen" class="plotly-trend fullscreen"></div>
      </div>
    </div>
  `
}

function renderSetpoints(setpoints) {
  if (!setpoints.length) return '<div class="small-note">No writable setpoints exposed for this device.</div>'
  return `
    <div class="setpoint-grid">
      ${setpoints.map(point => `
        <form class="setpoint-card" data-setpoint-form="${point.id}">
          <div>
            <strong>${escapeHtml(point.label)}</strong>
            <div class="muted">Current: ${escapeHtml(formatValue(point.value, point.units))}</div>
          </div>
          <div class="setpoint-controls">
            <input type="number" step="0.1" name="value" value="${typeof point.value === 'number' ? point.value : ''}" />
            <button type="submit">Write</button>
          </div>
        </form>
      `).join('')}
    </div>
  `
}

function renderNotes(notificationConfig) {
  return `
    <div class="panel simple-panel">
      <div class="panel-header">
        <h3>Operator Notes</h3>
        <span>simple bench mode</span>
      </div>
      <div class="config-stack compact">
        <div class="config-row"><span>Alarm setup</span><span>OpenClaw chat</span></div>
        <div class="config-row"><span>Trend setup</span><span>OpenClaw chat</span></div>
        <div class="config-row"><span>Email notifications</span><span>${notificationConfig.smtp.enabled ? 'enabled' : 'planned / placeholder'}</span></div>
        <div class="config-row"><span>SMTP host</span><span>${escapeHtml(notificationConfig.smtp.host)}</span></div>
        <div class="config-row"><span>SMTP test during setup</span><span>OpenClaw-guided commissioning target</span></div>
      </div>
      <p class="small-note">Alarm/trend setup and future SMTP dial-out testing can be driven through OpenClaw chat during commissioning.</p>
    </div>
  `
}

function plotLayout(trend) {
  return {
    margin: { l: 48, r: 16, t: 16, b: 42 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: getComputedStyle(document.documentElement).getPropertyValue('--text').trim() || '#e6edf3' },
    xaxis: { title: 'Time', gridcolor: 'rgba(120,140,170,0.15)' },
    yaxis: { title: trend.units || 'value', gridcolor: 'rgba(120,140,170,0.15)' }
  }
}

function plotConfig(trend) {
  return {
    responsive: true,
    displaylogo: false,
    toImageButtonOptions: { format: 'png', filename: `${trend.pointId}-trend`, height: 500, width: 900, scale: 1 }
  }
}

function renderPlotlyTrend(trend) {
  const mount = document.getElementById('plotly-trend')
  if (!mount || !window.Plotly) return
  const trace = [{
    x: (trend.items || []).map(item => item.ts),
    y: (trend.items || []).map(item => item.value),
    type: 'scatter',
    mode: 'lines+markers',
    line: { color: state.theme === 'light' ? '#0f62fe' : '#58a6ff', width: 3 },
    marker: { size: 6 }
  }]
  window.Plotly.react(mount, trace, plotLayout(trend), plotConfig(trend))
  const full = document.getElementById('plotly-trend-fullscreen')
  if (state.plotFullscreen && full) {
    window.Plotly.react(full, trace, plotLayout(trend), plotConfig(trend))
  }
}

function renderApp() {
  const app = document.getElementById('app')
  const health = state.cache.health
  const selectedDevice = getSelectedDevice()
  if (!health || !selectedDevice) {
    if (!state.initialized) app.innerHTML = '<div style="padding:24px">Loading App 7…</div>'
    return
  }

  const devicePoints = getDevicePoints(selectedDevice.id)
  const trend = getCurrentTrend()
  const graphics = state.cache.graphics
  const equipmentGraphics = selectedDevice.id === 'Zone1VAV' ? graphics.equipmentGraphics.vav.points : graphics.equipmentGraphics.ahu.points
  const setpoints = state.cache.setpointsByDevice[selectedDevice.id] || []

  app.innerHTML = `
    <div class="app-shell simple-shell">
      <aside class="sidebar">
        <div class="brand">
          <h1>App 7</h1>
          <p>BAS / BMS Lite</p>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-label">Theme</div>
          <div class="theme-toggle">
            <button class="theme-btn ${state.theme === 'dark' ? 'active' : ''}" data-theme="dark">Dark</button>
            <button class="theme-btn ${state.theme === 'light' ? 'active' : ''}" data-theme="light">Light</button>
          </div>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-label">Equipment Tree</div>
          <div class="device-tree">${renderDeviceTree(state.cache.devices)}</div>
        </div>
      </aside>

      <main class="main">
        <header class="topbar simple-topbar">
          <div>
            <h2>${escapeHtml(selectedDevice.displayName || selectedDevice.name)}</h2>
            <p>Device dashboard cached client-side for faster interactions.</p>
          </div>
          <div class="topbar-actions">
            <div class="status-pill ${state.cache.alarms.filter(a => a.deviceId === selectedDevice.id).length ? 'alarm' : 'ok'}">${state.cache.alarms.filter(a => a.deviceId === selectedDevice.id).length} active alarm(s)</div>
            <div class="status-pill ok">${escapeHtml(health.volttron.status)}</div>
          </div>
        </header>

        ${renderEquipmentSummary(selectedDevice, state.cache.alarms, equipmentGraphics)}

        <section class="simple-main-grid">
          <div class="panel table-panel">
            <div class="panel-header">
              <h3>Point Table</h3>
              <span>${devicePoints.length} points</span>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Point</th>
                    <th>Value</th>
                    <th>Last Updated</th>
                    <th>Adj.</th>
                    <th>Alarm</th>
                  </tr>
                </thead>
                <tbody>${renderPointRows(devicePoints)}</tbody>
              </table>
            </div>
          </div>

          <div class="panel trend-panel">
            <div class="panel-header">
              <h3>Trend</h3>
              <div class="trend-actions">
                <span>${escapeHtml(trend.label)}</span>
                <button class="theme-btn trend-expand-btn" data-open-plotly="true">Full Screen Plotly</button>
              </div>
            </div>
            ${renderPlotlyMount()}
          </div>
        </section>

        <section class="simple-main-grid">
          <div class="panel setpoints-panel">
            <div class="panel-header">
              <h3>Setpoints</h3>
              <span>real platform-driver write path</span>
            </div>
            ${renderSetpoints(setpoints)}
            ${state.writeMessage ? `<div class="write-message">${escapeHtml(state.writeMessage)}</div>` : ''}
          </div>
          ${renderNotes(state.cache.notificationConfig)}
        </section>
        ${renderPlotlyFullscreenShell()}
      </main>
    </div>
  `

  bindEvents()
  renderPlotlyTrend(trend)
  state.initialized = true
}

async function initialLoad() {
  const app = document.getElementById('app')
  app.innerHTML = '<div style="padding:24px">Loading App 7…</div>'
  setTheme(state.theme)
  await fetchInitialData()
  renderApp()
}

async function selectDevice(deviceId) {
  if (state.selectedDeviceId === deviceId) return
  state.selectedDeviceId = deviceId
  const devicePoints = getDevicePoints(deviceId)
  if (!devicePoints.find(p => p.id === state.selectedPointId) && devicePoints[0]) {
    state.selectedPointId = devicePoints[0].id
  }
  state.writeMessage = ''
  scheduleRender()
  await Promise.all([
    ensureSetpoints(deviceId),
    ensureTrend(state.selectedPointId)
  ])
  scheduleRender()
}

async function selectPoint(pointId) {
  if (state.selectedPointId === pointId) return
  state.selectedPointId = pointId
  scheduleRender()
  await ensureTrend(pointId)
  scheduleRender()
}

async function submitSetpoint(pointId, value) {
  state.writeMessage = `Writing ${pointId}…`
  renderApp()
  try {
    const result = await postJson('/app7/api/setpoints/write', { pointId, value })
    state.writeMessage = result.status === 'ok'
      ? `Write succeeded for ${result.pointName}: ${result.requestedValue}`
      : `Write failed for ${pointId}: ${result.message}`
    await refreshLiveData()
    state.cache.setpointsByDevice[state.selectedDeviceId] = undefined
    await ensureSetpoints(state.selectedDeviceId)
  } catch (error) {
    state.writeMessage = `Write failed for ${pointId}: ${error.message}`
  }
  renderApp()
}

function bindEvents() {
  document.querySelectorAll('[data-device-id]').forEach(el => {
    el.addEventListener('click', () => {
      selectDevice(el.dataset.deviceId)
    })
  })

  document.querySelectorAll('[data-point-id]').forEach(el => {
    el.addEventListener('click', () => {
      selectPoint(el.dataset.pointId)
    })
  })

  document.querySelectorAll('[data-theme]').forEach(el => {
    el.addEventListener('click', () => {
      setTheme(el.dataset.theme)
      renderApp()
    })
  })

  document.querySelectorAll('[data-open-plotly]').forEach(el => {
    el.addEventListener('click', () => {
      state.plotFullscreen = true
      renderApp()
    })
  })

  document.querySelectorAll('[data-close-plotly]').forEach(el => {
    el.addEventListener('click', () => {
      state.plotFullscreen = false
      renderApp()
    })
  })

  document.querySelectorAll('[data-setpoint-form]').forEach(form => {
    form.addEventListener('submit', async (event) => {
      event.preventDefault()
      const pointId = form.dataset.setpointForm
      const value = Number(form.querySelector('input[name="value"]').value)
      await submitSetpoint(pointId, value)
    })
  })
}

function startBackgroundRefresh() {
  if (refreshTimer) clearInterval(refreshTimer)
  refreshTimer = setInterval(async () => {
    if (refreshInFlight) return
    refreshInFlight = true
    try {
      await refreshLiveData()
      scheduleRender()
    } catch (error) {
      console.error('Background refresh failed', error)
    } finally {
      refreshInFlight = false
    }
  }, 30000)
}

initialLoad().then(startBackgroundRefresh).catch(error => {
  document.getElementById('app').innerHTML = `<div style="padding:24px; color:#ffb4ae; font-family:Segoe UI, sans-serif;"><h2>App 7 failed to load</h2><p>${escapeHtml(error.message)}</p></div>`
})
</div>`
})
)
      renderApp()
    } catch (error) {
      console.error('Background refresh failed', error)
    }
  }, 15000)
}

initialLoad().then(startBackgroundRefresh).catch(error => {
  document.getElementById('app').innerHTML = `<div style="padding:24px; color:#ffb4ae; font-family:Segoe UI, sans-serif;"><h2>App 7 failed to load</h2><p>${escapeHtml(error.message)}</p></div>`
})
