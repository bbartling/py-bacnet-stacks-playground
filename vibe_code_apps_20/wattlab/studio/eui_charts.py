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


def eui_peer_bullet_figure(
    *,
    peer_p20: float,
    peer_p50: float,
    peer_p80: float,
    series: Sequence[dict[str, Any]],
    title: str | None = None,
    height: int | None = None,
):
    """Horizontal bullet/box: peer p20–p80 band + p50 tick; one Y row per series.

    Each item in ``series`` needs ``label`` and ``eui`` (kBtu/ft²·yr). Optional
    ``color`` (hex) and ``symbol`` (plotly marker symbol).
    """
    import plotly.graph_objects as go

    rows = [s for s in series if s.get("eui") is not None and s.get("label")]
    if not rows:
        rows = [{"label": "Peers only", "eui": peer_p50, "color": "#888", "symbol": "circle"}]

    labels = [str(r["label"]) for r in rows]
    n = len(labels)
    fig = go.Figure()

    # One peer band + p50 per category row (boxplot-like horizontal band)
    for i, label in enumerate(labels):
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=float(peer_p20),
            x1=float(peer_p80),
            y0=i - 0.35,
            y1=i + 0.35,
            fillcolor="rgba(44,160,44,0.22)",
            line_width=0,
            layer="below",
        )
        fig.add_shape(
            type="line",
            xref="x",
            yref="y",
            x0=float(peer_p50),
            x1=float(peer_p50),
            y0=i - 0.35,
            y1=i + 0.35,
            line=dict(color="#2ca02c", width=2, dash="dash"),
            layer="below",
        )

    xs = [float(r["eui"]) for r in rows]
    colors = [str(r.get("color") or "#1f77b4") for r in rows]
    symbols = [str(r.get("symbol") or "diamond") for r in rows]
    fig.add_scatter(
        x=xs,
        y=labels,
        mode="markers+text",
        marker=dict(size=14, color=colors, symbol=symbols, line=dict(width=1, color="#333")),
        text=[f"{x:.1f}" for x in xs],
        textposition="middle right",
        name="Site EUI",
        hovertemplate="%{y}: %{x:.1f} kBtu/ft²<extra></extra>",
    )

    # Invisible peer reference for legend clarity
    fig.add_scatter(
        x=[None],
        y=[None],
        mode="markers",
        marker=dict(size=12, color="rgba(44,160,44,0.5)", symbol="square"),
        name=f"Peer p20–p80 ({peer_p20:.0f}–{peer_p80:.0f})",
    )
    fig.add_scatter(
        x=[None],
        y=[None],
        mode="lines",
        line=dict(color="#2ca02c", width=2, dash="dash"),
        name=f"Peer p50 ({peer_p50:.1f})",
    )

    h = height or max(160, 56 + 44 * n)
    fig.update_layout(
        height=h,
        margin=dict(l=10, r=80, t=40 if title else 16, b=40),
        title=title,
        xaxis_title="Site EUI (kBtu/ft²·yr)",
        yaxis=dict(
            categoryorder="array",
            categoryarray=list(reversed(labels)),
            automargin=True,
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        plot_bgcolor="rgba(0,0,0,0)",
    )
    xmax = max(float(peer_p80), max(xs) if xs else float(peer_p80)) * 1.15
    xmin = min(0.0, float(peer_p20) * 0.85, min(xs) if xs else 0.0)
    fig.update_xaxes(range=[xmin, xmax], showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    fig.update_yaxes(showgrid=False)
    return fig
