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


def strategy_setpoint_figure(
    series_by_id: Mapping[str, Sequence[float]],
    *,
    title: str = "Heating SP contracts (96 steps, repeats on weekends)",
) -> go.Figure:
    """Overlay RuleController heating setpoints for the five desktop strategies."""
    fig = go.Figure()
    for sid, series in series_by_id.items():
        ys = list(series)
        if not ys:
            continue
        hours = [i / 4.0 for i in range(len(ys))]
        fig.add_trace(
            go.Scatter(
                x=hours,
                y=ys,
                name=str(sid),
                line=dict(color=COLORS.get(str(sid), "#333333"), width=2),
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Hour (local)",
        yaxis_title="Heating SP °F",
        template="plotly_white",
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=48, b=36),
    )
    return fig


def fuel_monthly_figure(elec: pd.DataFrame, *, title: str = "Monthly electric") -> go.Figure:
    """vibe20-style monthly fuel bars from Campus electric meter bills."""
    fig = go.Figure()
    if elec.empty:
        fig.update_layout(title="No fuel/bill rows", template="plotly_white", height=360)
        return fig
    g = elec.groupby("month", as_index=False)["usage"].sum()
    fig.add_trace(
        go.Bar(
            x=g["month"],
            y=g["usage"],
            name="kWh",
            marker_color="#264653",
        )
    )
    if "demand_kw" in elec.columns and elec["demand_kw"].notna().any():
        d = elec.groupby("month", as_index=False)["demand_kw"].max()
        fig.add_trace(
            go.Scatter(
                x=d["month"],
                y=d["demand_kw"],
                name="Billed demand kW",
                yaxis="y2",
                mode="lines+markers",
                line=dict(color="#e76f51", width=2),
            )
        )
        fig.update_layout(
            yaxis2=dict(title="Demand kW", overlaying="y", side="right"),
        )
    fig.update_layout(
        title=title,
        xaxis_title="Month",
        yaxis_title="kWh",
        template="plotly_white",
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def gl14_monthly_kwh_figure(
    pairs: pd.DataFrame,
    *,
    highlight: str | None = None,
    sim_id: str = "A04",
) -> go.Figure:
    """Utility-bill kWh vs published E+ monthly facility kWh."""
    fig = go.Figure()
    if pairs is None or pairs.empty:
        fig.update_layout(
            title="No monthly bill ↔ E+ pairs",
            template="plotly_white",
            height=380,
        )
        return fig
    work = pairs.dropna(subset=["month"]).copy()
    xs = work["month"].astype(str).tolist()
    if "kwh_obs" in work.columns and work["kwh_obs"].notna().any():
        fig.add_trace(
            go.Bar(
                x=xs,
                y=work["kwh_obs"],
                name="Actual (utility bill)",
                marker_color="#1f2a30",
            )
        )
    if "kwh_sim" in work.columns and work["kwh_sim"].notna().any():
        fig.add_trace(
            go.Bar(
                x=xs,
                y=work["kwh_sim"],
                name=f"E+ {sim_id}",
                marker_color="#e76f51",
            )
        )
    if highlight and highlight in xs:
        fig.add_vline(x=highlight, line_dash="dot", line_color="#6c757d")
    fig.update_layout(
        title=f"GL14 monthly kWh · bills vs E+ {sim_id}",
        barmode="group",
        xaxis_title="Month",
        yaxis_title="kWh",
        template="plotly_white",
        height=400,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def gl14_monthly_peak_figure(
    pairs: pd.DataFrame,
    *,
    highlight: str | None = None,
    sim_id: str = "A04",
) -> go.Figure:
    """Billed / interval peak kW vs E+ monthly max hourly kW."""
    fig = go.Figure()
    if pairs is None or pairs.empty:
        fig.update_layout(
            title="No monthly peak pairs",
            template="plotly_white",
            height=360,
        )
        return fig
    work = pairs.dropna(subset=["month"]).copy()
    xs = work["month"].astype(str).tolist()
    if "peak_kw_obs" in work.columns and work["peak_kw_obs"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=work["peak_kw_obs"],
                mode="lines+markers",
                name="Actual peak kW",
                line=dict(color="#1f2a30", width=2),
            )
        )
    if "peak_kw_sim" in work.columns and work["peak_kw_sim"].notna().any():
        fig.add_trace(
            go.Scatter(
                x=xs,
                y=work["peak_kw_sim"],
                mode="lines+markers",
                name=f"E+ {sim_id} peak kW",
                line=dict(color="#e76f51", width=2),
            )
        )
    if highlight and highlight in xs:
        fig.add_vline(x=highlight, line_dash="dot", line_color="#6c757d")
    fig.update_layout(
        title=f"Monthly peak kW · bills vs E+ {sim_id}",
        xaxis_title="Month",
        yaxis_title="kW",
        template="plotly_white",
        height=360,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def gl14_monthly_pct_figure(
    pairs: pd.DataFrame,
    *,
    highlight: str | None = None,
    sim_id: str = "A04",
) -> go.Figure:
    """Month ±% (E+ − bill) / bill."""
    fig = go.Figure()
    if pairs is None or pairs.empty or "pct_error" not in pairs.columns:
        fig.update_layout(
            title="No monthly % error",
            template="plotly_white",
            height=320,
        )
        return fig
    work = pairs.dropna(subset=["month", "pct_error"]).copy()
    colors = ["#2a9d8f" if v <= 0 else "#e76f51" for v in work["pct_error"]]
    fig.add_trace(
        go.Bar(
            x=work["month"].astype(str),
            y=work["pct_error"],
            name=f"E+ {sim_id} vs bill",
            marker_color=colors,
        )
    )
    fig.add_hline(y=5.0, line_dash="dot", line_color="#6c757d")
    fig.add_hline(y=-5.0, line_dash="dot", line_color="#6c757d")
    if highlight:
        fig.add_vline(x=highlight, line_dash="dot", line_color="#6c757d")
    fig.update_layout(
        title=f"GL14 monthly % off · E+ {sim_id} vs utility bill",
        xaxis_title="Month",
        yaxis_title="% (sim − bill) / bill",
        template="plotly_white",
        height=320,
        showlegend=False,
    )
    return fig


def period_overlay_figure(overlay: Mapping[str, Any]) -> go.Figure:
    """Actual BAS vs one selected dial model over a period (clear 2-series legend)."""
    fig = go.Figure()
    actual = overlay.get("actual")
    sim = overlay.get("sim")
    raw_util = overlay.get("utility_peak_kw")
    try:
        util = float(raw_util) if raw_util is not None else float("nan")
    except (TypeError, ValueError):
        util = float("nan")
    preset = overlay.get("preset", "")
    n_days = overlay.get("n_days", 0)
    sim_id = overlay.get("sim_id") or overlay.get("model_id") or "Sim"

    if actual is not None and not getattr(actual, "empty", True):
        fig.add_trace(
            go.Scatter(
                x=actual["t_hours"],
                y=actual["kw"],
                mode="lines",
                name="Actual (BAS meter)",
                line=dict(color="#1f2a30", width=2.4),
            )
        )
    if sim is not None and not getattr(sim, "empty", True):
        fig.add_trace(
            go.Scatter(
                x=sim["t_hours"],
                y=sim["kw"],
                mode="lines",
                name=f"E+ {sim_id} (selected)",
                line=dict(color="#e76f51", width=2.2),
            )
        )
    if util == util:  # skip None / nan (do not invent a default peak)
        fig.add_hline(
            y=util,
            line_dash="dot",
            line_color="#6c757d",
            annotation_text=f"Utility {util:.1f} kW",
            annotation_position="top left",
        )
    fig.update_layout(
        title=f"{preset} · {n_days} day(s) · Actual vs {sim_id}",
        xaxis_title="Hours from period start",
        yaxis_title="kW",
        template="plotly_white",
        height=460,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


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
        title=f"IdealLoads DIAGNOSTIC mean daily kW · {month}{title_suffix}",
        xaxis_title="Hour",
        yaxis_title="IdealLoads facility kW (NOT W2A / NOT BAS)",
        template="plotly_white",
        height=440,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, title_text="DR strategy"),
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
    raw_util = overlay.get("utility_peak_kw")
    try:
        util = float(raw_util) if raw_util is not None else float("nan")
    except (TypeError, ValueError):
        util = float("nan")
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
    if util == util:
        fig.add_hline(
            y=util,
            line_dash="dot",
            line_color="#888",
            annotation_text=f"Utility {util:.1f} kW",
            annotation_position="top left",
        )
    fig.update_layout(
        title=f"Peak day {day} — dial progression to champion",
        xaxis_title="Hour",
        yaxis_title="kW",
        template="plotly_white",
        height=460,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


_EPLUS_SERIES_COLORS = {
    "AMY_OPEN_METEO": "#2a9d8f",
    "TMY_MSN": "#e9c46a",
    "TMY_SCREENING": "#9b2226",
    "E+ AMY": "#2a9d8f",
    "E+ TMY": "#e9c46a",
    "E+ champion (this run)": "#2a9d8f",
    "E+ A04 (this run)": "#2a9d8f",
}


def _hod(df: pd.DataFrame):
    if "hod" in df.columns:
        return df["hod"]
    if "step" in df.columns:
        return df["step"].to_numpy(dtype=float) / 4.0
    return list(range(len(df)))


def dsm_trajectory_figure(
    df: pd.DataFrame,
    *,
    title: str = "DSM run",
    actual: pd.DataFrame | None = None,
    extra_eplus: Sequence[tuple[str, str, pd.DataFrame]] | None = None,
) -> go.Figure:
    """15-min E+ facility kW, optional Actual BAS overlay, heating SP on y2."""
    fig = go.Figure()
    frames = list(extra_eplus or [])
    if not frames and df is not None and not getattr(df, "empty", True):
        frames = [("E+ champion (this run)", "#2a9d8f", df)]
    if not frames and (actual is None or getattr(actual, "empty", True)):
        fig.update_layout(title="No DSM trajectory", template="plotly_white", height=400)
        return fig
    if actual is not None and not getattr(actual, "empty", True):
        xcol = "hod" if "hod" in actual.columns else None
        ycol = "kw_avg" if "kw_avg" in actual.columns else ("kw" if "kw" in actual.columns else None)
        if xcol and ycol:
            fig.add_trace(
                go.Scatter(
                    x=actual[xcol],
                    y=actual[ycol],
                    name="Actual (BAS meter)",
                    line=dict(color="#1f2a30", width=2.5),
                )
            )
    for name, color, frame in frames:
        if frame is None or getattr(frame, "empty", True) or "facility_kw" not in frame.columns:
            continue
        fig.add_trace(
            go.Scatter(
                x=_hod(frame),
                y=frame["facility_kw"],
                name=name,
                line=dict(color=color or _EPLUS_SERIES_COLORS.get(name, "#2a9d8f"), width=2.2),
            )
        )
    primary = frames[0][2] if frames else None
    if primary is not None and not getattr(primary, "empty", True) and "htg_sp_f" in primary.columns:
        fig.add_trace(
            go.Scatter(
                x=_hod(primary),
                y=primary["htg_sp_f"],
                name="E+ htg SP °F",
                yaxis="y2",
                line=dict(color="#e76f51", width=1.5, dash="dot"),
            )
        )
        fig.update_layout(yaxis2=dict(title="htg SP °F", overlaying="y", side="right"))
    fig.update_layout(
        title=title,
        xaxis_title="Hour (local)",
        yaxis_title="kW",
        template="plotly_white",
        height=440,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def period_daily_peak_figure(
    daily: pd.DataFrame,
    *,
    highlight_day: str | None,
    title: str,
    eplus_peak_kw: float | None = None,
    eplus_daily: Mapping[str, pd.DataFrame] | None = None,
) -> go.Figure:
    """Daily BAS meter peaks plus optional E+ AMY / TMY daily-peak series."""
    fig = go.Figure()
    has_actual = daily is not None and not getattr(daily, "empty", True)
    extras = {k: v for k, v in (eplus_daily or {}).items() if v is not None and not getattr(v, "empty", True)}
    if not has_actual and not extras:
        fig.update_layout(title=title, template="plotly_white", height=320)
        return fig
    if has_actual:
        x = daily["local_day"].astype(str)
        y = daily["peak_kw"]
        colors = ["#e76f51" if d == str(highlight_day or "")[:10] else "#264653" for d in x]
        fig.add_trace(
            go.Bar(x=x, y=y, name="Actual BAS daily peak kW", marker_color=colors)
        )
    for name, series in extras.items():
        fig.add_trace(
            go.Scatter(
                x=series["local_day"].astype(str),
                y=series["peak_kw"],
                name=name,
                mode="lines+markers",
                line=dict(
                    color=_EPLUS_SERIES_COLORS.get(name)
                    or COLORS.get(str(name).split()[0], "#2a9d8f"),
                    width=2.2,
                ),
                marker=dict(size=6),
            )
        )
    if not extras and eplus_peak_kw is not None and eplus_peak_kw == eplus_peak_kw:
        fig.add_hline(
            y=float(eplus_peak_kw),
            line_dash="dot",
            line_color="#2a9d8f",
            annotation_text=f"E+ champion peak {float(eplus_peak_kw):.0f} kW",
            annotation_position="top left",
        )
    fig.update_layout(
        title=title,
        xaxis_title="Local day",
        yaxis_title="Daily peak kW",
        template="plotly_white",
        height=340,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=48, b=36),
    )
    return fig


def dsm_panel_figure(
    df: pd.DataFrame,
    *,
    title: str,
    ycol: str,
    name: str,
    color: str,
    oat_col: str | None = None,
    oat_name: str = "OAT °F",
) -> go.Figure:
    """One-series kW panel (Actual or E+) with optional OAT on y2."""
    fig = go.Figure()
    if df is None or getattr(df, "empty", True) or ycol not in df.columns:
        fig.update_layout(title=title, template="plotly_white", height=320)
        return fig
    if "hod" in df.columns:
        hours = df["hod"]
    elif "step" in df.columns:
        hours = df["step"].to_numpy(dtype=float) / 4.0
    else:
        hours = list(range(len(df)))
    fig.add_trace(
        go.Scatter(x=hours, y=df[ycol], name=name, line=dict(color=color, width=2.2))
    )
    if oat_col and oat_col in df.columns and df[oat_col].notna().any():
        fig.add_trace(
            go.Scatter(
                x=hours,
                y=df[oat_col],
                name=oat_name,
                yaxis="y2",
                line=dict(color="#e76f51", width=1.5, dash="dash"),
            )
        )
        fig.update_layout(yaxis2=dict(title="OAT °F", overlaying="y", side="right"))
    fig.update_layout(
        title=title,
        xaxis_title="Hour (local)",
        yaxis_title="kW",
        template="plotly_white",
        height=320,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        margin=dict(t=48, b=36),
    )
    return fig
