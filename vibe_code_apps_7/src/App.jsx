const devices = [
  {
    id: 'ahu-1',
    name: 'AHU-1',
    status: 'online',
    points: [
      { name: 'SAT', value: '55.2 °F', state: 'normal' },
      { name: 'OAT', value: '48.9 °F', state: 'normal' },
      { name: 'Smoke', value: 'Normal', state: 'normal' }
    ]
  },
  {
    id: 'vav-1',
    name: 'Zone1 VAV',
    status: 'alarm',
    points: [
      { name: 'Zone Temp', value: '79.3 °F', state: 'alarm' },
      { name: 'Damper Cmd', value: '82 %', state: 'normal' },
      { name: 'Flow', value: '410 CFM', state: 'normal' }
    ]
  }
]

const alarms = [
  {
    id: 'evt-0001',
    severity: 'warning',
    message: 'Zone1 VAV temperature high',
    state: 'active',
    time: '06:15'
  }
]

function App() {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <h1>App 7</h1>
          <p>BMS / BAS Lite</p>
        </div>
        <nav>
          <button className="nav-item active">Overview</button>
          <button className="nav-item">Devices</button>
          <button className="nav-item">Points</button>
          <button className="nav-item">Trends</button>
          <button className="nav-item">Alarms</button>
          <button className="nav-item">Notifications</button>
        </nav>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h2>Operator Overview</h2>
            <p>Open-FDD-inspired feel, slimmer BAS-lite shell.</p>
          </div>
          <div className="status-pill online">VOLTTRON connected</div>
        </header>

        <section className="grid two-up">
          <div className="panel">
            <div className="panel-header">
              <h3>Device Tree</h3>
              <span>2 devices</span>
            </div>
            <div className="device-list">
              {devices.map((device) => (
                <div key={device.id} className={`device-card ${device.status}`}>
                  <div className="device-title-row">
                    <strong>{device.name}</strong>
                    <span className={`status-dot ${device.status}`}>{device.status}</span>
                  </div>
                  <ul>
                    {device.points.map((point) => (
                      <li key={point.name} className={point.state}>
                        <span>{point.name}</span>
                        <span>{point.value}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <h3>Active Alarms</h3>
              <span>{alarms.length} active</span>
            </div>
            <div className="alarm-list">
              {alarms.map((alarm) => (
                <div key={alarm.id} className="alarm-card">
                  <div>
                    <strong>{alarm.message}</strong>
                    <p>{alarm.state}</p>
                  </div>
                  <div className="alarm-meta">
                    <span className="severity">{alarm.severity}</span>
                    <span>{alarm.time}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="grid two-up">
          <div className="panel trend-panel">
            <div className="panel-header">
              <h3>Trend View Placeholder</h3>
              <span>last 4h</span>
            </div>
            <div className="trend-placeholder">
              <div className="trend-line" />
              <div className="trend-line faint" />
              <div className="trend-line faint" />
            </div>
          </div>

          <div className="panel">
            <div className="panel-header">
              <h3>Alarm / SMTP Config Placeholder</h3>
              <span>draft</span>
            </div>
            <div className="config-stack">
              <div className="config-row"><span>SMTP</span><span>not wired</span></div>
              <div className="config-row"><span>Retention</span><span>7-30 days target</span></div>
              <div className="config-row"><span>Polling Control</span><span>API planned</span></div>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}

export default App
