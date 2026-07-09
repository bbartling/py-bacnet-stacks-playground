(function () {
  let selRule, selEquip, paramsEl, descEl, runBtn, statusEl, resultEl, errorsEl;
  let catalog = [];

  function setStatus(msg, kind) {
    if (!statusEl) return;
    statusEl.textContent = msg || "";
    statusEl.className = "tune-status" + (kind ? " " + kind : "");
  }

  function currentRule() {
    return catalog.find((r) => r.id === selRule.value);
  }

  function runScripts(container) {
    container.querySelectorAll("script").forEach((old) => {
      const s = document.createElement("script");
      if (old.src) s.src = old.src;
      else s.textContent = old.textContent;
      old.parentNode.replaceChild(s, old);
    });
  }

  function fmt(val, step) {
    return Number(val).toFixed(String(step).includes(".") ? 2 : 0);
  }

  function renderParams() {
    const rule = currentRule();
    paramsEl.innerHTML = "";
    if (!rule) return;
    descEl.innerHTML =
      `<span class="rule-kind rule-kind-${rule.kind}">${rule.kind.toUpperCase()}</span> ` +
      `${rule.description || ""} <em>(${rule.source})</em>`;
    (rule.params || []).forEach((p) => {
      const field = document.createElement("div");
      field.className = "tune-field";
      field.dataset.key = p.key;
      field.innerHTML = `
        <label>${p.label}
          <span class="val">${fmt(p.default, p.step)} ${p.unit}</span>
        </label>
        <input type="range" min="${p.min}" max="${p.max}" step="${p.step}" value="${p.default}" />
        <input type="number" min="${p.min}" max="${p.max}" step="${p.step}" value="${p.default}" />`;
      const range = field.querySelector('input[type="range"]');
      const num = field.querySelector('input[type="number"]');
      const label = field.querySelector(".val");
      function sync(v) {
        range.value = v;
        num.value = v;
        label.textContent = `${fmt(v, p.step)} ${p.unit}`;
      }
      range.addEventListener("input", () => sync(range.value));
      num.addEventListener("change", () => sync(num.value));
      paramsEl.appendChild(field);
    });
  }

  function collectParams() {
    const params = {};
    paramsEl.querySelectorAll(".tune-field").forEach((field) => {
      const num = field.querySelector('input[type="number"]');
      params[field.dataset.key] = Number(num.value);
    });
    return params;
  }

  async function loadCatalog() {
    const res = await fetch("/api/rules");
    const data = await res.json();
    catalog = data.rules || [];
    selRule.innerHTML = catalog
      .map((r) => `<option value="${r.id}">${r.title}</option>`)
      .join("");
    selEquip.innerHTML = (data.equipment || [])
      .map((e) => `<option value="${e}">${e}</option>`)
      .join("");
    if (data.errors && data.errors.length) {
      errorsEl.hidden = false;
      errorsEl.innerHTML =
        "<strong>Plugin load errors:</strong><ul>" +
        data.errors.map((e) => `<li>${e.file}: ${e.error}</li>`).join("") +
        "</ul>";
    }
    renderParams();
    if (!catalog.length) setStatus("No rule plugins found in rules/plugins/", "err");
  }

  async function runRule() {
    const rule = currentRule();
    if (!rule) return;
    runBtn.disabled = true;
    setStatus("Running " + rule.id + "…", "live");
    resultEl.innerHTML = "";
    try {
      const res = await fetch("/api/rules/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rule_id: rule.id,
          equipment_id: selEquip.value,
          params: collectParams(),
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Rule failed");
      const s = data.summary;
      const extra = s.extra && s.extra.engine ? ` · ${s.extra.engine}` : "";
      resultEl.innerHTML = `
        <div class="card ecm-card" data-rule="${data.rule_id}">
          <header class="ecm-head">
            <h3>${data.rule_id} — ${data.equipment_id}</h3>
            <span class="ecm-rule-id">${rule.kind.toUpperCase()}</span>
          </header>
          <div class="grid">
            <div class="kpi"><div class="val">${s.fault_hours.toFixed(1)}</div><div class="lbl">Confirmed fault hours</div></div>
            <div class="kpi"><div class="val">${s.fault_pct.toFixed(1)}%</div><div class="lbl">Of period</div></div>
            <div class="kpi"><div class="val">${s.total_hours.toFixed(0)}</div><div class="lbl">Total hours</div></div>
          </div>
          <p class="note">${s.message || ""}${extra}</p>
          <div class="ecm-chart">${data.chart || ""}</div>
        </div>`;
      runScripts(resultEl);
      setStatus("Done", "live");
    } catch (err) {
      setStatus(err.message, "err");
    } finally {
      runBtn.disabled = false;
    }
  }

  // ---- ML lab: persist fault, upload plugin, pip install, fault stores ----

  function setPersistStatus(msg, kind) {
    const el = document.getElementById("rule-persist-status");
    if (!el) return;
    el.textContent = msg || "";
    el.className = "tune-status" + (kind ? " " + kind : "");
  }

  async function persistFault() {
    const rule = currentRule();
    if (!rule) return;
    setPersistStatus("Persisting " + rule.id + "…", "live");
    try {
      const res = await fetch("/api/ml/persist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rule_id: rule.id,
          equipment_id: selEquip.value,
          params: collectParams(),
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Persist failed");
      const s = data.store;
      const ok = s.verified ? "verified" : "NOT verified";
      setPersistStatus(
        `Wrote ${s.fault_rows}/${s.rows} fault rows (${s.fault_hours} h) → feather, read-back ${ok}.`,
        s.verified ? "live" : "err"
      );
      loadFaultStores();
    } catch (err) {
      setPersistStatus(err.message, "err");
    }
  }

  async function loadFiles() {
    const res = await fetch("/api/ml/files");
    const data = await res.json();
    const sel = document.getElementById("ml-file-select");
    if (sel) {
      sel.innerHTML = (data.files || [])
        .map((f) => `<option value="${f.name}">${f.name}${f.protected ? " (example)" : ""}</option>`)
        .join("");
      if ((data.files || []).length) viewFile(sel.value);
    }
    renderFaultStores(data.faults || []);
  }

  function renderFaultStores(faults) {
    const box = document.getElementById("ml-fault-stores");
    if (!box) return;
    if (!faults.length) {
      box.innerHTML = '<p class="note">No fault stores yet — run a rule and persist it.</p>';
      return;
    }
    box.innerHTML = faults
      .map(
        (f) =>
          `<div class="ml-fault-row"><code>${f.equipment_id} · ${f.rule_id}</code>` +
          `<span>${f.fault_rows}/${f.rows} rows · ${f.fault_hours} h` +
          `${f.verified ? " ✓" : ""}</span></div>`
      )
      .join("");
  }

  async function loadFaultStores() {
    const res = await fetch("/api/ml/files");
    const data = await res.json();
    renderFaultStores(data.faults || []);
  }

  async function viewFile(name) {
    const view = document.getElementById("ml-file-view");
    if (!view || !name) return;
    view.textContent = "Loading…";
    try {
      const res = await fetch("/api/ml/file?name=" + encodeURIComponent(name));
      const data = await res.json();
      view.textContent = data.ok ? data.content : data.error;
    } catch (err) {
      view.textContent = err.message;
    }
  }

  async function uploadPlugin() {
    const input = document.getElementById("ml-upload-file");
    const status = document.getElementById("ml-upload-status");
    if (!input || !input.files || !input.files[0]) {
      if (status) { status.textContent = "Choose a .py file first."; status.className = "tune-status err"; }
      return;
    }
    const fd = new FormData();
    fd.append("file", input.files[0]);
    if (status) { status.textContent = "Uploading…"; status.className = "tune-status live"; }
    try {
      const res = await fetch("/api/ml/upload", { method: "POST", body: fd });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Upload failed");
      if (status) { status.textContent = "Saved " + data.name; status.className = "tune-status live"; }
      await loadCatalog(); // new rule may now be registered
      await loadFiles();
      const sel = document.getElementById("ml-file-select");
      if (sel) { sel.value = data.name; viewFile(data.name); }
    } catch (err) {
      if (status) { status.textContent = err.message; status.className = "tune-status err"; }
    }
  }

  async function pipInstall() {
    const input = document.getElementById("ml-pip-input");
    const status = document.getElementById("ml-pip-status");
    const out = document.getElementById("ml-pip-output");
    const btn = document.getElementById("btn-ml-pip");
    if (!input || !input.value.trim()) {
      if (status) { status.textContent = "Enter package name(s)."; status.className = "tune-status err"; }
      return;
    }
    if (btn) btn.disabled = true;
    if (status) { status.textContent = "Installing…"; status.className = "tune-status live"; }
    try {
      const res = await fetch("/api/ml/pip", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ packages: input.value }),
      });
      const data = await res.json();
      if (out) out.textContent = data.output || data.error || "(no output)";
      if (status) {
        status.textContent = data.ok ? "Installed" : "pip failed (rc " + data.returncode + ")";
        status.className = "tune-status " + (data.ok ? "live" : "err");
      }
    } catch (err) {
      if (status) { status.textContent = err.message; status.className = "tune-status err"; }
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  function init() {
    selRule = document.getElementById("rule-select");
    selEquip = document.getElementById("rule-equipment");
    paramsEl = document.getElementById("rule-params");
    descEl = document.getElementById("rule-description");
    runBtn = document.getElementById("btn-run-rule");
    statusEl = document.getElementById("rule-run-status");
    resultEl = document.getElementById("rule-result");
    errorsEl = document.getElementById("rule-lab-errors");
    if (!selRule || selRule.dataset.ready === "1") return;
    selRule.dataset.ready = "1";
    selRule.addEventListener("change", renderParams);
    runBtn.addEventListener("click", runRule);

    const persistBtn = document.getElementById("btn-persist-fault");
    if (persistBtn) persistBtn.addEventListener("click", persistFault);
    const uploadBtn = document.getElementById("btn-ml-upload");
    if (uploadBtn) uploadBtn.addEventListener("click", uploadPlugin);
    const pipBtn = document.getElementById("btn-ml-pip");
    if (pipBtn) pipBtn.addEventListener("click", pipInstall);
    const fileSel = document.getElementById("ml-file-select");
    if (fileSel) fileSel.addEventListener("change", () => viewFile(fileSel.value));

    loadCatalog();
    loadFiles();
  }

  // The rule-lab body is injected asynchronously via /api/refresh, so poll for it.
  if (window.DASHBOARD_PAGE === "custom_rules") {
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (document.getElementById("rule-select")) {
        clearInterval(timer);
        init();
      } else if (tries > 60) {
        clearInterval(timer);
      }
    }, 250);
  }
})();
