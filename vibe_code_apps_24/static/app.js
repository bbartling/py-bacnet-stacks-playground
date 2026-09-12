const THEME_KEY = "vibe24-theme";
const MODE_LABELS = ["OFF", "HEAT", "COOL", "FAN"];
let lastMode = null;
let speedDirty = false;

function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

function applyTheme(theme) {
  const next = theme === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch (e) {}
  const btn = document.getElementById("theme-toggle");
  if (btn) {
    const label = btn.querySelector(".label");
    if (label) label.textContent = next === "light" ? "Light" : "Dark";
  }
}

document.getElementById("theme-toggle")?.addEventListener("click", () => {
  applyTheme(currentTheme() === "dark" ? "light" : "dark");
});
applyTheme(currentTheme());

function fmt(n, digits = 2) {
  return Number(n).toFixed(digits);
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function stamp() {
  return new Date().toLocaleTimeString([], { hour12: false });
}

function logEvent(kind, message) {
  const box = document.getElementById("event-log");
  if (!box) return;
  const row = document.createElement("div");
  const cls = kind === "mode" ? "mode" : "op";
  row.innerHTML = `<span class="ts">${stamp()}</span><span class="${cls}">${message}</span>`;
  box.prepend(row);
  while (box.children.length > 40) box.removeChild(box.lastChild);
}

function updateClock(clock, claim) {
  if (!clock) return;
  const month = Number(clock.month ?? 0);
  const day = Number(clock.day ?? 0);
  const hour = Number(clock.hour ?? 0);
  const minute = Number(clock.minute ?? 0);
  setText("chip-DATE", `${String(month).padStart(2, "0")}/${String(day).padStart(2, "0")}`);
  setText("chip-TIME", `${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`);
  const factor = Number(clock.realtime_factor ?? 0);
  const paused = Boolean(clock.paused);
  setText("chip-SPEED", paused ? "PAUSE" : factor ? `${factor}×` : "—");
  const claimEl = document.getElementById("claim-line");
  if (claimEl && claim) {
    claimEl.innerHTML = `${claim} · sim ${clock.label || "—"} · UI writes at BACnet priority <b>8</b>`;
  }
  const slider = document.getElementById("speed-slider");
  if (slider && !speedDirty && factor) slider.value = String(Math.round(factor));
  setText("speed-label", paused ? `paused · ${factor}×` : factor ? `${factor}×` : "—");
  const pauseBtn = document.getElementById("btn-pause");
  if (pauseBtn) pauseBtn.textContent = paused ? "Resume" : "Pause";
}

async function setSpeed(factor) {
  const res = await fetch("/speed", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ realtime_factor: Number(factor) }),
  });
  speedDirty = false;
  if (res.ok) {
    logEvent("op", `SPEED ${factor}× realtime`);
    await refresh();
  }
}

async function setPaused(paused) {
  const res = await fetch("/pause", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ paused: Boolean(paused) }),
  });
  if (res.ok) {
    logEvent("op", paused ? "PAUSE" : "RESUME");
    await refresh();
  }
}

async function stepOnce() {
  const res = await fetch("/step?sim_minutes=1", { method: "POST" });
  if (res.ok) {
    logEvent("op", "STEP +1 sim-min");
    await refresh();
  }
}

document.getElementById("speed-slider")?.addEventListener("input", (ev) => {
  speedDirty = true;
  setText("speed-label", `${ev.target.value}×`);
});
document.getElementById("speed-slider")?.addEventListener("change", (ev) => setSpeed(ev.target.value));
document.getElementById("btn-pause")?.addEventListener("click", async () => {
  const chip = document.getElementById("chip-SPEED")?.textContent || "";
  await setPaused(chip !== "PAUSE");
});
document.getElementById("btn-step")?.addEventListener("click", () => stepOnce());

function updateMimic(byName) {
  const mode = Math.round(Number(byName["MODE"]?.present_value ?? 0));
  const fanOn = Number(byName["FAN-S"]?.present_value ?? 0) >= 0.5;
  const enable = Number(byName["UNIT-ENABLE"]?.present_value ?? 0) >= 0.5;
  const mimic = document.getElementById("mimic");
  if (mimic) {
    mimic.dataset.mode = String(mode);
    mimic.dataset.fan = fanOn ? "1" : "0";
    mimic.dataset.enable = enable ? "1" : "0";
  }
  if (lastMode !== null && lastMode !== mode) {
    logEvent("mode", `MODE ${MODE_LABELS[lastMode] || lastMode} → ${MODE_LABELS[mode] || mode}`);
  }
  lastMode = mode;

  setText("svg-OA-T", fmt(byName["OA-T"]?.present_value, 1));
  setText("svg-ZONE-T", fmt(byName["ZONE-T"]?.present_value, 1));
  setText("svg-HEAT-EFF", fmt(byName["HEAT-EFF"]?.present_value, 1));
  setText("svg-COOL-EFF", fmt(byName["COOL-EFF"]?.present_value, 1));
  setText("ro-HEAT-EFF", fmt(byName["HEAT-EFF"]?.present_value, 1));
  setText("ro-COOL-EFF", fmt(byName["COOL-EFF"]?.present_value, 1));
  setText("svg-RTU-KW", `${fmt(byName["RTU-KW"]?.present_value, 2)} kW`);
  setText("svg-FAN-S", fanOn ? "ON" : "OFF");
  setText("svg-MODE", MODE_LABELS[mode] || String(mode));
  setText("chip-MODE", MODE_LABELS[mode] || String(mode));
  setText("chip-FAN", fanOn ? "ON" : "OFF");
  setText("chip-KW", fmt(byName["RTU-KW"]?.present_value, 2));
  setText("chip-ZONE", fmt(byName["ZONE-T"]?.present_value, 1));
}

async function refresh() {
  const res = await fetch("/points");
  const data = await res.json();
  const byName = Object.fromEntries(data.points.map((p) => [p.name, p]));
  updateMimic(byName);
  updateClock(data.clock, data.claim);

  const tbody = document.querySelector("#points tbody");
  if (tbody) {
    tbody.innerHTML = "";
    for (const p of data.points) {
      const input = document.getElementById("in-" + p.name);
      if (input && document.activeElement !== input) input.value = Number(p.present_value);
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${p.name}</td><td>${fmt(p.present_value, 3)}</td><td>${p.winning_priority ?? "—"}</td><td>${p.winning_source ?? "—"}</td><td>${p.kind}</td>`;
      tbody.appendChild(tr);
    }
  }
}

document.querySelectorAll("[data-write]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const name = btn.getAttribute("data-write");
    const input = document.getElementById("in-" + name);
    const value = Number(input.value);
    const res = await fetch(`/points/${name}/write`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value, priority: 8, source: "ui" }),
    });
    if (res.ok) {
      const body = await res.json();
      logEvent(
        "op",
        `WRITE ${name}=${value} @8 → HEAT-EFF ${fmt(body.heat_eff, 1)} / COOL-EFF ${fmt(body.cool_eff, 1)}`,
      );
    }
    await refresh();
  });
});

document.querySelectorAll("[data-rel]").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const name = btn.getAttribute("data-rel");
    const res = await fetch(`/points/${name}/relinquish`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ priority: 8 }),
    });
    if (res.ok) logEvent("op", `RELINQUISH ${name} @ prio 8`);
    await refresh();
  });
});

refresh();
setInterval(refresh, 1000);
