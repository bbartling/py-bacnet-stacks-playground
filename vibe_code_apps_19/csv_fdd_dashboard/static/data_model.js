/* Haystack RDF / SPARQL data model UI — Open-FDD py feature parity */

const API = "/api/rdf";
let catalog = null;
let lastBindings = [];
let lastColumns = [];

function $(id) {
  return document.getElementById(id);
}

function setStatus(msg) {
  $("status").textContent = msg;
}

async function api(path, opts = {}) {
  const res = await fetch(API + path, {
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }
  if (!res.ok) throw new Error(res.statusText);
  return res.text();
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("hidden", p.dataset.panel !== name));
}

function renderTable(bindings) {
  const table = $("results-table");
  const thead = table.querySelector("thead");
  const tbody = table.querySelector("tbody");
  thead.innerHTML = "";
  tbody.innerHTML = "";
  lastBindings = bindings || [];
  lastColumns = lastBindings.length ? Object.keys(lastBindings[0]).sort() : [];
  if (!lastBindings.length) return;
  const hr = document.createElement("tr");
  lastColumns.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c;
    hr.appendChild(th);
  });
  thead.appendChild(hr);
  lastBindings.forEach((row) => {
    const tr = document.createElement("tr");
    lastColumns.forEach((c) => {
      const td = document.createElement("td");
      td.textContent = row[c] ?? "";
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
}

function bindingsAsText() {
  if (!lastBindings.length) return "(no results)";
  const lines = [lastColumns.join("\t")];
  lastBindings.forEach((row) => lines.push(lastColumns.map((c) => row[c] ?? "").join("\t")));
  return lines.join("\n");
}

function addPresetButtons(containerId, queries, category) {
  const el = $(containerId);
  el.innerHTML = "";
  queries.filter((q) => q.category === category).forEach((q) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn";
    btn.textContent = q.short_label || q.label;
    btn.title = q.label;
    btn.addEventListener("click", () => {
      const useBacnet = $("include-bacnet").checked && q.query_with_bacnet;
      $("sparql-editor").value = useBacnet ? q.query_with_bacnet : q.query;
      runQuery();
    });
    el.appendChild(btn);
  });
}

async function loadPredefined() {
  catalog = await api("/sparql/predefined");
  $("sparql-editor").value = catalog.default_query || "";
  addPresetButtons("preset-relationships", catalog.queries, "relationships");
  addPresetButtons("preset-haystack", catalog.queries, "haystack");
  addPresetButtons("preset-fdd", catalog.queries, "fdd_coverage");
}

async function loadSummary() {
  const badge = $("summary-badge");
  try {
    const health = await api("/health");
    const s = health.summary || (await api("/summary"));
    const building = health.building || "";
    const csvOk = health.csv_bundles > 0;
    badge.textContent =
      `${building ? building + " · " : ""}${s.ahus || 0} AHUs · ${s.vavs || 0} VAVs · ${s.points || 0} points · ${s.chillers || 0} chillers`;
    badge.className = "badge" + (csvOk && (s.points || 0) > 0 ? " ok" : "");
    if (health.ok) {
      setStatus(`Data loaded — ${health.csv_bundles} historian bundles · model synced`);
    }
  } catch (e) {
    badge.textContent = "model not ready";
    badge.className = "badge err";
    setStatus(String(e.message || e) + " — click Bootstrap from CSV");
  }
}

async function loadExportPreview() {
  try {
    const data = await api("/commissioning-export");
    $("export-text").value = JSON.stringify(data, null, 2);
  } catch (e) {
    $("export-text").value = "";
    setStatus(String(e.message || e));
  }
}

async function loadLlmPrompt() {
  try {
    const text = await fetch(API + "/llm-bundle").then((r) => r.text());
    const promptEnd = text.indexOf("---");
    $("llm-prompt").value = promptEnd > 0 ? text.slice(0, promptEnd).trim() : text.slice(0, 2000);
  } catch {
    $("llm-prompt").value = "(bootstrap model first)";
  }
}

async function runQuery() {
  const query = $("sparql-editor").value.trim();
  if (!query) return;
  setStatus("Running SPARQL…");
  try {
    const result = await api("/sparql", { method: "POST", body: JSON.stringify({ query }) });
    renderTable(result.bindings);
    $("results-meta").textContent = `${result.row_count} rows${result.truncated ? " (truncated)" : ""}`;
    setStatus("SPARQL OK");
  } catch (e) {
    setStatus(String(e.message || e));
  }
}

async function validateAllPresets() {
  setStatus("Validating all predefined SPARQL queries…");
  try {
    const r = await api("/sparql/validate", { method: "POST", body: "{}" });
    const msg = `Validated: ${r.passed?.length || 0} passed, ${r.failed?.length || 0} failed`;
    setStatus(msg);
    if (r.failed?.length) {
      openTextPopup("SPARQL validation failures", JSON.stringify(r.failed, null, 2));
    }
  } catch (e) {
    setStatus(String(e.message || e));
  }
}

async function bootstrapModel() {
  setStatus("Bootstrapping from CSV → model.json + TTL…");
  try {
    const r = await api("/bootstrap", { method: "POST", body: JSON.stringify({ force: true }) });
    setStatus(`Bootstrapped → ${r.ttl_path}\n${JSON.stringify(r.summary)}`);
    await loadSummary();
    await loadExportPreview();
    await loadLlmPrompt();
  } catch (e) {
    setStatus(String(e.message || e));
  }
}

async function syncTtl() {
  const r = await api("/sync-ttl", { method: "POST", body: "{}" });
  setStatus(`Synced TTL → ${r.ttl_path}`);
}

async function doImport(text) {
  const payload = JSON.parse(text);
  const r = await api("/commissioning-import", { method: "POST", body: JSON.stringify({ payload, replace: true }) });
  setStatus(`Imported: ${JSON.stringify(r.counts)}`);
  await loadSummary();
  await loadExportPreview();
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => switchTab(btn.dataset.tab));
});

$("btn-run").addEventListener("click", runQuery);
$("btn-validate-all").addEventListener("click", validateAllPresets);
$("btn-bootstrap").addEventListener("click", bootstrapModel);
$("btn-sync").addEventListener("click", () => syncTtl().catch((e) => setStatus(String(e.message))));
$("btn-export-commissioning").addEventListener("click", () => {
  const blob = new Blob([$("export-text").value || "{}"], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "haystack-commissioning.json";
  a.click();
});
$("btn-view-json-tab").addEventListener("click", () => {
  if (!openTextPopup("haystack-commissioning.json", $("export-text").value || "{}")) {
    setStatus("Popup blocked — allow popups for this site.");
  }
});
$("btn-view-ttl-tab").addEventListener("click", async () => {
  try {
    if (!(await openFetchedTextPopup("data_model.ttl", API + "/ttl"))) setStatus("Popup blocked.");
  } catch (e) {
    setStatus(String(e.message || e));
  }
});
$("btn-download-ttl").addEventListener("click", async () => {
  const text = await fetch(API + "/ttl").then((r) => r.text());
  const blob = new Blob([text], { type: "text/turtle" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "data_model.ttl";
  a.click();
});
$("btn-copy-llm").addEventListener("click", async () => {
  const text = await fetch(API + "/llm-bundle").then((r) => r.text());
  await navigator.clipboard.writeText(text);
  setStatus("Copied LLM prompt + commissioning JSON to clipboard.");
});
$("btn-results-tab").addEventListener("click", () => {
  const q = $("sparql-editor").value.trim();
  openTextPopup("SPARQL results", `Query:\n${q}\n\n---\n\n${bindingsAsText()}`);
});
$("import-file").addEventListener("change", (ev) => {
  const f = ev.target.files?.[0];
  if (!f) return;
  f.text().then((t) => ($("import-text").value = t));
});
$("sparql-file").addEventListener("change", (ev) => {
  const f = ev.target.files?.[0];
  if (!f) return;
  f.text().then((t) => ($("sparql-editor").value = t));
});
$("btn-validate-import").addEventListener("click", () => {
  try {
    JSON.parse($("import-text").value);
    setStatus("Import JSON is valid.");
  } catch (e) {
    setStatus(`Invalid JSON: ${e.message}`);
  }
});
$("btn-do-import").addEventListener("click", () => {
  doImport($("import-text").value).catch((e) => setStatus(String(e.message || e)));
});

loadPredefined();
loadSummary();
loadExportPreview();
loadLlmPrompt();
