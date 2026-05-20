(function () {
  "use strict";

  let hours = 168;
  let refreshMs = 60000;
  let refreshTimer = null;
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

  /** UTC line + browser local TZ (from ts_ms epoch). */
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

  function downsample(pts, plots) {
    if (pts.length <= CHART_MAX_PTS) return { pts, plots, stride: 1 };
    const stride = Math.ceil(pts.length / CHART_MAX_PTS);
    const idx = [];
    for (let i = 0; i < pts.length; i += stride) idx.push(i);
    if (idx[idx.length - 1] !== pts.length - 1) idx.push(pts.length - 1);
    return {
      pts: idx.map((i) => pts[i]),
      plots: Object.fromEntries(
        Object.entries(plots || {}).map(([k, s]) => [k, idx.map((i) => s[i] || 0)])
      ),
      stride,
    };
  }

  function faultBoolY(flags) {
    return flags.map((v) => (v ? 1 : 0));
  }

  function drawChart(data) {
    let pts = data.readings || [];
    let plots = data.fault_plots || {};
    const panels = data.fault_panels || [];
    const ds = downsample(pts, plots);
    pts = ds.pts;
    plots = ds.plots;
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
    const aux = data.aux_series || {};
    const avg1m = aux.degF_1min_avg;
    const traces = [
      {
        x,
        y: yF,
        name: "Temperature (raw)",
        type: "scatter",
        mode: "lines",
        line: { color: "#58a6ff", width: 2.5 },
        yaxis: "y",
        showlegend: !!avg1m,
        hovertemplate: "%{y:.1f} °F raw<extra></extra>",
      },
    ];
    if (avg1m && avg1m.length === pts.length) {
      traces.push({
        x,
        y: avg1m,
        name: "1-min rolling avg",
        type: "scatter",
        mode: "lines",
        line: { color: "#a371f7", width: 1.5, dash: "dot" },
        yaxis: "y",
        showlegend: true,
        opacity: 0.85,
        hovertemplate: "%{y:.1f} °F avg<extra></extra>",
      });
    }
    panels.forEach((panel) => {
      const flags = plots[panel.key] || pts.map(() => 0);
      traces.push({
        x,
        y: faultBoolY(flags),
        name: panel.title,
        type: "scatter",
        mode: "lines",
        line: { color: panel.color, width: 2, shape: "hv" },
        yaxis: "y2",
        showlegend: true,
        opacity: 0.9,
      });
    });
    Plotly.react(
      "chart",
      traces,
      {
        height: 460,
        paper_bgcolor: "#0f1419",
        plot_bgcolor: "#1c2128",
        font: { color: "#e6edf3" },
        margin: { t: 36, r: 64, b: 44, l: 52 },
        hovermode: "x unified",
        legend: { orientation: "h", y: 1.1 },
        xaxis: { title: "Time (UTC)", gridcolor: "#30363d" },
        yaxis: {
          title: "°F",
          side: "left",
          range: [Math.min(...yF) - pad, Math.max(...yF) + pad],
        },
        yaxis2: {
          side: "right",
          overlaying: "y",
          range: [0, 1],
          tickvals: [0, 1],
          ticktext: ["False", "True"],
        },
      },
      PLOT_CFG
    );
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

  document.addEventListener("DOMContentLoaded", () => {
    bindTabs();
    bindToolbar();
    pingHealth();
    refresh();
  });
})();
