(function () {
  const pageId = window.DASHBOARD_PAGE || "index";
  const controls = document.getElementById("tune-controls");
  const notesEl = document.getElementById("page-notes");
  const contentEl = document.getElementById("page-content");
  const refreshBtn = document.getElementById("btn-refresh-page");
  const saveBtn = document.getElementById("btn-save-session");
  const exportBtn = document.getElementById("btn-export-package");

  let config = null;
  let paramState = {};

  function fmt(val, step) {
    const d = String(step).includes(".") ? 2 : 0;
    return Number(val).toFixed(d);
  }

  function buildControls(pageParams) {
    if (!controls) return;
    controls.innerHTML = "";
    pageParams.forEach((p) => {
      const key = p.key;
      const val = paramState[key] ?? p.default;
      const field = document.createElement("div");
      field.className = "tune-field";
      field.innerHTML = `
        <label for="param-${key}">${p.label} <span class="val" id="val-${key}">${fmt(val, p.step)} ${p.unit}</span></label>
        <input type="range" id="param-${key}" min="${p.min}" max="${p.max}" step="${p.step}" value="${val}" />
        <input type="number" id="num-${key}" min="${p.min}" max="${p.max}" step="${p.step}" value="${val}" style="width:100%;margin-top:.25rem;background:#0f1419;color:#e8edf4;border:1px solid #334155;border-radius:4px;padding:.2rem .4rem;font-size:.8rem;" />
      `;
      controls.appendChild(field);
      const range = field.querySelector(`#param-${key}`);
      const num = field.querySelector(`#num-${key}`);
      const label = field.querySelector(`#val-${key}`);
      function sync(v) {
        paramState[key] = Number(v);
        range.value = v;
        num.value = v;
        label.textContent = `${fmt(v, p.step)} ${p.unit}`;
      }
      range.addEventListener("input", () => sync(range.value));
      num.addEventListener("change", () => sync(num.value));
    });
  }

  async function loadConfig() {
    const res = await fetch(`/api/config?page=${pageId}`);
    config = await res.json();
    paramState = { ...config.params };
    buildControls(config.page_params || []);
    if (notesEl && config.notes && config.notes[pageId]) {
      notesEl.value = config.notes[pageId];
    }
  }

  async function refreshPage() {
    if (refreshBtn) refreshBtn.disabled = true;
    try {
      const res = await fetch(`/api/refresh/${pageId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          params: paramState,
          note: notesEl ? notesEl.value : "",
        }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Refresh failed");
      if (contentEl) contentEl.innerHTML = data.content;
      paramState = data.params;
    } catch (err) {
      alert("Refresh failed: " + err.message);
    } finally {
      if (refreshBtn) refreshBtn.disabled = false;
    }
  }

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
      alert(
        `Read-only package ready!\n\nFolder: ${data.out_dir}\nZip: ${data.zip_path}\n\nUpload the zip to Google Drive, or deploy the unzipped folder to Netlify / Cloudflare Pages / GCS (see DEPLOY.md inside).`
      );
    } catch (err) {
      alert("Export failed: " + err.message);
    } finally {
      if (exportBtn) exportBtn.disabled = false;
    }
  }

  if (refreshBtn) refreshBtn.addEventListener("click", refreshPage);
  if (saveBtn) saveBtn.addEventListener("click", () => saveSession().then(() => alert("Settings saved.")).catch((e) => alert(e.message)));
  if (exportBtn) exportBtn.addEventListener("click", exportPackage);

  loadConfig().catch((e) => console.error(e));
})();
