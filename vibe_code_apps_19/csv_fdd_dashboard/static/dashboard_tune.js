(function () {
  const pageId = window.DASHBOARD_PAGE || "index";
  const notesEl = document.getElementById("page-notes");
  const contentEl = document.getElementById("page-content");
  const refreshBtn = document.getElementById("btn-refresh-page");
  const saveBtn = document.getElementById("btn-save-session");
  const exportBtn = document.getElementById("btn-export-package");
  const statusEl = document.getElementById("tune-live-status");

  let config = null;
  let paramState = {};
  let refreshTimer = null;
  let refreshInFlight = false;
  let pendingRefresh = false;
  const DEBOUNCE_MS = 900;

  function fmt(val, step) {
    const d = String(step).includes(".") ? 2 : 0;
    return Number(val).toFixed(d);
  }

  function setStatus(msg, kind) {
    if (!statusEl) return;
    statusEl.textContent = msg;
    statusEl.className = "tune-status" + (kind ? " " + kind : "");
  }

  function syncParamUi(key, val, step, unit) {
    document.querySelectorAll(`[data-param-key="${key}"]`).forEach((field) => {
      const range = field.querySelector('input[type="range"]');
      const num = field.querySelector('input[type="number"]');
      const label = field.querySelector(".val");
      if (range) range.value = val;
      if (num) num.value = val;
      if (label) label.textContent = `${fmt(val, step)} ${unit}`;
    });
  }

  function makeField(p, idPrefix) {
    const key = p.key;
    const val = paramState[key] ?? p.default;
    const uid = `${idPrefix}-${key}`;
    const field = document.createElement("div");
    field.className = "tune-field";
    field.dataset.paramKey = key;
    field.innerHTML = `
      <label for="${uid}-range">${p.label}
        <span class="val">${fmt(val, p.step)} ${p.unit}</span>
      </label>
      <input type="range" id="${uid}-range" min="${p.min}" max="${p.max}" step="${p.step}" value="${val}" />
      <input type="number" id="${uid}-num" min="${p.min}" max="${p.max}" step="${p.step}" value="${val}" />
    `;
    const range = field.querySelector('input[type="range"]');
    const num = field.querySelector('input[type="number"]');

    function onChange(v) {
      if (window.DASHBOARD_SESSION && !window.DASHBOARD_SESSION.can_edit) return;
      paramState[key] = Number(v);
      syncParamUi(key, v, p.step, p.unit);
      scheduleRefresh();
      highlightRule(p.rule);
    }

    range.addEventListener("input", () => onChange(range.value));
    num.addEventListener("change", () => onChange(num.value));
    return field;
  }

  function highlightRule(rule) {
    document.querySelectorAll(".ecm-card[data-rule], .card[data-rule]").forEach((el) => el.classList.remove("tune-highlight"));
    if (!rule) return;
    document.querySelectorAll(`.ecm-card[data-rule="${rule}"], .card[data-rule="${rule}"]`).forEach((el) => el.classList.add("tune-highlight"));
  }

  function buildRuleBox(ruleGroup, idPrefix) {
    const box = document.createElement("div");
    box.className = "rule-tune-box";
    box.dataset.rule = ruleGroup.rule;
    const h = document.createElement("h4");
    h.innerHTML = `${ruleGroup.group} <span class="rule-id">${ruleGroup.rule}</span>`;
    box.appendChild(h);
    ruleGroup.params.forEach((p) => box.appendChild(makeField(p, idPrefix)));
    return box;
  }

  function mountControls(ruleGroups) {
    const byRule = {};
    ruleGroups.forEach((g) => {
      byRule[g.rule] = g;
    });

    document.querySelectorAll(".rule-tune-mount[data-rule], .ecm-card[data-rule]").forEach((mount, idx) => {
      const rule = mount.dataset.rule;
      const group = byRule[rule];
      let target = mount;
      if (mount.classList.contains("ecm-card")) {
        target = mount.querySelector(".rule-tune-mount") || (() => {
          const el = document.createElement("div");
          el.className = "rule-tune-mount";
          el.dataset.rule = rule;
          mount.insertBefore(el, mount.querySelector(".ecm-chart"));
          return el;
        })();
      }
      target.innerHTML = "";
      if (!group) return;
      if (window.DASHBOARD_SESSION && !window.DASHBOARD_SESSION.can_edit) return;
      target.appendChild(buildRuleBox(group, `inline-${idx}`));
    });
  }

  function injectAnalytics(analytics) {
    if (!analytics || !analytics.ecms) return;
    analytics.ecms.forEach((e) => {
      const rule = e.rule_id;
      document.querySelectorAll(`.ecm-analytics[data-analytics-for="${rule}"]`).forEach((el) => {
        el.innerHTML =
          `<table class="table table-sm ecm-analytics-table mb-0"><tbody>` +
          `<tr><td>Fault hours</td><td>${Number(e.fault_hours || 0).toFixed(1)} h</td></tr>` +
          `<tr><td>% of period</td><td>${Number(e.fault_pct || 0).toFixed(1)}%</td></tr>` +
          `</tbody></table>`;
      });
    });
  }

  async function loadConfig() {
    const res = await fetch(`/api/config?page=${pageId}`);
    config = await res.json();
    paramState = { ...config.params };
    window.DASHBOARD_SESSION = config;
    mountControls(config.params_by_rule || []);
    if (notesEl && config.notes && config.notes[pageId]) {
      notesEl.value = config.notes[pageId];
    }
    setStatus(`${(config.page_params || []).length} parameters · live refresh on`, "");
  }

  async function refreshPage() {
    if (refreshInFlight) {
      pendingRefresh = true;
      return;
    }
    refreshInFlight = true;
    if (refreshBtn) refreshBtn.disabled = true;
    setStatus("Recomputing charts…", "live");
    try {
      const body = { note: notesEl ? notesEl.value : "" };
      if (window.DASHBOARD_SESSION && window.DASHBOARD_SESSION.can_edit) {
        body.params = paramState;
      }
      const res = await fetch(`/api/refresh/${pageId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Refresh failed");
      if (contentEl) {
        contentEl.innerHTML = data.content;
        mountControls(config.params_by_rule || []);
        injectAnalytics(data.analytics);
      }
      if (data.params) paramState = data.params;
      setStatus("Live — charts updated", "live");
    } catch (err) {
      setStatus("Refresh failed: " + err.message, "err");
    } finally {
      refreshInFlight = false;
      if (refreshBtn) refreshBtn.disabled = false;
      if (pendingRefresh) {
        pendingRefresh = false;
        refreshPage();
      }
    }
  }

  function scheduleRefresh() {
    if (refreshTimer) clearTimeout(refreshTimer);
    setStatus("Adjusting…", "live");
    refreshTimer = setTimeout(() => refreshPage(), DEBOUNCE_MS);
  }
  window.scheduleRefresh = scheduleRefresh;

  async function saveSession() {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        params: paramState,
        notes: { [pageId]: notesEl ? notesEl.value : "" },
      }),
    });
    const data = await res.json();
    if (!data.ok) throw new Error("Save failed");
  }

  async function exportPackage() {
    if (exportBtn) exportBtn.disabled = true;
    try {
      await saveSession();
      const res = await fetch("/api/export", { method: "POST" });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Export failed");
      alert(`Read-only package ready!\n\nFolder: ${data.out_dir}\nZip: ${data.zip_path}`);
      if (window.DASHBOARD_SESSION) window.DASHBOARD_SESSION.locked = true;
    } catch (err) {
      alert("Export failed: " + err.message);
    } finally {
      if (exportBtn) exportBtn.disabled = false;
    }
  }

  if (refreshBtn) refreshBtn.addEventListener("click", () => refreshPage());
  if (saveBtn) {
    saveBtn.addEventListener("click", () =>
      saveSession().then(() => setStatus("Settings saved", "live")).catch((e) => setStatus(e.message, "err"))
    );
  }
  if (exportBtn) exportBtn.addEventListener("click", exportPackage);

  loadConfig()
    .then(() => refreshPage())
    .catch((e) => setStatus(String(e.message), "err"));
})();
