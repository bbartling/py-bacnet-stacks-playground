"""Generate economizer_diagnostics.html — dedicated AHU economizer FDD page."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from economizer_fdd_engine import (
    export_fault_timeseries,
    load_point_mapping,
    results_to_dataframe,
    run_diagnostics,
)
from sensor_qa_engine import metric_reference_table

ROOT = Path(__file__).resolve().parent
_APP19 = ROOT.parent
if str(_APP19) not in sys.path:
    sys.path.insert(0, str(_APP19))

from shared.data_config import get_config  # noqa: E402

_cfg = get_config()
DATA = _cfg.building_dir
WEATHER = _cfg.weather_dir
OUT = ROOT
SITE_LABEL = _cfg.site_label()

COLORS = {
    "bg": "#0f1419", "card": "#1a2332", "text": "#e8edf4", "muted": "#8b9cb3",
    "accent": "#3b82f6", "good": "#22c55e", "warn": "#f59e0b", "bad": "#ef4444",
    "chart": ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#06b6d4"],
}


def _load_ahu(name: str) -> pd.DataFrame:
    df = pd.read_csv(DATA / name / "history_wide.csv")
    df["timestamp"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df.sort_values("timestamp").reset_index(drop=True)


def _load_weather() -> pd.DataFrame:
    wx = pd.read_csv(WEATHER / "history_wide.csv")
    wx["timestamp"] = pd.to_datetime(wx["timestamp_utc"], utc=True)
    return wx


def fig_to_div(fig: go.Figure, height: int = 520) -> str:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=COLORS["card"],
        plot_bgcolor=COLORS["card"],
        font=dict(color=COLORS["text"], size=11),
        margin=dict(l=55, r=40, t=72, b=90),
        height=height,
        title=dict(x=0.02, xanchor="left"),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.22,
            x=0,
            xanchor="left",
            font=dict(size=10),
        ),
    )
    return fig.to_html(full_html=False, include_plotlyjs=False, config={"displayModeBar": True, "scrollZoom": True})


def downsample(d: pd.DataFrame, n: int = 900) -> pd.DataFrame:
    if len(d) <= n:
        return d
    return d.iloc[:: max(1, len(d) // n)].copy()


def chart_econ_trends(d: pd.DataFrame, ahu_id: str) -> str:
    sub = downsample(d)
    ts = sub["timestamp_local"]
    fault_cols = [c for c in sub.columns if c.startswith("fault_") and c != "fault_econ_sensor"]
    fault_any = sub[fault_cols].any(axis=1).astype(float) * 100 if fault_cols else pd.Series(0, index=sub.index)

    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, row_heights=[0.35, 0.2, 0.2, 0.25], vertical_spacing=0.04)
    for col, name, color in [
        ("oat_s", "OAT", COLORS["chart"][0]), ("rat_s", "RAT", COLORS["chart"][1]),
        ("mat_s", "MAT", COLORS["chart"][2]), ("sat_s", "SAT", COLORS["chart"][3]),
    ]:
        if col in sub.columns:
            fig.add_trace(go.Scatter(x=ts, y=sub[col], name=name, line=dict(width=1.2, color=color)), row=1, col=1)
    if "sat_sp" in sub.columns:
        fig.add_trace(go.Scatter(x=ts, y=sub["sat_sp"], name="SAT SP", line=dict(dash="dot", color=COLORS["muted"])), row=1, col=1)
    fig.add_trace(go.Scatter(x=ts, y=sub["oad_pos_s"] * 100, name="OA damper %", line=dict(color=COLORS["chart"][4])), row=2, col=1)
    if "oad_min" in sub.columns:
        fig.add_trace(go.Scatter(x=ts, y=sub["oad_min"] * 100, name="OA min %", line=dict(dash="dot", color=COLORS["muted"])), row=2, col=1)
    fig.add_trace(go.Scatter(x=ts, y=sub["clg_s"] * 100, name="CHW valve %", line=dict(color=COLORS["chart"][2])), row=3, col=1)
    if "oa_fraction_est" in sub.columns:
        fig.add_trace(go.Scatter(x=ts, y=sub["oa_fraction_est"] * 100, name="Est. OA fraction %", line=dict(color=COLORS["chart"][5])), row=3, col=1)
    fig.add_trace(
        go.Scatter(x=ts, y=fault_any, name="Any economizer fault", fill="tozeroy",
                   line=dict(color=COLORS["bad"], width=0.5), opacity=0.45),
        row=4, col=1,
    )
    fig.update_yaxes(title_text="°F", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1)
    fig.update_yaxes(title_text="% / fraction", row=3, col=1)
    fig.update_yaxes(title_text="Fault", row=4, col=1)
    fig.update_layout(title=f"{ahu_id} — economizer diagnostic trends")
    return fig_to_div(fig, 560)


def status_badge(status: str) -> str:
    colors = {"normal": COLORS["good"], "warning": COLORS["warn"], "fault": COLORS["bad"], "not_evaluated": COLORS["muted"]}
    c = colors.get(status, COLORS["muted"])
    return f'<span style="background:{c}22;color:{c};padding:2px 8px;border-radius:4px;font-size:0.75rem;font-weight:600">{status}</span>'


def fault_cards(results_df: pd.DataFrame) -> str:
    cards = []
    for _, r in results_df.iterrows():
        if r["status"] == "normal" and r["fault_code"] == "ECON_ENTHALPY_NOT_EVALUATED":
            continue
        cards.append(f"""
<div class="fcard">
  <div class="fcard-head"><strong>{r['fault_code']}</strong> {status_badge(r['status'])}</div>
  <div class="fcard-name">{r['fault_name']}</div>
  <div class="fcard-meta">Severity: {r['severity']} · Confidence: {r['confidence']} · {r['total_fault_minutes']:.0f} min</div>
  <div class="fcard-evidence">{r['evidence_summary']}</div>
</div>""")
    return "\n".join(cards)


def point_mapping_table(ahu_id: str, meta: dict) -> str:
    mapping = load_point_mapping()["ahu_mappings"].get(ahu_id, {})
    rows = []
    for logical, col in mapping.items():
        if logical == "notes":
            continue
        status = "present" if meta["columns_mapped"].get(logical) else ("n/a" if col is None else "missing")
        rows.append(f"<tr><td>{logical}</td><td>{col or '—'}</td><td>{status}</td></tr>")
    return f"<table><thead><tr><th>Logical point</th><th>BAS column</th><th>Status</th></tr></thead><tbody>{''.join(rows)}</tbody></table>"


def sensor_qa_table(meta: dict) -> str:
    rows = meta.get("sensor_qa_summary") or []
    if not rows:
        return "<p class='note'>No sensor QA detail.</p>"
    hdr = "<tr><th>Point</th><th>Level</th><th>Code</th><th>Status</th><th>Min</th><th>Samples</th><th>Evidence</th></tr>"
    body = ""
    for r in rows:
        body += (
            f"<tr><td>{r.get('point','')}</td><td>{r.get('level','')}</td>"
            f"<td>{r.get('fault_code','')}</td><td>{r.get('status','')}</td>"
            f"<td>{r.get('total_fault_minutes',0):.0f}</td><td>{r.get('affected_samples',0)}</td>"
            f"<td>{r.get('evidence_summary','')}</td></tr>"
        )
    return f"<table><thead>{hdr}</thead><tbody>{body}</tbody></table>"


def sensor_limits_table() -> str:
    tbl = metric_reference_table()
    rows = ""
    for _, r in tbl.iterrows():
        if r["sensor"] not in ("outdoor_air_temp", "return_air_temp", "mixed_air_temp", "supply_air_temp"):
            continue
        rows += (
            f"<tr><td>{r['sensor']}</td>"
            f"<td>{r['hard_min_ip']} to {r['hard_max_ip']} °F</td>"
            f"<td>{r['hard_min_si']} to {r['hard_max_si']} °C</td>"
            f"<td>{r['max_roc_per_hour_ip']} °F/hr</td>"
            f"<td>{r['max_roc_per_hour_si']} °C/hr</td></tr>"
        )
    return f"""<table>
<thead><tr><th>Sensor</th><th>Hard range (IP)</th><th>Hard range (SI)</th><th>Max ROC (IP)</th><th>Max ROC (SI)</th></tr></thead>
<tbody>{rows}</tbody></table>"""


def results_table(results_df: pd.DataFrame) -> str:
    show = results_df[["fault_code", "status", "severity", "confidence", "total_fault_minutes", "affected_samples", "evidence_summary"]]
    hdr = "".join(f"<th>{c}</th>" for c in show.columns)
    body = ""
    for _, row in show.iterrows():
        body += "<tr>" + "".join(f"<td>{row[c]}</td>" for c in show.columns) + "</tr>"
    return f"<table><thead><tr>{hdr}</tr></thead><tbody>{body}</tbody></table>"


def build_page(meta_created: str | None = None) -> None:
    meta_created = meta_created or datetime.now().strftime("%Y-%m-%d %H:%M")
    metric_reference_table().to_csv(OUT / "sensor_limits_reference.csv", index=False)
    wx = _load_weather()
    sections = []
    all_results = []

    for ahu_id in ("AHU_1", "AHU_2"):
        raw = _load_ahu(ahu_id)
        d, results, meta = run_diagnostics(ahu_id, raw, wx)
        rdf = results_to_dataframe(results)
        all_results.append(rdf)
        ts_export = export_fault_timeseries(d, ahu_id)
        ts_export.to_csv(OUT / f"economizer_fault_timeseries_{ahu_id.lower()}.csv", index=False)
        rdf.to_csv(OUT / f"economizer_diagnostics_summary_{ahu_id.lower()}.csv", index=False)

        mech = rdf[rdf["fault_code"] == "ECON_MECH_COOLING_DURING_FREE_COOLING"]
        lost = float(mech["total_fault_minutes"].iloc[0]) if len(mech) else 0.0

        sections.append(f"""
<section class="card" id="{ahu_id.lower()}">
  <h2>{ahu_id} — Economizer diagnostics</h2>
  <p class="note">{meta.get('point_mapping_notes', '')}</p>
  <div class="grid">
    <div class="kpi"><div class="val">{lost:.0f}</div><div class="lbl">Lost economizer / mech-cool during free-cool (min)</div></div>
    <div class="kpi"><div class="val">{meta.get('sensor_fault_minutes', 0):.0f}</div><div class="lbl">Sensor fault minutes</div></div>
    <div class="kpi"><div class="val">{sum(1 for r in results if r.status == 'fault')}</div><div class="lbl">Active fault rules</div></div>
  </div>
  <h3>Point mapping</h3>
  {point_mapping_table(ahu_id, meta)}
  <h3>Diagnostic summary</h3>
  <div class="fcard-grid">{fault_cards(rdf)}</div>
  <h3>Sensor QA detail (L1–L4)</h3>
  <p class="note">L1 hard range · L2 ROC/spike · L3 flatline · L4 physics plausibility. Config: <code>sensor_fault_defaults.json</code></p>
  {sensor_qa_table(meta)}
  <h3>Trend plots</h3>
  <div class="chart">{chart_econ_trends(d, ahu_id)}</div>
  <h3>Evidence table</h3>
  {results_table(rdf)}
</section>""")

    combined = pd.concat(all_results, ignore_index=True)
    combined.to_csv(OUT / "economizer_diagnostics_summary_all.csv", index=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Economizer Diagnostics — {SITE_LABEL}</title>
<script src="plotly.min.js"></script>
<style>
:root {{ --bg:#0f1419; --card:#1a2332; --text:#e8edf4; --muted:#8b9cb3; --accent:#3b82f6; }}
body {{ margin:0; font-family:'Segoe UI',system-ui,sans-serif; background:var(--bg); color:var(--text); line-height:1.5; }}
header {{ background:#111827; border-bottom:1px solid #243044; padding:1rem 1.5rem; }}
header h1 {{ margin:0 0 .25rem; font-size:1.35rem; }}
header .meta {{ color:var(--muted); font-size:.875rem; }}
nav {{ display:flex; flex-wrap:wrap; gap:.5rem; padding:.75rem 1.5rem; background:#151c28; border-bottom:1px solid #243044; }}
nav a {{ color:var(--muted); text-decoration:none; padding:.35rem .75rem; border-radius:6px; font-size:.875rem; }}
nav a:hover {{ background:#243044; color:var(--text); }}
nav a.active {{ background:var(--accent); color:#fff; }}
main {{ max-width:1280px; margin:0 auto; padding:1.25rem 1.5rem 2rem; }}
.card {{ background:var(--card); border-radius:10px; padding:1rem 1.25rem; margin-bottom:1.25rem; border:1px solid #243044; }}
.card h2 {{ margin:0 0 .75rem; font-size:1.1rem; }}
.card h3 {{ margin:1rem 0 .5rem; font-size:.95rem; color:var(--muted); }}
.note {{ color:var(--muted); font-size:.875rem; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:.75rem; margin:.75rem 0; }}
.kpi {{ background:#111827; border-radius:8px; padding:.75rem; text-align:center; }}
.kpi .val {{ font-size:1.4rem; font-weight:700; color:var(--accent); }}
.kpi .lbl {{ font-size:.7rem; color:var(--muted); }}
table {{ width:100%; border-collapse:collapse; font-size:.78rem; }}
th,td {{ padding:.35rem .5rem; border-bottom:1px solid #243044; text-align:left; }}
th {{ color:var(--muted); }}
.fcard-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:.6rem; }}
.fcard {{ background:#111827; border:1px solid #243044; border-radius:8px; padding:.65rem .85rem; }}
.fcard-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:.25rem; }}
.fcard-name {{ font-size:.85rem; margin-bottom:.25rem; }}
.fcard-meta {{ font-size:.72rem; color:var(--muted); }}
.fcard-evidence {{ font-size:.75rem; color:var(--muted); margin-top:.35rem; }}
.chart {{ margin:.5rem 0; }}
</style>
</head>
<body>
<header>
  <h1>AHU Economizer Diagnostics</h1>
  <div class="meta">Created {meta_created} · Title 24 / G36 / PNNL-style rules · Real BAS points only · Enthalpy N/E (no humidity export)</div>
</header>
<nav>
  <a href="index.html">Overview</a>
  <a href="economizer_diagnostics.html" class="active">Economizer Diagnostics</a>
  <a href="economizer.html">Free Cooling Summary</a>
  <a href="ahu_1.html">AHU 1</a>
  <a href="ahu_2.html">AHU 2</a>
  <a href="weather.html">Weather</a>
</nav>
<main>
<div class="card">
  <h2>Diagnostic approach</h2>
  <p class="note">Deterministic RCx rules with 15-minute persistence. Hierarchy: data quality → sensor plausibility (4 levels) → damper → economizer performance → energy impact. Damper position uses command as proxy (no separate feedback in export).</p>
  <p class="note"><strong>Sensor QA levels:</strong> L1 hard range · L2 rate-of-change/spike (suppressed at fan start) · L3 stale/flatline · L4 cross-sensor plausibility (MAT envelope, SAT vs MAT).</p>
  <p class="note"><strong>Not evaluated:</strong> enthalpy economizer (no OA/RA humidity), CO2/DCV, freeze stat, hydronic/pressure points (not in AHU export).</p>
  <h3>AHU air temperature limits (defaults)</h3>
  {sensor_limits_table()}
</div>
{''.join(sections)}
</main>
</body>
</html>"""
    (OUT / "economizer_diagnostics.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    build_page()
