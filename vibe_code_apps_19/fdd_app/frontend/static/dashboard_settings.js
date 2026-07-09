(function () {
  const panel = document.getElementById("site-settings-panel");
  if (!panel) return;

  const form = panel.querySelector("form");
  const tzEl = document.getElementById("site-timezone");
  const spEl = document.getElementById("site-comfort-sp");
  const bandEl = document.getElementById("site-comfort-band");
  const headerMetaEl = document.getElementById("header-meta");

  const DAY_LABELS = {
    mon_fri: "Mon–Fri",
    sat: "Sat",
    sun: "Sun",
  };

  function fmtSchedule(occ) {
    const parts = [];
    ["mon_fri", "sat", "sun"].forEach((key) => {
      const cfg = occ[key] || {};
      const label = DAY_LABELS[key] || key;
      if (cfg.enabled === false) {
        parts.push(`${label} closed`);
      } else {
        parts.push(`${label} ${cfg.start || "06:00"}–${cfg.end || "17:00"}`);
      }
    });
    return parts.join(" · ");
  }

  function updateHeaderMeta(siteSettings, headerMeta) {
    if (!headerMetaEl) return;
    if (headerMeta) {
      headerMetaEl.textContent = headerMeta;
      return;
    }
    const s = siteSettings || {};
    const tz = s.timezone || "America/Chicago";
    const sp = s.comfort_setpoint_f != null ? s.comfort_setpoint_f : 72;
    const band = s.comfort_band_f != null ? s.comfort_band_f : 2;
    const units = window.DASHBOARD_UNITS || localStorage.getItem("fdd-dashboard-units") || "imperial";
    let setpoint;
    if (units === "metric") {
      const c = ((sp - 32) * 5) / 9;
      const b = (band * 5) / 9;
      setpoint = `${c.toFixed(1)}°C ±${b.toFixed(1)}°C`;
    } else {
      setpoint = `${sp}°F ±${band}°F`;
    }
    const building = (window.DASHBOARD_SESSION && window.DASHBOARD_SESSION.package_title) || "Building";
    const occ = fmtSchedule(s.occupancy || {});
    headerMetaEl.textContent = `${building} · Timezone: ${tz} · Setpoint: ${setpoint} occupied · ${occ}`;
  }

  window.updateHeaderMeta = updateHeaderMeta;

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
    updateHeaderMeta(s);
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
    updateHeaderMeta(payload.site_settings);
    if (window.scheduleRefresh) window.scheduleRefresh();
    else location.reload();
  });

  loadSettings();
})();
