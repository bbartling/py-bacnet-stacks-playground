(function () {
  'use strict';

  function escapeHtml(s) {
    return String(s ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  function pointSelectOptions(points, { commandableOnly = false } = {}) {
    return (points || [])
      .filter((p) => !!p.pointId && !!p.objectIdentifier && Number(p.deviceInstance || 0) > 0)
      .filter((p) => (commandableOnly ? !!p.commandable : true))
      .map((p) => `<option value="${escapeHtml(p.pointId)}">${escapeHtml(`${p.deviceInstance} · ${p.label || p.objectIdentifier || p.pointId}`)}</option>`)
      .join('');
  }

  function findPoint(points, pointId) {
    return (points || []).find((p) => String(p.pointId) === String(pointId)) || null;
  }

  function render(state) {
    const statusById = {};
    (state.wiresheetStatus || []).forEach((s) => {
      statusById[String(s.id)] = s;
    });
    const rulesRows = (state.wiresheetRules || [])
      .map((r) => {
        const st = statusById[String(r.id)] || {};
        const cls = st.state === 'good' ? 'dash-wire-good' : st.state === 'down' ? 'dash-wire-down' : 'dash-wire-wait';
        const outputs = Array.isArray(r.outputs) ? r.outputs.map((o) => escapeHtml(o.label || o.objectIdentifier || o.pointId || '')).join(', ') : '';
        return `<tr class="${cls}">
          <td>${escapeHtml(r.name || r.id)}</td>
          <td>${escapeHtml(String(r.pollMinutes || 5))} min</td>
          <td>${escapeHtml(String(st.priority ?? r.priority ?? 'null'))}</td>
          <td>${escapeHtml(String(st.inputValue ?? '—'))}</td>
          <td>${escapeHtml(st.state || 'waiting')}</td>
          <td>${escapeHtml(st.message || '')}</td>
          <td>${outputs}</td>
          <td>
            <button class="btn btn-sm" data-act="wire-run" data-id="${escapeHtml(r.id)}">Run now</button>
            <button class="btn btn-sm danger" data-act="wire-delete" data-id="${escapeHtml(r.id)}">Delete</button>
          </td>
        </tr>`;
      })
      .join('');
    return `
      <div class="dash-view-inner">
        <section class="panel">
          <div class="dash-panel-head"><h2>Global Logic Wire Sheet</h2><span>Read input, write commandable outputs, verify</span></div>
          <p class="dash-small-note">Use one input sensor to broadcast values to many commandable output points. Colors: green good, yellow waiting verify, red down.</p>
          <div class="dash-config-row"><span>Rule Name</span><span><input id="wire-name" class="control" placeholder="Outside Air Share" /></span></div>
          <div class="dash-config-row"><span>Input Point</span><span><select id="wire-input" class="control">${pointSelectOptions(state.points, { commandableOnly: false })}</select></span></div>
          <div class="dash-config-row">
            <span>Poll / Priority</span>
            <span>
              <select id="wire-poll" class="control" style="max-width:130px; margin-right:.4rem;">
                <option value="1">1 min</option><option value="5" selected>5 min</option><option value="15">15 min</option><option value="30">30 min</option><option value="60">60 min</option>
              </select>
              <select id="wire-priority" class="control" style="max-width:130px;">
                <option value="">No priority</option>
                <option value="1">Priority 1</option><option value="2">Priority 2</option><option value="8">Priority 8</option><option value="16">Priority 16</option>
              </select>
            </span>
          </div>
          <div class="dash-config-row"><span>Commandable Outputs</span><span><select id="wire-outputs" class="control" multiple size="8" style="min-width:460px;">${pointSelectOptions(state.points, { commandableOnly: true })}</select></span></div>
          <div style="margin-top:.75rem;"><button class="btn primary" data-act="wire-save">Save Global Logic Rule</button></div>
        </section>
        <section class="panel">
          <div class="dash-panel-head"><h2>Saved Wire Sheet Rules</h2><span>${(state.wiresheetRules || []).length} rules</span></div>
          <div class="dash-table-wrap">
            <table class="dash-table">
              <thead><tr><th>Name</th><th>Poll</th><th>Priority</th><th>Input Value</th><th>Status</th><th>Message</th><th>Outputs</th><th>Actions</th></tr></thead>
              <tbody>${rulesRows || '<tr><td colspan="8">No global logic rules yet.</td></tr>'}</tbody>
            </table>
          </div>
        </section>
      </div>`;
  }

  function bind({ mountEl, state, isIntegrator, fetchJson, refresh, setRoute, paint, apiBase }) {
    mountEl.querySelectorAll('[data-act="wire-save"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!isIntegrator()) return;
        const inputPointId = mountEl.querySelector('#wire-input')?.value || '';
        const inputPoint = findPoint(state.points, inputPointId);
        if (!inputPoint) return;
        const outputsSel = mountEl.querySelector('#wire-outputs');
        const selected = Array.from(outputsSel?.selectedOptions || []).map((o) => o.value);
        const outputs = selected
          .map((pointId) => findPoint(state.points, pointId))
          .filter((p) => !!p)
          .map((p) => ({
            pointId: p.pointId,
            label: p.label || p.objectIdentifier || p.pointId,
            deviceInstance: Number(p.deviceInstance || 0),
            objectIdentifier: p.objectIdentifier || '',
            propertyIdentifier: p.propertyIdentifier || 'present-value',
          }));
        await fetchJson(`${apiBase}/wiresheet/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            name: mountEl.querySelector('#wire-name')?.value || 'Global Logic',
            enabled: true,
            pollMinutes: Number(mountEl.querySelector('#wire-poll')?.value || 5),
            priority: mountEl.querySelector('#wire-priority')?.value || null,
            inputPointId: inputPoint.pointId,
            inputDeviceInstance: Number(inputPoint.deviceInstance || 0),
            inputObjectIdentifier: inputPoint.objectIdentifier || '',
            inputPropertyIdentifier: inputPoint.propertyIdentifier || 'present-value',
            outputs,
          }),
        });
        await refresh();
        setRoute('wiresheet');
        paint();
      });
    });
    mountEl.querySelectorAll('[data-act="wire-delete"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!isIntegrator()) return;
        const id = btn.getAttribute('data-id');
        if (!id) return;
        await fetchJson(`${apiBase}/wiresheet/config/${encodeURIComponent(id)}`, { method: 'DELETE' });
        await refresh();
        setRoute('wiresheet');
        paint();
      });
    });
    mountEl.querySelectorAll('[data-act="wire-run"]').forEach((btn) => {
      btn.addEventListener('click', async () => {
        if (!isIntegrator()) return;
        const id = btn.getAttribute('data-id');
        if (!id) return;
        await fetchJson(`${apiBase}/wiresheet/run/${encodeURIComponent(id)}`, { method: 'POST' });
        await refresh();
        setRoute('wiresheet');
        paint();
      });
    });
  }

  window.DiyBasWiresheet = {
    render,
    bind,
  };
})();
