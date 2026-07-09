"""Plotly charts for Streamlit demo."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.rules.base import RuleResult


def trend_chart(
    df: pd.DataFrame,
    series: dict[str, pd.Series],
    fault: pd.Series | None = None,
    title: str = "Trend",
) -> go.Figure:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    colors = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c"]
    for i, (name, s) in enumerate(series.items()):
        aligned = s.reindex(df.index)
        fig.add_trace(
            go.Scatter(x=aligned.index, y=aligned, name=name, line=dict(color=colors[i % len(colors)])),
            secondary_y=False,
        )
    if fault is not None:
        mask = fault.reindex(df.index).fillna(False).astype(bool)
        if mask.any():
            fig.add_trace(
                go.Scatter(
                    x=mask.index[mask],
                    y=[1] * int(mask.sum()),
                    mode="markers",
                    name="confirmed fault",
                    marker=dict(color="rgba(220,38,38,0.35)", size=6),
                ),
                secondary_y=True,
            )
    fig.update_layout(title=title, height=420, margin=dict(l=40, r=40, t=50, b=40), legend=dict(orientation="h"))
    fig.update_yaxes(title_text="value", secondary_y=False)
    fig.update_yaxes(title_text="fault", secondary_y=True, showgrid=False, range=[0, 1.2])
    return fig


def rule_result_chart(df: pd.DataFrame, result: RuleResult) -> go.Figure | None:
    series = dict(result.plot_series)
    if not series and result.rule_id in {"SAT-HIGH", "VAV-1", "ECON-2"}:
        for col in ("zone_t", "sat", "sat_sp", "oa_t", "oa_damper_pct", "fan_cmd"):
            if col in df.columns:
                series[col] = df[col]
    if not series:
        return None
    return trend_chart(df, series, fault=result.confirmed_fault, title=f"{result.rule_id} — {result.equipment_id}")
