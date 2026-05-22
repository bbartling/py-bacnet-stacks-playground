(function () {
  "use strict";

  let rules = [];
  let fieldMeta = {};
  let selectedIndex = 0;
  let activeEditor = null;
  let activeRuleId = null;
  let lintTimer = null;
  let syntaxPillEl = null;
  let activeCard = null;
  let lastTestReport = "";

  const MAX_CONSOLE_LINES = 400;
  const MAX_REPORT_PRINT_LINES = 800;

  const els = {
    ruleSelect: document.getElementById("ruleSelect"),
    ruleEditorSlot: document.getElementById("ruleEditorSlot"),
    consoleOut: document.getElementById("consoleOut"),
    consoleWrap: document.querySelector(".console-wrap"),
    tsTableWrap: document.querySelector(".ts-table-wrap"),
    elapsedMs: document.getElementById("elapsedMs"),
    tsTableBody: document.getElementById("tsTableBody"),
    tsSummary: document.getElementById("tsSummary"),
    testHours: document.getElementById("testHours"),
    testHoursLabel: document.getElementById("testHoursLabel"),
    addRuleBtn: document.getElementById("addRuleBtn"),
    removeRuleBtn: document.getElementById("removeRuleBtn"),
    testRuleBtn: document.getElementById("testRuleBtn"),
    saveRulesBtn: document.getElementById("saveRulesBtn"),
    goLiveBtn: document.getElementById("goLiveBtn"),
    copyReportBtn: document.getElementById("copyReportBtn"),
    testReport: document.getElementById("testReport"),
    verbosePrints: document.getElementById("verbosePrints"),
  };

  function newRuleId() {
    return "custom_rule_" + Date.now().toString(36);
  }

  function ruleTempUnit(rule) {
    const u = (rule && rule.config && rule.config.temp_unit) || "imperial";
    return String(u).toLowerCase() === "metric" ? "metric" : "imperial";
  }

  function unitSym(unit) {
    return ruleTempUnit({ config: { temp_unit: unit } }) === "metric" ? "°C" : "°F";
  }

  function chartGuidesSnapshot() {
    for (const r of rules) {
      const cfg = r.config || {};
      const u = ruleTempUnit(r);
      if (cfg.bounds_low != null && cfg.bounds_high != null) {
        return {
          bounds_low: Number(cfg.bounds_low),
          bounds_high: Number(cfg.bounds_high),
          temp_unit: u,
        };
      }
      if (cfg.bounds_low_f != null && cfg.bounds_high_f != null) {
        return {
          bounds_low: Number(cfg.bounds_low_f),
          bounds_high: Number(cfg.bounds_high_f),
          temp_unit: "imperial",
          bounds_low_f: Number(cfg.bounds_low_f),
          bounds_high_f: Number(cfg.bounds_high_f),
        };
      }
    }
    return { bounds_low: 65, bounds_high: 80, temp_unit: "imperial" };
  }

  function rulesMetaSnapshot() {
    return rules.map((r) => ({
      id: r.id,
      title: r.title || r.id,
      color: r.color || "#8b949e",
      enabled: r.enabled !== false,
      plot_on_chart: r.enabled !== false && r.plot_on_chart !== false,
    }));
  }

  function notifyDashboardRules() {
    if (window.vibe12DashboardSyncRules) {
      window.vibe12DashboardSyncRules(rulesMetaSnapshot(), chartGuidesSnapshot());
    }
  }

  function blankRule() {
    return {
      id: newRuleId(),
      title: "New rule",
      enabled: true,
      plot_on_chart: true,
      color: "#58a6ff",
      config_fields: [],
      config: {},
      code: 'def evaluate(row, cfg, prev_row=None, rows=None):\n    """Return True to flag this row."""\n    return False\n',
    };
  }

  function currentRule() {
    return rules[selectedIndex];
  }

  function persistActiveEditor() {
    if (!activeEditor || !activeRuleId) return;
    const rule = rules.find((r) => r.id === activeRuleId);
    if (rule) rule.code = activeEditor.getValue();
    syncConfigFromDom(rule, activeCard);
  }

  function destroyEditor() {
    if (activeEditor) {
      try {
        activeEditor.toTextArea();
      } catch (_) {
        /* ignore */
      }
      activeEditor = null;
      activeRuleId = null;
    }
    activeCard = null;
  }

  function refreshEditor() {
    if (!activeEditor) return;
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        activeEditor.refresh();
        const h = Math.max(180, activeCard?.querySelector(".rule-editor")?.offsetHeight || 180);
        activeEditor.setSize(null, h);
      });
    });
  }

  function appendConsole(text, cls) {
    const cur = els.consoleOut.querySelector(".cursor-blink");
    if (cur) cur.remove();
    const span = document.createElement("span");
    span.className = "console-line" + (cls ? " " + cls : "");
    span.textContent = text;
    els.consoleOut.appendChild(span);
    const lines = els.consoleOut.querySelectorAll(".console-line");
    if (lines.length > MAX_CONSOLE_LINES) {
      lines[0].remove();
    }
    const blink = document.createElement("span");
    blink.className = "cursor-blink";
    blink.textContent = "▌";
    els.consoleOut.appendChild(blink);
    els.consoleOut.scrollTop = els.consoleOut.scrollHeight;
  }

  function clearConsole() {
    els.consoleOut.innerHTML =
      '<span class="console-prompt">>>> </span><span class="cursor-blink">▌</span>';
    els.elapsedMs.textContent = "";
    if (els.consoleOut) els.consoleOut.scrollTop = 0;
  }

  function resetTsTable() {
    els.tsTableBody.querySelectorAll("tr").forEach((tr) => {
      tr.className = "";
    });
    if (els.tsTableWrap) els.tsTableWrap.scrollTop = 0;
  }

  function highlightRow(row, status) {
    const tr = els.tsTableBody.querySelector('tr[data-row="' + row + '"]');
    if (!tr || !els.tsTableWrap) return;
    tr.className = status;
    const wrap = els.tsTableWrap;
    const trTop = tr.offsetTop;
    const viewTop = wrap.scrollTop;
    const viewBottom = viewTop + wrap.clientHeight;
    if (trTop < viewTop + 20 || trTop > viewBottom - 28) {
      wrap.scrollTop = Math.max(0, trTop - wrap.clientHeight / 3);
    }
  }

  async function lintCode(code, pillEl) {
    try {
      const res = await fetch("/api/playground/lint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      });
      const data = await res.json();
      const err = (data.issues || []).find((i) => i.severity === "error");
      if (pillEl) {
        pillEl.textContent = err ? "syntax err" : "syntax ok";
        pillEl.className = "syntax-pill " + (err ? "err" : "ok");
        pillEl.title = err ? err.message : "ok";
      }
      return data.ok;
    } catch (_) {
      return false;
    }
  }

  function getRollingAvgMinutes() {
    const lab = document.getElementById("labRollingAvgMinutes");
    if (lab) return parseInt(lab.value, 10) || 1;
    if (window.vibe12GetRollingAvgMinutes) return window.vibe12GetRollingAvgMinutes();
    return 1;
  }

  function sanitizeCfgKey(raw) {
    return String(raw || "")
      .trim()
      .replace(/\s+/g, "_")
      .replace(/[^a-zA-Z0-9_]/g, "")
      .replace(/^(\d)/, "_$1");
  }

  function sanitizeRuleId(raw) {
    const s = String(raw || "")
      .trim()
      .replace(/\s+/g, "_")
      .replace(/[^a-zA-Z0-9_-]/g, "");
    return s || newRuleId();
  }

  function defaultCfgValue(key) {
    const meta = fieldMeta[key];
    if (!meta) return "";
    if (meta.default !== undefined) return meta.default;
    if (meta.type === "choice") return (meta.choices || [1])[0];
    if (meta.type === "int") return 0;
    if (meta.type === "float") return 0;
    return "";
  }

  function orderedConfigKeys(rule) {
    const cfg = rule.config || {};
    const listed = (rule.config_fields || []).filter((k) => k && k in cfg);
    const extra = Object.keys(cfg).filter((k) => listed.indexOf(k) < 0);
    return listed.concat(extra);
  }

  function normalizeRuleConfig(rule) {
    if (!rule.config || typeof rule.config !== "object") rule.config = {};
    const keys = Object.keys(rule.config);
    if (!rule.config_fields || !rule.config_fields.length) {
      rule.config_fields = keys.slice();
    }
    rule.config_fields.forEach((k) => {
      if (k && !(k in rule.config)) rule.config[k] = defaultCfgValue(k);
    });
  }

  function formatCfgValue(v) {
    if (v === null || v === undefined) return "";
    if (typeof v === "boolean") return v ? "true" : "false";
    return String(v);
  }

  function parseCfgValue(raw, key) {
    const meta = fieldMeta[key];
    const s = String(raw ?? "").trim();
    if (meta?.type === "choice") {
      const n = parseInt(s, 10);
      return Number.isFinite(n) ? n : meta.default ?? (meta.choices || [1])[0];
    }
    if (meta?.type === "int") {
      const n = parseInt(s, 10);
      return Number.isFinite(n) ? n : 0;
    }
    if (meta?.type === "float") {
      const n = parseFloat(s);
      return Number.isFinite(n) ? n : 0;
    }
    if (s === "true") return true;
    if (s === "false") return false;
    if (s !== "" && !Number.isNaN(Number(s)) && /^-?\d+(\.\d+)?$/.test(s)) {
      return s.indexOf(".") >= 0 ? parseFloat(s) : parseInt(s, 10);
    }
    return s;
  }

  function syncConfigFromDom(rule, card) {
    if (!rule || !card) return;
    const list = card.querySelector(".cfg-param-list");
    if (!list) return;
    const newConfig = {};
    const fields = [];
    const seen = new Set();
    list.querySelectorAll(".cfg-param-row").forEach((row) => {
      const keyInp = row.querySelector(".cfg-key");
      const key = sanitizeCfgKey(keyInp && keyInp.value);
      if (!key || seen.has(key)) {
        row.classList.toggle("cfg-dup", !key || seen.has(key));
        return;
      }
      seen.add(key);
      row.classList.remove("cfg-dup");
      const valEl = row.querySelector(".cfg-val");
      fields.push(key);
      newConfig[key] = parseCfgValue(valEl ? valEl.value : "", key);
      if (valEl && valEl.tagName === "SELECT") {
        newConfig[key] = parseInt(valEl.value, 10);
      }
    });
    rule.config_fields = fields;
    rule.config = newConfig;
  }

  function cfgRowDuplicateCheck(list) {
    const counts = {};
    list.querySelectorAll(".cfg-param-row").forEach((row) => {
      const k = sanitizeCfgKey(row.querySelector(".cfg-key")?.value);
      if (!k) return;
      counts[k] = (counts[k] || 0) + 1;
    });
    list.querySelectorAll(".cfg-param-row").forEach((row) => {
      const k = sanitizeCfgKey(row.querySelector(".cfg-key")?.value);
      row.classList.toggle("cfg-dup", k && counts[k] > 1);
    });
  }

  function createCfgValueControl(key, value, onChange) {
    const meta = fieldMeta[key];
    let el;
    if (meta?.type === "choice") {
      el = document.createElement("select");
      el.className = "cfg-val";
      (meta.choices || [1, 5, 10]).forEach((c) => {
        const opt = document.createElement("option");
        opt.value = String(c);
        opt.textContent =
          key === "rolling_avg_minutes" ? c + " min" : String(c);
        el.appendChild(opt);
      });
      el.value = String(value ?? meta.default ?? (meta.choices || [1])[0]);
    } else {
      el = document.createElement("input");
      el.className = "cfg-val";
      el.type = "text";
      el.placeholder = meta?.label || "value";
      el.value = formatCfgValue(value);
      if (meta?.type === "int" || meta?.type === "float") {
        el.inputMode = "decimal";
        el.title = meta.label || key;
      }
    }
    el.addEventListener("change", onChange);
    el.addEventListener("input", onChange);
    return el;
  }

  function addCfgParamRow(list, rule, key, value, onChanged) {
    const row = document.createElement("div");
    row.className = "cfg-param-row";

    const keyInp = document.createElement("input");
    keyInp.type = "text";
    keyInp.className = "cfg-key";
    keyInp.value = key || "";
    keyInp.placeholder = "param_name";
    keyInp.title = "Config key — used as cfg['name'] in your rule";
    const meta = key ? fieldMeta[key] : null;
    if (meta?.label) keyInp.title = meta.label + " (" + key + ")";

    const valWrap = document.createElement("div");
    valWrap.className = "cfg-val-wrap";

    function refreshValueControl() {
      const k = sanitizeCfgKey(keyInp.value);
      const cur = rule.config[k];
      valWrap.innerHTML = "";
      valWrap.appendChild(
        createCfgValueControl(k, cur !== undefined ? cur : value, () => {
          syncConfigFromDom(rule, activeCard);
          onChanged();
        })
      );
    }
    refreshValueControl();

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "btn btn-icon cfg-remove";
    removeBtn.textContent = "−";
    removeBtn.title = "Remove parameter";
    removeBtn.addEventListener("click", () => {
      row.remove();
      syncConfigFromDom(rule, activeCard);
      cfgRowDuplicateCheck(list);
      onChanged();
      if (!list.querySelector(".cfg-param-row")) {
        addCfgParamRow(list, rule, "", "", onChanged);
      }
    });

    keyInp.addEventListener("input", () => cfgRowDuplicateCheck(list));
    keyInp.addEventListener("blur", () => {
      keyInp.value = sanitizeCfgKey(keyInp.value);
      refreshValueControl();
      syncConfigFromDom(rule, activeCard);
      onChanged();
    });

    row.append(keyInp, valWrap, removeBtn);
    list.appendChild(row);
    cfgRowDuplicateCheck(list);
    return row;
  }

  function buildConfigPanel(rule, container) {
    container.innerHTML = "";
    container.className = "rule-config-panel";
    normalizeRuleConfig(rule);

    const panelHead = document.createElement("div");
    panelHead.className = "cfg-panel-head";
    const title = document.createElement("span");
    title.className = "cfg-panel-title";
    title.textContent = "Parameters (cfg)";
    const hint = document.createElement("span");
    hint.className = "cfg-panel-hint";
    hint.textContent = "Keys passed to evaluate(row, cfg, …)";
    panelHead.append(title, hint);

    const toolbar = document.createElement("div");
    toolbar.className = "cfg-toolbar";

    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.className = "btn btn-secondary btn-sm";
    addBtn.textContent = "+ Parameter";
    addBtn.title = "Add a custom config key";

    const presetSel = document.createElement("select");
    presetSel.className = "cfg-preset-select";
    presetSel.title = "Insert a known parameter with defaults";
    const presetOpt0 = document.createElement("option");
    presetOpt0.value = "";
    presetOpt0.textContent = "Add preset…";
    presetSel.appendChild(presetOpt0);
    Object.keys(fieldMeta).forEach((k) => {
      const opt = document.createElement("option");
      opt.value = k;
      const m = fieldMeta[k];
      opt.textContent = (m.label || k) + " (" + k + ")";
      presetSel.appendChild(opt);
    });

    const list = document.createElement("div");
    list.className = "cfg-param-list";

    function onCfgChanged() {
      notifyDashboardRules();
    }

    const keys = orderedConfigKeys(rule);
    if (keys.length) {
      keys.forEach((k) => addCfgParamRow(list, rule, k, rule.config[k], onCfgChanged));
    } else {
      addCfgParamRow(list, rule, "", "", onCfgChanged);
    }

    addBtn.addEventListener("click", () => {
      const row = addCfgParamRow(list, rule, "", "", onCfgChanged);
      row.querySelector(".cfg-key")?.focus();
    });

    presetSel.addEventListener("change", () => {
      const k = presetSel.value;
      presetSel.value = "";
      if (!k) return;
      const hasPreset = Array.from(list.querySelectorAll(".cfg-key")).some(
        (inp) => sanitizeCfgKey(inp.value) === k
      );
      if (hasPreset) {
        appendConsole("[cfg] preset " + k + " already present\n", "log-warn");
        return;
      }
      const emptyKey = list.querySelector(".cfg-param-row .cfg-key");
      if (emptyKey && !sanitizeCfgKey(emptyKey.value) && list.children.length === 1) {
        emptyKey.value = k;
        emptyKey.dispatchEvent(new Event("blur"));
        return;
      }
      addCfgParamRow(list, rule, k, defaultCfgValue(k), onCfgChanged);
      syncConfigFromDom(rule, activeCard);
      onCfgChanged();
    });

    toolbar.append(addBtn, presetSel);
    container.append(panelHead, toolbar, list);
  }

  function populateRuleSelect() {
    els.ruleSelect.innerHTML = "";
    rules.forEach((rule, i) => {
      const opt = document.createElement("option");
      opt.value = String(i);
      const on = rule.enabled !== false ? "" : " (off)";
      opt.textContent = (rule.title || rule.id) + on;
      if (i === selectedIndex) opt.selected = true;
      els.ruleSelect.appendChild(opt);
    });
    els.removeRuleBtn.disabled = rules.length <= 1;
  }

  function renderSelectedRule() {
    persistActiveEditor();
    destroyEditor();
    els.ruleEditorSlot.innerHTML = "";
    const rule = currentRule();
    if (!rule) return;

    const card = document.createElement("div");
    card.className = "rule-card";
    activeCard = card;

    const head = document.createElement("div");
    head.className = "rule-card-head";
    const colorInp = document.createElement("input");
    colorInp.type = "color";
    colorInp.className = "rule-color-inp";
    colorInp.value = rule.color || "#58a6ff";
    colorInp.title = "Fault lane color on chart";
    colorInp.addEventListener("input", () => {
      rule.color = colorInp.value;
      notifyDashboardRules();
    });
    const idLab = document.createElement("label");
    idLab.className = "rule-id-lab";
    idLab.title = "Stable rule id (fault lane key)";
    const idInp = document.createElement("input");
    idInp.type = "text";
    idInp.className = "rule-id-inp";
    idInp.value = rule.id;
    idInp.spellcheck = false;
    idInp.addEventListener("change", () => {
      const next = sanitizeRuleId(idInp.value);
      if (rules.some((r) => r !== rule && r.id === next)) {
        idInp.value = rule.id;
        appendConsole("[cfg] rule id already in use: " + next + "\n", "error");
        return;
      }
      rule.id = next;
      activeRuleId = next;
      populateRuleSelect();
      notifyDashboardRules();
    });
    idLab.append(document.createTextNode("id "), idInp);

    const titleInp = document.createElement("input");
    titleInp.type = "text";
    titleInp.className = "rule-title-inp";
    titleInp.value = rule.title || rule.id;
    titleInp.placeholder = "Display title";
    titleInp.addEventListener("input", () => {
      rule.title = titleInp.value;
      const opt = els.ruleSelect.options[selectedIndex];
      if (opt) opt.textContent = rule.title + (rule.enabled === false ? " (off)" : "");
    });
    const enLab = document.createElement("label");
    enLab.className = "enabled-chk";
    const enChk = document.createElement("input");
    enChk.type = "checkbox";
    enChk.checked = rule.enabled !== false;
    const plotLab = document.createElement("label");
    plotLab.className = "enabled-chk plot-on-chart-chk";
    const plotChk = document.createElement("input");
    plotChk.type = "checkbox";
    plotChk.checked = rule.plot_on_chart !== false;
    plotChk.disabled = rule.enabled === false;

    function syncPlotChk() {
      plotChk.disabled = rule.enabled === false;
      if (rule.enabled === false) {
        rule.plot_on_chart = false;
        plotChk.checked = false;
      } else if (rule.plot_on_chart === undefined) {
        rule.plot_on_chart = true;
        plotChk.checked = true;
      } else {
        plotChk.checked = rule.plot_on_chart !== false;
      }
    }
    syncPlotChk();

    enChk.addEventListener("change", () => {
      rule.enabled = enChk.checked;
      if (!enChk.checked) rule.plot_on_chart = false;
      else if (rule.plot_on_chart === undefined) rule.plot_on_chart = true;
      syncPlotChk();
      populateRuleSelect();
      notifyDashboardRules();
    });
    plotChk.addEventListener("change", () => {
      rule.plot_on_chart = plotChk.checked;
      notifyDashboardRules();
    });
    enLab.append(enChk, document.createTextNode(" Enabled"));
    plotLab.append(plotChk, document.createTextNode(" Plot on chart"));
    syntaxPillEl = document.createElement("span");
    syntaxPillEl.className = "syntax-pill ok";
    syntaxPillEl.textContent = "…";
    head.append(colorInp, idLab, titleInp, enLab, plotLab, syntaxPillEl);

    const cfgRow = document.createElement("div");
    buildConfigPanel(rule, cfgRow);

    const editorWrap = document.createElement("div");
    editorWrap.className = "rule-editor";
    const ta = document.createElement("textarea");
    ta.value = rule.code || "";
    editorWrap.appendChild(ta);

    card.append(head, cfgRow, editorWrap);
    els.ruleEditorSlot.appendChild(card);

    activeEditor = CodeMirror.fromTextArea(ta, {
      mode: "python",
      theme: "material-darker",
      lineNumbers: true,
      indentUnit: 4,
      lineWrapping: true,
    });
    activeRuleId = rule.id;
    activeEditor.setSize(null, 200);
    activeEditor.on("change", () => {
      rule.code = activeEditor.getValue();
      clearTimeout(lintTimer);
      lintTimer = setTimeout(() => lintCode(rule.code, syntaxPillEl), 400);
    });
    lintCode(rule.code, syntaxPillEl);
    refreshEditor();
  }

  function buildTestReport(rule, hours, data) {
    const events = data.events || [];
    const lines = [];
    lines.push("# Vibe12 FDD rule test report");
    lines.push("");
    lines.push("## Rule: " + (rule.title || rule.id));
    lines.push("## Test window: " + hours + " h");
    if (data.rolling_avg_minutes != null) {
      lines.push("## Rolling avg: " + data.rolling_avg_minutes + " min (by ts_ms)");
    }
    lines.push(
      "## Result: " +
        data.rows +
        " rows swept, " +
        data.flagged +
        " flagged (per-row or retroactive window), " +
        data.ms +
        " ms"
    );
    lines.push("");
    lines.push("## Config (JSON)");
    lines.push(JSON.stringify(rule.config, null, 2));
    lines.push("");
    lines.push("## Python");
    lines.push("```python");
    lines.push(rule.code || "");
    lines.push("```");
    lines.push("");
    lines.push("## Console / print output");
    let printCount = 0;
    let printTruncated = false;
    for (const evt of events) {
      if (evt.type === "stdout" || evt.type === "error") {
        if (printCount < MAX_REPORT_PRINT_LINES) {
          lines.push((evt.text || "").replace(/\n$/, ""));
          printCount += 1;
        } else if (!printTruncated) {
          printTruncated = true;
        }
      }
    }
    if (printTruncated) {
      lines.push("... (print output truncated in report at " + MAX_REPORT_PRINT_LINES + " lines)");
    }
    if (printCount === 0) {
      lines.push(
        "(no print output — rule returned False for all rows, or nothing called print())"
      );
      lines.push(
        "Tip: data may be in bounds (e.g. 65–68 F inside 65–80). Lower bounds_low_f or add:"
      );
      lines.push('  print(f"{row[\'row\']} {row[\'ts\']} {row[\'degF\']:.2f} F")');
    }
    lines.push("");
    lines.push("## Fault rows (sample up to 40)");
    const faults = events.filter((e) => e.type === "row" && e.status === "fault");
    faults.slice(0, 40).forEach((e) => {
      lines.push(
        "row " + e.row + "  " + e.ts + "  " + (e.degF != null ? e.degF.toFixed(2) + " F" : "")
      );
    });
    if (faults.length > 40) {
      lines.push("... and " + (faults.length - 40) + " more fault rows");
    }
    if (faults.length === 0) {
      lines.push("(none)");
    }
    return lines.join("\n");
  }

  async function copyReportToClipboard() {
    const text = lastTestReport || els.testReport.value;
    if (!text) {
      appendConsole("Run Test rule first to build a report.\n", "log-warn");
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      appendConsole("Report copied to clipboard.\n");
    } catch (_) {
      els.testReport.focus();
      els.testReport.select();
      appendConsole("Select report text and Ctrl+C (clipboard blocked).\n", "log-warn");
    }
  }

  function printCountFromEvents(events) {
    return (events || []).filter((e) => e.type === "stdout").length;
  }

  function setLabActionButtonsEnabled(enabled) {
    if (els.testRuleBtn) els.testRuleBtn.disabled = !enabled;
    if (els.goLiveBtn) els.goLiveBtn.disabled = !enabled;
  }

  function playEvents(events, delayMs, showAllPrints) {
    return new Promise((resolve) => {
      const total = events.length;
      const heavy = total > 1200;
      const maxSteps = heavy ? 400 : total;
      const skipRowAnim = total > 600;
      let i = 0;
      let faultLines = 0;
      let stdoutLines = 0;
      const stdoutCap = showAllPrints ? 120 : 60;
      const tickMs = delayMs > 0 ? delayMs : heavy ? 0 : 1;

      function finish(skipped) {
        if (skipped > 0) {
          appendConsole(
            "[console] Skipped " +
              skipped +
              " playback steps — full output in Copy report below.\n",
            "log-warn"
          );
        }
        resolve();
      }

      function step() {
        if (i >= total || i >= maxSteps) {
          finish(Math.max(0, total - i));
          return;
        }
        const evt = events[i++];
        if (evt.type === "stdout") {
          if (stdoutLines < stdoutCap) {
            appendConsole(evt.text);
            stdoutLines += 1;
          }
        } else if (evt.type === "error") {
          appendConsole(evt.text, "error");
        } else if (evt.type === "row") {
          if (!skipRowAnim) highlightRow(evt.row, evt.status);
          if (evt.status === "fault" && faultLines < 80) {
            faultLines += 1;
            appendConsole(
              evt.ts + "  FAULT  " + evt.degF.toFixed(2) + " F\n",
              "fault"
            );
          }
        } else if (evt.type === "summary") {
          els.tsSummary.textContent =
            evt.flagged + " flagged / " + evt.rows + " rows";
          appendConsole(
            "--- " + evt.flagged + " flagged (" + evt.rows + " rows) ---\n"
          );
        }
        setTimeout(step, tickMs);
      }

      if (heavy) {
        appendConsole(
          "[console] Large run (" +
            total +
            " events) — fast playback; use Copy report for full prints.\n",
          "log-warn"
        );
      }
      setTimeout(step, 0);
    });
  }

  async function loadTsPreview(hours) {
    const rollMin = getRollingAvgMinutes();
    const res = await fetch(
      "/api/readings?hours=" + hours + "&rolling_avg_minutes=" + rollMin
    );
    const data = await res.json();
    const rows = (data.eval_rows_preview || []).length
      ? data.eval_rows_preview
      : (data.readings || []).map((r, i) => ({
          row: i,
          ts: (r.ts_iso || "").replace("T", " ").slice(0, 19),
          degF: r.degF,
          degF_rolling_avg: r.degF,
        }));
    els.tsTableBody.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.dataset.row = r.row;
      const avg = r.degF_rolling_avg != null ? r.degF_rolling_avg : r.degF;
      tr.innerHTML =
        "<td>" +
        r.row +
        "</td><td>" +
        r.ts +
        '</td><td class="num">' +
        Number(r.degF).toFixed(2) +
        '</td><td class="num avg">' +
        Number(avg).toFixed(2) +
        "</td><td></td>";
      els.tsTableBody.appendChild(tr);
    });
    const period =
      rows.length && rows[0].rolling_avg_minutes != null
        ? " · " + rows[0].rolling_avg_minutes + " min avg"
        : rows.length && rows[0].sample_period_ms
          ? " · ~" + Math.round(rows[0].sample_period_ms / 1000) + "s MQTT"
          : "";
    els.tsSummary.textContent = rows.length + " rows" + period;
    if (data.numpy_available === false) {
      appendConsole("[hint] numpy not installed on Lambda — import numpy as np unavailable\n", "log-warn");
    }
  }

  async function testRule() {
    const rule = currentRule();
    if (!rule) return;
    persistActiveEditor();
    syncConfigFromDom(rule, activeCard);

    clearConsole();
    resetTsTable();
    if (els.consoleWrap) {
      els.consoleWrap.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }

    const hours = parseInt(els.testHours.value, 10) || 6;
    const rollMin = getRollingAvgMinutes();
    if (window.vibe12SetRollingAvgMinutes) window.vibe12SetRollingAvgMinutes(rollMin);
    appendConsole(
      "Testing \"" +
        (rule.title || rule.id) +
        "\" over " +
        hours +
        " h · rolling avg " +
        rollMin +
        " min\n"
    );

    const ok = await lintCode(rule.code, syntaxPillEl);
    if (!ok) {
      appendConsole("Fix syntax before run.\n", "error");
      return;
    }

    setLabActionButtonsEnabled(false);
    let eventsToPlay = [];
    let playOpts = [4, false];
    try {
      await loadTsPreview(hours);
      const res = await fetch("/api/playground/test-rule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rule, hours, rolling_avg_minutes: rollMin }),
      });
      const data = await res.json();
      if (!res.ok) {
        appendConsole((data.error || "failed") + "\n", "error");
        if (data.trace) appendConsole(data.trace, "error");
        return;
      }
      const verbose = els.verbosePrints && els.verbosePrints.checked;
      eventsToPlay = data.events || [];
      playOpts = [verbose ? 0 : 4, verbose];
      els.elapsedMs.textContent = data.ms + " ms · " + data.flagged + " flagged";
      lastTestReport = buildTestReport(rule, hours, data);
      els.testReport.value = lastTestReport;
      const printN = printCountFromEvents(eventsToPlay);
      if (printN > 200) {
        appendConsole(
          "[hint] " +
            printN +
            " print lines — console shows a sample; full log is in Copy report.\n",
          "log-warn"
        );
      }
      appendConsole(
        "Test complete. " +
          data.rows +
          " rows swept. See report below → Copy report.\n"
      );
      if (data.flagged === 0 && printN === 0) {
        appendConsole(
          "No faults & no prints: temps likely in bounds (65–80). Try bounds_low_f=66 or print each row.\n",
          "log-warn"
        );
      }
    } catch (e) {
      appendConsole(String(e) + "\n", "error");
    } finally {
      setLabActionButtonsEnabled(true);
    }
    if (eventsToPlay.length) {
      void playEvents(eventsToPlay, playOpts[0], playOpts[1]);
    }
  }

  function collectRules() {
    persistActiveEditor();
    return rules.map((r) => ({ ...r }));
  }

  async function pingHealth() {
    try {
      const h = await (await fetch("/api/health")).json();
      appendConsole(
        "[health] " +
          h.status +
          " · test≤" +
          h.test_hours_default +
          "h · go-live " +
          (h.go_live_batch_hours || 6) +
          "h×" +
          (h.go_live_max_hours || 168) +
          "h" +
          " · datetime ok" +
          (h.numpy_available ? " · numpy ok" : " · no numpy") +
          "\n"
      );
    } catch (e) {
      appendConsole("[health] failed: " + e + "\n", "error");
    }
  }

  async function saveDraft() {
    const payload = collectRules();
    const res = await fetch("/api/fdd-rules", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rules: payload }),
    });
    clearConsole();
    const data = await res.json().catch(() => ({}));
    if (res.ok) {
      appendConsole("Draft saved (" + (data.count || payload.length) + " rules, ts_ms=-2).\n");
      appendConsole("No 7d backfill yet — use Go live (7 d) for FDD status row.\n");
      notifyDashboardRules();
    } else appendConsole("Save failed.\n", "error");
  }

  async function goLive() {
    clearConsole();
    appendConsole(
      "Go live: save rules + AFDD backfill (6 h batches, max 7 d — server hard-coded)…\n"
    );
    const payload = collectRules();
    setLabActionButtonsEnabled(false);
    try {
      const res = await fetch("/api/playground/go-live", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rules: payload }),
      });
      const raw = await res.text();
      let data = {};
      try {
        data = raw ? JSON.parse(raw) : {};
      } catch (parseErr) {
        appendConsole(
          "Go live: server did not return JSON (often 502 timeout or Internal Server Error).\n",
          "error"
        );
        appendConsole(raw.slice(0, 400) + (raw.length > 400 ? "…" : "") + "\n", "error");
        return;
      }
      if (!res.ok) {
        appendConsole((data.error || "go-live failed") + "\n", "error");
        if (data.hint) appendConsole(data.hint + "\n", "error");
        (data.debug?.server_log || []).forEach((l) =>
          appendConsole("[srv] " + l + "\n", "error")
        );
        if (data.trace) appendConsole(data.trace, "error");
        return;
      }
      (data.debug?.server_log || []).forEach((l) =>
        appendConsole("[srv] " + l + "\n", "log-ok")
      );
      (data.debug?.server_log || data.summary?.server_log || []).forEach((l) =>
        appendConsole("[srv] " + l + "\n", "log-ok")
      );
      (data.summary?.eval_log || []).forEach((l) => appendConsole(l + "\n"));
      (data.summary?.chunk_log || []).slice(-8).forEach((c) => {
        appendConsole(
          "  chunk " +
            (c.samples || 0) +
            " samples, " +
            (c.flagged_in_chunk || 0) +
            " flags, " +
            (c.ms || "?") +
            " ms\n",
          "log-ok"
        );
      });
      appendConsole(
        "Backfill done (" +
          (data.summary?.chunk_count ?? "?") +
          " chunks × " +
          (data.summary?.chunk_hours ?? 6) +
          " h, lookback " +
          (data.hours ?? 168) +
          " h).\n"
      );
      notifyDashboardRules();
      if (window.vibe12DashboardRefresh) window.vibe12DashboardRefresh();
    } catch (e) {
      appendConsole(String(e) + "\n", "error");
    } finally {
      setLabActionButtonsEnabled(true);
    }
  }

  function selectRule(index) {
    if (index < 0 || index >= rules.length) return;
    selectedIndex = index;
    els.ruleSelect.value = String(index);
    const labUnit = labTempUnitEl();
    const rule = rules[index];
    if (labUnit && rule) {
      labUnit.value = ruleTempUnit(rule);
    }
    renderSelectedRule();
  }

  function addRule() {
    persistActiveEditor();
    rules.push(blankRule());
    selectedIndex = rules.length - 1;
    populateRuleSelect();
    renderSelectedRule();
    notifyDashboardRules();
  }

  function removeRule() {
    if (rules.length <= 1) return;
    persistActiveEditor();
    rules.splice(selectedIndex, 1);
    selectedIndex = Math.min(selectedIndex, rules.length - 1);
    populateRuleSelect();
    renderSelectedRule();
    notifyDashboardRules();
  }

  window.vibe12SetRulePlotOnChart = function (ruleId, on) {
    const r = rules.find((x) => x.id === ruleId);
    if (!r || r.enabled === false) return;
    r.plot_on_chart = !!on;
    if (selectedIndex >= 0 && rules[selectedIndex]?.id === ruleId) {
      renderSelectedRule();
    }
  };

  window.vibe12GetRulesMeta = rulesMetaSnapshot;

  function labTempUnitEl() {
    return document.getElementById("labTempUnit");
  }

  function getLabTempUnit() {
    const el = labTempUnitEl();
    if (!el) return "imperial";
    return String(el.value).toLowerCase() === "metric" ? "metric" : "imperial";
  }

  async function reloadFieldMeta(unit) {
    const res = await fetch(
      "/api/fdd-rules?temp_unit=" + encodeURIComponent(unit || getLabTempUnit())
    );
    const data = await res.json();
    fieldMeta = data.config_field_meta || fieldMeta;
  }

  async function boot() {
    const res = await fetch(
      "/api/fdd-rules?temp_unit=" + encodeURIComponent(getLabTempUnit())
    );
    const data = await res.json();
    fieldMeta = data.config_field_meta || {};
    rules = data.rules?.length ? data.rules : data.defaults || [];
    rules.forEach((r) => {
      if (r.plot_on_chart === undefined) r.plot_on_chart = true;
      normalizeRuleConfig(r);
    });
    selectedIndex = 0;
    populateRuleSelect();
    renderSelectedRule();

    els.ruleSelect.addEventListener("change", () => {
      selectRule(parseInt(els.ruleSelect.value, 10));
    });
    els.addRuleBtn.addEventListener("click", addRule);
    els.removeRuleBtn.addEventListener("click", removeRule);
    els.testRuleBtn.addEventListener("click", testRule);
    els.saveRulesBtn.addEventListener("click", saveDraft);
    els.goLiveBtn.addEventListener("click", goLive);
    els.copyReportBtn.addEventListener("click", copyReportToClipboard);
    els.testHours.addEventListener("change", () => {
      els.testHoursLabel.textContent = els.testHours.value;
      loadTsPreview(parseInt(els.testHours.value, 10));
    });
    const labUnit = labTempUnitEl();
    if (labUnit) {
      const rule = currentRule();
      if (rule && rule.config && rule.config.temp_unit) {
        labUnit.value = ruleTempUnit(rule);
      }
      labUnit.addEventListener("change", async () => {
        persistActiveEditor();
        const r = currentRule();
        if (r) {
          if (!r.config) r.config = {};
          r.config.temp_unit = getLabTempUnit();
        }
        await reloadFieldMeta(getLabTempUnit());
        renderSelectedRule();
        notifyDashboardRules();
      });
    }
    const labRoll = document.getElementById("labRollingAvgMinutes");
    if (labRoll) {
      const saved = localStorage.getItem("vibe12_rolling_avg_minutes");
      if (saved) labRoll.value = saved;
      labRoll.addEventListener("change", () => {
        if (window.vibe12SetRollingAvgMinutes) {
          window.vibe12SetRollingAvgMinutes(labRoll.value);
        } else {
          localStorage.setItem("vibe12_rolling_avg_minutes", labRoll.value);
        }
        loadTsPreview(parseInt(els.testHours.value, 10) || 6);
      });
    }

    setLabActionButtonsEnabled(true);
    await pingHealth();
    await loadTsPreview(parseInt(els.testHours.value, 10) || 6);
    notifyDashboardRules();
  }

  window.vibe12RuleLabOnTabShown = function () {
    refreshEditor();
  };

  document.addEventListener("DOMContentLoaded", boot);
})();
