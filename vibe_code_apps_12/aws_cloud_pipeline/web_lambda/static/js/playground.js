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

  function blankRule() {
    return {
      id: newRuleId(),
      title: "New rule",
      enabled: true,
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

  function buildConfigInputs(rule, container) {
    container.innerHTML = "";
    (rule.config_fields || []).forEach((key) => {
      const meta = fieldMeta[key] || { label: key, type: "float", step: 0.1 };
      const label = document.createElement("label");
      label.textContent = meta.label || key;
      const inp = document.createElement("input");
      inp.type = "number";
      inp.step = meta.step || (meta.type === "int" ? 1 : 0.1);
      inp.value = rule.config[key] ?? "";
      inp.dataset.cfgKey = key;
      inp.addEventListener("change", () => {
        rule.config[key] =
          meta.type === "int" ? parseInt(inp.value, 10) : parseFloat(inp.value);
      });
      label.appendChild(inp);
      container.appendChild(label);
    });
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
    const colorDot = document.createElement("span");
    colorDot.className = "rule-color";
    colorDot.style.background = rule.color || "#8b949e";
    const titleInp = document.createElement("input");
    titleInp.type = "text";
    titleInp.value = rule.title || rule.id;
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
    enChk.addEventListener("change", () => {
      rule.enabled = enChk.checked;
      populateRuleSelect();
    });
    enLab.append(enChk, document.createTextNode(" Enabled"));
    syntaxPillEl = document.createElement("span");
    syntaxPillEl.className = "syntax-pill ok";
    syntaxPillEl.textContent = "…";
    head.append(colorDot, titleInp, enLab, syntaxPillEl);

    const cfgRow = document.createElement("div");
    cfgRow.className = "rule-config-row";
    buildConfigInputs(rule, cfgRow);

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
    lines.push(
      "## Result: " +
        data.rows +
        " rows swept, " +
        data.flagged +
        " flagged (instant per row), " +
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

  function playEvents(events, delayMs, showAllPrints) {
    return new Promise((resolve) => {
      let i = 0;
      let faultLines = 0;
      let stdoutLines = 0;
      const stdoutCap = showAllPrints ? 500 : 60;
      function next() {
        if (i >= events.length) {
          resolve();
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
          highlightRow(evt.row, evt.status);
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
        if (delayMs > 0) setTimeout(next, delayMs);
        else next();
      }
      next();
    });
  }

  async function loadTsPreview(hours) {
    const res = await fetch("/api/readings?hours=" + hours);
    const data = await res.json();
    const rows = (data.readings || []).map((r, i) => ({
      row: i,
      ts: (r.ts_iso || "").replace("T", " ").slice(0, 19),
      degF: r.degF,
    }));
    els.tsTableBody.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      tr.dataset.row = r.row;
      tr.innerHTML =
        "<td>" +
        r.row +
        "</td><td>" +
        r.ts +
        '</td><td class="num">' +
        r.degF.toFixed(2) +
        "</td><td></td>";
      els.tsTableBody.appendChild(tr);
    });
    els.tsSummary.textContent = rows.length + " rows";
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
    appendConsole("Testing \"" + (rule.title || rule.id) + "\" over " + hours + " h\n");

    const ok = await lintCode(rule.code, syntaxPillEl);
    if (!ok) {
      appendConsole("Fix syntax before run.\n", "error");
      return;
    }

    els.testRuleBtn.disabled = true;
    els.goLiveBtn.disabled = true;
    try {
      await loadTsPreview(hours);
      const res = await fetch("/api/playground/test-rule", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rule, hours }),
      });
      const data = await res.json();
      if (!res.ok) {
        appendConsole((data.error || "failed") + "\n", "error");
        if (data.trace) appendConsole(data.trace, "error");
        return;
      }
      const verbose = els.verbosePrints && els.verbosePrints.checked;
      await playEvents(data.events || [], verbose ? 0 : 4, verbose);
      els.elapsedMs.textContent = data.ms + " ms · " + data.flagged + " flagged";
      lastTestReport = buildTestReport(rule, hours, data);
      els.testReport.value = lastTestReport;
      appendConsole(
        "Test complete. " +
          data.rows +
          " rows swept. See report below → Copy report.\n"
      );
      if (data.flagged === 0 && printCountFromEvents(data.events) === 0) {
        appendConsole(
          "No faults & no prints: temps likely in bounds (65–80). Try bounds_low_f=66 or print each row.\n",
          "log-warn"
        );
      }
    } catch (e) {
      appendConsole(String(e) + "\n", "error");
    } finally {
      els.testRuleBtn.disabled = false;
      els.goLiveBtn.disabled = false;
    }
  }

  function syncConfigFromDom(rule, card) {
    if (!rule || !card) return;
    card.querySelectorAll(".rule-config-row input").forEach((inp) => {
      const key = inp.dataset.cfgKey;
      const meta = fieldMeta[key] || { type: "float" };
      rule.config[key] =
        meta.type === "int" ? parseInt(inp.value, 10) : parseFloat(inp.value);
    });
  }

  function collectRules() {
    persistActiveEditor();
    return rules.map((r) => ({ ...r }));
  }

  async function pingHealth() {
    try {
      const h = await (await fetch("/api/health")).json();
      appendConsole(
        "[health] " + h.status + " · test≤" + h.test_hours_default + "h · go-live≤" + h.backfill_hours_max + "h\n"
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
    } else appendConsole("Save failed.\n", "error");
  }

  async function goLive() {
    clearConsole();
    appendConsole("Go live: saving rules + 7 d backfill…\n");
    const payload = collectRules();
    els.goLiveBtn.disabled = true;
    try {
      const res = await fetch("/api/playground/go-live", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rules: payload, hours: 168 }),
      });
      const data = await res.json();
      if (!res.ok) {
        appendConsole((data.error || "go-live failed") + "\n", "error");
        return;
      }
      (data.summary?.eval_log || []).forEach((l) => appendConsole(l + "\n"));
      appendConsole("Backfill written to FDD status row.\n");
      if (window.vibe12DashboardRefresh) window.vibe12DashboardRefresh();
    } catch (e) {
      appendConsole(String(e) + "\n", "error");
    } finally {
      els.goLiveBtn.disabled = false;
    }
  }

  function selectRule(index) {
    if (index < 0 || index >= rules.length) return;
    selectedIndex = index;
    els.ruleSelect.value = String(index);
    renderSelectedRule();
  }

  function addRule() {
    persistActiveEditor();
    rules.push(blankRule());
    selectedIndex = rules.length - 1;
    populateRuleSelect();
    renderSelectedRule();
  }

  function removeRule() {
    if (rules.length <= 1) return;
    persistActiveEditor();
    rules.splice(selectedIndex, 1);
    selectedIndex = Math.min(selectedIndex, rules.length - 1);
    populateRuleSelect();
    renderSelectedRule();
  }

  async function boot() {
    const res = await fetch("/api/fdd-rules");
    const data = await res.json();
    fieldMeta = data.config_field_meta || {};
    rules = data.rules?.length ? data.rules : data.defaults || [];
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

    await pingHealth();
    await loadTsPreview(parseInt(els.testHours.value, 10) || 6);
  }

  window.vibe12RuleLabOnTabShown = function () {
    refreshEditor();
  };

  document.addEventListener("DOMContentLoaded", boot);
})();
