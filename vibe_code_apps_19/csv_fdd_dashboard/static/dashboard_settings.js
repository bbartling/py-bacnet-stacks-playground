(function () {
  const panel = document.getElementById("site-settings-panel");
  if (!panel) return;

  const form = panel.querySelector("form");
  const tzEl = document.getElementById("site-timezone");
  const spEl = document.getElementById("site-comfort-sp");
  const bandEl = document.getElementById("site-comfort-band");

  async function loadSettings() {
    const res = await fetch("/api/session");
    const data = await res.json();
    const s = data.site_settings || {};
    if (tzEl && s.timezone) tzEl.value = s.timezone;
    if (spEl && s.comfort_setpoint_f != null) spEl.value = s.comfort_setpoint_f;
    if (bandEl && s.comfort_band_f != null) bandEl.value = s.comfort_band_f;
    const occ = s.occupancy || {};
    ["mon_fri", "sat", "sun"].forEach((key) => {
      const row = panel.querySelector(`[data-schedule="${key}"]`);
      if (!row) return;
      const cfg = occ[key] || {};
      const en = row.querySelector(".sched-enabled");
      const start = row.querySelector(".sched-start");
      const end = row.querySelector(".sched-end");
      if (en) en.checked = cfg.enabled !== false;
      if (start && cfg.start) start.value = cfg.start;
      if (end && cfg.end) end.value = cfg.end;
    });
  }

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const occupancy = {};
    ["mon_fri", "sat", "sun"].forEach((key) => {
      const row = panel.querySelector(`[data-schedule="${key}"]`);
      if (!row) return;
      occupancy[key] = {
        enabled: row.querySelector(".sched-enabled")?.checked ?? true,
        start: row.querySelector(".sched-start")?.value || "06:00",
        end: row.querySelector(".sched-end")?.value || "17:00",
      };
    });
    const payload = {
      site_settings: {
        timezone: tzEl?.value || "America/Chicago",
        comfort_setpoint_f: Number(spEl?.value || 72),
        comfort_band_f: Number(bandEl?.value || 2),
        occupancy,
      },
    };
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!data.ok) {
      alert("Save failed");
      return;
    }
    if (window.scheduleRefresh) window.scheduleRefresh();
    else location.reload();
  });

  loadSettings();
})();
