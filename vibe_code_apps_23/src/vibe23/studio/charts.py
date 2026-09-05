"""Plotly figures for the residential DSM Streamlit studio."""
from __future__ import annotations

import math
from typing import Sequence

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def _hours(n: int) -> list[float]:
    return [i * 24.0 / n for i in range(n)]


def playback_figure(
    *,
    hours: Sequence[float],
    house_kw: Sequence[float],
    purchased_kw: Sequence[float] | None,
    temp_f: Sequence[float],
    price: Sequence[float],
    soc_pct: Sequence[float] | None,
    cumulative_house_kwh: Sequence[float],
    cumulative_purchased_kwh: Sequence[float] | None,
    step: int,
    title: str,
) -> go.Figure:
    rows = 4 if soc_pct is not None else 3
    specs = [[{"secondary_y": True}], [{"secondary_y": False}], [{"secondary_y": False}]]
    row_titles = ["Power (kW) / TOU price", "Cumulative energy (kWh)", "Zone °F"]
    if soc_pct is not None:
        specs.append([{"secondary_y": False}])
        row_titles.append("Battery SOC %")
    fig = make_subplots(
        rows=rows,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        specs=specs,
        subplot_titles=tuple(row_titles),
    )
    end = max(1, min(step + 1, len(hours)))
    x = list(hours[:end])

    fig.add_trace(
        go.Scatter(x=x, y=list(house_kw[:end]), name="House kW", line=dict(color="#8FB8FF", width=2)),
        row=1,
        col=1,
        secondary_y=False,
    )
    if purchased_kw is not None:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=list(purchased_kw[:end]),
                name="Purchased kW",
                line=dict(color="#3DDC97", width=2),
            ),
            row=1,
            col=1,
            secondary_y=False,
        )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=list(price[:end]),
            name="TOU $/kWh",
            line=dict(color="#E8A838", width=1.5, dash="dot"),
        ),
        row=1,
        col=1,
        secondary_y=True,
    )

    fig.add_trace(
        go.Scatter(
            x=x,
            y=list(cumulative_house_kwh[:end]),
            name="House kWh (cum)",
            line=dict(color="#8FB8FF", width=2),
        ),
        row=2,
        col=1,
    )
    if cumulative_purchased_kwh is not None:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=list(cumulative_purchased_kwh[:end]),
                name="Purchased kWh (cum)",
                line=dict(color="#3DDC97", width=2),
            ),
            row=2,
            col=1,
        )

    fig.add_trace(
        go.Scatter(x=x, y=list(temp_f[:end]), name="Zone °F", line=dict(color="#FF6B6B", width=2)),
        row=3,
        col=1,
    )
    if soc_pct is not None:
        fig.add_trace(
            go.Scatter(
                x=x,
                y=list(soc_pct[:end]),
                name="SOC %",
                fill="tozeroy",
                line=dict(color="#F4D35E", width=2),
            ),
            row=4,
            col=1,
        )
        fig.update_yaxes(range=[0, 100], row=4, col=1, title_text="SOC %")

    t_now = hours[min(step, len(hours) - 1)]
    for r in range(1, rows + 1):
        fig.add_vline(x=t_now, line_width=1, line_dash="dash", line_color="#64748B", row=r, col=1)

    fig.update_yaxes(title_text="kW", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="$/kWh", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="kWh", row=2, col=1)
    fig.update_yaxes(title_text="°F", row=3, col=1)
    fig.update_xaxes(title_text="Hour of day", row=rows, col=1)
    fig.update_layout(
        title=title,
        height=640 if soc_pct is not None else 560,
        margin=dict(l=40, r=20, t=50, b=30),
        legend=dict(orientation="h", y=1.14),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(241,245,249,0.9)",
        font=dict(color="#1B2430"),
    )
    return fig


def cost_bar_figure(labels: Sequence[str], costs: Sequence[float], *, title: str) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Bar(
                x=list(labels),
                y=list(costs),
                marker_color=["#6B7280", "#2563EB", "#D97706", "#059669"][: len(labels)],
                text=[f"${c:.2f}" for c in costs],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title=title,
        yaxis_title="Illustrative $/day",
        height=280,
        margin=dict(l=40, r=20, t=50, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(241,245,249,0.9)",
        font=dict(color="#1B2430"),
    )
    return fig


def kwh_bar_figure(labels: Sequence[str], kwhs: Sequence[float], *, title: str) -> go.Figure:
    fig = go.Figure(
        data=[
            go.Bar(
                x=list(labels),
                y=list(kwhs),
                marker_color=["#6B7280", "#2563EB", "#D97706", "#059669"][: len(labels)],
                text=[f"{v:.1f} kWh" for v in kwhs],
                textposition="outside",
            )
        ]
    )
    fig.update_layout(
        title=title,
        yaxis_title="Daily energy (kWh)",
        height=280,
        margin=dict(l=40, r=20, t=50, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(241,245,249,0.9)",
        font=dict(color="#1B2430"),
    )
    return fig


def hour_axis(n: int) -> list[float]:
    return _hours(n)


def chart_layout(*, theme: str = "light") -> dict:
    dark = theme == "dark"
    return {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(26,35,50,0.35)" if dark else "rgba(241,245,249,0.9)",
        "font": {"color": "#E7ECF3" if dark else "#1B2430"},
        "legend": {"orientation": "h", "y": 1.12},
        "margin": dict(l=48, r=56, t=56, b=40),
        "autosize": True,
    }


def outdoor_kwh_cost_figure(
    *,
    hourly_kwh: Sequence[float],
    outdoor_f: Sequence[float],
    hourly_cost: Sequence[float],
    title: str,
    theme: str = "light",
):
    """Static 24-hour plot (does not follow the playhead).

    Top: house kWh/hour (left) and illustrative $/hour (right).
    Bottom: outdoor dry-bulb °F used by the weather file for this extreme day.
    """
    hours = list(range(24))
    dark = theme == "dark"
    kwh_color = "#2563EB" if not dark else "#8FB8FF"
    temp_color = "#B91C1C" if not dark else "#FF6B6B"
    cost_color = "#B45309" if not dark else "#E8A838"
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        specs=[[{"secondary_y": True}], [{"secondary_y": False}]],
        subplot_titles=("Hourly energy and illustrative cost", "Outdoor dry-bulb (weather file)"),
    )
    fig.add_trace(
        go.Scatter(x=hours, y=list(hourly_kwh), name="House kWh / hour", line=dict(color=kwh_color, width=2.5)),
        row=1,
        col=1,
        secondary_y=False,
    )
    fig.add_trace(
        go.Scatter(
            x=hours,
            y=list(hourly_cost),
            name="Illustrative $ / hour",
            line=dict(color=cost_color, width=2, dash="dot"),
        ),
        row=1,
        col=1,
        secondary_y=True,
    )
    fig.add_trace(
        go.Scatter(x=hours, y=list(outdoor_f), name="Outdoor °F", line=dict(color=temp_color, width=2.5), fill="tozeroy"),
        row=2,
        col=1,
    )
    layout = chart_layout(theme=theme)
    fig.update_layout(title=title, height=420, **{k: v for k, v in layout.items() if k != "margin"})
    fig.update_yaxes(title_text="kWh / hour", row=1, col=1, secondary_y=False)
    fig.update_yaxes(title_text="$ / hour", row=1, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Outdoor °F", row=2, col=1)
    fig.update_xaxes(title_text="Hour of day", row=2, col=1, dtick=2)
    return fig


def search_progress_ring(
    fraction: float,
    *,
    label: str,
    sublabel: str = "",
    theme: str = "light",
) -> go.Figure:
    """Clock-face donut: sweeps clockwise from 0→100% as candidates are evaluated."""
    frac = max(0.0, min(1.0, float(fraction)))
    done = max(frac, 1e-9)
    remaining = max(1.0 - frac, 1e-9)
    dark = theme == "dark"
    done_color = "#2563EB" if not dark else "#8FB8FF"
    rest_color = "#E2E8F0" if not dark else "#334155"
    fig = go.Figure(
        data=[
            go.Pie(
                values=[done, remaining],
                labels=["done", "remaining"],
                hole=0.72,
                sort=False,
                direction="clockwise",
                rotation=90,
                marker=dict(colors=[done_color, rest_color], line=dict(width=0)),
                textinfo="none",
                hoverinfo="skip",
                showlegend=False,
            )
        ]
    )
    layout = chart_layout(theme=theme)
    fig.update_layout(
        title=None,
        height=280,
        margin=dict(l=20, r=20, t=20, b=20),
        paper_bgcolor=layout["paper_bgcolor"],
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[
            dict(
                text=f"<b>{100.0 * frac:.0f}%</b><br>{label}",
                x=0.5,
                y=0.52,
                showarrow=False,
                font=dict(size=18, color=layout["font"]["color"]),
                align="center",
            ),
            dict(
                text=sublabel,
                x=0.5,
                y=0.32,
                showarrow=False,
                font=dict(size=12, color="#64748B" if not dark else "#94A3B8"),
                align="center",
            ),
        ],
    )
    return fig


def search_convergence_figure(
    *,
    costs: Sequence[float | None],
    best_so_far: Sequence[float | None],
    current_index: int,
    rejected_indices: Sequence[int] | None = None,
    title: str = "Search convergence",
    theme: str = "light",
) -> go.Figure:
    """Cost per candidate + monotone best-so-far line (search axis, not clock)."""
    dark = theme == "dark"
    xs = list(range(1, len(costs) + 1))
    cost_color = "#B45309" if not dark else "#E8A838"
    best_color = "#2563EB" if not dark else "#8FB8FF"
    reject_color = "#B91C1C" if not dark else "#FF6B6B"
    fig = go.Figure()
    y_cost = [None if v is None or not math.isfinite(float(v)) else float(v) for v in costs]
    y_best = [None if v is None or not math.isfinite(float(v)) else float(v) for v in best_so_far]
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=y_cost,
            mode="lines+markers",
            name="Candidate $/day",
            line=dict(color=cost_color, width=2),
            marker=dict(size=8),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=y_best,
            mode="lines+markers",
            name="Best so far",
            line=dict(color=best_color, width=2.5),
            marker=dict(size=7),
        )
    )
    rejected = set(rejected_indices or [])
    if rejected:
        rx = [i + 1 for i in range(len(costs)) if i in rejected]
        ry = [0.0 for _ in rx]
        # Place reject markers at the current y-range mid if costs exist.
        finite = [float(v) for v in y_cost if v is not None]
        y_mark = (min(finite) if finite else 0.0)
        ry = [y_mark for _ in rx]
        fig.add_trace(
            go.Scatter(
                x=rx,
                y=ry,
                mode="markers",
                name="Rejected",
                marker=dict(symbol="x", size=12, color=reject_color),
            )
        )
    if 0 <= current_index < len(costs):
        fig.add_vline(x=current_index + 1, line_dash="dash", line_color="#94A3B8")
    layout = chart_layout(theme=theme)
    fig.update_layout(
        title=title,
        height=320,
        xaxis_title="Candidate (enumeration order)",
        yaxis_title="Illustrative $/day",
        **{k: v for k, v in layout.items() if k != "margin"},
        margin=dict(l=48, r=24, t=48, b=48),
    )
    return fig


def qtable_heatmap_figure(
    *,
    pre_centers: Sequence[float],
    event_centers: Sequence[float],
    costs: Sequence[Sequence[float | None]],
    current: tuple[float, float] | None = None,
    best: tuple[float, float] | None = None,
    title: str = "Grid flex Q-table ($/day)",
    theme: str = "light",
) -> go.Figure:
    """Heatmap of purchased-grid $/day keyed by pre/event center setpoints."""
    dark = theme == "dark"
    z: list[list[float | None]] = [list(row) for row in costs]
    text = [
        ["" if v is None or not math.isfinite(float(v)) else f"{float(v):.2f}" for v in row]
        for row in z
    ]
    # Plotly heatmap: None shows as missing; use nan for rejected.
    z_plot: list[list[float]] = []
    for row in z:
        z_plot.append(
            [float("nan") if v is None or not math.isfinite(float(v)) else float(v) for v in row]
        )
    fig = go.Figure(
        data=[
            go.Heatmap(
                z=z_plot,
                x=[f"{v:g}" for v in event_centers],
                y=[f"{v:g}" for v in pre_centers],
                colorscale="YlGnBu_r",
                colorbar=dict(title="$/day"),
                hovertemplate="pre %{y}°F · event %{x}°F<br>$%{z:.2f}<extra></extra>",
                text=text,
                texttemplate="%{text}",
                textfont=dict(size=9),
            )
        ]
    )
    layout = chart_layout(theme=theme)
    fig.update_layout(
        title=title,
        height=520,
        xaxis_title="Event center °F",
        yaxis_title="Pre-window center °F",
        **{k: v for k, v in layout.items() if k != "margin"},
        margin=dict(l=64, r=24, t=56, b=56),
    )
    if current is not None and current[0] in tuple(pre_centers) and current[1] in tuple(event_centers):
        fig.add_annotation(
            x=f"{current[1]:g}",
            y=f"{current[0]:g}",
            text="◉",
            showarrow=False,
            font=dict(size=16, color="#DC2626"),
        )
    if best is not None:
        fig.add_annotation(
            x=f"{best[1]:g}",
            y=f"{best[0]:g}",
            text="★",
            showarrow=False,
            font=dict(size=16, color="#B45309" if not dark else "#E8A838"),
        )
    return fig
