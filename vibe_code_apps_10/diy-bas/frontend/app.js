;(function () {
  'use strict';

  let elTopTitle = null;
  let elTopSub = null;
  let elTopPill = null;
  let panelDashboard = null;
  let panelSchedule = null;
  let dashboardInner = null;
  let currentRoute = 'overview';
  let dashboardInited = false;
  let scheduleMounted = false;
  let currentUser = null;

  const NAV_BY_ROLE = {
    system_integrator: ['overview', 'wiresheet', 'builder', 'discovery', 'polling', 'devices', 'points', 'trends', 'alarms', 'notifications', 'schedule'],
    building_operator: ['overview', 'devices', 'alarms', 'trends'],
  };
  const NAV_LABELS = {
    overview: 'Overview',
    builder: 'Custom Dashboard',
    wiresheet: 'Global Logic Wire Sheet',
    discovery: 'Discovery',
    polling: 'Polling',
    devices: 'Devices',
    points: 'Points',
    trends: 'Trends',
    alarms: 'Alarms',
    notifications: 'Notifications',
    schedule: 'Schedule',
  };
  const NAV_ACCENT = new Set(['schedule', 'builder', 'wiresheet']);

  function applyTopPill(meta) {
    if (!elTopPill) return;
    elTopPill.textContent = meta?.pill || '…';
    elTopPill.classList.remove('bas-status-pill-ok', 'bas-status-pill-bad');
    if (meta?.pillTone === 'ok') elTopPill.classList.add('bas-status-pill-ok');
    if (meta?.pillTone === 'bad') elTopPill.classList.add('bas-status-pill-bad');
  }

  function updateTopbarForSchedule() {
    if (!elTopTitle || !elTopSub || !elTopPill) return;
    elTopTitle.textContent = 'Weekly equipment schedule';
    elTopSub.textContent =
      'Operating week, holidays, and BACnet points for the active profile. Switch to Overview for site-wide status.';
    elTopPill.textContent = 'Editor';
    elTopPill.classList.remove('bas-status-pill-ok', 'bas-status-pill-bad');
  }

  function setNavActive(route) {
    const root = document.getElementById('app-root');
    if (!root) return;
    root.querySelectorAll('.bas-nav-item').forEach((btn) => {
      const r = btn.getAttribute('data-route');
      btn.classList.toggle('bas-nav-item-active', r === route);
    });
  }

  function canAccessRoute(route) {
    if (!currentUser) return false;
    const allowed = NAV_BY_ROLE[currentUser.role] || NAV_BY_ROLE.building_operator;
    return allowed.includes(route);
  }

  async function navigate(route) {
    if (!canAccessRoute(route)) route = 'overview';
    currentRoute = route;
    setNavActive(route);

    if (route === 'schedule') {
      if (panelDashboard) panelDashboard.hidden = true;
      if (panelSchedule) panelSchedule.hidden = false;
      updateTopbarForSchedule();
      if (!scheduleMounted && panelSchedule && window.DiyBasSchedule) {
        window.DiyBasSchedule.init(panelSchedule);
        scheduleMounted = true;
      }
      return;
    }

    if (panelSchedule) panelSchedule.hidden = true;
    if (panelDashboard) panelDashboard.hidden = false;

    if (!dashboardInited && dashboardInner && window.DiyBasDashboard) {
      await window.DiyBasDashboard.init(dashboardInner);
      dashboardInited = true;
    }
    if (window.DiyBasDashboard) {
      window.DiyBasDashboard.setRoute(route);
    }
    if (elTopTitle && elTopSub && elTopPill && window.DiyBasDashboard) {
      const m = window.DiyBasDashboard.getTopbarMeta();
      elTopTitle.textContent = m.title;
      elTopSub.textContent = m.subtitle;
      applyTopPill(m);
    }
  }

  function navItemsForRole() {
    if (!currentUser) return [];
    return (NAV_BY_ROLE[currentUser.role] || NAV_BY_ROLE.building_operator).map((route) => {
      const cls = ['bas-nav-item'];
      if (route === currentRoute) cls.push('bas-nav-item-active');
      if (NAV_ACCENT.has(route)) cls.push('bas-nav-item-accent');
      return `<button type="button" class="${cls.join(' ')}" data-route="${route}">${NAV_LABELS[route] || route}</button>`;
    });
  }

  function buildShell() {
    const root = document.getElementById('app-root');
    if (!root) return;

    root.className = 'bas-app';
    root.innerHTML = `
      <aside class="bas-sidebar" aria-label="Main navigation">
        <div class="bas-brand">
          <h1 class="bas-brand-title">diy-bas</h1>
          <p class="bas-brand-sub">supervisory UI</p>
        </div>
        <nav class="bas-nav" aria-label="Views">${navItemsForRole().join('')}</nav>
        <p class="bas-sidebar-foot">
          Signed in as <strong>${currentUser?.username || 'unknown'}</strong><br/>Role: <strong>${currentUser?.role || 'unknown'}</strong>
        </p>
      </aside>
      <div class="bas-main">
        <header class="bas-topbar">
          <div class="bas-topbar-text">
            <h2 class="bas-topbar-title" id="bas-top-title">Dashboard</h2>
            <p class="bas-topbar-sub" id="bas-top-sub">Loading…</p>
          </div>
          <div class="bas-topbar-actions">
            <button type="button" class="btn secondary" id="bas-btn-refresh" title="Retry live API">Refresh data</button>
            <button type="button" class="btn" id="bas-btn-logout">Log out</button>
            <span class="bas-status-pill" id="bas-top-pill">…</span>
          </div>
        </header>
        <div class="bas-body">
          <div id="bas-panel-dashboard" class="bas-panel">
            <div id="bas-dashboard-inner" class="bas-dashboard-inner"></div>
          </div>
          <div id="bas-panel-schedule" class="bas-panel bas-panel-schedule" hidden></div>
        </div>
      </div>
    `;

    elTopTitle = root.querySelector('#bas-top-title');
    elTopSub = root.querySelector('#bas-top-sub');
    elTopPill = root.querySelector('#bas-top-pill');
    panelDashboard = root.querySelector('#bas-panel-dashboard');
    panelSchedule = root.querySelector('#bas-panel-schedule');
    dashboardInner = root.querySelector('#bas-dashboard-inner');

    root.querySelectorAll('.bas-nav-item').forEach((btn) => {
      btn.addEventListener('click', () => {
        const r = btn.getAttribute('data-route');
        if (r) void navigate(r);
      });
    });

    root.querySelector('#bas-btn-refresh')?.addEventListener('click', async () => {
      if (currentRoute === 'schedule' || !window.DiyBasDashboard || !dashboardInited) return;
      await window.DiyBasDashboard.refresh();
      window.DiyBasDashboard.setRoute(currentRoute);
      const m = window.DiyBasDashboard.getTopbarMeta();
      if (elTopTitle) elTopTitle.textContent = m.title;
      if (elTopSub) elTopSub.textContent = m.subtitle;
      applyTopPill(m);
    });
    root.querySelector('#bas-btn-logout')?.addEventListener('click', async () => {
      await fetch('/api/auth/logout', { method: 'POST' });
      currentUser = null;
      showLogin();
    });
  }

  function showLogin(errorText = '') {
    const root = document.getElementById('app-root');
    if (!root) return;
    root.className = 'bas-login-root';
    root.innerHTML = `
      <div class="bas-login-card">
        <h2>diy-bas sign in</h2>
        <p>System Integrator and Building Operator roles are enforced server-side.</p>
        ${errorText ? `<p class="dash-error-banner">${errorText}</p>` : ''}
        <label>Username <input id="login-username" class="control" value="integrator" /></label>
        <label>Password <input id="login-password" class="control" type="password" /></label>
        <button class="btn primary" id="login-submit">Sign in</button>
      </div>`;
    root.querySelector('#login-submit')?.addEventListener('click', async () => {
      const username = root.querySelector('#login-username')?.value || '';
      const password = root.querySelector('#login-password')?.value || '';
      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });
        const data = await res.json();
        if (!res.ok || !data?.ok) throw new Error(data?.error || 'login failed');
        currentUser = data.user;
        if (window.DiyBasDashboard) window.DiyBasDashboard.setAuthContext(currentUser);
        boot();
      } catch (err) {
        showLogin(String(err?.message || err));
      }
    });
  }

  async function boot() {
    buildShell();
    if (window.DiyBasDashboard) window.DiyBasDashboard.setAuthContext(currentUser);
    void navigate('overview');
  }

  async function init() {
    try {
      const me = await fetch('/api/auth/me');
      const payload = await me.json();
      if (payload?.authenticated && payload?.user) {
        currentUser = payload.user;
        await boot();
        return;
      }
    } catch (_) {}
    showLogin();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    void init();
  }
})();
