"""Plotly charts — multi-axis single figure, rainbow series colors, fault swim lane."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from app.rules.base import RuleResult
from app.units import resolve_role_unit, unit_family


# Distinct rainbow palette (cycle globally across series so plots don't collapse to blue/red).
RAINBOW_PALETTE: list[str] = [
    "#e11d48",  # rose
    "#ea580c",  # orange
    "#ca8a04",  # gold
    "#16a34a",  # green
    "#0d9488",  # teal
    "#2563eb",  # blue
    "#7c3aed",  # violet
    "#db2777",  # pink
    "#0891b2",  # cyan
    "#65a30d",  # lime
    "#9333ea",  # purple
    "#dc2626",  # red
]


PLOTLY_DOWNLOAD_CONFIG: dict[str, Any] = {
    "displaylogo": False,
    "toImageButtonOptions": {
        "format": "png",
        "filename": "open_fdd_vibe_coder_plot",
        "height": None,
        "width": None,
        "scale": 2,
    },
}


def plotly_config(*, filename: str = "open_fdd_vibe_coder_plot", fmt: str = "png") -> dict[str, Any]:
    return {
        "displaylogo": False,
        "toImageButtonOptions": {
            "format": fmt,
            "filename": filename,
            "height": None,
            "width": None,
            "scale": 2,
        },
    }


def _series_unit(name: str, units_map: dict[str, str] | None) -> str:
    role = name.split(" (", 1)[0].strip()
    return resolve_role_unit(role, units_map)


def rule_plot_series(
    df: pd.DataFrame,
    result: RuleResult,
    *,
    required_roles: list[str] | None = None,
) -> dict[str, pd.Series]:
    """Collect numeric series for a rule: explicit plot_series, else required roles on df."""
    series: dict[str, pd.Series] = {}
    if result.plot_series:
        for k, s in result.plot_series.items():
            if s is not None and getattr(s, "notna", None) and s.notna().any():
                series[str(k)] = s
    roles = required_roles or []
    for role in roles:
        if role in series:
            continue
        if role in df.columns and df[role].notna().any():
            series[role] = df[role]
    if not series:
        for col in ("zone_t", "sat", "sat_sp", "oa_t", "mat", "rat", "oa_damper_pct", "fan_cmd", "duct_static"):
            if col in df.columns and df[col].notna().any():
                series[col] = df[col]
    return series


def rule_result_chart(
    df: pd.DataFrame,
    result: RuleResult,
    *,
    required_roles: list[str] | None = None,
    units_map: dict[str, str] | None = None,
) -> go.Figure | None:
    """One figure: each unit family on its own y-axis domain; confirmed fault as shaded swim lane.

    Series colors walk a rainbow palette (global index) so traces stay visually distinct.
    """
    if result.confirmed_fault is None and result.status in {
        "SKIPPED_MISSING_ROLES",
        "SKIPPED_EQUIPMENT_OFF",
        "NOT_APPLICABLE_EQUIPMENT_TYPE",
        "ERROR",
    }:
        return None

    series = rule_plot_series(df, result, required_roles=required_roles)
    fault = result.confirmed_fault
    if fault is None and not series:
        return None

    groups: dict[str, list[tuple[str, pd.Series, str]]] = {}
    for name, s in series.items():
        unit = _series_unit(name, units_map)
        fam = unit_family(unit) if unit else f"other:{name}"
        if unit in {"bool", "0/1"}:
            fam = "bool"
        groups.setdefault(fam, []).append((name, s, unit or fam))

    order_pref = ["temp_F", "pct", "static", "flow", "bool"]
    fam_keys = [k for k in order_pref if k in groups] + sorted(k for k in groups if k not in order_pref)

    n_sig = len(fam_keys)
    has_fault = fault is not None
    n_rows = n_sig + (1 if has_fault else 0)
    if n_rows == 0:
        return None

    # Domain layout (top → bottom): signal lanes then fault swim lane
    fault_w = 0.55 if has_fault else 0.0
    sig_w = max(n_sig, 1)
    total_w = sig_w + fault_w
    usable = 0.88
    gap = 0.02
    domains: list[tuple[float, float]] = []
    top = 1.0
    for _ in range(n_sig):
        h = usable * (1.0 / total_w)
        domains.append((max(0.0, top - h), top))
        top = top - h - gap
    fault_domain = None
    if has_fault:
        h = usable * (fault_w / total_w)
        fault_domain = (max(0.0, top - h), top)

    fig = go.Figure()
    layout_axes: dict[str, Any] = {}
    color_i = 0
    last_y = "y"

    for i, fam in enumerate(fam_keys):
        axis_i = i + 1
        yname = "y" if axis_i == 1 else f"y{axis_i}"
        last_y = yname
        y0, y1 = domains[i]
        units_in = sorted({u for _, _, u in groups[fam] if u})
        title = ", ".join(units_in) if units_in else fam
        ax_key = "yaxis" if axis_i == 1 else f"yaxis{axis_i}"
        layout_axes[ax_key] = dict(
            domain=list(domains[i]),
            title=dict(text=title, font=dict(size=11)),
            showgrid=True,
            zeroline=False,
            anchor="x",
        )
        for name, s, unit in groups[fam]:
            aligned = s.reindex(df.index)
            label = f"{name} ({unit})" if unit else name
            color = RAINBOW_PALETTE[color_i % len(RAINBOW_PALETTE)]
            color_i += 1
            fig.add_trace(
                go.Scatter(
                    x=aligned.index,
                    y=aligned,
                    name=label,
                    mode="lines",
                    line=dict(color=color, width=1.6),
                    yaxis=yname,
                    connectgaps=False,
                )
            )

    if has_fault and fault_domain is not None:
        axis_i = n_sig + 1
        yname = "y" if axis_i == 1 else f"y{axis_i}"
        last_y = yname
        ax_key = "yaxis" if axis_i == 1 else f"yaxis{axis_i}"
        layout_axes[ax_key] = dict(
            domain=list(fault_domain),
            title=dict(text="fault", font=dict(size=11)),
            range=[-0.05, 1.15],
            tickvals=[0, 1],
            ticktext=["ok", "fault"],
            showgrid=True,
            anchor="x",
        )
        mask = fault.reindex(df.index).fillna(False).astype(bool)
        fig.add_trace(
            go.Scatter(
                x=mask.index,
                y=mask.astype(int),
                name="confirmed_fault",
                mode="lines",
                line=dict(color="rgba(220,38,38,0.9)", width=0.8, shape="hv"),
                fill="tozeroy",
                fillcolor="rgba(239,68,68,0.35)",
                yaxis=yname,
            )
        )

    fig.update_layout(
        title=None,
        height=max(320, 90 * n_sig + (90 if has_fault else 0) + 80),
        margin=dict(l=64, r=24, t=28, b=64),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(size=10)),
        hovermode="x unified",
        template="plotly_white",
        xaxis=dict(anchor=last_y, title="timestamp", showgrid=True),
        **layout_axes,
    )
    return fig


def multi_equipment_timeseries(
    series_map: dict[str, pd.Series],
    *,
    title: str,
    y_title: str = "",
    outlier_ids: set[str] | None = None,
) -> go.Figure | None:
    """Overlay many equipment series; outliers get a thicker dashed red-ish stroke."""
    if not series_map:
        return None
    outliers = outlier_ids or set()
    fig = go.Figure()
    color_i = 0
    for eq_id, s in sorted(series_map.items()):
        num = pd.to_numeric(s, errors="coerce")
        is_out = eq_id in outliers
        color = "#dc2626" if is_out else RAINBOW_PALETTE[color_i % len(RAINBOW_PALETTE)]
        if not is_out:
            color_i += 1
        fig.add_trace(
            go.Scatter(
                x=num.index,
                y=num,
                name=f"{eq_id}{' ★' if is_out else ''}",
                mode="lines",
                line=dict(color=color, width=2.4 if is_out else 1.4, dash="dash" if is_out else "solid"),
                connectgaps=False,
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="timestamp",
        yaxis_title=y_title,
        template="plotly_white",
        height=max(360, 40 + 18 * min(len(series_map), 20)),
        legend=dict(orientation="h", y=1.12, font=dict(size=10)),
        margin=dict(l=50, r=20, t=60, b=50),
        hovermode="x unified",
    )
    return fig


def multi_equipment_box(
    series_map: dict[str, pd.Series],
    *,
    title: str,
    y_title: str = "",
    outlier_ids: set[str] | None = None,
) -> go.Figure | None:
    if not series_map:
        return None
    outliers = outlier_ids or set()
    fig = go.Figure()
    for i, (eq_id, s) in enumerate(sorted(series_map.items())):
        num = pd.to_numeric(s, errors="coerce").dropna()
        if num.empty:
            continue
        is_out = eq_id in outliers
        fig.add_trace(
            go.Box(
                y=num,
                name=f"{eq_id}{' ★' if is_out else ''}",
                marker_color="#dc2626" if is_out else RAINBOW_PALETTE[i % len(RAINBOW_PALETTE)],
                boxpoints="outliers",
            )
        )
    fig.update_layout(
        title=title,
        yaxis_title=y_title,
        template="plotly_white",
        height=420,
        showlegend=True,
        margin=dict(l=50, r=20, t=60, b=50),
    )
    return fig


def oat_scatter(
    long_df: pd.DataFrame,
    *,
    title: str,
    x_title: str = "Web OAT °F",
    y_title: str = "",
) -> go.Figure | None:
    if long_df is None or long_df.empty:
        return None
    fig = go.Figure()
    for i, eq_id in enumerate(sorted(long_df["equipment_id"].unique())):
        sub = long_df[long_df["equipment_id"] == eq_id]
        # downsample for plot speed
        if len(sub) > 4000:
            sub = sub.iloc[:: max(1, len(sub) // 4000)]
        fig.add_trace(
            go.Scatter(
                x=sub["oat"],
                y=sub["y"],
                name=str(eq_id),
                mode="markers",
                marker=dict(size=4, opacity=0.45, color=RAINBOW_PALETTE[i % len(RAINBOW_PALETTE)]),
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis_title=y_title,
        template="plotly_white",
        height=420,
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=50, r=20, t=60, b=50),
    )
    return fig


def motor_weekly_runtime_chart(
    weekly_df: pd.DataFrame,
    *,
    title: str = "Motor run hours by week (full dataset)",
) -> go.Figure | None:
    """Grouped bar chart: run hours per week for each motor (equipment · signal)."""
    if weekly_df is None or weekly_df.empty:
        return None
    fig = go.Figure()
    labels = list(weekly_df.sort_values(["motor_kind", "label"])["label"].unique())
    weeks = (
        weekly_df[["week_start", "week_label"]]
        .drop_duplicates()
        .sort_values("week_start")
    )
    week_labels = list(weeks["week_label"])
    for i, lab in enumerate(labels):
        sub = weekly_df.loc[weekly_df["label"] == lab, ["week_label", "hours"]].drop_duplicates(
            "week_label", keep="last"
        )
        by_week = dict(zip(sub["week_label"], sub["hours"]))
        y = [float(by_week.get(w, 0.0)) for w in week_labels]
        fig.add_trace(
            go.Bar(
                x=week_labels,
                y=y,
                name=str(lab),
                marker_color=RAINBOW_PALETTE[i % len(RAINBOW_PALETTE)],
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Week starting (Mon)",
        yaxis_title="Run hours",
        barmode="group",
        template="plotly_white",
        height=max(420, 60 + 18 * min(len(labels), 12)),
        legend=dict(orientation="h", y=1.14, font=dict(size=10)),
        margin=dict(l=50, r=20, t=80, b=80),
        xaxis=dict(tickangle=-45),
    )
    return fig


def mech_cooling_oat_histogram(bins_df: pd.DataFrame) -> go.Figure | None:
    """Grouped bar histogram: mechanical cooling run hours by OAT 5°F bin."""
    if bins_df is None or bins_df.empty:
        return None
    fig = go.Figure()
    sources = list(bins_df["source"].unique())
    for i, src in enumerate(sources):
        sub = bins_df[bins_df["source"] == src]
        fig.add_trace(
            go.Bar(
                x=sub["bin_label"],
                y=sub["hours"],
                name=str(src),
                marker_color=RAINBOW_PALETTE[i % len(RAINBOW_PALETTE)],
            )
        )
    fig.update_layout(
        title="Mechanical cooling run hours by outdoor-air temperature (5°F bins)",
        xaxis_title="OAT bin °F",
        yaxis_title="Run hours",
        barmode="group",
        template="plotly_white",
        height=420,
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=50, r=20, t=60, b=50),
    )
    return fig
