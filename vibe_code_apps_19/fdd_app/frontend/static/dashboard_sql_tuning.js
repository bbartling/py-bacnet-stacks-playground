// SQL / DataFusion rule tuning panel (registry metadata + preview from Rust cache).
(function () {
  "use strict";

  var mount = null;
  var rules = [];
  var selectedRule = null;
  var selectedEquipment = "";
  var sessionParams = {};
  var rustEnabled = false;

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

  function parityBadge(status) {
    var s = (status || "unknown").toLowerCase();
    var cls = "sql-parity-unknown";
    if (s.indexOf("proven") >= 0) cls = "sql-parity-proven";
    else if (s.indexOf("near") >= 0) cls = "sql-parity-near";
    else if (s.indexOf("skip") >= 0) cls = "sql-parity-skip";
    else if (s.indexOf("mismatch") >= 0) cls = "sql-parity-bad";
    return el("span", "sql-parity-badge " + cls, esc(status || "unknown"));
  }

  function paramSlider(ruleId, p, effective) {
    var wrap = el("div", "sql-param");
    var val = (sessionParams[ruleId] && sessionParams[ruleId][p.key] != null)
      ? sessionParams[ruleId][p.key]
      : (effective && effective[p.key] != null ? effective[p.key] : p.default);
    var lab = el("label", "sql-param-label",
      esc(p.label) + " <span class='sql-unit'>" + esc(p.unit) + "</span>" +
      " <span class='sql-default-hint'>(default " + esc(p.default) + ")</span>");
    var row = el("div", "sql-param-row");
    var range = el("input");
    range.type = "range";
    range.min = p.min; range.max = p.max; range.step = p.step; range.value = val;
    var num = el("input", "sql-num");
    num.type = "number";
    num.min = p.min; num.max = p.max; num.step = p.step; num.value = val;
    function commit(v) {
      v = parseFloat(v);
      if (isNaN(v)) return;
      range.value = v; num.value = v;
      if (!sessionParams[ruleId]) sessionParams[ruleId] = {};
      sessionParams[ruleId][p.key] = v;
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

  function renderDetail() {
    if (!mount) return;
    mount.innerHTML = "";
    if (!rustEnabled) {
      mount.appendChild(el("p", "sql-warn", "SQL preview disabled — set VIBE19_RUST_CACHE=1 and restart the dashboard."));
      return;
    }
    if (!selectedRule) {
      mount.appendChild(el("p", "sql-muted", "Select a SQL rule to tune parameters."));
      return;
    }
    var r = selectedRule;
    var head = el("div", "sql-detail-head");
    head.appendChild(el("h3", "sql-rule-title", esc(r.rule_id)));
    head.appendChild(parityBadge(r.parity_status));
    if ((r.parity_status || "").indexOf("proven") < 0) {
      head.appendChild(el("span", "sql-warn-badge", "Not parity-proven yet"));
    }
    mount.appendChild(head);
    mount.appendChild(el("p", "sql-desc", esc(r.description)));
    mount.appendChild(el("p", "sql-meta", "Engine: SQL DataFusion · Roles: " + esc((r.required_roles || []).join(", "))));

    var eqRow = el("div", "sql-eq-row");
    eqRow.appendChild(el("label", "", "Equipment ID"));
    var eqInput = el("input", "sql-eq-input");
    eqInput.type = "text";
    eqInput.placeholder = "e.g. VAV_7 or AHU_1";
    eqInput.value = selectedEquipment;
    eqInput.addEventListener("change", function () { selectedEquipment = eqInput.value.trim(); });
    eqRow.appendChild(eqInput);
    mount.appendChild(eqRow);

    var paramsWrap = el("div", "sql-params");
    (r.parameters || []).forEach(function (p) {
      paramsWrap.appendChild(paramSlider(r.rule_id, p, r.effective_values));
    });
    if (!(r.parameters || []).length) {
      paramsWrap.appendChild(el("p", "sql-muted", "No tunable parameters declared in registry yet."));
    }
    mount.appendChild(paramsWrap);

    var actions = el("div", "sql-actions");
    var btnPreview = el("button", "btn btn-secondary", "Preview (Rust cache)");
    var btnSave = el("button", "btn btn-secondary", "Save profile");
    var btnReset = el("button", "btn btn-link", "Reset to defaults");
    var out = el("pre", "sql-preview-out", "");
    btnPreview.addEventListener("click", function () {
      out.textContent = "Loading…";
      fetch("/api/sql-rules/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rule_id: r.rule_id,
          equipment_id: selectedEquipment || "AHU_1",
          params: sessionParams[r.rule_id] || {},
          use_rust_cache: true,
        }),
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          out.textContent = JSON.stringify(data, null, 2);
        })
        .catch(function (err) {
          out.textContent = String(err);
        });
    });
    btnSave.addEventListener("click", function () {
      fetch("/api/sql-rules/save-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          rule_id: r.rule_id,
          scope: "equipment",
          equipment_id: selectedEquipment || undefined,
          params: sessionParams[r.rule_id] || {},
        }),
      })
        .then(function (res) { return res.json(); })
        .then(function (data) {
          out.textContent = JSON.stringify(data, null, 2);
        })
        .catch(function (err) {
          out.textContent = String(err);
        });
    });
    btnReset.addEventListener("click", function () {
      delete sessionParams[r.rule_id];
      renderDetail();
    });
    actions.appendChild(btnPreview);
    actions.appendChild(btnSave);
    actions.appendChild(btnReset);
    mount.appendChild(actions);
    mount.appendChild(out);
  }

  function renderList() {
    var listMount = document.getElementById("sql-rules-list");
    if (!listMount) return;
    listMount.innerHTML = "";
    rules.forEach(function (r) {
      var item = el("button", "sql-rule-item" + (selectedRule && selectedRule.rule_id === r.rule_id ? " active" : ""), esc(r.rule_id));
      item.type = "button";
      item.addEventListener("click", function () {
        selectedRule = r;
        renderList();
        renderDetail();
      });
      listMount.appendChild(item);
    });
  }

  function init() {
    mount = document.getElementById("sql-tuning-panel");
    var section = document.getElementById("sql-tuning-section");
    if (!mount) return;
    fetch("/api/sql-rules")
      .then(function (res) { return res.json(); })
      .then(function (data) {
        if (!data.ok) {
          mount.textContent = data.error || "Failed to load SQL rules";
          return;
        }
        if (section) section.hidden = false;
        rustEnabled = !!data.rust_cache_enabled;
        rules = data.rules || [];
        if (rules.length && !selectedRule) selectedRule = rules[0];
        renderList();
        renderDetail();
      })
      .catch(function (err) {
        mount.textContent = String(err);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
