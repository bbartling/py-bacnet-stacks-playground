"""Shared Plotly charts for Site EUI vs peer bands (Fuel + Twin)."""

from __future__ import annotations

from typing import Any, Sequence


MONTH_ABBREV = (
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


def month_abbrev(mm: int | str) -> str:
    """Map month number (1–12 or '01'–'12') to Jan…Dec."""
    try:
        n = int(str(mm).strip())
    except (TypeError, ValueError):
        return str(mm)
    if 1 <= n <= 12:
        return MONTH_ABBREV[n - 1]
    return str(mm)


def month_abbrev_columns(frame_or_cols: Any) -> Any:
    """Rename DataFrame columns 1..12 (or '01'..'12') to Jan…Dec; else return as-is."""
    import pandas as pd

    if isinstance(frame_or_cols, pd.DataFrame):
        mapping = {}
        for c in frame_or_cols.columns:
            n: int | None
            if isinstance(c, (int, float)) and not isinstance(c, bool):
                n = int(c)
            else:
                s = str(c).strip()
                if s.isdigit():
                    n = int(s)
                else:
                    continue
            if 1 <= n <= 12:
                mapping[c] = month_abbrev(n)
        return frame_or_cols.rename(columns=mapping) if mapping else frame_or_cols
    return [month_abbrev(c) for c in frame_or_cols]


def plotly_layout_clean(
    fig: Any,
    *,
    title: str | None = None,
    height: int = 420,
    yaxis_title: str | None = None,
    xaxis_title: str | None = None,
) -> Any:
    """Apply consistent margins + horizontal legend above the plot (no title clash)."""
    fig.update_layout(
        height=int(height),
        margin=dict(l=64, r=24, t=72 if title else 56, b=48),
        title=dict(text=title, y=0.98, x=0.01, xanchor="left", yanchor="top") if title else None,
        yaxis_title=yaxis_title,
        xaxis_title=xaxis_title,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,
            x=0,
            xanchor="left",
            bgcolor="rgba(255,255,255,0.75)",
        ),
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(size=12),
    )
    return fig


def eui_peer_bullet_figure(
    *,
    peer_p20: float,
    peer_p50: float,
    peer_p80: float,
    series: Sequence[dict[str, Any]],
    title: str | None = None,
    height: int | None = None,
):
    """Upright peer-band chart: p20–p80 box per category + markers for Bills/Model/….

    Each item in ``series`` needs ``label`` and ``eui`` (kBtu/ft²·yr). Optional
    ``color`` (hex) and ``symbol`` (plotly marker symbol).
    """
    import plotly.graph_objects as go

    rows = [s for s in series if s.get("eui") is not None and s.get("label")]
    if not rows:
        rows = [{"label": "Same-type band only", "eui": peer_p50, "color": "#888", "symbol": "circle"}]

    labels = [str(r["label"]) for r in rows]
    n = len(labels)
    fig = go.Figure()

    # Vertical peer band + p50 tick under each category (boxplot-like upright)
    for i, _label in enumerate(labels):
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=i - 0.35,
            x1=i + 0.35,
            y0=float(peer_p20),
            y1=float(peer_p80),
            fillcolor="rgba(44,160,44,0.22)",
            line_width=0,
            layer="below",
        )
        fig.add_shape(
            type="line",
            xref="x",
            yref="y",
            x0=i - 0.35,
            x1=i + 0.35,
            y0=float(peer_p50),
            y1=float(peer_p50),
            line=dict(color="#2ca02c", width=2, dash="dash"),
            layer="below",
        )

    ys = [float(r["eui"]) for r in rows]
    colors = [str(r.get("color") or "#1f77b4") for r in rows]
    symbols = [str(r.get("symbol") or "diamond") for r in rows]
    fig.add_scatter(
        x=labels,
        y=ys,
        mode="markers+text",
        marker=dict(size=16, color=colors, symbol=symbols, line=dict(width=1, color="#333")),
        text=[f"{y:.1f}" for y in ys],
        textposition="top center",
        name="Site EUI",
        hovertemplate="%{x}: %{y:.1f} kBtu/ft²·yr<extra></extra>",
    )

    fig.add_scatter(
        x=[None],
        y=[None],
        mode="markers",
        marker=dict(size=12, color="rgba(44,160,44,0.5)", symbol="square"),
        name=f"Same-type band p20–p80 ({peer_p20:.0f}–{peer_p80:.0f})",
    )
    fig.add_scatter(
        x=[None],
        y=[None],
        mode="lines",
        line=dict(color="#2ca02c", width=2, dash="dash"),
        name=f"Typical same-type (p50={peer_p50:.1f})",
    )

    h = height or max(420, 360 + 20 * max(0, n - 2))
    plotly_layout_clean(
        fig,
        title=title,
        height=h,
        yaxis_title="Site EUI (kBtu/ft²·yr)",
        xaxis_title=None,
    )
    ymax = max(float(peer_p80), max(ys) if ys else float(peer_p80)) * 1.18
    ymin = min(0.0, float(peer_p20) * 0.85, min(ys) if ys else 0.0)
    fig.update_yaxes(range=[ymin, ymax], showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    fig.update_xaxes(
        categoryorder="array",
        categoryarray=labels,
        showgrid=False,
        automargin=True,
    )
    return fig
