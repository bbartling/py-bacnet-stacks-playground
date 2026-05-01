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

  /** Day-to-day / building operations (integrator sidebar — neutral “user” styling). */
  const NAV_USER_INTEGRATOR = [
    'overview',
    'trends',
    'alarms',
    'notifications',
    'schedule',
    'dockerlogs',
  ];
  /** Engineering + point/device administration (integrator sidebar — green styling). */
  const NAV_SYSTEM_INTEGRATOR = ['discovery', 'devices', 'points', 'wiresheet', 'builder'];

  const NAV_INTEGRATOR_ALL = NAV_USER_INTEGRATOR.concat(NAV_SYSTEM_INTEGRATOR);

  const NAV_BUILDING_OPERATOR_BASE = ['overview', 'devices', 'alarms', 'trends'];

  const NAV_LABELS = {
    overview: 'Overview',
    builder: 'Custom Dashboard',
    wiresheet: 'Global Logic Wire Sheet',
    discovery: 'Discovery',
    devices: 'Devices',
    points: 'Points',
    trends: 'Trends',
    alarms: 'Alarms',
    notifications: 'Notifications',
    schedule: 'Schedule',
    dockerlogs: 'Docker logs',
  };
  function routesForUser() {
    if (!currentUser) return [];
    if (currentUser.role === 'system_integrator') {
      return NAV_INTEGRATOR_ALL.slice();
    }
    const routes = NAV_BUILDING_OPERATOR_BASE.slice();
    if (currentUser.basRole === 'maintenance') routes.push('dockerlogs');
    return routes;
  }

  function escNav(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/"/g, '&quot;');
  }

  function adminLinksHtml() {
    if (!currentUser) return '';
    const br = currentUser.basRole || '';
    const showManage = currentUser.isSuperuser || br === 'system_integrator' || br === 'maintenance';
    if (!showManage) return '';
    const parts = ['<br/><span class="bas-sidebar-links">'];
    parts.push('<a href="/bas/manage/" target="_blank" rel="noopener">Users &amp; roles</a>');
    if (currentUser.isSuperuser) {
      parts.push(' · <a href="/admin/" target="_blank" rel="noopener">Django admin</a>');
    }
    parts.push('</span>');
    return parts.join('');
  }

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
    return routesForUser().includes(route);
  }

  async function navigate(route) {
    if (!canAccessRoute(route)) route = 'overview';
    const fromRoute = currentRoute;
    if (typeof console !== 'undefined' && console.info) {
      console.info('[diy-bas][shell]', 'navigate', {
        from: fromRoute,
        to: route,
        role: currentUser?.role,
        basRole: currentUser?.basRole,
      });
    }
    currentRoute = route;
    setNavActive(route);

    if (route === 'schedule') {
      if (!dashboardInited && dashboardInner && window.DiyBasDashboard) {
        await window.DiyBasDashboard.init(dashboardInner);
        dashboardInited = true;
      }
      if (window.DiyBasDashboard) {
        window.DiyBasDashboard.setRoute('schedule');
      }
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

  function navItemTone(route) {
    if (currentUser?.role === 'system_integrator' && NAV_SYSTEM_INTEGRATOR.includes(route)) {
      return 'integrator';
    }
    return 'user';
  }

  function navButton(route) {
    const tone = navItemTone(route);
    const cls = ['bas-nav-item', tone === 'integrator' ? 'bas-nav-item--integrator' : 'bas-nav-item--user'];
    if (route === currentRoute) cls.push('bas-nav-item-active');
    const label = escNav(NAV_LABELS[route] || route);
    return `<button type="button" class="${cls.join(' ')}" data-route="${route}">${label}</button>`;
  }

  /** Sidebar: grouped for integrators; single block for operators. */
  function navHtmlForRole() {
    if (!currentUser) return '';
    const role = currentUser.role;
    if (role === 'system_integrator') {
      const userBtns = NAV_USER_INTEGRATOR.map(navButton).join('');
      const intBtns = NAV_SYSTEM_INTEGRATOR.map(navButton).join('');
      return `
        <div class="bas-nav-group bas-nav-group--user" role="group" aria-label="Building and operations">
          <div class="bas-nav-group-label">Building &amp; operations</div>
          <div class="bas-nav-group-items">${userBtns}</div>
        </div>
        <div class="bas-nav-group bas-nav-group--integrator" role="group" aria-label="System integrator">
          <div class="bas-nav-group-label">System integrator</div>
          <div class="bas-nav-group-items">${intBtns}</div>
        </div>`;
    }
    const routes = routesForUser();
    const btns = routes.map(navButton).join('');
    return `
      <div class="bas-nav-group bas-nav-group--user" role="group" aria-label="Operations">
        <div class="bas-nav-group-label">Operations</div>
        <div class="bas-nav-group-items">${btns}</div>
      </div>`;
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
        <nav class="bas-nav" aria-label="Views">${navHtmlForRole()}</nav>
        <p class="bas-sidebar-foot">
          Signed in as <strong>${currentUser?.username || 'unknown'}</strong><br/>Role: <strong>${currentUser?.basRole || currentUser?.role || 'unknown'}</strong>${currentUser?.readOnly ? ' · <span title="Write actions blocked server-side">read-only</span>' : ''}
          ${adminLinksHtml()}
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
      if (typeof console !== 'undefined' && console.info) {
        console.info('[diy-bas][shell]', 'manual refresh');
      }
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
        <h1 class="bas-login-brand">DIY BAS</h1>
        ${errorText ? `<p class="dash-error-banner">${errorText}</p>` : ''}
        <label><span class="bas-login-label">Username</span><input id="login-username" class="control" type="text" value="" autocomplete="username" /></label>
        <label><span class="bas-login-label">Password</span><input id="login-password" class="control" type="password" value="" autocomplete="current-password" /></label>
        <button class="btn primary" id="login-submit">Sign in</button>
      </div>`;
    root.querySelector('#login-submit')?.addEventListener('click', async () => {
      const username = root.querySelector('#login-username')?.value?.trim() || '';
      const password = root.querySelector('#login-password')?.value || '';
      if (!username) {
        showLogin('Enter your username.');
        return;
      }
      if (!password) {
        showLogin('Enter your password.');
        return;
      }
      try {
        const res = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ username, password }),
        });
        const data = await res.json();
        if (!res.ok || !data?.ok) throw new Error(data?.error || 'login failed');
        currentUser = data.user;
        if (typeof console !== 'undefined' && console.info) {
          console.info('[diy-bas][shell]', 'login ok', { user: currentUser.username, role: currentUser.role });
        }
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
