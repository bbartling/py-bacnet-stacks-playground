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
let initialLoadPromise = null
let refreshInFlight = false
let renderScheduled = false
let appDelegationBound = false
let setpointDockBuilt = false

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

function escapeAttr(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('"', '&quot;')
    .replaceAll('<', '&lt;')
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

function getWritableSetpointsForDevice(deviceId) {
  const raw = state.cache.setpointsByDevice[deviceId]
  if (!raw || typeof raw.then === 'function') return []
  return raw
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
  const cached = state.cache.trendsByPoint[pointId]
  if (!cached) {
    const promise = getJson(`/app7/api/trends?pointId=${encodeURIComponent(pointId)}`).then(result => {
      state.cache.trendsByPoint[pointId] = result
      return state.cache.trendsByPoint[pointId]
    })
    state.cache.trendsByPoint[pointId] = promise
    await promise
  } else if (typeof cached.then === 'function') {
    await cached
  }
}

async function ensureSetpoints(deviceId) {
  const cached = state.cache.setpointsByDevice[deviceId]
  if (!cached) {
    const promise = getJson(`/app7/api/setpoints?deviceId=${encodeURIComponent(deviceId)}`).then(result => {
      state.cache.setpointsByDevice[deviceId] = result.items || []
      return state.cache.setpointsByDevice[deviceId]
    })
    state.cache.setpointsByDevice[deviceId] = promise
    await promise
  } else if (typeof cached.then === 'function') {
    await cached
  }
}

function renderDeviceTree(devices) {
  return devices.map(device => `
    <button type="button" class="device-tree-item ${state.selectedDeviceId === device.id ? 'selected' : ''} ${statusClass(device.status)}" data-device-id="${device.id}">
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

function renderHeroPanels(device, alarms, graphicsPoints) {
  const activeAlarms = alarms.filter(alarm => alarm.deviceId === device.id)
  const cards = (graphicsPoints || []).slice(0, 4).map(point => `
    <button type="button" class="graphic-tile ${state.selectedPointId === point.id ? 'selected' : ''} ${point.alarmState === 'alarm' ? 'alarm' : ''}" data-point-id="${point.id}">
      <span class="graphic-label">${escapeHtml(point.label)}</span>
      <strong>${escapeHtml(formatValue(point.value, point.units))}</strong>
      <span class="muted">${point.adjustable ? 'writable setpoint' : 'read only'}</span>
    </button>
  `).join('')

  return `
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
          <button type="button" class="theme-btn" data-close-plotly="true">Close</button>
        </div>
        <div id="plotly-trend-fullscreen" class="plotly-trend fullscreen"></div>
      </div>
    </div>
  `
}

/** Read-only cards; BACnet write uses fixed dock outside #app */
function renderSetpointSummaries(setpoints) {
  if (!setpoints.length) return '<div class="small-note">No writable setpoints exposed for this device.</div>'
  return `
    <div class="setpoint-summary-grid">
      ${setpoints.map(point => `
        <div class="setpoint-summary-card" data-setpoint-summary-id="${point.id}">
          <strong>${escapeHtml(point.label)}</strong>
          <div class="muted">Current: <span class="setpoint-current-val">${escapeHtml(formatValue(point.value, point.units))}</span></div>
        </div>
      `).join('')}
    </div>
    <p class="small-note setpoint-dock-hint">Use the <strong>setpoint bar</strong> below the dashboard to write values — it stays mounted so typing is never interrupted by live updates.</p>
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

function patchSetpointSummaryValues() {
  const byId = {}
  for (const p of state.cache.allPoints || []) {
    byId[p.id] = p
  }
  document.querySelectorAll('[data-setpoint-summary-id]').forEach(card => {
    const pid = card.dataset.setpointSummaryId
    const p = byId[pid]
    const span = card.querySelector('.setpoint-current-val')
    if (span && p) span.textContent = formatValue(p.value, p.units)
  })
}

function applyLivePatches() {
  const shell = document.querySelector('#app .app-shell')
  if (!shell) return

  const selectedDevice = getSelectedDevice()
  if (!selectedDevice) return

  const graphics = state.cache.graphics
  if (!graphics) return
  const equipmentGraphics = selectedDevice.id === 'Zone1VAV' ? graphics.equipmentGraphics.vav.points : graphics.equipmentGraphics.ahu.points

  const dt = shell.querySelector('#device-tree-root')
  if (dt) dt.innerHTML = renderDeviceTree(state.cache.devices)

  const hero = shell.querySelector('#hero-section')
  if (hero) hero.innerHTML = renderHeroPanels(selectedDevice, state.cache.alarms, equipmentGraphics)

  const tb = shell.querySelector('#points-tbody')
  if (tb) tb.innerHTML = renderPointRows(getDevicePoints(selectedDevice.id))

  const alarmCount = state.cache.alarms.filter(a => a.deviceId === selectedDevice.id).length
  const pill = shell.querySelector('#topbar-alarm-pill')
  if (pill) {
    pill.textContent = `${alarmCount} active alarm(s)`
    pill.className = `status-pill ${alarmCount ? 'alarm' : 'ok'}`
  }

  const setpoints = getWritableSetpointsForDevice(selectedDevice.id)
  const sumMount = shell.querySelector('#setpoint-summary-mount')
  if (sumMount) sumMount.innerHTML = renderSetpointSummaries(setpoints)

  const wm = shell.querySelector('#write-message-mount')
  if (wm && state.writeMessage) wm.innerHTML = `<div class="write-message">${escapeHtml(state.writeMessage)}</div>`
  else if (wm && !state.writeMessage) wm.innerHTML = ''

  patchSetpointSummaryValues()
  renderPlotlyTrend(getCurrentTrend())
}

function renderApp() {
  renderScheduled = false
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
  const setpoints = getWritableSetpointsForDevice(selectedDevice.id)

  const alarmCount = state.cache.alarms.filter(a => a.deviceId === selectedDevice.id).length

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
            <button type="button" class="theme-btn ${state.theme === 'dark' ? 'active' : ''}" data-theme="dark">Dark</button>
            <button type="button" class="theme-btn ${state.theme === 'light' ? 'active' : ''}" data-theme="light">Light</button>
          </div>
        </div>
        <div class="sidebar-section">
          <div class="sidebar-label">Equipment Tree</div>
          <div id="device-tree-root" class="device-tree">${renderDeviceTree(state.cache.devices)}</div>
        </div>
      </aside>

      <main class="main">
        <header class="topbar simple-topbar">
          <div>
            <h2>${escapeHtml(selectedDevice.displayName || selectedDevice.name)}</h2>
            <p>Device dashboard — live values patch in place; setpoint writer is pinned below.</p>
          </div>
          <div class="topbar-actions">
            <div id="topbar-alarm-pill" class="status-pill ${alarmCount ? 'alarm' : 'ok'}">${alarmCount} active alarm(s)</div>
            <div class="status-pill ok">${escapeHtml(health.volttron.status)}</div>
          </div>
        </header>

        <section class="hero-grid" id="hero-section">${renderHeroPanels(selectedDevice, state.cache.alarms, equipmentGraphics)}</section>

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
                <tbody id="points-tbody">${renderPointRows(devicePoints)}</tbody>
              </table>
            </div>
          </div>

          <div class="panel trend-panel">
            <div class="panel-header">
              <h3>Trend</h3>
              <div class="trend-actions">
                <span>${escapeHtml(trend.label)}</span>
                <button type="button" class="theme-btn trend-expand-btn" data-open-plotly="true">Full Screen Plotly</button>
              </div>
            </div>
            ${renderPlotlyMount()}
          </div>
        </section>

        <section class="simple-main-grid single-panel-row">
          ${renderNotes(state.cache.notificationConfig)}
        </section>
        ${renderPlotlyFullscreenShell()}
      </main>
    </div>
  `

  bindInteractiveHandlers()
  renderPlotlyTrend(trend)
  state.initialized = true
  syncSetpointDock()
}

function bindInteractiveHandlers() {
  document.querySelectorAll('[data-theme]').forEach(el => {
    el.onclick = () => {
      setTheme(el.dataset.theme)
      scheduleRender()
    }
  })

  document.querySelectorAll('[data-device-id]').forEach(el => {
    el.onclick = () => {
      selectDevice(el.dataset.deviceId)
    }
  })

  document.querySelectorAll('[data-point-id]').forEach(el => {
    el.onclick = () => {
      selectPoint(el.dataset.pointId)
    }
  })

  document.querySelectorAll('[data-open-plotly]').forEach(el => {
    el.onclick = () => {
      state.plotFullscreen = true
      scheduleRender()
    }
  })

  document.querySelectorAll('[data-close-plotly]').forEach(el => {
    el.onclick = () => {
      state.plotFullscreen = false
      scheduleRender()
    }
  })
}

function buildSetpointDock() {
  const dock = document.getElementById('setpoint-dock')
  if (!dock || setpointDockBuilt) return
  setpointDockBuilt = true
  dock.innerHTML = `
    <div class="setpoint-dock-inner">
      <div class="setpoint-dock-head">
        <div>
          <strong>Setpoint write</strong>
          <div class="muted small">Platform driver · priority write</div>
        </div>
        <span id="setpoint-dock-device-label" class="muted"></span>
      </div>
      <div class="setpoint-dock-grid">
        <label class="setpoint-dock-label" for="setpoint-target-select">Point</label>
        <select id="setpoint-target-select" class="setpoint-dock-select"></select>
        <label class="setpoint-dock-label" for="setpoint-value-input">New value</label>
        <input id="setpoint-value-input" class="setpoint-dock-input" type="number" step="any" inputmode="decimal" placeholder="e.g. 72" autocomplete="off" />
        <div class="setpoint-dock-actions">
          <button type="button" id="setpoint-write-btn" class="setpoint-dock-write-btn">Write to BACnet</button>
        </div>
      </div>
      <div id="setpoint-dock-message" class="setpoint-dock-message" role="status"></div>
    </div>
  `

  document.getElementById('setpoint-write-btn').addEventListener('click', async () => {
    const sel = document.getElementById('setpoint-target-select')
    const inp = document.getElementById('setpoint-value-input')
    const msg = document.getElementById('setpoint-dock-message')
    const pointId = sel.value
    const raw = inp.value
    const value = Number(raw)
    if (!pointId) {
      msg.textContent = 'Pick a setpoint first.'
      return
    }
    if (raw === '' || Number.isNaN(value)) {
      msg.textContent = 'Enter a valid number.'
      return
    }
    msg.textContent = `Writing ${pointId}…`
    try {
      const result = await postJson('/app7/api/setpoints/write', { pointId, value })
      if (result.status === 'ok') {
        msg.textContent = `OK — ${result.pointName}: ${result.requestedValue}`
        state.writeMessage = `Write succeeded: ${result.pointName} = ${result.requestedValue}`
        inp.value = ''
        await refreshLiveData()
        state.cache.setpointsByDevice[state.selectedDeviceId] = undefined
        await ensureSetpoints(state.selectedDeviceId)
        applyLivePatches()
        syncSetpointDock()
      } else {
        msg.textContent = result.message || 'Write failed'
        state.writeMessage = `Write failed: ${result.message || pointId}`
        applyLivePatches()
      }
    } catch (err) {
      msg.textContent = err.message || 'Request failed'
      state.writeMessage = `Write failed: ${err.message}`
      applyLivePatches()
    }
  })
}

function syncSetpointDock() {
  buildSetpointDock()
  const dock = document.getElementById('setpoint-dock')
  const sel = document.getElementById('setpoint-target-select')
  const label = document.getElementById('setpoint-dock-device-label')
  if (!dock || !sel) return

  const dev = getSelectedDevice()
  label.textContent = dev ? `${dev.displayName || dev.name}` : ''

  const points = getWritableSetpointsForDevice(state.selectedDeviceId)
  const prev = sel.value
  sel.innerHTML = points.length
    ? points.map(p => `<option value="${escapeAttr(p.id)}">${escapeHtml(p.label)} (${escapeHtml(p.name)})</option>`).join('')
    : '<option value="">(no writable points)</option>'

  if (prev && [...sel.options].some(o => o.value === prev)) sel.value = prev
  else if (points[0]) sel.value = points[0].id
}

function scheduleRender() {
  if (renderScheduled) return
  renderScheduled = true
  requestAnimationFrame(() => renderApp())
}

async function initialLoad() {
  if (initialLoadPromise) return initialLoadPromise
  const app = document.getElementById('app')
  app.innerHTML = '<div style="padding:24px">Loading App 7…</div>'
  setTheme(state.theme)
  buildSetpointDock()
  initialLoadPromise = fetchInitialData().then(() => {
    renderApp()
    syncSetpointDock()
  })
  return initialLoadPromise
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

function startBackgroundRefresh() {
  if (refreshTimer) clearInterval(refreshTimer)
  refreshTimer = setInterval(async () => {
    if (refreshInFlight) return
    const dockInput = document.getElementById('setpoint-value-input')
    const dockSelect = document.getElementById('setpoint-target-select')
    const ae = document.activeElement
    if (dockInput && ae === dockInput) return
    if (dockSelect && ae === dockSelect) return
    refreshInFlight = true
    try {
      await refreshLiveData()
      applyLivePatches()
      syncSetpointDock()
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
