/* BRICK data model tab — export/import, TTL popup, health check, AI prompt */

(function () {
  "use strict";

  const BRICK_EQUIPMENT_CLASSES = [
    "Air_Handling_Unit",
    "Variable_Air_Volume_Box",
    "Variable_Air_Volume_Box_With_Reheat",
    "Chiller",
    "Boiler",
    "HVAC_Equipment",
  ];

  const BRICK_POINT_CLASSES = [
    "Zone_Air_Temperature_Sensor",
    "Supply_Air_Temperature_Sensor",
    "Return_Air_Temperature_Sensor",
    "Outside_Air_Temperature_Sensor",
    "Mixed_Air_Temperature_Sensor",
    "Sensor",
  ];

  const DATA_MODEL_REDESIGN_PROMPT = `You are an HVAC ontology engineer for Vibe12 (AWS IoT + DynamoDB telemetry).

Task:
1) Wait until I upload BOTH:
   - data_model_export.json from GET /api/data-model/{site}/{building}/export
   - Bake-a-Py FDD rule definitions (JSON list with id, code, config, optional brick_scope)

When files are available:
- Analyze the model JSON and FDD rules together.
- Enrich the model with BRICK classes, equipment/point typing, and relationships (feeds, isFedBy).
- CRITICAL: preserve metadata.external_ref (DynamoDB series_id) for every point with telemetry.
- external_id = operator tag (SAT, ZAT); metadata.external_ref = full series_id.

Import-ready JSON must contain: sites, equipment, points, relationships (optional).
Return === FILE: vibe12_data_model_import_ready.json === with valid JSON only when done.`;

  let exportJsonText = "";
  let importJsonText = "";

  function siteBuilding() {
    const site =
      document.getElementById("dmSiteSelect")?.value ||
      document.getElementById("siteSelect")?.value ||
      "demo";
    const building =
      document.getElementById("dmBuildingSelect")?.value ||
      document.getElementById("buildingSelect")?.value ||
      "pi";
    return { site, building };
  }

  function apiBase() {
    const { site, building } = siteBuilding();
    return "/api/data-model/" + encodeURIComponent(site) + "/" + encodeURIComponent(building);
  }

  function setStatus(msg, cls) {
    const el = document.getElementById("dmStatus");
    if (!el) return;
    el.textContent = msg;
    el.className = "dm-status" + (cls ? " " + cls : "");
  }

  function parseImportPayload(text) {
    const trimmed = String(text || "").trim();
    if (!trimmed) throw new Error("empty JSON");
    let obj;
    try {
      obj = JSON.parse(trimmed);
    } catch (e) {
      const m = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
      if (m) obj = JSON.parse(m[1]);
      else throw e;
    }
    if (obj.import_ready_json) obj = obj.import_ready_json;
    return {
      sites: obj.sites || [],
      equipment: obj.equipment || [],
      points: obj.points || [],
      relationships: obj.relationships || [],
    };
  }

  function writeTtlToPopup(popup, ttl) {
    if (!popup || popup.closed) return;
    const doc = popup.document;
    const escaped = String(ttl)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    doc.write(
      '<!DOCTYPE html><html><head><meta charset="utf-8"><title>Data model TTL</title></head>' +
        '<body style="margin:0;background:#0d1117;color:#c9d1d9;">' +
        '<pre style="margin:0;padding:1rem;font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;line-height:1.4;white-space:pre-wrap;word-break:break-word;">' +
        escaped +
        "</pre></body></html>"
    );
    doc.close();
  }

  async function doExport() {
    try {
      const res = await fetch(apiBase() + "/export");
      const model = await res.json();
      if (!res.ok) throw new Error(model.error || "export failed");
      exportJsonText = JSON.stringify(model, null, 2);
      const ta = document.getElementById("dmExportJson");
      if (ta) ta.value = exportJsonText;
      setStatus(
        "Exported " +
          (model.points || []).length +
          " points, " +
          (model.equipment || []).length +
          " equipment.",
        "ok"
      );
      refreshCounts(model);
    } catch (e) {
      setStatus("Export failed: " + e.message, "err");
    }
  }

  function refreshCounts(model) {
    const el = document.getElementById("dmCounts");
    if (!el || !model) return;
    el.textContent =
      "Sites: " +
      (model.sites || []).length +
      " · Equipment: " +
      (model.equipment || []).length +
      " · Points: " +
      (model.points || []).length;
  }

  async function doValidate() {
    const ta = document.getElementById("dmImportJson");
    const text = ta?.value || importJsonText;
    try {
      const payload = parseImportPayload(text);
      const res = await fetch(apiBase() + "/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload }),
      });
      const data = await res.json();
      const el = document.getElementById("dmHealthOut");
      if (el) el.textContent = JSON.stringify(data, null, 2);
      setStatus(
        data.valid ? "Valid (score " + data.score + ")" : "Issues: " + (data.issues || []).length,
        data.valid ? "ok" : "warn"
      );
    } catch (e) {
      setStatus("Validate failed: " + e.message, "err");
    }
  }

  async function doImport() {
    const ta = document.getElementById("dmImportJson");
    const text = ta?.value || importJsonText;
    try {
      const payload = parseImportPayload(text);
      const res = await fetch(apiBase() + "/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload, replace: true }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "import failed");
      setStatus(
        "Imported " + data.points + " points, " + data.equipment + " equipment.",
        "ok"
      );
      await doExport();
      await refreshTtlStatus();
    } catch (e) {
      setStatus("Import failed: " + e.message, "err");
    }
  }

  async function viewTtlInNewTab() {
    try {
      const popup = window.open("", "_blank");
      if (!popup) {
        setStatus("Popup blocked — allow popups for this site.", "err");
        return;
      }
      popup.document.write("<p style='font-family:sans-serif;padding:1rem'>Loading TTL…</p>");
      const res = await fetch(apiBase() + "/ttl?sync=true");
      const ttl = await res.text();
      if (!res.ok) throw new Error(ttl);
      writeTtlToPopup(popup, ttl);
      setStatus("Opened TTL in new tab (" + ttl.length + " bytes).", "ok");
      await refreshTtlStatus();
    } catch (e) {
      setStatus("TTL view failed: " + e.message, "err");
    }
  }

  async function refreshTtlStatus() {
    try {
      const res = await fetch(apiBase() + "/ttl/status");
      const data = await res.json();
      const chip = document.getElementById("dmTtlStatus");
      if (chip) {
        chip.textContent = data.last_sync_iso
          ? "TTL synced " + data.last_sync_iso
          : "TTL not synced yet";
      }
    } catch (_) {
      /* ignore */
    }
  }

  async function runHealthCheck() {
    try {
      const res = await fetch(apiBase() + "/health");
      const data = await res.json();
      const el = document.getElementById("dmHealthOut");
      if (el) el.textContent = JSON.stringify(data, null, 2);
      setStatus("Health score: " + data.score + " — " + data.summary, data.score >= 80 ? "ok" : "warn");
    } catch (e) {
      setStatus("Health check failed: " + e.message, "err");
    }
  }

  async function copyPrompt() {
    try {
      await navigator.clipboard.writeText(DATA_MODEL_REDESIGN_PROMPT);
      setStatus("Copied LLM prompt to clipboard.", "ok");
    } catch (e) {
      setStatus("Copy failed: " + e.message, "err");
    }
  }

  function downloadExportJson() {
    const text = document.getElementById("dmExportJson")?.value || exportJsonText;
    if (!text) {
      setStatus("Export first.", "warn");
      return;
    }
    const blob = new Blob([text], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    const { site, building } = siteBuilding();
    a.download = "vibe12-data-model-" + site + "-" + building + ".json";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function syncBuildingsFromDashboard() {
    const siteSel = document.getElementById("dmSiteSelect");
    const bldSel = document.getElementById("dmBuildingSelect");
    const dashSite = document.getElementById("siteSelect");
    const dashBld = document.getElementById("buildingSelect");
    if (!siteSel || !bldSel) return;
    try {
      const res = await fetch("/api/buildings");
      const data = await res.json();
      const buildings = data.buildings || [];
      const sites = [...new Set(buildings.map((b) => b.site_id))];
      siteSel.innerHTML = "";
      sites.forEach((s) => {
        const o = document.createElement("option");
        o.value = s;
        o.textContent = s;
        siteSel.appendChild(o);
      });
      if (dashSite?.value) siteSel.value = dashSite.value;
      function fillBuildings() {
        bldSel.innerHTML = "";
        buildings
          .filter((b) => b.site_id === siteSel.value)
          .forEach((b) => {
            const o = document.createElement("option");
            o.value = b.building_id;
            o.textContent = b.building_id;
            bldSel.appendChild(o);
          });
        if (dashBld?.value && siteSel.value === dashSite?.value) bldSel.value = dashBld.value;
      }
      siteSel.onchange = fillBuildings;
      fillBuildings();
    } catch (_) {
      /* ignore */
    }
  }

  function bindDataModelTab() {
    document.getElementById("dmExportBtn")?.addEventListener("click", doExport);
    document.getElementById("dmImportBtn")?.addEventListener("click", doImport);
    document.getElementById("dmValidateBtn")?.addEventListener("click", doValidate);
    document.getElementById("dmTtlBtn")?.addEventListener("click", viewTtlInNewTab);
    document.getElementById("dmHealthBtn")?.addEventListener("click", runHealthCheck);
    document.getElementById("dmCopyPromptBtn")?.addEventListener("click", copyPrompt);
    document.getElementById("dmDownloadBtn")?.addEventListener("click", downloadExportJson);
    document.getElementById("dmImportJson")?.addEventListener("input", (e) => {
      importJsonText = e.target.value;
    });
  }

  window.vibe12DataModelOnTabShown = async function () {
    await syncBuildingsFromDashboard();
    await refreshTtlStatus();
  };

  window.vibe12BrickClassPresets = {
    equipment: BRICK_EQUIPMENT_CLASSES,
    points: BRICK_POINT_CLASSES,
  };

  document.addEventListener("DOMContentLoaded", bindDataModelTab);
})();
