(function () {
  "use strict";

  let hours = 168;
  let refreshMs = 60000;
  let refreshTimer = null;
  let lastChartData = null;
  /** rule id → show fault lane on chart */
  const chartPlotVisible = {};
  let showBoundsGuides = localStorage.getItem("vibe12_show_bounds_guides") !== "0";
  let showRollingAvg = localStorage.getItem("vibe12_show_rolling_avg") !== "0";
  const ROLLING_TARGET_MS = 60000;
  const PLOT_CFG = { responsive: true, displayModeBar: true };
  const CHART_MAX_PTS = 4000;

  function logMsg(t, c) {
    const el = document.getElementById("dashLog");
    if (!el) return;
    const d = document.createElement("div");
    d.className = c || "log-ok";
    d.textContent = new Date().toISOString().slice(11, 19) + "  " + t;
    el.appendChild(d);
    while (el.childNodes.length > 60) el.removeChild(el.firstChild);
  }

  function faultClass(s) {
    return "fdd-badge fdd-" + (s || "NORMAL");
  }

  function utcStamp(ts_ms, ts_iso) {
    if (ts_iso) return String(ts_iso).replace("T", " ").slice(0, 19);
    if (ts_ms != null) return new Date(ts_ms).toISOString().replace("T", " ").slice(0, 19);
    return "—";
  }

  function formatLastSampleTime(last) {
    const ms = last && last.ts_ms;
    if (ms == null) return { html: "—", title: "" };
    const utc = utcStamp(ms, last.ts_iso);
    const dt = new Date(ms);
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone || "local";
    const local = dt.toLocaleString(undefined, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
      timeZoneName: "short",
    });
    return {
      html:
        '<span class="ts-utc">' +
        utc +
        " UTC</span>" +
        '<span class="ts-local">' +
        local +
        "</span>",
      title: "UTC: " + utc + "\nLocal (" + tz + "): " + local,
    };
  }

  function setLatestTs(last) {
    const el = document.getElementById("latestTs");
    if (!el) return;
    const fmt = formatLastSampleTime(last);
    el.innerHTML = fmt.html;
    el.title = fmt.title;
  }

  function xLabels(pts) {
    return pts.map((p) => utcStamp(p.ts_ms, p.ts_iso));
  }

  function medianSampleMs(pts) {
    if (pts.length < 2) return 10000;
    const dts = [];
    for (let i = 1; i < pts.length; i++) {
      const d = pts[i].ts_ms - pts[i - 1].ts_ms;
      if (d > 0) dts.push(d);
    }
    if (!dts.length) return 10000;
    dts.sort((a, b) => a - b);
    return dts[Math.floor(dts.length / 2)];
  }

  /** Trailing average sized to ~60s of data at whatever MQTT cadence we have. */
  function adaptiveRollingAvg(pts, targetWindowMs) {
    const periodMs = medianSampleMs(pts);
    const windowSamples = Math.max(
      2,
      Math.min(Math.round(targetWindowMs / periodMs), 900)
    );
    const values = [];
    for (let i = 0; i < pts.length; i++) {
      const start = Math.max(0, i - windowSamples + 1);
      let sum = 0;
      for (let j = start; j <= i; j++) sum += pts[j].degF;
      values.push(sum / (i - start + 1));
    }
    const windowSec = (periodMs * windowSamples) / 1000;
    let label;
    if (windowSec >= 90) {
      label = "~" + Math.round(windowSec / 60) + " min";
    } else {
      label = "~" + Math.round(windowSec) + " s";
    }
    return {
      values,
      periodMs,
      windowSamples,
      label: label + " · " + windowSamples + " pts @ " + Math.round(periodMs / 1000) + "s",
    };
  }

  function downsample(pts, plots, series) {
    series = series || {};
    if (pts.length <= CHART_MAX_PTS) {
      return { pts, plots, series, stride: 1 };
    }
    const stride = Math.ceil(pts.length / CHART_MAX_PTS);
    const idx = [];
    for (let i = 0; i < pts.length; i += stride) idx.push(i);
    if (idx[idx.length - 1] !== pts.length - 1) idx.push(pts.length - 1);
    return {
      pts: idx.map((i) => pts[i]),
      plots: Object.fromEntries(
        Object.entries(plots || {}).map(([k, s]) => [k, idx.map((i) => s[i] || 0)])
      ),
      series: Object.fromEntries(
        Object.entries(series).map(([k, s]) => [k, idx.map((i) => s[i])])
      ),
      stride,
    };
  }

  function boundsShapes(x, low, high) {
    if (x.length < 1 || low == null || high == null) return [];
    const x0 = x[0];
    const x1 = x[x.length - 1];
    const line = { color: "#3fb950", width: 1.5, dash: "dash" };
    return [
      {
        type: "line",
        xref: "x",
        yref: "y",
        x0,
        x1,
        y0: low,
        y1: low,
        line,
        layer: "below",
      },
      {
        type: "line",
        xref: "x",
        yref: "y",
        x0,
        x1,
        y0: high,
        y1: high,
        line,
        layer: "below",
      },
    ];
  }

  function faultBoolY(flags) {
    return flags.map((v) => (v ? 1 : 0));
  }

  function shouldPlotFault(ruleId) {
    return chartPlotVisible[ruleId] === true;
  }

  function syncPlotStateFromMeta(metaList) {
    (metaList || []).forEach((r) => {
      const on = r.enabled !== false && r.plot_on_chart !== false;
      chartPlotVisible[r.id] = on;
    });
  }

  function updateGuideLabels(data, rollInfo) {
    const guides = data.chart_guides || {};
    const bl = document.getElementById("boundsGuideLabel");
    if (bl && guides.bounds_low_f != null) {
      bl.textContent = guides.bounds_low_f + "–" + guides.bounds_high_f + " °F";
    }
    const rl = document.getElementById("rollingAvgLabel");
    if (rl && rollInfo) rl.textContent = rollInfo.label;
  }

  function renderPlotToggles(metaList) {
    const host = document.getElementById("faultPlotToggles");
    if (!host) return;
    host.innerHTML = "";
    if (!metaList || !metaList.length) {
      host.textContent = "No rules — add in Rule Lab";
      return;
    }
    (metaList || []).forEach((r) => {
      const lab = document.createElement("label");
      lab.className = "plot-toggle-item";
      if (r.enabled === false) lab.classList.add("plot-toggle-off-rule");

      const dot = document.createElement("span");
      dot.className = "plot-toggle-dot";
      dot.style.background = r.color || "#8b949e";

      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.dataset.ruleId = r.id;
      chk.checked = shouldPlotFault(r.id);
      chk.disabled = r.enabled === false;
      chk.title =
        r.enabled === false
          ? "Rule disabled in Rule Lab — enable there first"
          : "Show this fault lane on the chart";

      chk.addEventListener("change", () => {
        chartPlotVisible[r.id] = chk.checked;
        if (window.vibe12SetRulePlotOnChart) {
          window.vibe12SetRulePlotOnChart(r.id, chk.checked);
        }
        if (lastChartData) drawChart(lastChartData);
      });

      lab.append(chk, dot, document.createTextNode(" " + (r.title || r.id)));
      host.appendChild(lab);
    });
  }

  function drawChart(data) {
    let pts = data.readings || [];
    let plots = data.fault_plots || {};
    const panels = (data.fault_panels || []).filter((p) => shouldPlotFault(p.key));
    const guides = data.chart_guides || {};

    let rollInfo = null;
    let rollingSeries = {};
    if (pts.length >= 2) {
      rollInfo = adaptiveRollingAvg(pts, ROLLING_TARGET_MS);
      rollingSeries.auto_rolling_avg = rollInfo.values;
    }
    const aux = data.aux_series || {};
    if (aux.degF_1min_avg && aux.degF_1min_avg.length === pts.length) {
      rollingSeries.rule_rolling_avg = aux.degF_1min_avg;
    }

    const ds = downsample(pts, plots, rollingSeries);
    pts = ds.pts;
    plots = ds.plots;
    const rolled = ds.series || {};
    rollInfo = rollInfo || null;
    if (rollInfo && rolled.auto_rolling_avg) {
      rollInfo = { ...rollInfo, values: rolled.auto_rolling_avg };
    }
    if (!pts.length) {
      Plotly.react(
        "chart",
        [],
        {
          height: 320,
          paper_bgcolor: "#0f1419",
          plot_bgcolor: "#1c2128",
          title: { text: "Waiting for telemetry…", font: { color: "#e6edf3" } },
        },
        PLOT_CFG
      );
      return ds.stride;
    }
    const x = xLabels(pts);
    const yF = pts.map((p) => p.degF);
    const pad = Math.max(3, (Math.max(...yF) - Math.min(...yF)) * 0.1);
    const traces = [
      {
        x,
        y: yF,
        name: "Temperature (raw)",
        type: "scatter",
        mode: "lines",
        line: { color: "#58a6ff", width: 2.5 },
        yaxis: "y",
        showlegend: true,
        hovertemplate: "%{y:.1f} °F raw<extra></extra>",
      },
    ];
    if (showRollingAvg && rolled.rule_rolling_avg) {
      traces.push({
        x,
        y: rolled.rule_rolling_avg,
        name: "Rolling avg (rule code)",
        type: "scatter",
        mode: "lines",
        line: { color: "#d2a8ff", width: 1.5, dash: "dot" },
        yaxis: "y",
        showlegend: true,
        opacity: 0.9,
        hovertemplate: "%{y:.1f} °F rule avg<extra></extra>",
      });
    } else if (showRollingAvg && rollInfo && rollInfo.values) {
      traces.push({
        x,
        y: rollInfo.values,
        name: "Rolling avg (" + rollInfo.label + ")",
        type: "scatter",
        mode: "lines",
        line: { color: "#a371f7", width: 1.5, dash: "dash" },
        yaxis: "y",
        showlegend: true,
        opacity: 0.88,
        hovertemplate: "%{y:.1f} °F avg<extra></extra>",
      });
    }
    const showFaultAxis = panels.length > 0;
    panels.forEach((panel) => {
      const flags = plots[panel.key] || pts.map(() => 0);
      traces.push({
        x,
        y: faultBoolY(flags),
        name: panel.title,
        type: "scatter",
        mode: "lines",
        line: { color: panel.color, width: 2, shape: "hv" },
        yaxis: showFaultAxis ? "y2" : "y",
        showlegend: true,
        opacity: 0.9,
      });
    });
    const layout = {
      height: 460,
      paper_bgcolor: "#0f1419",
      plot_bgcolor: "#1c2128",
      font: { color: "#e6edf3" },
      margin: { t: 36, r: 64, b: 44, l: 52 },
      hovermode: "x unified",
      legend: { orientation: "h", y: 1.12 },
      xaxis: { title: "Time (UTC)", gridcolor: "#30363d" },
      yaxis: {
        title: "°F",
        side: "left",
        range: [Math.min(...yF) - pad, Math.max(...yF) + pad],
      },
    };
    if (showFaultAxis) {
      layout.yaxis2 = {
        side: "right",
        overlaying: "y",
        range: [0, 1],
        tickvals: [0, 1],
        ticktext: ["False", "True"],
      };
    }
    if (
      showBoundsGuides &&
      guides.bounds_low_f != null &&
      guides.bounds_high_f != null
    ) {
      layout.shapes = boundsShapes(x, guides.bounds_low_f, guides.bounds_high_f);
    }
    Plotly.react("chart", traces, layout, PLOT_CFG);
    return ds.stride;
  }

  async function refresh() {
    const url = "/api/readings?hours=" + hours;
    logMsg("GET " + url);
    let data;
    try {
      data = await (await fetch(url)).json();
    } catch (e) {
      logMsg("fetch error: " + e, "log-err");
      return;
    }
    lastChartData = data;
    const meta = data.rules_meta || [];
    syncPlotStateFromMeta(meta);
    renderPlotToggles(meta);
    const rollPreview =
      (data.readings || []).length >= 2
        ? adaptiveRollingAvg(data.readings, ROLLING_TARGET_MS)
        : null;
    updateGuideLabels(data, rollPreview);

    const pts = data.readings || [];
    const fdd = data.fdd_open || {};
    logMsg(pts.length + " pts · FDD " + (fdd.fdd_status || "PENDING"));
    (data.debug?.fdd_eval_log || []).slice(-2).forEach((l) => logMsg("FDD: " + l));
    const stride = pts.length ? drawChart(data) : 1;
    document.getElementById("status").textContent =
      pts.length + " pts · " + hours + " h" + (stride > 1 ? " · chart 1/" + stride : "");
    const b = document.getElementById("fddBadge");
    b.textContent = "FDD: " + (fdd.fdd_status || "PENDING");
    b.className = faultClass(fdd.fdd_status);
    if (pts.length) {
      const last = pts[pts.length - 1];
      document.getElementById("latestC").textContent = last.degC.toFixed(2);
      document.getElementById("latestF").textContent = last.degF.toFixed(2);
      setLatestTs(last);
    }
  }

  /** Called from Rule Lab when enabled / plot checkboxes change */
  window.vibe12DashboardSyncRules = function (metaList, chartGuides) {
    syncPlotStateFromMeta(metaList);
    renderPlotToggles(metaList);
    if (lastChartData) {
      lastChartData.rules_meta = metaList;
      if (chartGuides) lastChartData.chart_guides = chartGuides;
      const rollPreview =
        (lastChartData.readings || []).length >= 2
          ? adaptiveRollingAvg(lastChartData.readings, ROLLING_TARGET_MS)
          : null;
      updateGuideLabels(lastChartData, rollPreview);
      drawChart(lastChartData);
    }
  };

  function bindTabs() {
    document.querySelectorAll(".tab").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
        document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
        btn.classList.add("active");
        document.getElementById("tab-" + btn.dataset.tab).classList.add("active");
        if (btn.dataset.tab === "rulelab" && window.vibe12RuleLabOnTabShown) {
          window.vibe12RuleLabOnTabShown();
        }
        if (btn.dataset.tab === "dashboard") refresh();
      });
    });
  }

  function bindToolbar() {
    const rs = document.getElementById("refreshSelect");
    rs.innerHTML =
      '<option value="10000">10 s</option><option value="60000" selected>1 min</option><option value="300000">5 min</option>';
    const hs = document.getElementById("hoursSelect");
    [1, 3, 6, 12, 24, 168].forEach((h) => {
      const o = document.createElement("option");
      o.value = h;
      o.textContent = h === 168 ? "7 d" : h + " h";
      if (h === 168) o.selected = true;
      hs.appendChild(o);
    });
    const savedR = localStorage.getItem("vibe12_refresh_ms");
    const savedH = localStorage.getItem("vibe12_hours");
    if (savedR) {
      rs.value = savedR;
      refreshMs = parseInt(savedR, 10);
    }
    if (savedH) {
      hs.value = savedH;
      hours = parseInt(savedH, 10);
    }
    rs.addEventListener("change", () => {
      refreshMs = parseInt(rs.value, 10);
      localStorage.setItem("vibe12_refresh_ms", String(refreshMs));
      clearInterval(refreshTimer);
      refreshTimer = setInterval(refresh, refreshMs);
      refresh();
    });
    hs.addEventListener("change", () => {
      hours = parseInt(hs.value, 10);
      localStorage.setItem("vibe12_hours", String(hours));
      refresh();
    });
    document.getElementById("refreshNow").addEventListener("click", refresh);
    refreshTimer = setInterval(refresh, refreshMs);
  }

  window.vibe12DashboardRefresh = refresh;

  async function pingHealth() {
    try {
      const h = await (await fetch("/api/health")).json();
      logMsg(
        "API OK · " + h.app + " · test≤" + h.test_hours_default + "h · backfill≤" + h.backfill_hours_max + "h",
        "log-ok"
      );
      if (h.deploy_revision) logMsg("deploy rev " + h.deploy_revision, "log-ok");
    } catch (e) {
      logMsg("health check failed: " + e, "log-err");
    }
  }

  function bindGuideToggles() {
    const b = document.getElementById("showBoundsGuides");
    const r = document.getElementById("showRollingAvg");
    if (b) {
      b.checked = showBoundsGuides;
      b.addEventListener("change", () => {
        showBoundsGuides = b.checked;
        localStorage.setItem("vibe12_show_bounds_guides", showBoundsGuides ? "1" : "0");
        if (lastChartData) drawChart(lastChartData);
      });
    }
    if (r) {
      r.checked = showRollingAvg;
      r.addEventListener("change", () => {
        showRollingAvg = r.checked;
        localStorage.setItem("vibe12_show_rolling_avg", showRollingAvg ? "1" : "0");
        if (lastChartData) drawChart(lastChartData);
      });
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindTabs();
    bindToolbar();
    bindGuideToggles();
    pingHealth();
    refresh();
  });
})();
