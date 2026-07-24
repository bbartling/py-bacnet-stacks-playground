"""Finding-specific charts → optional PNG (Plotly + Kaleido when available)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.reporting.models import EngineeringFinding, ReportArtifacts


def build_report_charts(
    artifacts: ReportArtifacts,
    *,
    out_dir: Path | None = None,
    comfort_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Attach chart metadata (and PNG paths when Kaleido works)."""
    try:
        import plotly.graph_objects as go
    except ImportError:
        return []

    out_dir = Path(out_dir) if out_dir else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    charts: list[dict[str, Any]] = []

    # 1) Confidence summary
    from collections import Counter

    counts = Counter(f.effective_classification.value for f in artifacts.findings)
    for s in artifacts.suppressed:
        counts[s.get("classification") or "SUPPRESSED"] += 0  # don't inflate
    fig = go.Figure(
        data=[
            go.Bar(
                x=list(counts.keys()),
                y=list(counts.values()),
                marker_color="#2c5282",
            )
        ]
    )
    fig.update_layout(
        title="Findings by confidence category",
        xaxis_title="Category",
        yaxis_title="Count",
        height=360,
        margin=dict(l=40, r=20, t=50, b=80),
        font=dict(size=12),
    )
    charts.append(_export(fig, "confidence_summary", out_dir))

    # 2) Comfort ranking (valid sensors only)
    rows = comfort_rows or (artifacts.comfort_summary.get("rows") or [])
    valid = [
        r
        for r in rows
        if not r.get("flag_dead_sensor")
        and not r.get("outlier")
        and (r.get("mean_zone_t") or 99) >= 40
    ]
    valid = sorted(valid, key=lambda r: float(r.get("in_band_pct") or r.get("in_band_%") or 0))[:15]
    if valid:
        fig2 = go.Figure(
            data=[
                go.Bar(
                    y=[r.get("equipment_id") for r in valid][::-1],
                    x=[float(r.get("in_band_pct") or r.get("in_band_%") or 0) for r in valid][::-1],
                    orientation="h",
                    marker_color="#c05621",
                )
            ]
        )
        fig2.update_layout(
            title="Zone comfort ranking (dead/implausible sensors excluded)",
            xaxis_title="In-band % (occupied)",
            height=420,
            margin=dict(l=100, r=20, t=50, b=40),
        )
        charts.append(_export(fig2, "comfort_ranking", out_dir))

    # 3) Per priority finding chart
    for f in artifacts.findings:
        if not f.include_in_report or not f.chart_spec:
            continue
        fig_f = _figure_for_finding(f, go)
        if fig_f is None:
            continue
        meta = _export(fig_f, f"finding_{f.finding_id}", out_dir)
        f.chart_path = meta.get("path")
        charts.append({**meta, "finding_id": f.finding_id})

    artifacts.charts = charts
    return charts


def _figure_for_finding(f: EngineeringFinding, go):
    spec = f.chart_spec or {}
    kind = spec.get("kind")
    if kind == "fan_off_static":
        fig = go.Figure(
            data=[
                go.Bar(
                    x=["Fan OFF", "Fan ON"],
                    y=[float(spec.get("fan_off_p50") or 0), float(spec.get("fan_on_p50") or 0)],
                    marker_color=["#c53030", "#2b6cb0"],
                )
            ]
        )
        fig.update_layout(
            title=f"{spec.get('equipment_id')} duct static — fan OFF vs ON ({spec.get('units')})",
            yaxis_title=str(spec.get("units") or "in. w.c."),
            height=360,
        )
        return fig
    if kind == "vav5_damper_flow":
        fig = go.Figure(
            data=[
                go.Bar(
                    x=["Damper %", "Airflow"],
                    y=[float(spec.get("damper") or 0), float(spec.get("airflow") or 0)],
                    marker_color=["#805ad5", "#dd6b20"],
                )
            ]
        )
        fig.update_layout(
            title=f"{spec.get('equipment_id')} closed-damper / airflow spot check",
            height=360,
            annotations=[
                dict(
                    text="Units: damper %, airflow CFM (spot medians)",
                    xref="paper",
                    yref="paper",
                    x=0,
                    y=-0.15,
                    showarrow=False,
                )
            ],
        )
        return fig
    if kind == "fault_hours_bar" and spec.get("fault_hours") is not None:
        fig = go.Figure(
            data=[
                go.Bar(
                    x=[f"{spec.get('equipment_id')} / {spec.get('rule_id')}"],
                    y=[float(spec.get("fault_hours"))],
                )
            ]
        )
        fig.update_layout(title="Fault hours", yaxis_title="Hours", height=320)
        return fig
    return None


def _export(fig, name: str, out_dir: Path | None) -> dict[str, Any]:
    meta: dict[str, Any] = {"name": name, "path": None}
    if out_dir is None:
        return meta
    png = out_dir / f"{name}.png"
    try:
        fig.write_image(str(png), scale=2, width=900, height=420)
        meta["path"] = str(png)
    except Exception as exc:  # kaleido optional / may fail headless
        meta["export_error"] = str(exc)
        # still save interactive html for debugging
        html = out_dir / f"{name}.html"
        try:
            fig.write_html(str(html), include_plotlyjs="cdn")
            meta["html"] = str(html)
        except Exception:
            pass
    return meta
