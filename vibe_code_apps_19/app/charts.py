"""Plotly charts — multi-axis single figure, rainbow series colors, fault swim lane.

Large historian traces are **downsampled for rendering only** (default ~5k points via
``VIBE19_MAX_PLOT_POINTS``). Full-resolution data stays in rule results / exports.
"""

from __future__ import annotations

import os
from typing import Any, Iterable

import numpy as np
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


DEFAULT_MAX_PLOT_POINTS = 5000


def max_plot_points() -> int:
    """Max samples sent to Plotly per trace (env ``VIBE19_MAX_PLOT_POINTS``, default 5000)."""
    raw = (os.environ.get("VIBE19_MAX_PLOT_POINTS") or "").strip()
    if not raw:
        return DEFAULT_MAX_PLOT_POINTS
    try:
        n = int(raw)
    except ValueError:
        return DEFAULT_MAX_PLOT_POINTS
    return max(64, n)


def _transition_positions(mask: pd.Series | np.ndarray | None, n: int) -> list[int]:
    if mask is None or n < 2:
        return []
    arr = np.asarray(mask, dtype=bool).ravel()
    if arr.size != n:
        return []
    # indices where value changes vs previous
    changes = np.flatnonzero(arr[1:] != arr[:-1]) + 1
    return [int(i) for i in changes.tolist()]


def select_plot_positions(
    n: int,
    max_points: int | None = None,
    *,
    prefer: Iterable[int] | None = None,
) -> np.ndarray:
    """Deterministic iloc positions: always first/last; prefer fault edges; fill evenly.

    Used only for Plotly payloads — never for rule math.
    """
    if n <= 0:
        return np.array([], dtype=int)
    cap = int(max_points if max_points is not None else max_plot_points())
    if n <= cap:
        return np.arange(n, dtype=int)

    chosen: set[int] = {0, n - 1}
    if prefer:
        for i in prefer:
            ii = int(i)
            if 0 <= ii < n:
                chosen.add(ii)

    # Even grid fill
    grid = np.linspace(0, n - 1, num=cap, dtype=float)
    for g in grid:
        chosen.add(int(round(g)))

    # If still over cap (many transitions), keep ends + evenly thinned prefer set
    if len(chosen) > cap:
        prefs = sorted(i for i in chosen if i not in (0, n - 1))
        keep_pref = max(0, cap - 2)
        if keep_pref == 0:
            chosen = {0, n - 1}
        else:
            step = max(1, len(prefs) // keep_pref)
            thinned = prefs[::step][:keep_pref]
            chosen = {0, n - 1, *thinned}

    # Top up with linspace if under cap
    while len(chosen) < cap:
        for g in np.linspace(0, n - 1, num=cap * 2, dtype=float):
            chosen.add(int(round(g)))
            if len(chosen) >= cap:
                break
        break

    return np.array(sorted(chosen)[:cap], dtype=int)


def downsample_series_for_plot(
    s: pd.Series,
    *,
    max_points: int | None = None,
    prefer_index: pd.Index | None = None,
    fault_mask: pd.Series | None = None,
) -> pd.Series:
    """Return a shorter series for Plotly; preserves first/last and optional fault edges."""
    if s is None or len(s) == 0:
        return s
    n = len(s)
    cap = int(max_points if max_points is not None else max_plot_points())
    if n <= cap:
        return s

    prefer: list[int] = []
    if fault_mask is not None:
        prefer.extend(_transition_positions(fault_mask.reindex(s.index).fillna(False), n))
    if prefer_index is not None and len(prefer_index):
        # map preferred timestamps to positions when possible
        try:
            pos = s.index.get_indexer(prefer_index)
            prefer.extend(int(p) for p in pos if p >= 0)
        except Exception:
            pass

    iloc = select_plot_positions(n, cap, prefer=prefer)
    return s.iloc[iloc]


def downsample_frame_index(
    index: pd.Index,
    *,
    max_points: int | None = None,
    fault_mask: pd.Series | None = None,
) -> pd.Index:
    """Shared index downsample for multi-trace alignment on one chart."""
    n = len(index)
    cap = int(max_points if max_points is not None else max_plot_points())
    if n <= cap:
        return index
    prefer = _transition_positions(
        fault_mask.reindex(index).fillna(False) if fault_mask is not None else None,
        n,
    )
    iloc = select_plot_positions(n, cap, prefer=prefer)
    return index[iloc]


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
    """Collect numeric series for a rule.

    Prefer **live** ``df`` columns (reflects current role_map) over baked
    ``result.plot_series`` so Data Model remaps refresh FDD Plots without
    requiring a full re-run. Baked series are kept only as fallback for
    derived / non-column keys (e.g. control-output sweeps).
    """
    series: dict[str, pd.Series] = {}
    roles = required_roles or []
    # Live columns first (mapping-aware).
    for role in roles:
        if role in df.columns and df[role].notna().any():
            series[role] = df[role]
    # Fill any live columns already present but not in required_roles.
    for col in df.columns:
        if col in series:
            continue
        if col in {
            "zone-air-temp",
            "discharge-air-temp",
            "discharge-air-temp-sp",
            "outside-air-temp",
            "web-outside-air-temp",
            "web-outside-air-dewpoint",
            "mixed-air-temp",
            "return-air-temp",
            "outside-air-damper",
            "cooling-valve",
            "heating-valve",
            "duct-static-pressure",
            "fan-cmd",
            "fan-status",
            "motor-on",
        } and df[col].notna().any():
            series[col] = df[col]
    # Baked plot_series: only for keys not already supplied by live df.
    if result.plot_series:
        for k, s in result.plot_series.items():
            key = str(k)
            if key in series:
                continue
            if s is not None and getattr(s, "notna", None) and s.notna().any():
                series[key] = s
    if not series:
        for col in (
            "zone-air-temp",
            "discharge-air-temp",
            "discharge-air-temp-sp",
            "outside-air-temp",
            "mixed-air-temp",
            "return-air-temp",
            "outside-air-damper",
            "cooling-valve",
            "heating-valve",
            "duct-static-pressure",
            "fan-cmd",
        ):
            if col in df.columns and df[col].notna().any():
                # Prefer OA damper / valves over fan-cmd for temperature-only fallbacks.
                if col == "fan-cmd" and any(
                    t in series for t in ("discharge-air-temp", "mixed-air-temp", "return-air-temp", "zone-air-temp")
                ) and "duct-static-pressure" not in series:
                    continue
                series[col] = df[col]
    return series


def rule_result_chart(
    df: pd.DataFrame,
    result: RuleResult,
    *,
    required_roles: list[str] | None = None,
    units_map: dict[str, str] | None = None,
    max_points: int | None = None,
) -> go.Figure | None:
    """One figure: each unit family on its own y-axis domain; confirmed fault as shaded swim lane.

    Series colors walk a rainbow palette (global index) so traces stay visually distinct.
    Long series are downsampled for Plotly only (see ``max_plot_points``).
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

    cap = int(max_points if max_points is not None else max_plot_points())
    plot_index = downsample_frame_index(df.index, max_points=cap, fault_mask=fault)

    groups: dict[str, list[tuple[str, pd.Series, str]]] = {}
    for name, s in series.items():
        unit = _series_unit(name, units_map)
        fam = unit_family(unit) if unit else f"other:{name}"
        if unit in {"bool", "0/1"}:
            fam = "bool"
        aligned = s.reindex(df.index).loc[plot_index]
        groups.setdefault(fam, []).append((name, aligned, unit or fam))

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
        for name, aligned, unit in groups[fam]:
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
        mask = fault.reindex(df.index).fillna(False).astype(bool).loc[plot_index]
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
    max_points: int | None = None,
    status_map: dict[str, pd.Series] | None = None,
) -> go.Figure | None:
    """Overlay many equipment series; outliers get a thicker dashed red-ish stroke.

    ``status_map`` (equipment_id → 0/1 motor/fan status) adds dotted step traces on a
    secondary right-hand axis so run status reads alongside the primary series.
    """
    if not series_map:
        return None
    outliers = outlier_ids or set()
    fig = go.Figure()
    color_i = 0
    cap = int(max_points if max_points is not None else max_plot_points())
    colors_by_eq: dict[str, str] = {}
    for eq_id, s in sorted(series_map.items()):
        num = downsample_series_for_plot(pd.to_numeric(s, errors="coerce"), max_points=cap)
        is_out = eq_id in outliers
        color = "#dc2626" if is_out else RAINBOW_PALETTE[color_i % len(RAINBOW_PALETTE)]
        colors_by_eq[eq_id] = color
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
    has_status = False
    for eq_id, s in sorted((status_map or {}).items()):
        if eq_id not in colors_by_eq:
            continue
        num = downsample_series_for_plot(pd.to_numeric(s, errors="coerce"), max_points=cap)
        if not num.notna().any():
            continue
        has_status = True
        fig.add_trace(
            go.Scatter(
                x=num.index,
                y=num,
                name=f"{eq_id} · motor on",
                mode="lines",
                line=dict(color=colors_by_eq[eq_id], width=1.0, dash="dot", shape="hv"),
                yaxis="y2",
                opacity=0.7,
                connectgaps=False,
            )
        )
    layout_extra: dict[str, Any] = {}
    if has_status:
        layout_extra["yaxis2"] = dict(
            overlaying="y",
            side="right",
            range=[-0.08, 1.4],
            tickvals=[0, 1],
            ticktext=["off", "on"],
            title=dict(text="motor on", font=dict(size=10)),
            showgrid=False,
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
        **layout_extra,
    )
    return fig


def multi_equipment_box(
    series_map: dict[str, pd.Series],
    *,
    title: str,
    y_title: str = "",
    outlier_ids: set[str] | None = None,
    max_points: int | None = None,
) -> go.Figure | None:
    if not series_map:
        return None
    outliers = outlier_ids or set()
    fig = go.Figure()
    cap = int(max_points if max_points is not None else max_plot_points())
    for i, (eq_id, s) in enumerate(sorted(series_map.items())):
        num = pd.to_numeric(s, errors="coerce").dropna()
        if num.empty:
            continue
        if len(num) > cap:
            # Uniform sample for box (stats approximate; rules/exports unchanged)
            iloc = select_plot_positions(len(num), cap)
            num = num.iloc[iloc]
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
    max_points: int | None = None,
    dry_bulb_ref: bool = False,
) -> go.Figure | None:
    if long_df is None or long_df.empty:
        return None
    fig = go.Figure()
    cap = int(max_points if max_points is not None else max_plot_points())
    for i, eq_id in enumerate(sorted(long_df["equipment_id"].unique())):
        sub = long_df[long_df["equipment_id"] == eq_id]
        if len(sub) > cap:
            iloc = select_plot_positions(len(sub), cap)
            sub = sub.iloc[iloc]
        fig.add_trace(
            go.Scatter(
                x=sub["oat"],
                y=sub["y"],
                name=str(eq_id),
                mode="markers",
                marker=dict(size=4, opacity=0.45, color=RAINBOW_PALETTE[i % len(RAINBOW_PALETTE)]),
            )
        )
        if dry_bulb_ref and "dry_bulb" in sub.columns and sub["dry_bulb"].notna().any():
            fig.add_trace(
                go.Scatter(
                    x=sub["dry_bulb"],
                    y=sub["y"],
                    name=f"{eq_id} · dry-bulb",
                    mode="markers",
                    marker=dict(
                        size=3,
                        opacity=0.25,
                        symbol="x",
                        color=RAINBOW_PALETTE[i % len(RAINBOW_PALETTE)],
                    ),
                    legendgroup=str(eq_id),
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


def monthly_energy_bar(
    monthly_df: pd.DataFrame,
    *,
    energy_col: str,
    title: str,
    y_title: str = "",
) -> go.Figure | None:
    """Grouped bars: monthly energy per equipment."""
    if monthly_df is None or monthly_df.empty or energy_col not in monthly_df.columns:
        return None
    if "month_label" not in monthly_df.columns:
        return None
    fig = go.Figure()
    months = list(monthly_df.sort_values("month")["month_label"].unique())
    for i, eq_id in enumerate(sorted(monthly_df["equipment_id"].astype(str).unique())):
        sub = monthly_df.loc[monthly_df["equipment_id"].astype(str) == eq_id]
        by_m = dict(zip(sub["month_label"], sub[energy_col]))
        fig.add_trace(
            go.Bar(
                x=months,
                y=[float(by_m.get(m, 0.0) or 0.0) for m in months],
                name=str(eq_id),
                marker_color=RAINBOW_PALETTE[i % len(RAINBOW_PALETTE)],
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Month",
        yaxis_title=y_title or energy_col,
        barmode="group",
        template="plotly_white",
        height=420,
        legend=dict(orientation="h", y=1.12),
        margin=dict(l=50, r=20, t=60, b=50),
    )
    return fig


def energy_degree_day_scatter(
    scatter_df: pd.DataFrame,
    *,
    title: str,
    x_title: str,
    y_title: str,
) -> go.Figure | None:
    """Scatter monthly energy (y) vs degree-days (x)."""
    if scatter_df is None or scatter_df.empty:
        return None
    if not {"x", "y", "equipment_id"} <= set(scatter_df.columns):
        return None
    fig = go.Figure()
    for i, eq_id in enumerate(sorted(scatter_df["equipment_id"].astype(str).unique())):
        sub = scatter_df.loc[scatter_df["equipment_id"].astype(str) == eq_id]
        fig.add_trace(
            go.Scatter(
                x=sub["x"],
                y=sub["y"],
                name=str(eq_id),
                mode="markers+text" if len(sub) <= 24 else "markers",
                text=sub["month_label"] if "month_label" in sub.columns and len(sub) <= 24 else None,
                textposition="top center",
                marker=dict(size=9, opacity=0.75, color=RAINBOW_PALETTE[i % len(RAINBOW_PALETTE)]),
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
    min_hours_line: float | None = None,
    show_avg_oat: bool = True,
) -> go.Figure | None:
    """Grouped bar chart: run hours per week; optional avg OAT (°F) on secondary axis."""
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
    if show_avg_oat and "avg_oat_f" in weekly_df.columns:
        oat_by_week = (
            weekly_df.dropna(subset=["avg_oat_f"])
            .groupby("week_label", sort=False)["avg_oat_f"]
            .mean()
        )
        oat_y = [float(oat_by_week[w]) if w in oat_by_week.index else None for w in week_labels]
        if any(v is not None for v in oat_y):
            fig.add_trace(
                go.Scatter(
                    x=week_labels,
                    y=oat_y,
                    name="Avg OAT °F (while on)",
                    mode="lines+markers",
                    yaxis="y2",
                    line=dict(color="#333333", width=2, dash="dot"),
                    marker=dict(size=7),
                )
            )
    if min_hours_line is not None and float(min_hours_line) > 0:
        fig.add_hline(
            y=float(min_hours_line),
            line_dash="dash",
            line_color="#c45c26",
            annotation_text=f"Bare-min occupied hours/week ({min_hours_line:.0f} h)",
            annotation_position="top left",
        )
    layout_kwargs: dict[str, Any] = dict(
        title=title,
        xaxis_title="Week starting (Mon)",
        yaxis_title="Run hours",
        barmode="group",
        template="plotly_white",
        height=max(420, 60 + 18 * min(len(labels), 12)),
        legend=dict(orientation="h", y=1.14, font=dict(size=10)),
        margin=dict(l=50, r=60, t=80, b=80),
        xaxis=dict(tickangle=-45),
    )
    if show_avg_oat and "avg_oat_f" in weekly_df.columns:
        layout_kwargs["yaxis2"] = dict(
            title="Avg OAT °F",
            overlaying="y",
            side="right",
            showgrid=False,
        )
    fig.update_layout(**layout_kwargs)
    return fig


def mech_cooling_oat_histogram(bins_df: pd.DataFrame) -> go.Figure | None:
    """Grouped bar histogram: mechanical cooling run hours by OAT 5°F bin (sorted cold→hot).

    Rows with ``source_kind == "total"`` (aggregated across devices) render as a
    visually distinct outlined dark bar so the aggregate is obvious next to the
    per-device breakdown.
    """
    if bins_df is None or bins_df.empty:
        return None
    df = bins_df.sort_values(["bin_start", "source"]).copy()
    order = list(df.drop_duplicates("bin_start").sort_values("bin_start")["bin_label"])
    has_kind = "source_kind" in df.columns
    is_total = df["source_kind"].eq("total") if has_kind else pd.Series(False, index=df.index)
    dev_df = df[~is_total]
    tot_df = df[is_total]
    fig = go.Figure()
    sources = list(dev_df["source"].unique())
    for i, src in enumerate(sources):
        sub = dev_df[dev_df["source"] == src]
        fig.add_trace(
            go.Bar(
                x=sub["bin_label"],
                y=sub["hours"],
                name=str(src),
                marker_color=RAINBOW_PALETTE[i % len(RAINBOW_PALETTE)],
            )
        )
    for src in tot_df["source"].unique():
        sub = tot_df[tot_df["source"] == src]
        fig.add_trace(
            go.Bar(
                x=sub["bin_label"],
                y=sub["hours"],
                name=str(src),
                marker_color="rgba(55, 65, 81, 0.55)",
                marker_line=dict(color="#111827", width=1.6),
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
        xaxis=dict(categoryorder="array", categoryarray=order),
    )
    return fig


def sensor_fault_chart(
    series: pd.Series,
    *,
    sensor_name: str,
    rule_masks: dict[str, pd.Series] | None = None,
    y_title: str | None = None,
) -> go.Figure | None:
    """Single-sensor timeseries with optional per-rule fault shading + bool lanes."""
    if series is None or len(series) == 0 or series.notna().sum() == 0:
        return None
    num = pd.to_numeric(series, errors="coerce")
    plot_index = downsample_frame_index(num.index, max_points=max_plot_points())
    y = num.reindex(plot_index)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=y.index,
            y=y,
            name=sensor_name,
            mode="lines",
            line=dict(color=RAINBOW_PALETTE[0], width=1.4),
        )
    )
    colors = {
        "SV-RANGE": "rgba(220,38,38,0.25)",
        "SV-SPIKE": "rgba(234,179,8,0.25)",
        "SV-FLATLINE": "rgba(59,130,246,0.25)",
        "SV-STALE": "rgba(168,85,247,0.25)",
        "SV-RATE": "rgba(16,185,129,0.25)",
    }
    lane_i = 0
    for rid, mask in (rule_masks or {}).items():
        if mask is None:
            continue
        m = mask.reindex(num.index).fillna(False).astype(bool).loc[plot_index]
        if not m.any():
            continue
        fig.add_trace(
            go.Scatter(
                x=m.index,
                y=m.astype(int),
                name=f"{rid} fault",
                mode="lines",
                line=dict(width=0.6, color=colors.get(rid, "rgba(239,68,68,0.8)"), shape="hv"),
                fill="tozeroy",
                fillcolor=colors.get(rid, "rgba(239,68,68,0.3)"),
                yaxis="y2",
            )
        )
        lane_i += 1
    fig.update_layout(
        title=f"Sensor health — {sensor_name}",
        template="plotly_white",
        height=420,
        margin=dict(l=50, r=20, t=50, b=40),
        yaxis=dict(title=y_title or sensor_name, domain=[0.28, 1.0] if lane_i else [0.0, 1.0]),
        yaxis2=dict(
            title="fault",
            domain=[0.0, 0.22],
            range=[-0.05, 1.05],
            tickvals=[0, 1],
            ticktext=["ok", "fault"],
            showgrid=False,
        )
        if lane_i
        else None,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def bas_vs_web_oat_overlay(
    frames: dict[str, pd.DataFrame],
    role_map: dict | None = None,
    *,
    weather: pd.DataFrame | None = None,
    oat_err: float = 5.0,
) -> go.Figure | None:
    """Overlay BAS vs web OAT on one axis with ±oat_err band and fault bool lane."""
    from app.role_map import apply_role_map

    role_map = role_map or {}
    bas_s = web_s = None
    for eq_id, raw in (frames or {}).items():
        mapped = apply_role_map(raw, eq_id, role_map)
        bas = None
        if "bas-outside-air-temp" in mapped.columns and mapped["bas-outside-air-temp"].notna().any():
            bas = pd.to_numeric(mapped["bas-outside-air-temp"], errors="coerce")
        elif "outside-air-temp" in mapped.columns and mapped["outside-air-temp"].notna().any():
            bas = pd.to_numeric(mapped["outside-air-temp"], errors="coerce")
        web = None
        if "web-outside-air-temp" in mapped.columns and mapped["web-outside-air-temp"].notna().any():
            web = pd.to_numeric(mapped["web-outside-air-temp"], errors="coerce")
        elif weather is not None and "web-outside-air-temp" in weather.columns:
            web = pd.to_numeric(weather["web-outside-air-temp"], errors="coerce").reindex(mapped.index)
        if bas is None or web is None:
            continue
        both = bas.notna() & web.notna()
        if both.sum() < 5:
            continue
        bas_s, web_s = bas, web
        break
    if bas_s is None or web_s is None:
        return None
    idx = downsample_frame_index(bas_s.index, max_points=max_plot_points())
    bas_p = bas_s.reindex(idx)
    web_p = web_s.reindex(idx)
    diff = (bas_p - web_p).abs()
    fault = diff > float(oat_err)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bas_p.index, y=bas_p, name="BAS OAT", mode="lines", line=dict(width=1.4, color=RAINBOW_PALETTE[0])))
    fig.add_trace(go.Scatter(x=web_p.index, y=web_p, name="Web dry-bulb OAT", mode="lines", line=dict(width=1.4, color=RAINBOW_PALETTE[3])))
    # Band around web: web ± oat_err
    fig.add_trace(
        go.Scatter(
            x=web_p.index,
            y=web_p + float(oat_err),
            name=f"+{oat_err:g}°F band",
            mode="lines",
            line=dict(width=0, color="rgba(0,0,0,0)"),
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=web_p.index,
            y=web_p - float(oat_err),
            name=f"±{oat_err:g}°F tolerance",
            mode="lines",
            line=dict(width=0),
            fill="tonexty",
            fillcolor="rgba(234,179,8,0.18)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=fault.index,
            y=fault.fillna(False).astype(int),
            name="OAT-METEO fault",
            mode="lines",
            line=dict(color="rgba(220,38,38,0.9)", width=0.8, shape="hv"),
            fill="tozeroy",
            fillcolor="rgba(239,68,68,0.35)",
            yaxis="y2",
        )
    )
    fig.update_layout(
        title=f"BAS vs web outdoor-air temperature (±{oat_err:g}°F band)",
        template="plotly_white",
        height=440,
        margin=dict(l=50, r=20, t=50, b=40),
        yaxis=dict(title="Temperature °F", domain=[0.28, 1.0]),
        yaxis2=dict(title="fault", domain=[0.0, 0.22], range=[-0.05, 1.05], tickvals=[0, 1], ticktext=["ok", "fault"], showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    return fig


def vav_comfort_donut(
    rank: pd.DataFrame,
    *,
    title: str = "Occupied time — comfort band",
) -> go.Figure | None:
    """Donut of aggregated in-band / too-cold / too-hot occupied samples across VAVs."""
    if rank is None or rank.empty:
        return None
    n_occ = int(rank["n_occupied"].sum()) if "n_occupied" in rank.columns else 0
    n_below = int(rank["n_below"].sum()) if "n_below" in rank.columns else 0
    n_above = int(rank["n_above"].sum()) if "n_above" in rank.columns else 0
    if n_occ <= 0:
        return None
    n_in = max(0, n_occ - n_below - n_above)
    labels = ["In band", "Too cold", "Too hot"]
    values = [n_in, n_below, n_above]
    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.45,
                marker=dict(colors=["#22c55e", "#3b82f6", "#ef4444"]),
                textinfo="label+percent",
            )
        ]
    )
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=360,
        margin=dict(l=20, r=20, t=50, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=-0.05),
    )
    return fig


def _is_status_like(series: pd.Series) -> bool:
    """True for 0/1 / boolean status traces (draw as step lines)."""
    if pd.api.types.is_bool_dtype(series):
        return True
    num = pd.to_numeric(series, errors="coerce").dropna()
    if num.empty:
        return False
    uniq = set(float(x) for x in num.unique())
    return uniq.issubset({0.0, 1.0})


def equipment_inspection_chart(
    df: pd.DataFrame,
    *,
    equipment_id: str = "",
    columns: list[str] | None = None,
    max_height: int = 4000,
    row_height: int = 160,
) -> go.Figure | None:
    """Tall stacked Plotly line chart of all plottable columns in a raw equipment CSV.

    Keeps numeric / boolean columns only. One subplot row per column, shared x-axis.
    Downsamples for rendering via :func:`downsample_frame_index`.
    """
    from plotly.subplots import make_subplots

    if df is None or df.empty:
        return None
    if columns is None:
        cols = list(df.columns)
    else:
        cols = [c for c in columns if c in df.columns]
    plot_cols: list[str] = []
    for c in cols:
        s = df[c]
        if pd.api.types.is_bool_dtype(s):
            plot_cols.append(c)
            continue
        if pd.api.types.is_numeric_dtype(s) and s.notna().any():
            plot_cols.append(c)
            continue
        # object columns that coerce cleanly to numeric
        coerced = pd.to_numeric(s, errors="coerce")
        if coerced.notna().sum() >= max(1, int(0.5 * len(s))):
            plot_cols.append(c)
    if not plot_cols:
        return None

    idx = downsample_frame_index(df.index, max_points=max_plot_points())
    n = len(plot_cols)
    height = min(max_height, max(700, int(row_height) * n + 80))
    titles = [str(c) for c in plot_cols]
    fig = make_subplots(
        rows=n,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=min(0.02, 0.5 / max(n, 1)),
        subplot_titles=titles,
    )
    for i, col in enumerate(plot_cols, start=1):
        raw = df[col]
        if pd.api.types.is_bool_dtype(raw):
            y = raw.astype(float).reindex(idx)
            step = True
        else:
            y = pd.to_numeric(raw, errors="coerce").reindex(idx)
            step = _is_status_like(raw)
        color = RAINBOW_PALETTE[(i - 1) % len(RAINBOW_PALETTE)]
        fig.add_trace(
            go.Scatter(
                x=y.index,
                y=y,
                name=str(col),
                mode="lines",
                line=dict(width=1.2, color=color, shape="hv" if step else "linear"),
                showlegend=False,
            ),
            row=i,
            col=1,
        )
        fig.update_yaxes(title_text="", row=i, col=1)
    title = f"Data inspection — {equipment_id}" if equipment_id else "Data inspection"
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=height,
        margin=dict(l=50, r=20, t=60, b=40),
        hovermode="x unified",
    )
    fig.update_xaxes(showticklabels=True, row=n, col=1)
    return fig


def bas_vs_web_oat_histogram(
    frames: dict[str, pd.DataFrame],
    role_map: dict | None = None,
    *,
    weather: pd.DataFrame | None = None,
    nbins: int = 40,
) -> go.Figure | None:
    """Histogram of BAS OAT − web OAT (°F) when both series exist.

    Prefers ``bas_oa_t`` / mapped ``oa_t`` vs ``wx_oa_t`` (frame or weather).
    """
    from app.role_map import apply_role_map

    deltas: list[float] = []
    role_map = role_map or {}
    for eq_id, raw in (frames or {}).items():
        mapped = apply_role_map(raw, eq_id, role_map)
        bas = None
        if "bas-outside-air-temp" in mapped.columns and mapped["bas-outside-air-temp"].notna().any():
            bas = pd.to_numeric(mapped["bas-outside-air-temp"], errors="coerce")
        elif "outside-air-temp" in mapped.columns and mapped["outside-air-temp"].notna().any():
            bas = pd.to_numeric(mapped["outside-air-temp"], errors="coerce")
        web = None
        if "web-outside-air-temp" in mapped.columns and mapped["web-outside-air-temp"].notna().any():
            web = pd.to_numeric(mapped["web-outside-air-temp"], errors="coerce")
        elif weather is not None and "web-outside-air-temp" in weather.columns:
            web = pd.to_numeric(weather["web-outside-air-temp"], errors="coerce").reindex(mapped.index)
        if bas is None or web is None:
            continue
        d = (bas - web).dropna()
        if not d.empty:
            deltas.extend(float(x) for x in d.tolist())
            break  # one representative equipment / aligned weather is enough for Overview
    if len(deltas) < 5:
        return None
    fig = go.Figure(
        data=[
            go.Histogram(
                x=deltas,
                nbinsx=max(10, int(nbins)),
                marker_color=RAINBOW_PALETTE[0],
                name="BAS − web °F",
            )
        ]
    )
    fig.update_layout(
        title="BAS vs web outdoor-air temperature deviation (°F)",
        xaxis_title="BAS OAT − web OAT (°F)",
        yaxis_title="Sample count",
        template="plotly_white",
        height=380,
        bargap=0.05,
        margin=dict(l=50, r=20, t=60, b=50),
    )
    return fig
