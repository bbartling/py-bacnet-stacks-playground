;(function () {
  'use strict';

  function esc(v) {
    return String(v ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function formatPointValue(value) {
    if (value === null || value === undefined || value === '') return '—';
    if (typeof value === 'boolean') return value ? 'true' : 'false';
    const n = typeof value === 'number' ? value : Number(value);
    if (!Number.isFinite(n)) return String(value);
    if (
      typeof value === 'string' &&
      value.trim() !== '' &&
      !/^[-+]?(?:\d+\.?\d*|\d*\.\d+)(?:[eE][-+]?\d+)?$/.test(value.trim())
    ) {
      return String(value);
    }
    return n.toFixed(2);
  }

  function pollLabel(p) {
    if (!p.pollingEnabled) return 'off';
    return `${Number(p.intervalSec) || 30}s`;
  }

  function pollChip(p) {
    const on = !!p.pollingEnabled;
    const cls = on ? 'points-poll points-poll--on' : 'points-poll points-poll--off';
    return `<span class="${cls}" title="BACnet polling">${esc(pollLabel(p))}</span>`;
  }

  function groupByDevice(points) {
    const map = new Map();
    (points || []).forEach((p) => {
      const key = p.deviceId || `bacnet-device-${p.deviceInstance || 'unknown'}`;
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(p);
    });
    return map;
  }

  function renderTree(points) {
    const byDevice = groupByDevice(points);
    const devices = Array.from(byDevice.keys()).sort();
    if (!devices.length) return '<p class="dash-small-note">No discovered points yet.</p>';
    return `
      <div class="points-tree">
        ${devices
          .map((dev) => {
            const rows = byDevice.get(dev) || [];
            return `
              <details class="points-tree-device" open>
                <summary>${esc(dev)} <span class="points-tree-count">(${rows.length})</span></summary>
                <div class="points-tree-head">
                  <span class="points-tree-hpick"></span>
                  <span>Point</span>
                  <span>Object</span>
                  <span>Mode</span>
                  <span>Poll</span>
                  <span>Updated</span>
                  <span>Value</span>
                </div>
                <ul class="points-tree-list">
                  ${rows
                    .map(
                      (p) => `
                      <li class="points-tree-item points-tree-${esc(p.valueState || 'fresh')}${p.inAlarm ? ' points-tree-alarm' : ''}" data-point-id="${esc(p.pointId)}">
                        <span class="points-tree-pick-wrap"><input type="checkbox" class="points-tree-pick" data-point-id="${esc(p.pointId)}" aria-label="Select for bulk actions" /></span>
                        <span class="points-tree-name">${esc(p.label || p.objectIdentifier || p.pointId)}</span>
                        <span class="points-tree-meta">${esc(p.objectIdentifier || '')}</span>
                        <span class="points-tree-meta">${p.commandable ? 'commandable' : 'readonly'}</span>
                        <span class="points-tree-meta">${pollChip(p)}</span>
                        <span class="points-tree-meta">${esc(p.lastUpdated || '—')}</span>
                        <span class="points-tree-value">${esc(formatPointValue(p.value))}</span>
                      </li>`
                    )
                    .join('')}
                </ul>
              </details>
            `;
          })
          .join('')}
      </div>`;
  }

  function bindContextMenu(rootEl, handlers) {
    rootEl.querySelectorAll('.points-tree-item').forEach((row) => {
      row.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        const pointId = row.getAttribute('data-point-id');
        if (!pointId) return;
        const p = handlers.getPoint ? handlers.getPoint(pointId) : null;
        showMenu(e.clientX, e.clientY, pointId, p, handlers);
      });
    });
  }

  function showMenu(x, y, pointId, point, handlers) {
    closeMenu();
    const m = document.createElement('div');
    m.className = 'points-menu';
    const title = point ? esc(point.label || point.objectIdentifier || pointId) : esc(pointId);
    const cur = point ? pollLabel(point) : '—';
    m.innerHTML = `
      <div class="points-menu-head">Polling <span class="points-menu-cur">(${esc(cur)})</span></div>
      <button type="button" data-act="poll-off">Off</button>
      <button type="button" data-act="poll-10">Every 10s</button>
      <button type="button" data-act="poll-30">Every 30s</button>
      <button type="button" data-act="poll-60">Every 60s</button>
      <button type="button" data-act="poll-120">Every 120s</button>
      <button type="button" data-act="poll-300">Every 300s (5m)</button>
      <button type="button" data-act="poll-read-now">Read value now</button>
      <hr class="points-menu-divider" />
      <div class="points-menu-head">${title}</div>
      ${handlers.canConfigureAlarms ? '<button type="button" data-act="alarm-config">Configure alarm…</button>' : ''}
      <button type="button" data-act="delete">Delete point</button>
    `;
    m.style.left = `${x}px`;
    m.style.top = `${y}px`;
    m.addEventListener('click', async (e) => {
      const btn = e.target && e.target.closest ? e.target.closest('[data-act]') : null;
      const act = btn ? btn.getAttribute('data-act') : '';
      closeMenu();
      if (act === 'poll-off' && handlers.onSetPolling) await handlers.onSetPolling(pointId, false);
      if (act === 'poll-10' && handlers.onSetPollingPreset) await handlers.onSetPollingPreset(pointId, 10);
      if (act === 'poll-30' && handlers.onSetPollingPreset) await handlers.onSetPollingPreset(pointId, 30);
      if (act === 'poll-60' && handlers.onSetPollingPreset) await handlers.onSetPollingPreset(pointId, 60);
      if (act === 'poll-120' && handlers.onSetPollingPreset) await handlers.onSetPollingPreset(pointId, 120);
      if (act === 'poll-300' && handlers.onSetPollingPreset) await handlers.onSetPollingPreset(pointId, 300);
      if (act === 'poll-read-now' && handlers.onReadPointNow) await handlers.onReadPointNow(pointId);
      if (act === 'alarm-config' && handlers.onConfigureAlarm) await handlers.onConfigureAlarm(pointId);
      if (act === 'delete' && handlers.onDeletePoint) await handlers.onDeletePoint(pointId);
    });
    document.body.appendChild(m);
    setTimeout(() => document.addEventListener('click', closeMenu, { once: true }), 0);
  }

  function closeMenu() {
    const old = document.querySelector('.points-menu');
    if (old) old.remove();
  }

  window.DiyBasPointsTree = {
    renderTree,
    bindContextMenu,
  };
})();
