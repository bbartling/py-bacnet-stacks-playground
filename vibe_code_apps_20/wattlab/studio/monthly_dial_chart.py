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


PLACEHOLDER_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)

# Honest agent checklist when utility_bills.per_month JSON is missing.
AGENT_MONTHLY_PCT_PROMPT_LINES = (
    "Publish / attach `calibration_scorecard.json` (or `campaign_stamp.json` → scorecard_path).",
    "Fill `utility_bills.per_month` with 12 months of pairs:",
    "  • elec: `observed_kwh` + `modeled_kwh` (or `simulated_kwh`)",
    "  • gas: `observed_therms` + `modeled_therms` (or `simulated_therms`)",
    "Point ECMs / Twin at the same calibrated run under `runs/…`.",
    "Re-open this tab — monthly ±% bars must stay visible once JSON is present.",
)


def build_empty_monthly_pm_figure(
    *,
    fuel: str,
    title: str | None = None,
    ok_band_pct: float = DEFAULT_OK_BAND_PCT,
):
    """Always-visible placeholder chart when monthly JSON pairs are absent."""
    import plotly.graph_objects as go

    fuel_label = "Electricity" if fuel == "elec" else "Natural gas"
    zeros = [0.0] * len(PLACEHOLDER_MONTHS)
    fig = go.Figure(
        data=[
            go.Bar(
                x=list(PLACEHOLDER_MONTHS),
                y=zeros,
                marker_color="#cbd5e0",
                text=["—"] * len(PLACEHOLDER_MONTHS),
                textposition="outside",
                hovertemplate="%{x}: no bill↔E+ pair yet<extra></extra>",
                name=f"{fuel} ±% (awaiting data)",
            )
        ]
    )
    fig.add_hline(y=ok_band_pct, line_dash="dot", line_color=BAND_COLOR)
    fig.add_hline(y=-ok_band_pct, line_dash="dot", line_color=BAND_COLOR)
    fig.add_hline(y=0, line_color="#2d3748", line_width=1)
    fig.add_annotation(
        text="Awaiting utility_bills.per_month — chart slot reserved",
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.55,
        showarrow=False,
        font=dict(size=13, color="#4a5568"),
    )
    fig.update_layout(
        title=title or f"{fuel_label} — monthly dial ±% (model vs bills)",
        yaxis_title="% off (model − bill) / bill",
        yaxis=dict(range=[-ok_band_pct * 2, ok_band_pct * 2]),
        height=360,
        margin=dict(l=40, r=20, t=50, b=40),
        showlegend=False,
    )
    return fig


def build_monthly_pm_figure(
    per_month: list[dict[str, Any]] | None,
    *,
    fuel: str,
    title: str | None = None,
    ok_band_pct: float = DEFAULT_OK_BAND_PCT,
    placeholder_when_empty: bool = False,
):
    """Plotly diverging bar: monthly ±% for one fuel.

    When ``placeholder_when_empty`` is True, never returns None — reserves the
    chart slot so ECM / Twin UI does not collapse when JSON is missing.
    """
    import plotly.graph_objects as go

    series = monthly_pct_series(per_month, fuel=fuel)
    if not series:
        if placeholder_when_empty:
            return build_empty_monthly_pm_figure(
                fuel=fuel, title=title, ok_band_pct=ok_band_pct
            )
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


def agent_monthly_pct_prompt_text(*, twin_hint: str | None = None) -> str:
    """Operator-visible checklist for agents when scorecard months are missing."""
    lines = ["**Please have AI agent render / attach:**"]
    lines.extend(f"- {line}" for line in AGENT_MONTHLY_PCT_PROMPT_LINES)
    if twin_hint:
        lines.append(f"- ECM Twin hint: `{twin_hint}`")
    return "\n".join(lines)


def render_required_monthly_pct_charts(
    per_month: list[dict[str, Any]] | None,
    *,
    key_prefix: str = "monthly_pm",
    twin_hint: str | None = None,
    fuels: tuple[str, ...] = ("elec", "gas"),
) -> dict[str, bool]:
    """Always render monthly ±% chart slots (real data or placeholder).

    Returns ``{fuel: has_series}`` for callers / tests.
    """
    import streamlit as st

    from wattlab.studio.monthly_fuel_chart import normalize_per_month_rows

    rows = normalize_per_month_rows(list(per_month or []))
    st.markdown("#### Monthly dial ±% (E+ model vs actual bills)")
    st.caption(
        "Required on Twin and ECMs. Positive = model over-predicts bills; negative = under. "
        "Chart frames stay visible even when JSON is missing."
    )
    status: dict[str, bool] = {}
    any_series = False
    for fuel in fuels:
        series = monthly_pct_series(rows, fuel=fuel)
        has = bool(series)
        status[fuel] = has
        any_series = any_series or has
        fig = build_monthly_pm_figure(rows, fuel=fuel, placeholder_when_empty=True)
        st.plotly_chart(fig, width="stretch", key=f"{key_prefix}_{fuel}")
        if not has:
            fuel_lab = "Electricity" if fuel == "elec" else "Natural gas"
            st.info(
                f"{fuel_lab}: no monthly bill↔E+ pairs yet — placeholder chart kept above."
            )
    if not any_series:
        st.warning(agent_monthly_pct_prompt_text(twin_hint=twin_hint))
    return status



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
