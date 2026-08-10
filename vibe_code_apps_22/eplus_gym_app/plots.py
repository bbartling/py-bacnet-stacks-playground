"""Plotly figures for Lakeside E+ gym Streamlit app."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from eplus_gym_app.load_profiles import DIAL_COLORS

COLORS = {
    "baseline": "#264653",
    "flat_24_7": "#6c757d",
    "deep_setback": "#2a9d8f",
    "stagger_preheat": "#e9c46a",
    "morning_all_on": "#e76f51",
}


def facility_overlay_figure(
    profiles: pd.DataFrame,
    *,
    month: str,
    title_suffix: str = "",
) -> go.Figure:
    fig = go.Figure()
    if profiles.empty:
        fig.update_layout(
            title=f"No farm data · {month}",
            template="plotly_white",
            height=420,
        )
        return fig
    for sid in profiles["strategy_id"].astype(str).unique():
        sub = profiles[profiles["strategy_id"] == sid]
        fig.add_trace(
            go.Scatter(
                x=sub["step"].to_numpy(dtype=float) / 4.0,
                y=sub["facility_kw"],
                mode="lines",
                name=str(sid),
                line=dict(color=COLORS.get(str(sid), "#333333"), width=2),
            )
        )
    fig.update_layout(
        title=f"IdealLoads mean daily kW · {month}{title_suffix}",
        xaxis_title="Hour",
        yaxis_title="facility kW (mean over days present)",
        template="plotly_white",
        height=440,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(l=40, r=20, t=60, b=40),
    )
    return fig


def kpi_table(kpis: Sequence[dict]) -> pd.DataFrame:
    return pd.DataFrame(list(kpis))


def demand_vs_oat_figure(bas: pd.DataFrame, *, peak_day: str | None = None) -> go.Figure:
    """Scatter: BAS kW vs Open-Meteo OAT (weekday / weekend / peak day hours)."""
    fig = go.Figure()
    if bas.empty:
        fig.update_layout(title="No BAS×OAT data", template="plotly_white", height=420)
        return fig
    df = bas.dropna(subset=["oat_f", "kw_avg"]).copy()
    r = float(np.corrcoef(df["oat_f"], df["kw_avg"])[0, 1]) if len(df) > 2 else float("nan")

    for dtype, symbol, color in (
        ("Weekday", "circle", "#2a9d8f"),
        ("Weekend", "triangle-up", "#e76f51"),
    ):
        sub = df[df["day_type"].astype(str).str.lower() == dtype.lower()]
        if sub.empty:
            continue
        fig.add_trace(
            go.Scatter(
                x=sub["oat_f"],
                y=sub["kw_avg"],
                mode="markers",
                name=dtype,
                marker=dict(symbol=symbol, size=6, color=color, opacity=0.55),
            )
        )
    if peak_day:
        peak = df[df["local_day"] == peak_day]
        if not peak.empty:
            fig.add_trace(
                go.Scatter(
                    x=peak["oat_f"],
                    y=peak["kw_avg"],
                    mode="markers",
                    name=f"Peak day {peak_day}",
                    marker=dict(symbol="star", size=10, color="#4cc9f0"),
                )
            )
    fig.update_layout(
        title=(
            f"Demand vs Open-Meteo OAT · Pearson r = {r:.2f}"
            if np.isfinite(r)
            else "Demand vs Open-Meteo OAT"
        ),
        xaxis_title="OAT (°F)",
        yaxis_title="Hourly avg demand (kW)",
        template="plotly_white",
        height=440,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def peak_day_profile_figure(
    bas_day: pd.DataFrame,
    *,
    day: str,
    peak_kw: float | None = None,
) -> go.Figure:
    """Dual-axis peak day: demand + OAT (BAS only)."""
    fig = go.Figure()
    if bas_day.empty:
        fig.update_layout(title=f"No BAS profile · {day}", template="plotly_white")
        return fig
    fig.add_trace(
        go.Scatter(
            x=bas_day["hod"],
            y=bas_day["kw_avg"],
            name="Demand",
            line=dict(color="#264653", width=2.4),
            yaxis="y",
        )
    )
    if "oat_f" in bas_day.columns:
        fig.add_trace(
            go.Scatter(
                x=bas_day["hod"],
                y=bas_day["oat_f"],
                name="OAT",
                line=dict(color="#e76f51", width=2, dash="dash"),
                yaxis="y2",
            )
        )
    if peak_kw is not None and np.isfinite(peak_kw):
        peak_row = bas_day.loc[bas_day["kw_avg"].idxmax()]
        fig.add_trace(
            go.Scatter(
                x=[float(peak_row["hod"])],
                y=[float(peak_row["kw_avg"])],
                mode="markers+text",
                text=[f"Peak {peak_kw:.0f} kW"],
                textposition="top center",
                marker=dict(color="#e63946", size=10),
                name="Peak",
                yaxis="y",
            )
        )
    oat_min = (
        float(bas_day["oat_f"].min()) if "oat_f" in bas_day.columns else float("nan")
    )
    fig.update_layout(
        title=(
            f"Peak demand day · {day}"
            + (f" max {peak_kw:.0f} kW" if peak_kw and np.isfinite(peak_kw) else "")
            + (f" · OAT {oat_min:.0f}°F" if np.isfinite(oat_min) else "")
        ),
        xaxis_title="Hour (local)",
        yaxis=dict(title="Demand (kW)"),
        yaxis2=dict(title="OAT (°F)", overlaying="y", side="right"),
        template="plotly_white",
        height=440,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def dial_progression_figure(overlay: Mapping[str, Any]) -> go.Figure:
    """Actual vs dial-ladder models on peak day + utility threshold."""
    fig = go.Figure()
    series: dict = overlay.get("series") or {}
    day = overlay.get("day", "")
    util = float(overlay.get("utility_peak_kw") or 284.8)
    for name, frame in series.items():
        if frame is None or getattr(frame, "empty", True):
            continue
        ycol = "kw" if "kw" in frame.columns else (
            "kw_avg" if "kw_avg" in frame.columns else None
        )
        if ycol is None:
            continue
        fig.add_trace(
            go.Scatter(
                x=frame["hod"],
                y=frame[ycol],
                mode="lines",
                name=str(name),
                line=dict(
                    color=DIAL_COLORS.get(str(name), "#666"),
                    width=2.6 if name == "A04" else (2.4 if name == "Actual" else 1.7),
                ),
            )
        )
    fig.add_hline(
        y=util,
        line_dash="dot",
        line_color="#888",
        annotation_text=f"Utility {util:.1f} kW",
        annotation_position="top left",
    )
    fig.update_layout(
        title=f"Peak day {day} — dial progression to A04",
        xaxis_title="Hour",
        yaxis_title="kW",
        template="plotly_white",
        height=460,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig
