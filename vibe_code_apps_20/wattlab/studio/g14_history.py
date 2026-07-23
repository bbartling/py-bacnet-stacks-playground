"""G14 calibration history across published Twin runs (epoch / loss-style chart)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wattlab.studio.eui_charts import plotly_layout_clean
from wattlab.studio.ep_viz import list_iteration_runs, read_run_progress

G14_NMBE_GATE = 5.0
G14_CVRMSE_GATE = 15.0


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _g14_from_scorecard(data: dict[str, Any]) -> dict[str, Any]:
    """Extract NMBE/CVRMSE from calibration_scorecard or wattlab_report utility_bills."""
    bills = data.get("utility_bills") or {}
    if not isinstance(bills, dict):
        bills = {}
    stats_e = bills.get("stats_electricity") or bills.get("stats") or {}
    stats_g = bills.get("stats_natural_gas") or bills.get("stats_gas") or {}
    if not isinstance(stats_e, dict):
        stats_e = {}
    if not isinstance(stats_g, dict):
        stats_g = {}
    # Some stamps put nmbe at top level
    out = {
        "nmbe_elec_pct": stats_e.get("nmbe_pct", data.get("nmbe_elec_pct")),
        "cvrmse_elec_pct": stats_e.get("cvrmse_pct", data.get("cvrmse_elec_pct")),
        "nmbe_gas_pct": stats_g.get("nmbe_pct", data.get("nmbe_gas_pct")),
        "cvrmse_gas_pct": stats_g.get("cvrmse_pct", data.get("cvrmse_gas_pct")),
        "pass_fail": bills.get("pass_fail")
        or data.get("pass_fail")
        or data.get("status")
        or data.get("overall"),
    }
    return out


def extract_run_g14(run_dir: Path | str | None) -> dict[str, Any]:
    """Load G14 metrics from a published run directory."""
    if not run_dir:
        return {}
    root = Path(run_dir)
    for name in ("calibration_scorecard.json", "campaign_stamp.json", "wattlab_report.json"):
        p = root / name
        if p.is_file():
            g = _g14_from_scorecard(_load_json(p))
            if any(g.get(k) is not None for k in ("nmbe_elec_pct", "cvrmse_elec_pct", "nmbe_gas_pct")):
                return g
    return {}


def iter_g14_history(runs_root: Path | str, *, limit: int = 30) -> list[dict[str, Any]]:
    """Return chronological G14 rows for published runs (oldest → newest)."""
    rows: list[dict[str, Any]] = []
    for h in list_iteration_runs(Path(runs_root), limit=limit):
        d = Path(str(h["dir"])) if h.get("dir") else None
        g14 = extract_run_g14(d)
        prog = read_run_progress(d) if d else {}
        rows.append(
            {
                "run_id": h.get("run_id"),
                "dir": str(d) if d else None,
                "started_at": h.get("started_at") or prog.get("started_at"),
                "finished_at": h.get("finished_at") or prog.get("finished_at"),
                "status": h.get("status"),
                "hypothesis": h.get("hypothesis"),
                "has_eplusout": h.get("has_eplusout"),
                "elapsed_s": h.get("elapsed_s"),
                "mtime": h.get("mtime"),
                **g14,
            }
        )

    def _sort_key(r: dict[str, Any]) -> tuple:
        ts = r.get("started_at") or ""
        if ts:
            return (0, str(ts), str(r.get("run_id") or ""))
        mt = r.get("mtime")
        return (1, float(mt) if mt is not None else 0.0, str(r.get("run_id") or ""))

    rows.sort(key=_sort_key)
    return rows


def g14_epoch_figure(rows: list[dict[str, Any]], *, height: int = 440):
    """Plot |NMBE| and CV(RMSE) vs iteration index (training-loss style)."""
    import plotly.graph_objects as go

    usable = [
        r
        for r in rows
        if r.get("nmbe_elec_pct") is not None or r.get("cvrmse_elec_pct") is not None
    ]
    fig = go.Figure()
    if not usable:
        fig.add_annotation(
            text="No per-run G14 scorecards yet — publish calibration_scorecard.json with each Twin run.",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
        return plotly_layout_clean(
            fig,
            title="G14 calibration across iterations",
            height=height,
            yaxis_title="% error",
        )

    xs = list(range(1, len(usable) + 1))
    hover = [
        f"{r.get('run_id')}<br>{r.get('started_at') or ''}<br>{(r.get('hypothesis') or '')[:80]}"
        for r in usable
    ]

    def _abs_series(key: str) -> list[float | None]:
        out: list[float | None] = []
        for r in usable:
            v = r.get(key)
            try:
                out.append(abs(float(v)) if v is not None else None)
            except (TypeError, ValueError):
                out.append(None)
        return out

    fig.add_scatter(
        x=xs,
        y=_abs_series("nmbe_elec_pct"),
        mode="lines+markers",
        name="|NMBE| elec %",
        text=hover,
        hovertemplate="iter %{x}<br>%{text}<br>|NMBE| %{y:.2f}%<extra></extra>",
        line=dict(color="#1f77b4", width=2),
    )
    fig.add_scatter(
        x=xs,
        y=_abs_series("cvrmse_elec_pct"),
        mode="lines+markers",
        name="CV(RMSE) elec %",
        text=hover,
        hovertemplate="iter %{x}<br>%{text}<br>CVRMSE %{y:.2f}%<extra></extra>",
        line=dict(color="#ff7f0e", width=2),
    )
    if any(r.get("nmbe_gas_pct") is not None for r in usable):
        fig.add_scatter(
            x=xs,
            y=_abs_series("nmbe_gas_pct"),
            mode="lines+markers",
            name="|NMBE| gas %",
            text=hover,
            hovertemplate="iter %{x}<br>%{text}<br>|NMBE| gas %{y:.2f}%<extra></extra>",
            line=dict(color="#2ca02c", width=2, dash="dot"),
        )
    if any(r.get("cvrmse_gas_pct") is not None for r in usable):
        fig.add_scatter(
            x=xs,
            y=_abs_series("cvrmse_gas_pct"),
            mode="lines+markers",
            name="CV(RMSE) gas %",
            text=hover,
            hovertemplate="iter %{x}<br>%{text}<br>CVRMSE gas %{y:.2f}%<extra></extra>",
            line=dict(color="#9467bd", width=2, dash="dot"),
        )

    # ASHRAE G14 monthly gates — as legend traces (add_hline annotations alone
    # do not appear in the Plotly legend and look like anonymous dashboard lines).
    x0, x1 = xs[0], xs[-1]
    fig.add_scatter(
        x=[x0, x1],
        y=[G14_NMBE_GATE, G14_NMBE_GATE],
        mode="lines",
        name=f"G14 |NMBE| gate ≤{G14_NMBE_GATE:g}%",
        line=dict(color="#d62728", width=2, dash="dash"),
        hovertemplate=f"ASHRAE G14 monthly |NMBE| gate ≤ {G14_NMBE_GATE:g}%<extra></extra>",
        showlegend=True,
    )
    fig.add_scatter(
        x=[x0, x1],
        y=[G14_CVRMSE_GATE, G14_CVRMSE_GATE],
        mode="lines",
        name=f"G14 CV(RMSE) gate ≤{G14_CVRMSE_GATE:g}%",
        line=dict(color="#8c564b", width=2, dash="dash"),
        hovertemplate=f"ASHRAE G14 monthly CV(RMSE) gate ≤ {G14_CVRMSE_GATE:g}%<extra></extra>",
        showlegend=True,
    )

    plotly_layout_clean(
        fig,
        title="G14 calibration across iterations (lower is better)",
        height=height,
        yaxis_title="% error",
        xaxis_title="Iteration (oldest → newest)",
    )
    fig.update_layout(
        legend=dict(
            title_text="Series (dashed = ASHRAE G14 monthly gates)",
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
        ),
    )
    fig.update_xaxes(dtick=1, showgrid=True, gridcolor="rgba(0,0,0,0.06)")
    fig.update_yaxes(rangemode="tozero", showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    return fig
