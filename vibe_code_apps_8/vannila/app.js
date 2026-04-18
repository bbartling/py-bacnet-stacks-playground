(function () {
  'use strict';

  /** @type {HTMLElement | null} */
  let elTopTitle = null;
  /** @type {HTMLElement | null} */
  let elTopSub = null;
  /** @type {HTMLElement | null} */
  let elTopPill = null;
  /** @type {HTMLElement | null} */
  let panelDashboard = null;
  /** @type {HTMLElement | null} */
  let panelSchedule = null;
  /** @type {HTMLElement | null} */
  let dashboardInner = null;

  let scheduleMounted = false;
  let dashboardInited = false;
  /** @type {string} */
  let currentRoute = 'overview';

  function updateTopbarForSchedule() {
    if (!elTopTitle || !elTopSub || !elTopPill) return;
    elTopTitle.textContent = 'Weekly equipment schedule';
    elTopSub.textContent =
      'Operating week, holidays, and BACnet points for the active profile. Switch to Overview for site-wide status.';
    elTopPill.textContent = 'Editor';
  }

  function setNavActive(route) {
    const root = document.getElementById('app-root');
    if (!root) return;
    root.querySelectorAll('.bas-nav-item').forEach((btn) => {
      const r = btn.getAttribute('data-route');
      btn.classList.toggle('bas-nav-item-active', r === route);
    });
  }

  async function navigate(route) {
    currentRoute = route;
    setNavActive(route);

    if (route === 'schedule') {
      if (panelDashboard) panelDashboard.hidden = true;
      if (panelSchedule) panelSchedule.hidden = false;
      updateTopbarForSchedule();
      if (!scheduleMounted && panelSchedule && window.Bas8Schedule) {
        window.Bas8Schedule.init(panelSchedule);
        scheduleMounted = true;
      }
      return;
    }

    if (panelSchedule) panelSchedule.hidden = true;
    if (panelDashboard) panelDashboard.hidden = false;

    if (!dashboardInited && dashboardInner && window.Bas8Dashboard) {
      await window.Bas8Dashboard.init(dashboardInner);
      dashboardInited = true;
    }
    if (window.Bas8Dashboard) {
      window.Bas8Dashboard.setRoute(route);
    }
    if (elTopTitle && elTopSub && elTopPill && window.Bas8Dashboard) {
      const m = window.Bas8Dashboard.getTopbarMeta();
      elTopTitle.textContent = m.title;
      elTopSub.textContent = m.subtitle;
      elTopPill.textContent = m.pill;
    }
  }

  function buildShell() {
    const root = document.getElementById('app-root');
    if (!root) return;

    root.className = 'bas-app';
    root.innerHTML = `
      <aside class="bas-sidebar" aria-label="Main navigation">
        <div class="bas-brand">
          <h1 class="bas-brand-title">BAS Lite</h1>
          <p class="bas-brand-sub">Dashboard + schedules</p>
        </div>
        <nav class="bas-nav" aria-label="Views">
          <button type="button" class="bas-nav-item bas-nav-item-active" data-route="overview">Overview</button>
          <button type="button" class="bas-nav-item" data-route="devices">Devices</button>
          <button type="button" class="bas-nav-item" data-route="points">Points</button>
          <button type="button" class="bas-nav-item" data-route="trends">Trends</button>
          <button type="button" class="bas-nav-item" data-route="alarms">Alarms</button>
          <button type="button" class="bas-nav-item" data-route="notifications">Notifications</button>
          <div class="bas-nav-divider" role="presentation"></div>
          <button type="button" class="bas-nav-item bas-nav-item-accent" data-route="schedule">Schedule editor</button>
        </nav>
        <p class="bas-sidebar-foot">
          Static demo UI: <code>/api/*</code> or <code>/app7/api/*</code> is tried first; otherwise mock data is shown until your Flask app is wired.
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
      if (currentRoute === 'schedule' || !window.Bas8Dashboard || !dashboardInited) return;
      await window.Bas8Dashboard.refresh();
      window.Bas8Dashboard.setRoute(currentRoute);
      const m = window.Bas8Dashboard.getTopbarMeta();
      if (elTopTitle) elTopTitle.textContent = m.title;
      if (elTopSub) elTopSub.textContent = m.subtitle;
      if (elTopPill) elTopPill.textContent = m.pill;
    });
  }

  function boot() {
    buildShell();
    void navigate('overview');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
