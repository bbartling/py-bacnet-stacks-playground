(function () {
  "use strict";

  let hours = 24;
  let refreshMs = 60000;
  let refreshTimer = null;
  let lastChartData = null;
  /** rule id → show fault lane on chart */
  const chartPlotVisible = {};
  let showBoundsGuides = localStorage.getItem("vibe12_show_bounds_guides") !== "0";
  let showRollingAvg = localStorage.getItem("vibe12_show_rolling_avg") !== "0";
  const ROLLING_STORAGE_KEY = "vibe12_rolling_avg_minutes";
  const TEMP_UNIT_STORAGE_KEY = "vibe12_display_temp_unit";
  const ROLLING_ALLOWED = [1, 5, 10];

  function normalizeDisplayUnit(v) {
    const s = String(v || "imperial").toLowerCase();
    return s === "metric" || s === "c" || s === "celsius" ? "metric" : "imperial";
  }

  function unitSym(unit) {
    return normalizeDisplayUnit(unit) === "metric" ? "°C" : "°F";
  }

  function chartTemp(p, displayUnit) {
    if (!p) return null;
    return normalizeDisplayUnit(displayUnit) === "metric" ? p.degC : p.degF;
  }

  let displayTempUnit = normalizeDisplayUnit(
    localStorage.getItem(TEMP_UNIT_STORAGE_KEY) || "imperial"
  );

  function normalizeRollingMinutes(v) {
    const m = parseInt(v, 10);
    if (ROLLING_ALLOWED.indexOf(m) >= 0) return m;
    return 1;
  }

  let rollingAvgMinutes = normalizeRollingMinutes(
    localStorage.getItem(ROLLING_STORAGE_KEY) || "1"
  );
  const PLOT_CFG = { responsive: true, displayModeBar: true };
  const CHART_MAX_PTS = 4000;
  const CHART_UIREVISION = "vibe12-chart";
  let preserveUserZoom = false;
  const pauseRefreshWhenZoomed = true;
  let chartRelayoutBound = false;
  let refreshInFlight = 0;
  let selectedSiteId = localStorage.getItem("vibe12_site_id") || "";
  let selectedBuildingId = localStorage.getItem("vibe12_building_id") || "";
  let buildingPoints = [];
  let selectedSeriesIds = new Set(
    JSON.parse(localStorage.getItem("vibe12_selected_series") || "[]")
  );
  let multiSeriesData = null;
  let showMultiSeries = localStorage.getItem("vibe12_show_multi_series") === "1";

  function historyLabel(h) {
    const n = parseInt(h, 10);
    if (n === 168) return "7 d";
    if (n === 72) return "3 d";
    return n + " h";
  }

  function formatDuration(ms) {
    if (ms == null || ms <= 0) return "0s";
    const sec = Math.floor(ms / 1000);
    if (sec < 60) return sec + "s";
    const min = Math.floor(sec / 60);
    if (min < 60) return min + "m";
    const hr = Math.floor(min / 60);
    const rm = min % 60;
    if (hr < 48) return rm ? hr + "h " + rm + "m" : hr + "h";
    const d = Math.floor(hr / 24);
    const rh = hr % 24;
    return rh ? d + "d " + rh + "h" : d + "d";
  }

  function hexToRgb(hex) {
    const h = String(hex || "#8b949e").replace("#", "");
    if (h.length !== 6) return { r: 139, g: 148, b: 158 };
    return {
      r: parseInt(h.slice(0, 2), 16),
      g: parseInt(h.slice(2, 4), 16),
      b: parseInt(h.slice(4, 6), 16),
    };
  }

  function faultCardBackground(color, intensity) {
    const rgb = hexToRgb(color);
    const a = 0.08 + Math.min(1, Math.max(0, intensity)) * 0.42;
    return "rgba(" + rgb.r + "," + rgb.g + "," + rgb.b + "," + a.toFixed(3) + ")";
  }

  function setRefreshLoading(on) {
    const btn = document.getElementById("refreshNow");
    const wrap = document.getElementById("faultAnalyticsWrap");
    if (btn) btn.classList.toggle("is-loading", on);
    if (wrap) wrap.classList.toggle("is-loading", on);
  }

  function renderFaultAnalytics(data) {
    const titleEl = document.getElementById("faultAnalyticsTitle");
    const chip = document.getElementById("fddStatusChip");
    const grid = document.getElementById("faultAnalyticsGrid");
    if (!grid) return;

    const h = data.hours != null ? data.hours : hours;
    const fdd = data.fdd_open || {};
    const status = fdd.fdd_status || "PENDING";
    if (titleEl) {
      titleEl.textContent = "Fault analytics · " + historyLabel(h);
    }
    if (chip) {
      chip.textContent = status.replace(/_/g, " ");
      chip.className = "fdd-status-chip " + faultClass(status);
      chip.title = "Latest FDD status row (go-live backfill)";
    }

    let items = data.fault_analytics || [];
    if (!items.length && data.rules_meta && data.rules_meta.length) {
      items = data.rules_meta.map((r) => ({
        id: r.id,
        title: r.title || r.id,
        color: r.color || "#8b949e",
        count: (data.fault_totals || {})[r.id] || 0,
        elapsed_ms: 0,
      }));
      items.sort((a, b) => b.count - a.count);
    }

    grid.innerHTML = "";
    if (!items.length) {
      const empty = document.createElement("span");
      empty.className = "fault-analytics-empty";
      empty.textContent = "No rules — add in Rule Lab";
      grid.appendChild(empty);
      return;
    }

    const maxCount = Math.max(1, ...items.map((x) => x.count || 0));
    items.forEach((item) => {
      const card = document.createElement("div");
      card.className = "fault-analytics-card";
      const intensity = (item.count || 0) / maxCount;
      const color = item.color || "#8b949e";
      card.style.borderLeftColor = color;
      card.style.background = faultCardBackground(color, intensity);
      card.title = item.id;

      const t = document.createElement("div");
      t.className = "fault-analytics-card-title";
      t.textContent = item.title || item.id;

      const hits = document.createElement("div");
      hits.className = "fault-analytics-card-stat";
      hits.innerHTML =
        "<strong>" +
        (item.count || 0).toLocaleString() +
        "</strong> hits";

      const elapsed = document.createElement("div");
      elapsed.className = "fault-analytics-card-stat";
      elapsed.innerHTML =
        "<strong>" +
        formatDuration(item.elapsed_ms || 0) +
        "</strong> in fault";

      card.append(t, hits, elapsed);
      grid.appendChild(card);
    });
  }

  function logMsg(t, c) {
    const el = document.getElementById("dashLog");
    if (!el) return;
    const d = document.createElement("div");
    d.className = c || "log-ok";
    d.textContent = new Date().toISOString().slice(11, 19) + "  " + t;
    el.appendChild(d);
    while (el.childNodes.length > 80) el.removeChild(el.firstChild);
  }

  /** Surface API debug.server_log and eval_log in the dashboard log panel. */
  function logServerDebug(data, prefix) {
    if (!data) return;
    const dbg = data.debug || {};
    if (dbg.stage) logMsg((prefix || "API") + " stage=" + dbg.stage, "log-ok");
    if (dbg.eval_ms != null) logMsg("server eval_ms=" + dbg.eval_ms, "log-ok");
    if (dbg.chunk_count != null) logMsg("FDD chunks=" + dbg.chunk_count, "log-ok");
    (dbg.server_log || []).forEach((line) => logMsg("srv: " + line, "log-ok"));
    (dbg.fdd_eval_log || []).forEach((line) => logMsg("FDD: " + line, "log-ok"));
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

  function rollingAvgLabel(minutes, aux) {
    const m = minutes || rollingAvgMinutes;
    let extra = "";
    if (aux && aux.degF_1min_avg && aux.degF_1min_avg.length) {
      extra = " · server";
    }
    return m + " min" + extra;
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

  function updateGuideLabels(data) {
    const guides = data.chart_guides || {};
    const sym = unitSym(guides.temp_unit || data.display_temp_unit || displayTempUnit);
    const lo = guides.bounds_low != null ? guides.bounds_low : guides.bounds_low_f;
    const hi = guides.bounds_high != null ? guides.bounds_high : guides.bounds_high_f;
    const bl = document.getElementById("boundsGuideLabel");
    if (bl && lo != null && hi != null) {
      bl.textContent = lo + "–" + hi + " " + sym;
    }
    const rl = document.getElementById("rollingAvgLabel");
    const mins = data.rolling_avg_minutes != null ? data.rolling_avg_minutes : rollingAvgMinutes;
    if (rl) rl.textContent = rollingAvgLabel(mins, data.aux_series);
  }

  function renderPlotToggles(metaList) {
    const host = document.getElementById("faultPlotToggles");
    if (!host) return;
    host.innerHTML = "";
    if (!metaList || !metaList.length) {
      const empty = document.createElement("span");
      empty.className = "chart-empty-hint";
      empty.textContent = "No rules yet — add in Rule Lab (Bake-a-Py)";
      host.appendChild(empty);
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
        if (lastChartData) drawChart(lastChartData, { resetZoom: false });
      });

      lab.append(chk, dot, document.createTextNode(" " + (r.title || r.id)));
      host.appendChild(lab);
    });
  }

  function updateChartZoomHint() {
    const el = document.getElementById("chartZoomHint");
    if (!el) return;
    if (preserveUserZoom) {
      el.hidden = false;
      el.textContent =
        "Auto-refresh paused while zoomed — double-click chart or use home in Plotly toolbar to reset";
    } else {
      el.hidden = true;
      el.textContent = "";
    }
  }

  function bindChartZoomPreserve() {
    if (chartRelayoutBound) return;
    const gd = document.getElementById("chart");
    if (!gd || !gd.on) return;
    chartRelayoutBound = true;
    gd.on("plotly_relayout", (ev) => {
      if (!ev) return;
      if (ev["xaxis.autorange"] === true || ev["yaxis.autorange"] === true) {
        preserveUserZoom = false;
        updateChartZoomHint();
        return;
      }
      const keys = Object.keys(ev);
      if (
        keys.some(
          (k) =>
            k.indexOf("range") >= 0 ||
            k === "xaxis.range" ||
            k === "yaxis.range" ||
            k.indexOf("xaxis.range") === 0
        )
      ) {
        preserveUserZoom = true;
        updateChartZoomHint();
      }
    });
    gd.on("plotly_doubleclick", () => {
      preserveUserZoom = false;
      updateChartZoomHint();
    });
  }

  function drawChart(data, opts) {
    opts = opts || {};
    const resetZoom = !!opts.resetZoom;
    if (resetZoom) preserveUserZoom = false;
    let pts = data.readings || [];
    let plots = data.fault_plots || {};
    const panels = (data.fault_panels || []).filter((p) => shouldPlotFault(p.key));
    const guides = data.chart_guides || {};

    const aux = data.aux_series || {};
    const rollingSeries = {};
    if (aux.degF_1min_avg && aux.degF_1min_avg.length === pts.length) {
      rollingSeries.rule_rolling_avg = aux.degF_1min_avg;
    }

    const ds = downsample(pts, plots, rollingSeries);
    pts = ds.pts;
    plots = ds.plots;
    const rolled = ds.series || {};
    const rollMins = data.rolling_avg_minutes != null ? data.rolling_avg_minutes : rollingAvgMinutes;
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
    const du = normalizeDisplayUnit(data.display_temp_unit || displayTempUnit);
    const sym = unitSym(du);
    const yT = pts.map((p) => chartTemp(p, du));
    const pad = Math.max(3, (Math.max(...yT) - Math.min(...yT)) * 0.1);
    const traces = [
      {
        x,
        y: yT,
        name: "Temperature (raw)",
        type: "scatter",
        mode: "lines",
        line: { color: "#58a6ff", width: 2.5 },
        yaxis: "y",
        showlegend: true,
        hovertemplate: "%{y:.1f} " + sym + " raw<extra></extra>",
      },
    ];
    if (showRollingAvg && rolled.rule_rolling_avg) {
      const yAvg =
        du === "metric"
          ? rolled.rule_rolling_avg.map((v) => (v - 32) * (5 / 9))
          : rolled.rule_rolling_avg;
      traces.push({
        x,
        y: yAvg,
        name: "Rolling avg (" + rollMins + " min)",
        type: "scatter",
        mode: "lines",
        line: { color: "#d2a8ff", width: 1.5, dash: "dot" },
        yaxis: "y",
        showlegend: true,
        opacity: 0.9,
        hovertemplate: "%{y:.1f} " + sym + " rule avg<extra></extra>",
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
  const multiYs = [];
  if (showMultiSeries && multiSeriesData && multiSeriesData.series) {
    const palette = ["#f0883e", "#a371f7", "#3fb950", "#ffa657", "#79c0ff", "#ff7b72"];
    let pi = 0;
    Object.entries(multiSeriesData.series).forEach(([sid, samples]) => {
      if (!selectedSeriesIds.size || selectedSeriesIds.has(sid)) {
        const xs = samples.map((s) => utcStamp(s.ts_ms, s.ts));
        const ys = samples.map((s) => Number(s.value));
        ys.forEach((v) => {
          if (!Number.isNaN(v)) multiYs.push(v);
        });
        traces.push({
          x: xs,
          y: ys,
          name: sid.split("#").pop(),
          type: "scatter",
          mode: "lines",
          line: { color: palette[pi % palette.length], width: 1.5 },
          yaxis: "y",
          showlegend: true,
          opacity: 0.85,
        });
        pi += 1;
      }
    });
  }
    const yAll = yT.concat(multiYs.length ? multiYs : []);
    const yLo = Math.min(...yAll) - pad;
    const yHi = Math.max(...yAll) + pad;
    const layout = {
      height: 460,
      paper_bgcolor: "#0f1419",
      plot_bgcolor: "#1c2128",
      font: { color: "#e6edf3" },
      margin: { t: 36, r: 64, b: 44, l: 52 },
      hovermode: "x unified",
      legend: { orientation: "h", y: 1.12 },
      uirevision: CHART_UIREVISION,
      xaxis: { title: "Time (UTC)", gridcolor: "#30363d" },
      yaxis: {
        title: sym,
        side: "left",
      },
    };
    if (!preserveUserZoom || resetZoom) {
      layout.yaxis.range = [yLo, yHi];
      layout.xaxis.autorange = true;
    }
    if (showFaultAxis) {
      layout.yaxis2 = {
        side: "right",
        overlaying: "y",
        range: [0, 1],
        tickvals: [0, 1],
        ticktext: ["False", "True"],
      };
    }
    const gLo = guides.bounds_low != null ? guides.bounds_low : guides.bounds_low_f;
    const gHi = guides.bounds_high != null ? guides.bounds_high : guides.bounds_high_f;
    if (showBoundsGuides && gLo != null && gHi != null) {
      layout.shapes = boundsShapes(x, gLo, gHi);
    }
    Plotly.react("chart", traces, layout, PLOT_CFG).then(() => {
      bindChartZoomPreserve();
      updateChartZoomHint();
    });
    return ds.stride;
  }

  function setRollingAvgMinutes(m, persist) {
    rollingAvgMinutes = normalizeRollingMinutes(m);
    const sel = document.getElementById("rollingAvgMinutes");
    if (sel) sel.value = String(rollingAvgMinutes);
    if (persist !== false) {
      localStorage.setItem(ROLLING_STORAGE_KEY, String(rollingAvgMinutes));
    }
  }

  async function refresh(opts) {
    opts = opts || {};
    const showLoading = !opts.silent;
    if (showLoading) {
      refreshInFlight += 1;
      setRefreshLoading(true);
    }
    const url =
      "/api/readings?hours=" +
      hours +
      "&rolling_avg_minutes=" +
      rollingAvgMinutes +
      "&temp_unit=" +
      encodeURIComponent(displayTempUnit);
    if (!(opts.silent && preserveUserZoom && pauseRefreshWhenZoomed)) {
      logMsg("GET " + url);
    }
    let data;
    let fetchOk = false;
    try {
      const res = await fetch(url);
      const raw = await res.text();
      try {
        data = raw ? JSON.parse(raw) : {};
      } catch (parseErr) {
        logMsg(
          "HTTP " +
            res.status +
            " — not JSON (often 502 timeout or Internal Server Error). " +
            raw.slice(0, 160),
          "log-err"
        );
        return;
      }
      if (!res.ok) {
        logMsg(
          (data.error || "request failed") +
            (data.hint ? " — " + data.hint : "") +
            " (HTTP " +
            res.status +
            ")",
          "log-err"
        );
        if (data.trace) logMsg(data.trace.slice(0, 500), "log-err");
        logServerDebug(data, "readings error");
        return;
      }
      fetchOk = true;
    } catch (e) {
      logMsg("fetch error: " + e, "log-err");
      return;
    } finally {
      if (showLoading && !fetchOk) {
        refreshInFlight = Math.max(0, refreshInFlight - 1);
        if (refreshInFlight === 0) setRefreshLoading(false);
      }
    }
    if (!fetchOk || !data) return;
    logServerDebug(data, "readings");
    lastChartData = data;
    const meta = data.rules_meta || [];
    renderFaultAnalytics(data);
    syncPlotStateFromMeta(meta);
    renderPlotToggles(meta);
    updateGuideLabels(data);

    const pts = data.readings || [];
    const fdd = data.fdd_open || {};
    const countFull = data.count != null ? data.count : pts.length;
    let statusExtra = pts.length + " chart pts";
    if (data.chart_truncated && countFull > pts.length) {
      statusExtra =
        pts.length + " of " + countFull + " pts (stride " + (data.chart_stride || "?") + ")";
      logMsg(
        "Chart downsampled server-side: " + statusExtra + " · totals use full " + countFull,
        "log-ok"
      );
    }
    logMsg(statusExtra + " · FDD " + (fdd.fdd_status || "PENDING"));
    (data.debug?.fdd_eval_log || []).slice(-2).forEach((l) => logMsg("FDD: " + l));
    const skipChartRedraw =
      !opts.forceChart &&
      preserveUserZoom &&
      pauseRefreshWhenZoomed &&
      !opts.resetZoom;
    let stride = 1;
    if (pts.length && !skipChartRedraw) {
      stride = drawChart(data, { resetZoom: !!opts.resetZoom });
    } else if (pts.length && skipChartRedraw) {
      stride = lastChartData?.readings?.length
        ? Math.max(1, Math.ceil(lastChartData.readings.length / CHART_MAX_PTS))
        : 1;
    }
    document.getElementById("status").textContent =
      (data.chart_truncated ? pts.length + "/" + countFull : pts.length) +
      " pts · " +
      historyLabel(hours) +
      (stride > 1 ? " · chart 1/" + stride : "");
    if (pts.length) {
      const last = pts[pts.length - 1];
      document.getElementById("latestC").textContent = last.degC.toFixed(2);
      document.getElementById("latestF").textContent = last.degF.toFixed(2);
      const primary = document.getElementById(
        normalizeDisplayUnit(data.display_temp_unit) === "metric" ? "latestC" : "latestF"
      );
      if (primary) primary.classList.add("val-primary");
      const other = document.getElementById(
        normalizeDisplayUnit(data.display_temp_unit) === "metric" ? "latestF" : "latestC"
      );
      if (other) other.classList.remove("val-primary");
      setLatestTs(last);
    }
    if (showLoading) {
      refreshInFlight = Math.max(0, refreshInFlight - 1);
      if (refreshInFlight === 0) setRefreshLoading(false);
    }
  }

  /** Called from Rule Lab when enabled / plot checkboxes change */
  window.vibe12DashboardSyncRules = function (metaList, chartGuides) {
    syncPlotStateFromMeta(metaList);
    renderPlotToggles(metaList);
    if (lastChartData) {
      lastChartData.rules_meta = metaList;
      if (chartGuides) lastChartData.chart_guides = chartGuides;
      updateGuideLabels(lastChartData);
      renderFaultAnalytics(lastChartData);
      drawChart(lastChartData, { resetZoom: false });
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
        if (btn.dataset.tab === "dashboard") refresh({ resetZoom: false });
      });
    });
  }

  async function loadBuildings() {
    const siteSel = document.getElementById("siteSelect");
    const bldSel = document.getElementById("buildingSelect");
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
        if (s === selectedSiteId) o.selected = true;
        siteSel.appendChild(o);
      });
      if (!selectedSiteId && sites.length) {
        selectedSiteId = sites[0];
        siteSel.value = selectedSiteId;
      }
      function fillBuildings() {
        bldSel.innerHTML = "";
        buildings
          .filter((b) => b.site_id === selectedSiteId)
          .forEach((b) => {
            const o = document.createElement("option");
            o.value = b.building_id;
            o.textContent = b.building_id;
            if (b.building_id === selectedBuildingId) o.selected = true;
            bldSel.appendChild(o);
          });
        if (!selectedBuildingId && bldSel.options.length) {
          selectedBuildingId = bldSel.options[0].value;
        }
      }
      fillBuildings();
      siteSel.addEventListener("change", () => {
        selectedSiteId = siteSel.value;
        selectedBuildingId = "";
        localStorage.setItem("vibe12_site_id", selectedSiteId);
        fillBuildings();
        loadBuildingPoints();
      });
      bldSel.addEventListener("change", () => {
        selectedBuildingId = bldSel.value;
        localStorage.setItem("vibe12_building_id", selectedBuildingId);
        loadBuildingPoints();
      });
      await loadBuildingPoints();
    } catch (e) {
      logMsg("buildings load: " + e, "log-err");
    }
  }

  function renderPointPicker() {
    const host = document.getElementById("pointPickerGrid");
    if (!host) return;
    host.innerHTML = "";
    if (!buildingPoints.length) {
      host.innerHTML = '<span class="chart-empty-hint">No BACnet points registered yet</span>';
      return;
    }
    buildingPoints.forEach((p) => {
      const lab = document.createElement("label");
      lab.className = "plot-toggle-item point-pick-item";
      const chk = document.createElement("input");
      chk.type = "checkbox";
      chk.checked = selectedSeriesIds.has(p.series_id);
      chk.addEventListener("change", () => {
        if (chk.checked) selectedSeriesIds.add(p.series_id);
        else selectedSeriesIds.delete(p.series_id);
        localStorage.setItem(
          "vibe12_selected_series",
          JSON.stringify([...selectedSeriesIds])
        );
      });
      const label = p.brick_tag || p.object_name || p.point_id || p.series_id;
      lab.append(chk, document.createTextNode(" " + label));
      if (p.brick_class) {
        const meta = document.createElement("span");
        meta.className = "guide-meta";
        meta.textContent = " · " + p.brick_class;
        lab.appendChild(meta);
      }
      host.appendChild(lab);
    });
  }

  async function loadBuildingPoints() {
    if (!selectedSiteId || !selectedBuildingId) return;
    try {
      const res = await fetch(
        "/api/points/" +
          encodeURIComponent(selectedSiteId) +
          "/" +
          encodeURIComponent(selectedBuildingId)
      );
      const data = await res.json();
      buildingPoints = data.points || [];
      renderPointPicker();
    } catch (e) {
      logMsg("points load: " + e, "log-err");
    }
  }

  async function loadMultiSeriesChart() {
    const ids = [...selectedSeriesIds];
    if (!ids.length && buildingPoints.length) {
      buildingPoints.slice(0, 6).forEach((p) => selectedSeriesIds.add(p.series_id));
      localStorage.setItem(
        "vibe12_selected_series",
        JSON.stringify([...selectedSeriesIds])
      );
      renderPointPicker();
    }
    const useIds = [...selectedSeriesIds];
    if (!useIds.length) {
      logMsg("select points for multi-series chart", "log-err");
      return;
    }
    const url =
      "/api/series?series_ids=" +
      encodeURIComponent(useIds.join(",")) +
      "&hours=" +
      hours;
    logMsg("GET " + url);
    try {
      const res = await fetch(url);
      multiSeriesData = await res.json();
      if (lastChartData) drawChart(lastChartData, { resetZoom: false });
      logMsg("loaded " + useIds.length + " BACnet series", "log-ok");
    } catch (e) {
      logMsg("multi-series: " + e, "log-err");
    }
  }

  function bindMultiSeries() {
    const chk = document.getElementById("showMultiSeries");
    const btn = document.getElementById("loadMultiSeries");
    const filt = document.getElementById("brickClassFilter");
    if (chk) {
      chk.checked = showMultiSeries;
      chk.addEventListener("change", () => {
        showMultiSeries = chk.checked;
        localStorage.setItem("vibe12_show_multi_series", showMultiSeries ? "1" : "0");
        if (lastChartData) drawChart(lastChartData, { resetZoom: false });
      });
    }
    if (btn) {
      btn.addEventListener("click", () => {
        if (filt && filt.value) {
          buildingPoints
            .filter((p) => p.brick_class === filt.value)
            .forEach((p) => selectedSeriesIds.add(p.series_id));
          localStorage.setItem(
            "vibe12_selected_series",
            JSON.stringify([...selectedSeriesIds])
          );
          renderPointPicker();
        }
        loadMultiSeriesChart();
      });
    }
  }

  function bindToolbar() {
    const rs = document.getElementById("refreshSelect");
    rs.innerHTML =
      '<option value="10000">10 s</option><option value="60000" selected>1 min</option><option value="300000">5 min</option>';
    const hs = document.getElementById("hoursSelect");
    [1, 3, 6, 12, 24, 72, 168].forEach((h) => {
      const o = document.createElement("option");
      o.value = h;
      o.textContent = historyLabel(h);
      if (h === 24) o.selected = true;
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
      refreshTimer = setInterval(() => {
        refresh({ silent: true, resetZoom: false });
      }, refreshMs);
      refresh({ resetZoom: false });
    });
    hs.addEventListener("change", () => {
      hours = parseInt(hs.value, 10);
      localStorage.setItem("vibe12_hours", String(hours));
      preserveUserZoom = false;
      refresh({ resetZoom: true });
    });
    const tu = document.getElementById("displayTempUnit");
    if (tu) {
      tu.value = displayTempUnit;
      tu.addEventListener("change", () => {
        displayTempUnit = normalizeDisplayUnit(tu.value);
        localStorage.setItem(TEMP_UNIT_STORAGE_KEY, displayTempUnit);
        preserveUserZoom = false;
        refresh({ resetZoom: true });
      });
    }
    document.getElementById("refreshNow").addEventListener("click", () => {
      refresh({ forceChart: true, resetZoom: false });
    });
    refreshTimer = setInterval(() => {
      refresh({ silent: true, resetZoom: false });
    }, refreshMs);
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

  window.vibe12GetRollingAvgMinutes = function () {
    return rollingAvgMinutes;
  };
  window.vibe12SetRollingAvgMinutes = setRollingAvgMinutes;

  function bindGuideToggles() {
    const b = document.getElementById("showBoundsGuides");
    const r = document.getElementById("showRollingAvg");
    const rm = document.getElementById("rollingAvgMinutes");
    if (b) {
      b.checked = showBoundsGuides;
      b.addEventListener("change", () => {
        showBoundsGuides = b.checked;
        localStorage.setItem("vibe12_show_bounds_guides", showBoundsGuides ? "1" : "0");
        if (lastChartData) drawChart(lastChartData, { resetZoom: false });
      });
    }
    if (r) {
      r.checked = showRollingAvg;
      r.addEventListener("change", () => {
        showRollingAvg = r.checked;
        localStorage.setItem("vibe12_show_rolling_avg", showRollingAvg ? "1" : "0");
        if (lastChartData) drawChart(lastChartData, { resetZoom: false });
      });
    }
    setRollingAvgMinutes(rollingAvgMinutes, false);
    if (rm) {
      rm.addEventListener("change", () => {
        setRollingAvgMinutes(rm.value);
        preserveUserZoom = false;
        refresh({ resetZoom: true });
      });
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    bindTabs();
    bindToolbar();
    bindGuideToggles();
    bindMultiSeries();
    loadBuildings();
    pingHealth();
    refresh();
  });
})();
