/** Notes-only editor for PythonAnywhere deploy mode (charts are pre-built in site/). */
(function () {
  const pageId = window.DASHBOARD_PAGE || "index";
  const notesEl = document.getElementById("page-notes");
  const saveBtn = document.getElementById("btn-save-notes");

  async function saveNotes() {
    if (!notesEl) return;
    if (saveBtn) saveBtn.disabled = true;
    try {
      const res = await fetch("/api/notes", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ page: pageId, note: notesEl.value }),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.error || "Save failed");
      alert("Notes saved. Charts are still from the last local build — re-run build_pa_deploy.py to update charts.");
    } catch (err) {
      alert("Save failed: " + err.message);
    } finally {
      if (saveBtn) saveBtn.disabled = false;
    }
  }

  if (saveBtn) saveBtn.addEventListener("click", saveNotes);
})();
