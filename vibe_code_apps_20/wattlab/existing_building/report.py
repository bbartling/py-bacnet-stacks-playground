"""Portable HTML reporting for the Existing Building Hypothesis Lab."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


def _table(rows: Sequence[Mapping[str, Any]]) -> str:
    if not rows:
        return "<p>No records available.</p>"
    columns = list(dict.fromkeys(key for row in rows for key in row))
    head = "".join(f"<th>{html.escape(str(column))}</th>" for column in columns)
    body = []
    for row in rows:
        cells = []
        for column in columns:
            value = row.get(column, "")
            if isinstance(value, (dict, list)):
                value = json.dumps(value, sort_keys=True)
            cells.append(f"<td>{html.escape(str(value if value is not None else '—'))}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f"<table><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def build_existing_building_report(
    path: str | Path,
    *,
    badge: str,
    profile: Mapping[str, Any],
    evidence: Sequence[Mapping[str, Any]],
    assumptions: Sequence[Mapping[str, Any]],
    scenarios: Sequence[Mapping[str, Any]],
    ranking: Sequence[Mapping[str, Any]],
    proxy_crosscheck: Sequence[Mapping[str, Any]],
    measurements: Sequence[Mapping[str, Any]],
    limitations: Sequence[str],
) -> Path:
    """Write a self-contained report, with optional Plotly charts."""
    escaped_badge = html.escape(badge)
    chart = ""
    try:
        import plotly.graph_objects as go
        import plotly.io as pio

        chart_rows = [row for row in ranking if row.get("score") is not None][:12]
        figure = go.Figure(
            go.Bar(
                x=[str(row.get("scenario_id")) for row in chart_rows],
                y=[float(row.get("score", 0)) for row in chart_rows],
            )
        )
        figure.update_layout(title="Hypothesis ranking", xaxis_title="Scenario", yaxis_title="Score")
        chart = pio.to_html(figure, full_html=False, include_plotlyjs="inline")
    except ImportError:
        chart = "<p>Plotly is not installed; rankings are provided in the table below.</p>"

    sections = [
        ("Executive summary", f"<p><strong>{escaped_badge}</strong></p><p>This report ranks hypotheses; it does not assert measured savings.</p>"),
        ("Evidence inventory", _table(evidence)),
        ("Resolved building profile", f"<pre>{html.escape(json.dumps(profile, indent=2, default=str))}</pre>"),
        ("Assumption register", _table(assumptions)),
        ("Autosizing reference", "<p>See <code>autosizing_inventory.json</code> for the sizing-run plan or parsed inventory.</p>"),
        ("Scenario design", _table(scenarios)),
        ("Scenario results and ranking", chart + _table(ranking)),
        ("Calibration or hypothesis scorecard", f"<p>Badge: <strong>{escaped_badge}</strong>. Validation requires an independent holdout period.</p>"),
        ("Proxy cross-check", _table(proxy_crosscheck)),
        ("Weather quality", "<p>Weather provenance and quality checks are recorded in <code>weather_quality_report.json</code>.</p>"),
        ("Recommended field measurements", _table(measurements)),
        ("Limitations", "<ul>" + "".join(f"<li>{html.escape(str(item))}</li>" for item in limitations) + "</ul>"),
    ]
    content = "".join(f"<section><h2>{title}</h2>{body}</section>" for title, body in sections)
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>WattLab Existing Building Hypothesis Lab</title>
<style>body{{font:15px system-ui;max-width:1200px;margin:auto;padding:2rem;color:#17202a}}table{{border-collapse:collapse;width:100%;display:block;overflow:auto}}th,td{{border:1px solid #ccd1d1;padding:.45rem;text-align:left;vertical-align:top}}th{{background:#eef2f3}}section{{margin:2rem 0}}pre{{white-space:pre-wrap;background:#f6f8fa;padding:1rem}}</style>
</head><body><h1>WattLab Existing Building Hypothesis Lab</h1>{content}</body></html>"""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")
    return destination
