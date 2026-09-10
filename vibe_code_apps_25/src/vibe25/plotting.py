"""Controls-tech-friendly plots for the PID hunting tutorial."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .synth import COLUMN


def plot_valve_overview(
    df: pd.DataFrame,
    metrics: pd.DataFrame | None = None,
    *,
    column: str = COLUMN,
    title: str = "Cooling valve command (full trend)",
) -> plt.Figure:
    """Single clear plot: AO % vs time, optional light fault shading."""
    fig, ax = plt.subplots(figsize=(11, 3.8), constrained_layout=True)
    series = df[column]
    ax.plot(series.index, series.values, color="#0d9b8c", lw=1.4, label="Cooling valve %")
    if metrics is not None and "fault" in metrics.columns:
        fault = metrics["fault"].reindex(series.index).fillna(False)
        ax.fill_between(
            series.index,
            0,
            100,
            where=fault.to_numpy(),
            color="#f87171",
            alpha=0.18,
            label="Open-FDD says: hunting",
        )
    ax.set_ylim(0, 100)
    ax.set_ylabel("Valve command (%)")
    ax.set_xlabel("Time")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=9)
    return fig


def plot_valve_zoom_with_tv(
    df: pd.DataFrame,
    *,
    column: str = COLUMN,
    start_sample: int = 30,
    n_cycles: int = 3,
    period_samples: int = 6,
    title: str = "Zoom: a few hunting cycles — what TV means",
) -> plt.Figure:
    """Zoom 2–3 sine cycles and annotate TV (travel) vs span (high−low)."""
    series = df[column]
    width = max(period_samples * n_cycles + 1, 8)
    end = min(len(series), start_sample + width)
    start = max(0, start_sample)
    zoom = series.iloc[start:end]
    if len(zoom) < 4:
        raise ValueError("not enough samples for zoom window")

    fig, ax = plt.subplots(figsize=(11, 4.2), constrained_layout=True)
    ax.plot(zoom.index, zoom.values, color="#0d9b8c", lw=2.0, marker="o", ms=4, label="Valve %")

    # Span: high / low in this zoom window
    zmin = float(zoom.min())
    zmax = float(zoom.max())
    ax.axhline(zmax, color="#c47b08", ls="--", lw=1.2)
    ax.axhline(zmin, color="#c47b08", ls="--", lw=1.2)
    ax.annotate(
        f"SPAN ≈ {zmax - zmin:.0f}%\n(high − low)",
        xy=(zoom.index[len(zoom) // 2], (zmin + zmax) / 2),
        xytext=(12, 0),
        textcoords="offset points",
        color="#c47b08",
        fontsize=10,
        fontweight="600",
        va="center",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#c47b08", "alpha": 0.9},
    )

    # TV callouts: sample-to-sample |delta| on the first 1–2 rising/falling legs
    deltas = zoom.diff().fillna(0.0)
    # Mark a few consecutive moves so the tech sees "travel adds up"
    labeled = 0
    for i in range(1, len(zoom)):
        step = float(deltas.iloc[i])
        if abs(step) < 1.0:
            continue
        x0, x1 = zoom.index[i - 1], zoom.index[i]
        y0, y1 = float(zoom.iloc[i - 1]), float(zoom.iloc[i])
        ax.annotate(
            "",
            xy=(x1, y1),
            xytext=(x0, y0),
            arrowprops={"arrowstyle": "->", "color": "#2563eb", "lw": 1.4},
        )
        mid_t = x0 + (x1 - x0) / 2
        mid_y = (y0 + y1) / 2
        ax.text(
            mid_t,
            mid_y + (3 if step > 0 else -6),
            f"{abs(step):.0f}%",
            color="#2563eb",
            fontsize=8,
            ha="center",
            fontweight="600",
        )
        labeled += 1
        if labeled >= 6:
            break

    window_tv = float(np.abs(deltas.to_numpy()).sum())
    ax.text(
        0.02,
        0.98,
        (
            "TV (total variation) = add up every move\n"
            f"(ups + downs) on this zoom ≈ {window_tv:.0f} points\n"
            "Open-FDD does this over a rolling 1 hour."
        ),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=10,
        color="#1e3a5f",
        bbox={"boxstyle": "round,pad=0.4", "facecolor": "#e8f1fb", "edgecolor": "#2563eb", "alpha": 0.95},
    )

    ax.set_ylim(0, 100)
    ax.set_ylabel("Valve command (%)")
    ax.set_xlabel("Time (zoomed)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", fontsize=9)
    return fig


def plot_healthy_vs_hunting(
    healthy: pd.DataFrame,
    hunting: pd.DataFrame,
    *,
    column: str = COLUMN,
) -> plt.Figure:
    """Side-by-side: settled command vs hunting sine — one idea each."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), sharey=True, constrained_layout=True)
    axes[0].plot(healthy.index, healthy[column], color="#0d9b8c", lw=1.4)
    axes[0].set_title("Healthy — slow, settles")
    axes[0].set_ylabel("Valve %")
    axes[0].set_ylim(0, 100)
    axes[0].grid(True, alpha=0.3)

    axes[1].plot(hunting.index, hunting[column], color="#dc2626", lw=1.2)
    axes[1].set_title("Hunting — keeps swinging")
    axes[1].set_ylim(0, 100)
    axes[1].grid(True, alpha=0.3)
    for ax in axes:
        ax.set_xlabel("Time")
    fig.suptitle("What a tech sees on a trend", fontsize=12, fontweight="600")
    return fig
