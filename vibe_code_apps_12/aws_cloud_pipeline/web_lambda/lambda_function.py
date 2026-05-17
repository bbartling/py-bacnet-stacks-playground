"""
Lambda Function URL: HTML dashboard (Plotly) + /api/readings JSON from DynamoDB.
Plotly: °F trace + four hard-coded open-fdd fault subplots (server-aligned series).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
DEVICE_ID = os.environ.get("DEVICE_ID", "bosspi-ds18b20")
READINGS_LIMIT = int(os.environ.get("READINGS_LIMIT", "500"))
DEFAULT_HOURS = int(os.environ.get("DEFAULT_HOURS", "24"))
ROLLING_WINDOW = 6

_table = boto3.resource("dynamodb").Table(TABLE_NAME)

# Hard-coded fault subplots (matches fdd_lambda/rules/*.yaml)
FAULT_PANELS = [
    {
        "key": "temp_out_of_bounds_flag",
        "title": "Out of bounds (65–80 °F)",
        "color": "#f85149",
    },
    {
        "key": "temp_flatline_flag",
        "title": "Flatline (stuck sensor)",
        "color": "#d29922",
    },
    {
        "key": "temp_rate_per_hour_flag",
        "title": "Rate > 15 °F/hr",
        "color": "#a371f7",
    },
    {
        "key": "temp_rate_per_minute_flag",
        "title": "Rate > 2 °F/min",
        "color": "#ff7b72",
    },
]


def _json_safe(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    return obj


def _get_hours(event) -> int:
    try:
        q = event.get("queryStringParameters") or {}
        return max(1, min(168, int(q.get("hours", DEFAULT_HOURS))))
    except (TypeError, ValueError):
        return DEFAULT_HOURS


def _normalize_reading(item: dict) -> dict | None:
    """Telemetry row only (skip FDD status row ts_ms=0)."""
    ts_ms = item.get("ts_ms")
    if ts_ms is None or int(ts_ms) <= 0:
        return None
    if "degF" not in item or "degC" not in item:
        return None
    ts_ms = int(ts_ms)
    deg_f = float(item["degF"])
    deg_c = float(item["degC"])
    ts_iso = item.get("ts_iso")
    if not ts_iso:
        ts_iso = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).isoformat()
    return {
        "ts_ms": ts_ms,
        "ts_iso": str(ts_iso),
        "degF": deg_f,
        "degC": deg_c,
        "seq": item.get("seq"),
        "source": item.get("source"),
    }


def _fetch_readings(hours: int) -> list[dict]:
    cutoff_ms = int((time.time() - hours * 3600) * 1000)
    resp = _table.query(
        KeyConditionExpression=Key("device_id").eq(DEVICE_ID) & Key("ts_ms").gte(cutoff_ms),
        ScanIndexForward=True,
        Limit=READINGS_LIMIT,
    )
    rows: list[dict] = []
    for it in resp.get("Items", []):
        row = _normalize_reading(_json_safe(it))
        if row:
            rows.append(row)
    return rows


def _rolling_window_flags(raw: list[int], window: int = ROLLING_WINDOW) -> list[int]:
    """Match open-fdd rolling_window: flag only after N consecutive raw hits."""
    out: list[int] = []
    run = 0
    for i, hit in enumerate(raw):
        run += 1 if hit else 0
        if i >= window:
            run -= raw[i - window]
        out.append(1 if run >= window else 0)
    return out


def _preview_bounds(readings: list[dict]) -> list[int]:
    raw = [1 if r["degF"] < 65 or r["degF"] > 80 else 0 for r in readings]
    return _rolling_window_flags(raw)


def _align_flag_series(readings: list[dict], fdd_open: dict) -> dict[str, list[int]]:
    """Map open-fdd flag_series onto the same ts_ms list as dashboard readings."""
    ts_index = {int(t): i for i, t in enumerate(fdd_open.get("ts_ms") or [])}
    series = fdd_open.get("flag_series") or {}
    aligned: dict[str, list[int]] = {}
    for panel in FAULT_PANELS:
        key = panel["key"]
        vals = series.get(key)
        row: list[int] = []
        for r in readings:
            idx = ts_index.get(int(r["ts_ms"]))
            if vals is not None and idx is not None and idx < len(vals):
                row.append(1 if vals[idx] else 0)
            else:
                row.append(0)
        aligned[key] = row
    return aligned


def _build_fault_plots(readings: list[dict], fdd_open: dict) -> dict[str, list[int]]:
    aligned = _align_flag_series(readings, fdd_open)
    has_fdd = bool(fdd_open.get("flag_series"))
    if not has_fdd and readings:
        aligned["temp_out_of_bounds_flag"] = _preview_bounds(readings)
    return aligned


def _fetch_open_fdd_status() -> dict:
    """Latest summary from scheduled open-fdd Lambda (ts_ms=0 row)."""
    resp = _table.get_item(Key={"device_id": DEVICE_ID, "ts_ms": 0})
    item = _json_safe(resp.get("Item") or {})
    raw = item.get("summary_json")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    flags = [f for f in (item.get("active_flags") or "").split(",") if f]
    return {
        "fdd_status": item.get("fdd_status", "PENDING"),
        "active_flags": flags,
        "sample_count": item.get("sample_count", 0),
        "updated_at": item.get("updated_at"),
    }


def _readings_payload(hours: int) -> dict:
    readings = _fetch_readings(hours)
    fdd_open = _fetch_open_fdd_status()
    latest = readings[-1] if readings else None
    flag_series = fdd_open.get("flag_series") or {}
    fault_plots = _build_fault_plots(readings, fdd_open)
    fault_totals = {k: sum(v) for k, v in fault_plots.items()}
    return {
        "device_id": DEVICE_ID,
        "hours": hours,
        "count": len(readings),
        "latest": latest,
        "readings": readings,
        "fdd_open": fdd_open,
        "fault_panels": FAULT_PANELS,
        "fault_plots": fault_plots,
        "fault_totals": fault_totals,
        "debug": {
            "readings_count": len(readings),
            "fdd_ts_count": len(fdd_open.get("ts_ms") or []),
            "fdd_flag_keys": list(flag_series.keys()),
            "fdd_status": fdd_open.get("fdd_status"),
            "fdd_evaluated_at": fdd_open.get("evaluated_at"),
            "fdd_flag_counts": fdd_open.get("flag_counts", {}),
            "fdd_eval_log": fdd_open.get("eval_log", []),
            "has_flag_series": bool(flag_series),
            "bounds_preview_only": bool(readings) and not bool(flag_series),
        },
    }


def _response(status: int, body, content_type: str = "application/json"):
    if content_type == "application/json":
        body_out = json.dumps(body)
    else:
        body_out = body
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": content_type,
            "Cache-Control": "no-store",
        },
        "body": body_out,
    }


def _html_page() -> str:
    return r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Vibe 12 — Pi temperature (AWS)</title>
  <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
  <style>
    * { box-sizing: border-box; }
    body { font-family: system-ui, sans-serif; margin: 0; padding: 1rem; background: #0f1419; color: #e6edf3; }
    .wrap { max-width: 1200px; margin: 0 auto; }
    h1 { font-size: 1.5rem; text-align: center; margin: 0 0 0.25rem; }
    .sub { text-align: center; opacity: 0.7; margin-bottom: 0.75rem; font-size: 0.9rem; }
    .cards { display: flex; gap: 0.75rem; flex-wrap: wrap; justify-content: center; margin-bottom: 0.75rem; }
    .card { background: #1c2128; border: 1px solid #30363d; border-radius: 10px; padding: 0.6rem 1rem; text-align: center; min-width: 110px; }
    .lbl { font-size: 0.72rem; opacity: 0.75; text-transform: uppercase; }
    .val { font-size: 1.6rem; font-weight: 700; }
    .fdd-row { text-align: center; margin-bottom: 0.5rem; }
    .fdd-badge { display: inline-block; padding: 0.35rem 0.9rem; border-radius: 999px; font-weight: 700; font-size: 0.9rem; }
    .fdd-NORMAL { background: #238636; color: #fff; }
    .fdd-MISSING_DATA, .fdd-TEMP_OUT_OF_BOUNDS, .fdd-TEMP_RATE_PER_HOUR,
    .fdd-TEMP_RATE_PER_MINUTE, .fdd-PENDING { background: #da3633; color: #fff; }
    .fdd-TEMP_FLATLINE { background: #9e6a03; color: #fff; }
    .chart-stack { width: 100%; margin-top: 0.5rem; }
    .plot-box { background: #1c2128; border: 1px solid #30363d; border-radius: 8px; margin-bottom: 6px; overflow: hidden; }
    .plot-box.temp { margin-bottom: 10px; }
    .plot-title { font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.04em; opacity: 0.8; padding: 6px 10px 0; text-align: left; }
    .plot { width: 100%; }
    .meta { text-align: center; font-size: 0.8rem; opacity: 0.65; margin-top: 0.25rem; }
    .log-panel { margin-top: 0.5rem; background: #161b22; border: 1px solid #30363d; border-radius: 8px;
      padding: 0.4rem 0.6rem; max-height: 120px; overflow-y: auto; font-family: monospace; font-size: 0.7rem; }
    .log-err { color: #f85149; } .log-warn { color: #d29922; } .log-ok { color: #8b949e; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>DS18B20 temperature</h1>
    <p class="sub">Separate charts — temp °F and 4 fault strips (never shared y-axis)</p>
    <div class="cards">
      <div class="card"><div class="lbl">°C</div><div id="latestC" class="val">—</div></div>
      <div class="card"><div class="lbl">°F</div><div id="latestF" class="val">—</div></div>
      <div class="card"><div class="lbl">Last</div><div id="latestTs" class="val" style="font-size:0.85rem">—</div></div>
    </div>
    <div class="fdd-row"><span id="fddBadge" class="fdd-badge fdd-NORMAL">open-fdd: —</span></div>
    <div class="chart-stack">
      <div class="plot-box temp">
        <div class="plot-title">Temperature °F</div>
        <div id="plotTemp" class="plot"></div>
      </div>
      <div class="plot-box">
        <div class="plot-title">Out of bounds (65–80 °F)</div>
        <div id="plotBounds" class="plot"></div>
      </div>
      <div class="plot-box">
        <div class="plot-title">Flatline (stuck sensor)</div>
        <div id="plotFlatline" class="plot"></div>
      </div>
      <div class="plot-box">
        <div class="plot-title">Rate &gt; 15 °F/hr</div>
        <div id="plotRateH" class="plot"></div>
      </div>
      <div class="plot-box">
        <div class="plot-title">Rate &gt; 2 °F/min</div>
        <div id="plotRateM" class="plot"></div>
      </div>
    </div>
    <p class="meta" id="status">Loading…</p>
    <div id="logPanel" class="log-panel"></div>
  </div>
  <script>
    const HOURS = 6, REFRESH_MS = 15000;
    const PLOT_CFG = { responsive: true, displayModeBar: false };
    const FAULT_SLOTS = [
      { id: 'plotBounds', key: 'temp_out_of_bounds_flag' },
      { id: 'plotFlatline', key: 'temp_flatline_flag' },
      { id: 'plotRateH', key: 'temp_rate_per_hour_flag' },
      { id: 'plotRateM', key: 'temp_rate_per_minute_flag' }
    ];
    const BASE = {
      paper_bgcolor: '#0f1419', plot_bgcolor: '#1c2128',
      font: { color: '#e6edf3', size: 10 },
      margin: { t: 4, r: 12, b: 28, l: 44 }
    };

    function faultClass(s) { return 'fdd-badge fdd-' + (s || 'NORMAL'); }
    function logMsg(t, c) {
      const el = document.getElementById('logPanel'), d = document.createElement('div');
      d.className = c || 'log-ok';
      d.textContent = new Date().toISOString().slice(11, 19) + '  ' + t;
      el.appendChild(d);
      while (el.childNodes.length > 80) el.removeChild(el.firstChild);
      el.scrollTop = el.scrollHeight;
    }

    function xLabels(pts) {
      return pts.map(p => (p.ts_iso || '').replace('T', ' ').slice(0, 19));
    }

    function plotTemp(x, yF) {
      const yMin = Math.min(...yF), yMax = Math.max(...yF);
      const pad = Math.max(3, (yMax - yMin) * 0.12);
      Plotly.react('plotTemp', [{
        x, y: yF, type: 'scatter', mode: 'lines',
        line: { color: '#58a6ff', width: 2 }
      }], Object.assign({}, BASE, {
        height: 300,
        margin: { t: 8, r: 12, b: 24, l: 48 },
        xaxis: { showticklabels: false, gridcolor: '#30363d' },
        yaxis: { title: '°F', gridcolor: '#30363d', range: [yMin - pad, yMax + pad] },
        shapes: [
          { type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 65, y1: 65,
            line: { color: '#3fb950', dash: 'dash', width: 1 } },
          { type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: 80, y1: 80,
            line: { color: '#3fb950', dash: 'dash', width: 1 } }
        ]
      }), PLOT_CFG);
    }

    function plotFault(elId, x, yVals, color, showX) {
      Plotly.react(elId, [{
        x, y: yVals, type: 'scatter', mode: 'lines',
        line: { color, width: 1.2, shape: 'hv' },
        fill: 'tozeroy', fillcolor: color + '44'
      }], Object.assign({}, BASE, {
        height: 78,
        xaxis: {
          showticklabels: !!showX, title: showX ? 'Time (UTC)' : '',
          gridcolor: '#30363d', tickangle: -20
        },
        yaxis: {
          tickvals: [0, 1], ticktext: ['OK', 'FLT'],
          range: [0, 1], fixedrange: true, gridcolor: '#30363d'
        }
      }), PLOT_CFG);
    }

    function drawCharts(data) {
      const pts = data.readings || [];
      const panels = data.fault_panels || [];
      const plots = data.fault_plots || {};
      const totals = data.fault_totals || {};
      if (!pts.length) return;
      const x = xLabels(pts);
      const yF = pts.map(p => p.degF);
      plotTemp(x, yF);
      FAULT_SLOTS.forEach((slot, i) => {
        const panel = panels.find(p => p.key === slot.key) || {};
        const yVals = plots[slot.key] || pts.map(() => 0);
        const n = totals[slot.key] || 0;
        const box = document.getElementById(slot.id).closest('.plot-box');
        const titleEl = box && box.querySelector('.plot-title');
        if (titleEl && panel.title) {
          titleEl.textContent = panel.title + (n ? ' · ' + n + ' flt' : '');
        }
        plotFault(slot.id, x, yVals, panel.color || '#f85149', i === FAULT_SLOTS.length - 1);
      });
    }

    async function refresh() {
      logMsg('GET /api/readings?hours=' + HOURS);
      let data;
      try {
        data = await (await fetch('/api/readings?hours=' + HOURS)).json();
      } catch (e) {
        logMsg('fetch error: ' + e, 'log-err');
        return;
      }
      const pts = data.readings || [], fdd = data.fdd_open || {}, dbg = data.debug || {};
      logMsg(pts.length + ' readings · open-fdd ' + (fdd.fdd_status || 'PENDING'));
      if ((fdd.fdd_status || 'PENDING') === 'PENDING') {
        logMsg('Run FddFunction once: Lambda console → Test', 'log-warn');
      }
      if (dbg.bounds_preview_only) {
        logMsg('bounds = server preview (rolling 6); other faults need FDD', 'log-warn');
      }
      if (dbg.has_flag_series) {
        logMsg('FDD flag_series OK · ' + JSON.stringify(data.fault_totals || {}));
      }
      (dbg.fdd_eval_log || []).slice(-4).forEach(l => logMsg('open-fdd: ' + l));
      document.getElementById('status').textContent = pts.length + ' pts · ' + HOURS + ' h';
      const b = document.getElementById('fddBadge');
      b.textContent = 'open-fdd: ' + (fdd.fdd_status || 'PENDING');
      b.className = faultClass(fdd.fdd_status);
      if (pts.length) {
        const last = pts[pts.length - 1];
        document.getElementById('latestC').textContent = last.degC.toFixed(2);
        document.getElementById('latestF').textContent = last.degF.toFixed(2);
        document.getElementById('latestTs').textContent = (last.ts_iso || '').replace('T', ' ').slice(0, 19);
        drawCharts(data);
      }
    }
    refresh();
    setInterval(refresh, REFRESH_MS);
  </script>
</body>
</html>"""



def lambda_handler(event, context):
    path = event.get("rawPath") or event.get("path") or "/"
    if path.startswith("/api/readings"):
        hours = _get_hours(event)
        return _response(200, _readings_payload(hours))
    return _response(200, _html_page(), "text/html; charset=utf-8")
