(function () {
  'use strict';

  function esc(v) {
    return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
                  <span>Point</span>
                  <span>Object</span>
                  <span>Mode</span>
                  <span>Updated</span>
                  <span>Value</span>
                </div>
                <ul class="points-tree-list">
                  ${rows
                    .map(
                      (p) => `
                      <li class="points-tree-item points-tree-${esc(p.valueState || 'fresh')}" data-point-id="${esc(p.pointId)}">
                        <span class="points-tree-name">${esc(p.label || p.objectIdentifier || p.pointId)}</span>
                        <span class="points-tree-meta">${esc(p.objectIdentifier || '')}</span>
                        <span class="points-tree-meta">${p.commandable ? 'commandable' : 'readonly'}</span>
                        <span class="points-tree-meta">${esc(p.lastUpdated || '—')}</span>
                        <span class="points-tree-value">${esc(p.value ?? '—')}</span>
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
        showMenu(e.clientX, e.clientY, pointId, handlers);
      });
    });
  }

  function showMenu(x, y, pointId, handlers) {
    closeMenu();
    const m = document.createElement('div');
    m.className = 'points-menu';
    m.innerHTML = `
      <button data-act="poll-true">Set polling true</button>
      <button data-act="poll-false">Set polling false</button>
      <button data-act="poll-fast">Polling 10s</button>
      <button data-act="poll-medium">Polling 30s</button>
      <button data-act="poll-slow">Polling 120s</button>
      <button data-act="alarm-config">Configure alarm</button>
      <button data-act="delete">Delete point</button>
    `;
    m.style.left = `${x}px`;
    m.style.top = `${y}px`;
    m.addEventListener('click', async (e) => {
      const act = e.target && e.target.getAttribute ? e.target.getAttribute('data-act') : '';
      closeMenu();
      if (act === 'poll-true' && handlers.onSetPolling) await handlers.onSetPolling(pointId, true);
      if (act === 'poll-false' && handlers.onSetPolling) await handlers.onSetPolling(pointId, false);
      if (act === 'poll-fast' && handlers.onSetPollingPreset) await handlers.onSetPollingPreset(pointId, 10);
      if (act === 'poll-medium' && handlers.onSetPollingPreset) await handlers.onSetPollingPreset(pointId, 30);
      if (act === 'poll-slow' && handlers.onSetPollingPreset) await handlers.onSetPollingPreset(pointId, 120);
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
