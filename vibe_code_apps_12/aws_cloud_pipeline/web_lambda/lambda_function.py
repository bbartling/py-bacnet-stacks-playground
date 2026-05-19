"""
Lambda Function URL: HTML dashboard (Plotly) + /api/readings JSON from DynamoDB.
Fault lanes computed with fdd_rules.py (tunable via form / saved DynamoDB config).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
import boto3
from boto3.dynamodb.conditions import Key

from fdd_rules import DEFAULT_CONFIG, RuleConfig, config_from_dict, config_to_dict, evaluate_all

TABLE_NAME = os.environ.get("TABLE_NAME", "vibe12-telemetry")
DEVICE_ID = os.environ.get("DEVICE_ID", "bosspi-ds18b20")
READINGS_LIMIT = int(os.environ.get("READINGS_LIMIT", "62000"))
DEFAULT_HOURS = int(os.environ.get("DEFAULT_HOURS", "168"))
FDD_CONFIG_TS = -1

_table = boto3.resource("dynamodb").Table(TABLE_NAME)


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


def _parse_query_config(event) -> dict[str, Any]:
    q = event.get("queryStringParameters") or {}
    out: dict[str, Any] = {}
    float_keys = (
        "bounds_low_f",
        "bounds_high_f",
        "flatline_tolerance_f",
        "max_f_per_hour",
        "max_f_per_minute",
    )
    int_keys = ("flatline_window", "rolling_window")
    for key in float_keys:
        if key in q and q[key] not in (None, ""):
            out[key] = float(q[key])
    for key in int_keys:
        if key in q and q[key] not in (None, ""):
            out[key] = int(q[key])
    return out


def _load_saved_config() -> RuleConfig:
    try:
        resp = _table.get_item(Key={"device_id": DEVICE_ID, "ts_ms": FDD_CONFIG_TS})
        item = _json_safe(resp.get("Item") or {})
        raw = item.get("config_json")
        if raw:
            data = json.loads(raw) if isinstance(raw, str) else raw
            return config_from_dict(data)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return DEFAULT_CONFIG


def _save_config(cfg: RuleConfig) -> None:
    data = config_to_dict(cfg)
    _table.put_item(
        Item={
            "device_id": DEVICE_ID,
            "ts_ms": FDD_CONFIG_TS,
            "record_type": "fdd_config",
            "config_json": json.dumps(data),
            "updated_at": int(time.time()),
            "expires_at": int(time.time()) + 30 * 86400,
        }
    )


def _effective_config(event) -> tuple[RuleConfig, dict, dict]:
    saved = _load_saved_config()
    overrides = _parse_query_config(event)
    merged = {**config_to_dict(saved), **overrides}
    cfg = config_from_dict(merged)
    return cfg, config_to_dict(saved), overrides


def _normalize_reading(item: dict) -> dict | None:
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
    rows: list[dict] = []
    eks = None
    while len(rows) < READINGS_LIMIT:
        kwargs: dict = {
            "KeyConditionExpression": Key("device_id").eq(DEVICE_ID)
            & Key("ts_ms").gte(cutoff_ms),
            "ScanIndexForward": False,
            "Limit": min(1000, READINGS_LIMIT - len(rows)),
        }
        if eks:
            kwargs["ExclusiveStartKey"] = eks
        resp = _table.query(**kwargs)
        for it in resp.get("Items", []):
            row = _normalize_reading(_json_safe(it))
            if row:
                rows.append(row)
        eks = resp.get("LastEvaluatedKey")
        if not eks:
            break
    rows.reverse()
    return rows


def _build_fault_plots(readings: list[dict], cfg: RuleConfig) -> dict[str, list[int]]:
    if not readings:
        return {k: [] for k in cfg.flag_labels()}
    series = evaluate_all(readings, cfg)
    return {k: series.get(k, [0] * len(readings)) for k in cfg.flag_labels()}


def _fetch_fdd_status() -> dict:
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


def _readings_payload(hours: int, event) -> dict:
    cfg, saved_dict, overrides = _effective_config(event)
    readings = _fetch_readings(hours)
    fdd_status = _fetch_fdd_status()
    latest = readings[-1] if readings else None
    fault_plots = _build_fault_plots(readings, cfg)
    fault_totals = {k: sum(v) for k, v in fault_plots.items()}
    return {
        "device_id": DEVICE_ID,
        "hours": hours,
        "count": len(readings),
        "latest": latest,
        "readings": readings,
        "fdd_open": fdd_status,
        "fault_panels": cfg.fault_panels(),
        "fault_plots": fault_plots,
        "fault_totals": fault_totals,
        "rule_config": config_to_dict(cfg),
        "rule_config_saved": saved_dict,
        "rule_config_overrides": overrides,
        "debug": {
            "readings_count": len(readings),
            "fdd_status": fdd_status.get("fdd_status"),
            "fdd_evaluated_at": fdd_status.get("evaluated_at"),
            "fdd_eval_log": fdd_status.get("eval_log", []),
            "preview_from_form": bool(overrides),
        },
    }


def _parse_body(event) -> dict:
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        import base64

        body = base64.b64decode(body).decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {}


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
    .toolbar, .rule-form {
      display: flex; flex-wrap: wrap; gap: 0.75rem 1rem; justify-content: center;
      align-items: flex-end; margin: 0.5rem 0 0.75rem; font-size: 0.85rem;
    }
    .toolbar label, .rule-form label {
      display: flex; flex-direction: column; gap: 0.2rem; opacity: 0.85; font-size: 0.75rem;
    }
    .toolbar select, .rule-form input {
      background: #1c2128; color: #e6edf3; border: 1px solid #30363d;
      border-radius: 6px; padding: 0.35rem 0.45rem; font-size: 0.85rem; width: 5.5rem;
    }
    .rule-panel {
      background: #161b22; border: 1px solid #30363d; border-radius: 8px;
      padding: 0.6rem 0.75rem; margin-bottom: 0.5rem;
    }
    .rule-panel summary { cursor: pointer; font-weight: 600; font-size: 0.9rem; }
    .btn-row { display: flex; gap: 0.5rem; flex-wrap: wrap; justify-content: center; width: 100%; margin-top: 0.35rem; }
    .btn { border: none; border-radius: 6px; padding: 0.35rem 0.75rem; cursor: pointer; font-size: 0.85rem; }
    .btn-primary { background: #238636; color: #fff; }
    .btn-secondary { background: #30363d; color: #e6edf3; }
    .fdd-row { text-align: center; margin-bottom: 0.5rem; }
    .fdd-badge { display: inline-block; padding: 0.35rem 0.9rem; border-radius: 999px; font-weight: 700; font-size: 0.9rem; }
    .fdd-NORMAL { background: #238636; color: #fff; }
    .fdd-MISSING_DATA, .fdd-TEMP_OUT_OF_BOUNDS, .fdd-TEMP_RATE_PER_HOUR,
    .fdd-TEMP_RATE_PER_MINUTE, .fdd-PENDING { background: #da3633; color: #fff; }
    .fdd-TEMP_FLATLINE { background: #9e6a03; color: #fff; }
    #chart { width: 100%; height: 460px; background: #1c2128; border: 1px solid #30363d; border-radius: 8px; margin-top: 0.5rem; }
    .meta { text-align: center; font-size: 0.8rem; opacity: 0.65; margin-top: 0.25rem; }
    .log-panel { margin-top: 0.5rem; background: #161b22; border: 1px solid #30363d; border-radius: 8px;
      padding: 0.4rem 0.6rem; max-height: 120px; overflow-y: auto; font-family: monospace; font-size: 0.7rem; }
    .log-err { color: #f85149; } .log-warn { color: #d29922; } .log-ok { color: #8b949e; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>DS18B20 temperature</h1>
    <p class="sub">°F (left) · faults on right (False/True) · tune rules below · default 7 d history</p>
    <div class="cards">
      <div class="card"><div class="lbl">°C</div><div id="latestC" class="val">—</div></div>
      <div class="card"><div class="lbl">°F</div><div id="latestF" class="val">—</div></div>
      <div class="card"><div class="lbl">Last</div><div id="latestTs" class="val" style="font-size:0.85rem">—</div></div>
    </div>
    <div class="fdd-row"><span id="fddBadge" class="fdd-badge fdd-NORMAL">FDD: —</span></div>
    <details class="rule-panel" open>
      <summary>Fault rule tuning (chart preview + save for scheduled FDD)</summary>
      <form id="ruleForm" class="rule-form" onsubmit="return false;">
        <label>Low °F <input type="number" step="0.1" name="bounds_low_f" id="bounds_low_f" /></label>
        <label>High °F <input type="number" step="0.1" name="bounds_high_f" id="bounds_high_f" /></label>
        <label>Flatline tol <input type="number" step="0.01" name="flatline_tolerance_f" id="flatline_tolerance_f" /></label>
        <label>Flatline win <input type="number" step="1" name="flatline_window" id="flatline_window" /></label>
        <label>Max °F/hr <input type="number" step="0.1" name="max_f_per_hour" id="max_f_per_hour" /></label>
        <label>Max °F/min <input type="number" step="0.1" name="max_f_per_minute" id="max_f_per_minute" /></label>
        <label>Rolling win <input type="number" step="1" name="rolling_window" id="rolling_window" /></label>
        <div class="btn-row">
          <button type="button" class="btn btn-primary" id="applyRules">Apply preview</button>
          <button type="button" class="btn btn-secondary" id="saveRules">Save to cloud (FDD λ)</button>
          <button type="button" class="btn btn-secondary" id="resetRules">Reset defaults</button>
        </div>
      </form>
    </details>
    <div class="toolbar">
      <label>Refresh
        <select id="refreshSelect" aria-label="Auto refresh interval">
          <option value="10000">Every 10 s</option>
          <option value="15000">Every 15 s</option>
          <option value="30000">Every 30 s</option>
          <option value="60000" selected>Every 1 min</option>
          <option value="120000">Every 2 min</option>
          <option value="300000">Every 5 min</option>
        </select>
      </label>
      <label>History
        <select id="hoursSelect" aria-label="Hours of data">
          <option value="1">1 h</option>
          <option value="3">3 h</option>
          <option value="6">6 h</option>
          <option value="12">12 h</option>
          <option value="24">24 h</option>
          <option value="168" selected>7 d (TTL)</option>
        </select>
      </label>
      <button type="button" id="refreshNow" class="btn btn-primary">Refresh now</button>
    </div>
    <div id="chart"></div>
    <p class="meta" id="status">Loading…</p>
    <div id="logPanel" class="log-panel"></div>
  </div>
  <script>
    const LS_REFRESH = 'vibe12_refresh_ms';
    const LS_HOURS = 'vibe12_hours';
    const LS_RULES = 'vibe12_fdd_rules';
    const RULE_FIELDS = [
      'bounds_low_f', 'bounds_high_f', 'flatline_tolerance_f', 'flatline_window',
      'max_f_per_hour', 'max_f_per_minute', 'rolling_window'
    ];
    const DEFAULT_RULES = {
      bounds_low_f: 65, bounds_high_f: 80, flatline_tolerance_f: 0.05,
      flatline_window: 18, max_f_per_hour: 15, max_f_per_minute: 2, rolling_window: 6
    };
    let hours = 168;
    let refreshMs = 60000;
    let refreshTimer = null;
    const PLOT_CFG = { responsive: true, displayModeBar: true };
    const CHART_MAX_PTS = 4000;

    function readRulesFromForm() {
      const o = {};
      RULE_FIELDS.forEach(k => {
        const el = document.getElementById(k);
        if (!el || el.value === '') return;
        o[k] = (k.endsWith('_window') ? parseInt(el.value, 10) : parseFloat(el.value));
      });
      return o;
    }

    function writeRulesToForm(cfg) {
      RULE_FIELDS.forEach(k => {
        const el = document.getElementById(k);
        if (el && cfg[k] !== undefined) el.value = cfg[k];
      });
    }

    function rulesQueryString() {
      const o = readRulesFromForm();
      return RULE_FIELDS.filter(k => o[k] !== undefined)
        .map(k => encodeURIComponent(k) + '=' + encodeURIComponent(o[k])).join('&');
    }

    function startAutoRefresh() {
      if (refreshTimer) clearInterval(refreshTimer);
      refreshTimer = setInterval(refresh, refreshMs);
    }

    function applyToolbarFromStorage() {
      const rs = document.getElementById('refreshSelect');
      const hs = document.getElementById('hoursSelect');
      const savedR = localStorage.getItem(LS_REFRESH);
      const savedH = localStorage.getItem(LS_HOURS);
      if (savedR && rs) { rs.value = savedR; refreshMs = parseInt(savedR, 10); }
      if (savedH && hs) { hs.value = savedH; hours = parseInt(savedH, 10); }
      const savedRules = localStorage.getItem(LS_RULES);
      if (savedRules) {
        try { writeRulesToForm(JSON.parse(savedRules)); } catch (e) {}
      } else {
        writeRulesToForm(DEFAULT_RULES);
      }
    }

    function bindToolbar() {
      const rs = document.getElementById('refreshSelect');
      const hs = document.getElementById('hoursSelect');
      const btn = document.getElementById('refreshNow');
      rs.addEventListener('change', () => {
        refreshMs = parseInt(rs.value, 10);
        localStorage.setItem(LS_REFRESH, String(refreshMs));
        startAutoRefresh();
        refresh();
      });
      hs.addEventListener('change', () => {
        hours = parseInt(hs.value, 10);
        localStorage.setItem(LS_HOURS, String(hours));
        refresh();
      });
      btn.addEventListener('click', () => refresh());
      document.getElementById('applyRules').addEventListener('click', () => {
        localStorage.setItem(LS_RULES, JSON.stringify(readRulesFromForm()));
        refresh();
      });
      document.getElementById('resetRules').addEventListener('click', () => {
        writeRulesToForm(DEFAULT_RULES);
        localStorage.setItem(LS_RULES, JSON.stringify(DEFAULT_RULES));
        refresh();
      });
      document.getElementById('saveRules').addEventListener('click', async () => {
        const cfg = readRulesFromForm();
        localStorage.setItem(LS_RULES, JSON.stringify(cfg));
        try {
          const r = await fetch('/api/fdd-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cfg)
          });
          const j = await r.json();
          logMsg(j.ok ? 'saved FDD config to DynamoDB' : 'save failed', j.ok ? 'log-ok' : 'log-err');
        } catch (e) {
          logMsg('save error: ' + e, 'log-err');
        }
      });
    }

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

    function downsample(pts, plots) {
      if (pts.length <= CHART_MAX_PTS) return { pts, plots, stride: 1 };
      const stride = Math.ceil(pts.length / CHART_MAX_PTS);
      const idx = [];
      for (let i = 0; i < pts.length; i += stride) idx.push(i);
      if (idx[idx.length - 1] !== pts.length - 1) idx.push(pts.length - 1);
      const outPts = idx.map(i => pts[i]);
      const outPlots = {};
      Object.keys(plots || {}).forEach(k => {
        const s = plots[k] || [];
        outPlots[k] = idx.map(i => (s[i] || 0));
      });
      return { pts: outPts, plots: outPlots, stride };
    }

    function faultBoolY(flags) { return flags.map(v => (v ? 1 : 0)); }

    function drawChart(data) {
      let pts = data.readings || [];
      let plots = data.fault_plots || {};
      const panels = data.fault_panels || [];
      const cfg = data.rule_config || DEFAULT_RULES;
      const ds = downsample(pts, plots);
      pts = ds.pts;
      plots = ds.plots;
      if (!pts.length) {
        Plotly.react('chart', [], {
          height: 320, paper_bgcolor: '#0f1419', plot_bgcolor: '#1c2128',
          title: { text: 'Waiting for telemetry…', font: { color: '#e6edf3' } }
        }, PLOT_CFG);
        return ds.stride;
      }
      const x = xLabels(pts);
      const yF = pts.map(p => p.degF);
      const yMin = Math.min(...yF), yMax = Math.max(...yF);
      const pad = Math.max(3, (yMax - yMin) * 0.1);
      const lo = cfg.bounds_low_f ?? 65, hi = cfg.bounds_high_f ?? 80;

      const traces = [{
        x, y: yF, name: 'Temperature',
        type: 'scatter', mode: 'lines',
        line: { color: '#58a6ff', width: 2.5 },
        xaxis: 'x', yaxis: 'y', showlegend: false,
        hovertemplate: '%{y:.1f} °F<extra></extra>'
      }];

      panels.forEach((panel) => {
        const flags = plots[panel.key] || pts.map(() => 0);
        traces.push({
          x, y: faultBoolY(flags),
          name: panel.title,
          type: 'scatter', mode: 'lines',
          line: { color: panel.color, width: 2.5, shape: 'hv' },
          xaxis: 'x', yaxis: 'y2', showlegend: true, opacity: 0.92,
          hovertemplate: panel.title + ': %{customdata}<extra></extra>',
          customdata: flags.map(v => (v ? 'True' : 'False'))
        });
      });

      Plotly.react('chart', traces, {
        height: 460, autosize: true,
        paper_bgcolor: '#0f1419', plot_bgcolor: '#1c2128',
        font: { color: '#e6edf3', size: 11 },
        margin: { t: 36, r: 64, b: 44, l: 52 },
        hovermode: 'x unified',
        legend: { orientation: 'h', y: 1.12, x: 0, font: { size: 9 },
          title: { text: 'Fault type (color)', font: { size: 9 } } },
        xaxis: { title: 'Time (UTC)', gridcolor: '#30363d', tickangle: -15 },
        yaxis: { title: '°F', side: 'left', gridcolor: '#30363d',
          range: [yMin - pad, yMax + pad], zeroline: false },
        yaxis2: {
          title: '', side: 'right', overlaying: 'y', anchor: 'x',
          range: [0, 1], fixedrange: true, showgrid: false,
          tickmode: 'array', tickvals: [0, 1], ticktext: ['False', 'True']
        },
        shapes: [
          { type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: lo, y1: lo,
            line: { color: '#3fb950', dash: 'dash', width: 1 } },
          { type: 'line', xref: 'paper', x0: 0, x1: 1, yref: 'y', y0: hi, y1: hi,
            line: { color: '#3fb950', dash: 'dash', width: 1 } }
        ]
      }, PLOT_CFG);
      return ds.stride;
    }

    async function refresh() {
      const rq = rulesQueryString();
      const url = '/api/readings?hours=' + hours + (rq ? '&' + rq : '');
      logMsg('GET ' + url);
      let data;
      try {
        data = await (await fetch(url)).json();
      } catch (e) {
        logMsg('fetch error: ' + e, 'log-err');
        return;
      }
      if (data.rule_config) writeRulesToForm(data.rule_config);
      const pts = data.readings || [], fdd = data.fdd_open || {}, dbg = data.debug || {};
      logMsg(pts.length + ' readings · FDD ' + (fdd.fdd_status || 'PENDING'));
      if ((fdd.fdd_status || 'PENDING') === 'PENDING') {
        logMsg('Invoke FddFunction once in Lambda console', 'log-warn');
      }
      if (dbg.preview_from_form) logMsg('chart uses form rule overrides', 'log-warn');
      logMsg('fault totals ' + JSON.stringify(data.fault_totals || {}));
      (dbg.fdd_eval_log || []).slice(-3).forEach(l => logMsg('FDD: ' + l));
      const rs = document.getElementById('refreshSelect');
      const label = rs ? rs.options[rs.selectedIndex].text : '';
      const stride = pts.length ? drawChart(data) : 1;
      const chartNote = stride > 1 ? ' · chart every ' + stride + 'th pt' : '';
      document.getElementById('status').textContent =
        pts.length + ' pts · ' + hours + ' h window' + chartNote + ' · ' + label;
      const b = document.getElementById('fddBadge');
      b.textContent = 'FDD: ' + (fdd.fdd_status || 'PENDING');
      b.className = faultClass(fdd.fdd_status);
      if (pts.length) {
        const last = pts[pts.length - 1];
        document.getElementById('latestC').textContent = last.degC.toFixed(2);
        document.getElementById('latestF').textContent = last.degF.toFixed(2);
        document.getElementById('latestTs').textContent = (last.ts_iso || '').replace('T', ' ').slice(0, 19);
      }
    }
    applyToolbarFromStorage();
    bindToolbar();
    refresh();
    startAutoRefresh();
  </script>
</body>
</html>"""


def lambda_handler(event, context):
    path = event.get("rawPath") or event.get("path") or "/"
    method = (event.get("requestContext", {}).get("http", {}).get("method") or "GET").upper()

    if path.startswith("/api/fdd-config"):
        if method == "POST":
            body = _parse_body(event)
            cfg = config_from_dict({**config_to_dict(DEFAULT_CONFIG), **body})
            _save_config(cfg)
            return _response(200, {"ok": True, "rule_config": config_to_dict(cfg)})
        cfg = _load_saved_config()
        return _response(200, {"rule_config": config_to_dict(cfg), "defaults": config_to_dict(DEFAULT_CONFIG)})

    if path.startswith("/api/readings"):
        hours = _get_hours(event)
        return _response(200, _readings_payload(hours, event))
    return _response(200, _html_page(), "text/html; charset=utf-8")
