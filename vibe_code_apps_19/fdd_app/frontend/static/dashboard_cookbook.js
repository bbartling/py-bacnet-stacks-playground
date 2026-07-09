// Open-FDD cookbook faults — auto-populated per mechanical category from the Haystack data model.
// Unified layout: every page picks ONE piece of equipment at a time via a dropdown (AHU-style),
// then renders that equipment's applicable rules as full-width, top-down cards. Each applicable
// rule shows its sliders and a Plotly chart (signals on unique axes + confirmed fault on a bool axis).
(function () {
  "use strict";

  var FAMILY_ORDER = ["sensor", "ahu", "trim", "vav", "plant", "heatpump", "weather"];
  var FAMILY_LABEL = {
    sensor: "Sensor validation (every modeled sensor)",
    ahu: "Air handler faults (ASHRAE GL36 · FC1–FC15 + economizer)",
    trim: "Trim & respond advisory",
    vav: "VAV / zone faults",
    plant: "Central plant faults",
    heatpump: "Heat pump faults",
    weather: "Weather station faults",
  };
  var KIND_LABEL = { ahu: "AHU", vav: "VAV box", chiller: "Chiller", boiler: "Boiler", weather: "Weather", heatpump: "Heat pump", zone: "Zone" };
  var PALETTE = ["#38bdf8", "#a78bfa", "#f59e0b", "#34d399", "#f472b6", "#60a5fa", "#fbbf24", "#4ade80"];

  var mount = null;
  var pageId = "";
  var targets = [];
  var current = null;              // { equipment_id, kind }
  var paramsByRule = {};           // { RULE_ID: { key: value } }
  var pending = null;
  var reqToken = 0;                // guards against out-of-order responses
  var bodyEl = null;

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function faultBadge(rule) {
    if (!rule.applicable) return el("span", "cb-badge cb-na", "Not in data model");
    var pct = rule.fault_pct || 0;
    var cls = pct <= 0 ? "cb-ok" : pct < 5 ? "cb-warn" : "cb-bad";
    return el("span", "cb-badge " + cls, (rule.fault_hours || 0).toFixed(1) + " h · " + pct.toFixed(1) + "%");
  }

  function slider(ruleId, p) {
    var wrap = el("div", "cb-param");
    var val = (paramsByRule[ruleId] && paramsByRule[ruleId][p.key] != null)
      ? paramsByRule[ruleId][p.key]
      : p.default;
    var lab = el("label", "cb-param-label", esc(p.label) + " <span class='cb-unit'>" + esc(p.unit) + "</span>");
    var row = el("div", "cb-param-row");
    var range = el("input");
    range.type = "range";
    range.min = p.min; range.max = p.max; range.step = p.step; range.value = val;
    var num = el("input", "cb-num");
    num.type = "number";
    num.min = p.min; num.max = p.max; num.step = p.step; num.value = val;
    function commit(v) {
      v = parseFloat(v);
      if (isNaN(v)) return;
      range.value = v; num.value = v;
      if (!paramsByRule[ruleId]) paramsByRule[ruleId] = {};
      paramsByRule[ruleId][p.key] = v;
      scheduleRerun();
    }
    range.addEventListener("input", function () { num.value = range.value; });
    range.addEventListener("change", function () { commit(range.value); });
    num.addEventListener("change", function () { commit(num.value); });
    row.appendChild(range);
    row.appendChild(num);
    wrap.appendChild(lab);
    wrap.appendChild(row);
    return wrap;
  }

  // ---- Plotly chart: stacked panels, unique axes, fault on its own bool axis ----
  function themeVars() {
    var cs = getComputedStyle(document.documentElement);
    function v(name, dflt) { var x = cs.getPropertyValue(name); return (x && x.trim()) || dflt; }
    return {
      bg: v("--card", v("--panel", "#141c2b")),
      text: v("--text", "#e8edf4"),
      grid: v("--border", "rgba(148,163,184,0.22)"),
    };
  }

  function buildChart(container, rule, timestamps) {
    if (!window.Plotly) { container.innerHTML = "<p class='cb-msg-na'>Plotly unavailable.</p>"; return; }
    var tv = themeVars();
    var signals = rule.signals || [];
    var panelMap = {};
    signals.forEach(function (s) { (panelMap[s.panel] = panelMap[s.panel] || []).push(s); });
    var panelKeys = Object.keys(panelMap).map(Number).sort(function (a, b) { return a - b; });
    var hasFault = rule.fault && rule.fault.length;
    var nSig = panelKeys.length;
    if (!nSig && !hasFault) { container.innerHTML = "<p class='cb-msg-na'>No signals to plot.</p>"; return; }

    var faultW = hasFault ? 0.5 : 0;
    var totalW = nSig + faultW;
    var gap = 0.045;
    var nRows = nSig + (hasFault ? 1 : 0);
    var usable = 1 - gap * Math.max(nRows - 1, 0);

    var layout = {
      height: 78 * nSig + (hasFault ? 78 : 0) + 54,
      margin: { l: 56, r: 12, t: 6, b: 26 },
      paper_bgcolor: tv.bg,
      plot_bgcolor: tv.bg,
      font: { color: tv.text, size: 10 },
      showlegend: true,
      legend: { orientation: "h", y: 1.0, yanchor: "bottom", x: 0, font: { size: 9 }, bgcolor: "rgba(0,0,0,0)" },
      hovermode: "x unified",
    };
    var traces = [];
    var top = 1.0, axis = 0, colorI = 0, lastAxis = "y";

    panelKeys.forEach(function (pk) {
      axis++;
      var h = usable * (1 / totalW);
      var bottom = top - h;
      var ax = axis === 1 ? "y" : "y" + axis;
      var axKey = axis === 1 ? "yaxis" : "yaxis" + axis;
      layout[axKey] = {
        domain: [Math.max(bottom, 0), Math.max(top, 0)],
        gridcolor: tv.grid, zerolinecolor: tv.grid, tickfont: { size: 9 },
      };
      panelMap[pk].forEach(function (s) {
        traces.push({
          x: timestamps, y: s.values, name: s.label, type: "scatter", mode: "lines",
          line: { width: 1.3, color: PALETTE[colorI++ % PALETTE.length] }, yaxis: ax, connectgaps: false,
        });
      });
      lastAxis = ax;
      top = bottom - gap;
    });

    if (hasFault) {
      axis++;
      var h2 = usable * (faultW / totalW);
      var bottom2 = top - h2;
      var ax2 = "y" + axis;
      layout["yaxis" + axis] = {
        domain: [Math.max(bottom2, 0), Math.max(top, 0)],
        range: [-0.1, 1.1], tickvals: [0, 1], ticktext: ["ok", "fault"],
        gridcolor: tv.grid, tickfont: { size: 9 },
      };
      traces.push({
        x: timestamps, y: rule.fault, name: "fault confirmed", type: "scatter", mode: "lines",
        line: { width: 0.4, color: "#ef4444" }, fill: "tozeroy", fillcolor: "rgba(239,68,68,0.4)", yaxis: ax2,
      });
      lastAxis = ax2;
    }
    layout.xaxis = { anchor: lastAxis, gridcolor: tv.grid, tickfont: { size: 9 }, type: "date" };
    Plotly.newPlot(container, traces, layout, { displayModeBar: false, responsive: true });
  }

  // ---- Rule card (full width, stacked) ----
  function ruleCard(rule, timestamps) {
    var card = el("div", "cb-card" + (rule.applicable ? "" : " cb-card-na"));
    card.setAttribute("data-rule", rule.id);
    var head = el("div", "cb-card-head");
    head.appendChild(el("span", "cb-id", esc(rule.id)));
    head.appendChild(el("span", "cb-title", esc(rule.title)));
    head.appendChild(faultBadge(rule));
    card.appendChild(head);
    card.appendChild(el("p", "cb-eq", esc(rule.equation)));
    if (rule.weather_gate) {
      card.appendChild(el("p", "cb-gate", "Availability gate: " + esc(rule.weather_gate)));
    }
    if (rule.applicable) {
      card.appendChild(el("p", "cb-msg", esc(rule.message)));
      if (rule.params && rule.params.length) {
        var pbox = el("div", "cb-params");
        rule.params.forEach(function (p) { pbox.appendChild(slider(rule.id, p)); });
        card.appendChild(pbox);
      }
      if (rule.signals && rule.signals.length) {
        var plot = el("div", "cb-plot");
        card.appendChild(plot);
        // defer so the card is in the DOM (Plotly needs a laid-out container)
        setTimeout(function () { buildChart(plot, rule, timestamps); }, 0);
      }
    } else {
      card.appendChild(el("p", "cb-msg cb-msg-na", esc(rule.message)));
    }
    return card;
  }

  function renderEquipment(data) {
    bodyEl.innerHTML = "";
    var meta = el("div", "cb-equip-head");
    var mtxt = data.n_applicable + " / " + data.n_rules + " rules apply · " +
      (data.total_fault_hours || 0).toFixed(1) + " fault-hours";
    if (data.weather_available) mtxt += " · Open-Meteo linked";
    meta.appendChild(el("span", "cb-equip-meta", esc(mtxt)));
    bodyEl.appendChild(meta);

    var byFamily = {};
    (data.rules || []).forEach(function (r) { (byFamily[r.family] = byFamily[r.family] || []).push(r); });
    FAMILY_ORDER.forEach(function (fam) {
      if (!byFamily[fam]) return;
      bodyEl.appendChild(el("h4", "cb-family", esc(FAMILY_LABEL[fam] || fam)));
      var col = el("div", "cb-stack");
      byFamily[fam].forEach(function (r) { col.appendChild(ruleCard(r, data.timestamps)); });
      bodyEl.appendChild(col);
    });
  }

  function selectEquipment(eq) {
    current = eq;
    var token = ++reqToken;
    bodyEl.innerHTML = spinnerHtml("Computing " + (KIND_LABEL[eq.kind] || eq.kind) + " faults for " + eq.equipment_id + "…");
    fetch("/api/cookbook/equipment/" + encodeURIComponent(eq.equipment_id), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ kind: eq.kind, params_by_rule: paramsByRule }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (token !== reqToken) return;   // a newer request superseded this one
        if (d && d.ok) renderEquipment(d);
        else bodyEl.innerHTML = "<p class='cb-msg-na'>Could not load faults" + (d && d.error ? ": " + esc(d.error) : ".") + "</p>";
      })
      .catch(function () { if (token === reqToken) bodyEl.innerHTML = "<p class='cb-msg-na'>Load failed.</p>"; });
  }

  function scheduleRerun() {
    if (pending) clearTimeout(pending);
    pending = setTimeout(function () { if (current) selectEquipment(current); }, 450);
  }

  function renderShell() {
    mount.innerHTML = "";
    var head = el("header", "cb-head");
    head.appendChild(el("h2", null, "Open-FDD cookbook faults"));
    head.appendChild(el("p", "note",
      "Every applicable Open-FDD pandas cookbook rule, run against this system's Haystack data model. " +
      "Pick equipment below; adjust thresholds to re-run against the loaded history."));
    mount.appendChild(head);

    if (targets.length > 1) {
      var bar = el("div", "cb-picker");
      bar.appendChild(el("label", "cb-picker-label", KIND_LABEL[targets[0].kind] || "Equipment"));
      var sel = el("select", "cb-select");
      targets.forEach(function (t, i) {
        var o = document.createElement("option");
        o.value = String(i);
        o.textContent = t.equipment_id;
        sel.appendChild(o);
      });
      sel.addEventListener("change", function () { selectEquipment(targets[parseInt(sel.value, 10) || 0]); });
      bar.appendChild(sel);
      bar.appendChild(el("span", "cb-picker-count", targets.length + " " + (KIND_LABEL[targets[0].kind] || "unit") + "s"));
      mount.appendChild(bar);
    }

    bodyEl = el("div", "cb-eqbody");
    mount.appendChild(bodyEl);
  }

  function spinnerHtml(msg) {
    return (
      "<div class='cb-loading-box' role='status' aria-live='polite'>" +
      "<span class='cb-spinner' aria-hidden='true'></span>" +
      "<div class='cb-loading-text'><strong>" + esc(msg) + "</strong>" +
      "<span class='cb-loading-sub'>Running Open-FDD rules against the historian — first pass only, then cached.</span>" +
      "</div></div>"
    );
  }

  function load() {
    mount.hidden = false;
    mount.innerHTML = spinnerHtml("Linking cookbook faults to the data model…");
    fetch("/api/cookbook/targets/" + encodeURIComponent(pageId))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || !d.ok || !d.targets || !d.targets.length) { mount.hidden = true; return; }
        targets = d.targets;
        renderShell();
        selectEquipment(targets[0]);
      })
      .catch(function () { mount.hidden = true; });
  }

  function init() {
    mount = document.getElementById("cookbook-mount");
    if (!mount) return;
    pageId = mount.getAttribute("data-page") || window.DASHBOARD_PAGE || "";
    if (!pageId) { mount.hidden = true; return; }
    load();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
