"""Monthly dial ±% charts — model vs bills over/under by month (and dial history)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from wattlab.studio.monthly_pct_off import (
    DEFAULT_OK_BAND_PCT,
    load_per_month_from_run,
    month_short_label,
    pct_off,
)

OVER_COLOR = "#c53030"
UNDER_COLOR = "#2b6cb0"
OK_COLOR = "#718096"
BAND_COLOR = "rgba(160,174,192,0.35)"

SEASON_BY_MONTH = {
    "Jan": "DJF",
    "Feb": "DJF",
    "Mar": "MAM",
    "Apr": "MAM",
    "May": "MAM",
    "Jun": "JJA",
    "Jul": "JJA",
    "Aug": "JJA",
    "Sep": "SON",
    "Oct": "SON",
    "Nov": "SON",
    "Dec": "DJF",
}


def monthly_pct_series(
    per_month: list[dict[str, Any]] | None,
    *,
    fuel: str,
) -> list[dict[str, Any]]:
    """Return ordered rows: month label, pct_off, season."""
    out: list[dict[str, Any]] = []
    for row in per_month or []:
        if not isinstance(row, dict):
            continue
        if fuel == "elec":
            sim = row.get("modeled_kwh")
            if sim is None:
                sim = row.get("simulated_kwh")
            obs = row.get("observed_kwh")
        else:
            sim = row.get("modeled_therms")
            if sim is None:
                sim = row.get("simulated_therms")
            obs = row.get("observed_therms")
        try:
            sim_f = float(sim) if sim is not None and sim != "" else None
            obs_f = float(obs) if obs is not None and obs != "" else None
        except (TypeError, ValueError):
            continue
        pct = pct_off(sim_f, obs_f)
        if pct is None:
            continue
        lab = month_short_label(row.get("month") or row.get("period"))
        out.append(
            {
                "month": lab,
                "pct_off": round(pct, 2),
                "season": SEASON_BY_MONTH.get(lab, "?"),
                "modeled": sim_f,
                "observed": obs_f,
            }
        )
    return out


def bar_colors(pcts: list[float], *, ok_band_pct: float = DEFAULT_OK_BAND_PCT) -> list[str]:
    colors: list[str] = []
    for p in pcts:
        if p > ok_band_pct:
            colors.append(OVER_COLOR)
        elif p < -ok_band_pct:
            colors.append(UNDER_COLOR)
        else:
            colors.append(OK_COLOR)
    return colors


def build_monthly_pm_figure(
    per_month: list[dict[str, Any]] | None,
    *,
    fuel: str,
    title: str | None = None,
    ok_band_pct: float = DEFAULT_OK_BAND_PCT,
):
    """Plotly diverging bar: monthly ±% for one fuel."""
    import plotly.graph_objects as go

    series = monthly_pct_series(per_month, fuel=fuel)
    if not series:
        return None
    months = [r["month"] for r in series]
    pcts = [float(r["pct_off"]) for r in series]
    seasons = [r["season"] for r in series]
    fig = go.Figure(
        data=[
            go.Bar(
                x=months,
                y=pcts,
                marker_color=bar_colors(pcts, ok_band_pct=ok_band_pct),
                text=[f"{p:+.0f}%" for p in pcts],
                textposition="outside",
                hovertemplate="%{x} (%{customdata}): %{y:+.1f}%<extra></extra>",
                customdata=seasons,
                name=f"{fuel} ±%",
            )
        ]
    )
    fig.add_hline(y=ok_band_pct, line_dash="dot", line_color=BAND_COLOR)
    fig.add_hline(y=-ok_band_pct, line_dash="dot", line_color=BAND_COLOR)
    fig.add_hline(y=0, line_color="#2d3748", line_width=1)
    fuel_label = "Electricity" if fuel == "elec" else "Natural gas"
    fig.update_layout(
        title=title or f"{fuel_label} — monthly dial ±% (model vs bills)",
        yaxis_title="% off (model − bill) / bill",
        height=360,
        margin=dict(l=40, r=20, t=50, b=40),
        showlegend=False,
    )
    return fig


def history_heatmap_matrix(
    run_rows: list[dict[str, Any]],
    *,
    fuel: str,
    limit: int = 12,
) -> dict[str, Any]:
    """Build run × month ±% matrix from G14 history rows with ``dir`` keys."""
    usable = [r for r in run_rows if r.get("dir")][-limit:]
    month_order: list[str] = []
    series_by_run: list[tuple[str, dict[str, float]]] = []
    for r in usable:
        series = monthly_pct_series(load_per_month_from_run(r.get("dir")), fuel=fuel)
        if not series:
            continue
        by_m = {s["month"]: float(s["pct_off"]) for s in series}
        for m in by_m:
            if m not in month_order:
                month_order.append(m)
        n = r.get("run")
        rid = r.get("run_id") or Path(str(r.get("dir"))).name
        label = f"#{n}" if n is not None else str(rid)[:16]
        series_by_run.append((label, by_m))

    y_labels = [lab for lab, _ in series_by_run]
    matrix = [[by_m.get(m) for m in month_order] for _, by_m in series_by_run]
    return {"months": month_order, "runs": y_labels, "z": matrix, "fuel": fuel}


def build_history_heatmap_figure(
    run_rows: list[dict[str, Any]],
    *,
    fuel: str,
    limit: int = 12,
    title: str | None = None,
):
    """Plotly heatmap of dial attempts × month ±%."""
    import plotly.graph_objects as go

    data = history_heatmap_matrix(run_rows, fuel=fuel, limit=limit)
    if not data["months"] or not data["runs"]:
        return None
    fuel_label = "elec" if fuel == "elec" else "gas"
    fig = go.Figure(
        data=[
            go.Heatmap(
                z=data["z"],
                x=data["months"],
                y=data["runs"],
                colorscale="RdBu_r",
                zmid=0,
                colorbar=dict(title="% off"),
                hovertemplate="run %{y} · %{x}: %{z:+.1f}%<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title=title or f"Dial attempts — monthly {fuel_label} ±% history",
        height=max(280, 36 * len(data["runs"]) + 80),
        margin=dict(l=60, r=20, t=50, b=40),
    )
    return fig


def season_summary(series: list[dict[str, Any]]) -> dict[str, float]:
    """Mean ±% by meteorological season."""
    buckets: dict[str, list[float]] = {}
    for row in series:
        buckets.setdefault(str(row.get("season") or "?"), []).append(float(row["pct_off"]))
    return {k: round(sum(v) / len(v), 1) for k, v in buckets.items() if v}
