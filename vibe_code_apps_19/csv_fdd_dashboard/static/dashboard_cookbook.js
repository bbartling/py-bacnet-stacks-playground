// Open-FDD cookbook faults — auto-populated per mechanical category from the Haystack data model.
// Fetches /api/cookbook/{page_id}, renders every rule as a card with sliders. Rules whose
// required points are absent from the model render as a muted "Not in data model" card.
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

  var mount = null;
  var pageId = "";
  var paramsByRule = {}; // { RULE_ID: { key: value } } — user overrides across the page
  var pending = null;

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

  function ruleCard(rule) {
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
    } else {
      card.appendChild(el("p", "cb-msg cb-msg-na", esc(rule.message)));
    }
    return card;
  }

  function equipmentBlock(eq) {
    var block = el("section", "cb-equip");
    var head = el("div", "cb-equip-head");
    head.appendChild(el("h3", null, esc(eq.equipment_id) + " <span class='cb-kind'>" + esc(eq.kind) + "</span>"));
    var meta = eq.n_applicable + " / " + eq.n_rules + " rules apply · " +
      (eq.total_fault_hours || 0).toFixed(1) + " fault-hours";
    if (eq.weather_available) meta += " · Open-Meteo linked";
    head.appendChild(el("span", "cb-equip-meta", esc(meta)));
    block.appendChild(head);
    if (eq.error) {
      block.appendChild(el("p", "cb-msg-na", esc(eq.error)));
      return block;
    }
    var byFamily = {};
    (eq.rules || []).forEach(function (r) {
      (byFamily[r.family] = byFamily[r.family] || []).push(r);
    });
    FAMILY_ORDER.forEach(function (fam) {
      if (!byFamily[fam]) return;
      block.appendChild(el("h4", "cb-family", esc(FAMILY_LABEL[fam] || fam)));
      var grid = el("div", "cb-grid");
      byFamily[fam].forEach(function (r) { grid.appendChild(ruleCard(r)); });
      block.appendChild(grid);
    });
    return block;
  }

  function render(data) {
    mount.innerHTML = "";
    if (!data || !data.equipment || !data.equipment.length) {
      mount.hidden = true;
      return;
    }
    mount.hidden = false;
    var head = el("header", "cb-head");
    head.appendChild(el("h2", null, "Open-FDD cookbook faults"));
    head.appendChild(el("p", "note",
      "Every applicable Open-FDD pandas cookbook rule, run against this system's Haystack data model. " +
      "Adjust thresholds to re-run against the loaded history."));
    mount.appendChild(head);
    data.equipment.forEach(function (eq) { mount.appendChild(equipmentBlock(eq)); });
  }

  function scheduleRerun() {
    if (pending) clearTimeout(pending);
    pending = setTimeout(rerun, 450);
  }

  function rerun() {
    mount.classList.add("cb-loading");
    fetch("/api/cookbook/" + encodeURIComponent(pageId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ params_by_rule: paramsByRule }),
    })
      .then(function (r) { return r.json(); })
      .then(function (d) { mount.classList.remove("cb-loading"); if (d && d.ok) render(d); })
      .catch(function () { mount.classList.remove("cb-loading"); });
  }

  function load() {
    mount.hidden = false;
    mount.innerHTML = "<p class='note cb-loading-note'>Linking cookbook faults to the data model…</p>";
    fetch("/api/cookbook/" + encodeURIComponent(pageId))
      .then(function (r) { return r.json(); })
      .then(function (d) { if (d && d.ok) render(d); else mount.hidden = true; })
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
