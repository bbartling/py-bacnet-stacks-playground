"""Plotly charts for Streamlit demo — unit-separated panels + fault bool + PNG download."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.rules.base import RuleResult
from app.units import resolve_role_unit, unit_family


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
    cfg = {
        "displaylogo": False,
        "toImageButtonOptions": {
            "format": fmt,
            "filename": filename,
            "height": None,
            "width": None,
            "scale": 2,
        },
    }
    return cfg


def _series_unit(name: str, units_map: dict[str, str] | None) -> str:
    # name may be "sat (°F)" already — strip
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
    """Multi-row figure: one subplot per unit family, plus a dedicated confirmed-fault bool row.

    Never mixes °F with % / cfm / in.w.c. on the same y-axis.
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

    # Group series by unit family
    groups: dict[str, list[tuple[str, pd.Series, str]]] = {}
    for name, s in series.items():
        unit = _series_unit(name, units_map)
        fam = unit_family(unit) if unit else "other:unknown"
        # bool-like series go to their own family, not with temps
        if unit in {"bool", "0/1"} or set(pd.Series(s).dropna().unique().tolist()).issubset({0, 1, True, False}):
            if str(s.dtype) == "bool" or set(pd.Series(s).dropna().astype(float).unique().tolist()).issubset({0.0, 1.0}):
                if name.lower() in {"fan_status", "occ_mode"} or unit == "bool":
                    fam = "bool"
                    unit = "bool"
        groups.setdefault(fam, []).append((name, s, unit or ""))

    # Stable order: temp, pct, static, flow, bool-ish, other — then fault row
    order_pref = ["temp_F", "pct", "static", "flow", "bool"]
    fam_keys = [k for k in order_pref if k in groups] + sorted(
        k for k in groups if k not in order_pref
    )

    n_data = len(fam_keys)
    n_rows = n_data + (1 if fault is not None else 0)
    if n_rows == 0:
        return None

    row_titles: list[str] = []
    for fam in fam_keys:
        units_in = sorted({u for _, _, u in groups[fam] if u})
        label = ", ".join(units_in) if units_in else fam
        row_titles.append(label)
    if fault is not None:
        row_titles.append("confirmed fault (bool)")

    fig = make_subplots(
        rows=n_rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.10 if n_rows < 4 else 0.08,
        subplot_titles=row_titles,
        row_heights=[1.0] * n_data + ([0.45] if fault is not None else []),
    )

    colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2", "#a16207"]
    for row_i, fam in enumerate(fam_keys, start=1):
        for j, (name, s, unit) in enumerate(groups[fam]):
            aligned = s.reindex(df.index)
            label = f"{name} ({unit})" if unit else name
            fig.add_trace(
                go.Scatter(
                    x=aligned.index,
                    y=aligned,
                    name=label,
                    line=dict(color=colors[j % len(colors)], width=1.5),
                    legendgroup=fam,
                ),
                row=row_i,
                col=1,
            )
        if groups[fam] and groups[fam][0][2]:
            fig.update_yaxes(title_text=groups[fam][0][2], row=row_i, col=1)

    if fault is not None:
        mask = fault.reindex(df.index).fillna(False).astype(bool)
        fig.add_trace(
            go.Scatter(
                x=mask.index,
                y=mask.astype(int),
                name="confirmed_fault",
                line=dict(color="rgba(220,38,38,0.85)", width=1.5, shape="hv"),
                fill="tozeroy",
                fillcolor="rgba(220,38,38,0.15)",
                legendgroup="fault",
            ),
            row=n_rows,
            col=1,
        )
        fig.update_yaxes(title_text="0/1", range=[-0.05, 1.15], row=n_rows, col=1, dtick=1)

    fig.update_layout(
        title=None,
        height=max(280, 200 * n_rows + 100),
        margin=dict(l=56, r=24, t=36, b=72),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.12,
            x=0,
            bgcolor="rgba(255,255,255,0.85)",
        ),
        hovermode="x unified",
        template="plotly_white",
    )
    fig.update_xaxes(title_text="timestamp", row=n_rows, col=1)
    # Keep subplot titles from colliding with traces
    fig.update_annotations(font_size=11)
    return fig
