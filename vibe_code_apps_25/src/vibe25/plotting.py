"""Controls-tech-friendly plots for the PID hunting tutorial."""

from __future__ import annotations

import matplotlib.pyplot as plt
import pandas as pd

from .synth import COLUMN


def _first_fault_index(metrics: pd.DataFrame) -> pd.Timestamp | None:
    fault = metrics["fault"].fillna(False)
    if not bool(fault.any()):
        return None
    return fault.index[fault.to_numpy().argmax()]  # first True


def plot_valve_overview(
    df: pd.DataFrame,
    metrics: pd.DataFrame | None = None,
    *,
    column: str = COLUMN,
    title: str = "Cooling valve command (full trend)",
    annotate_tv_at_fault: bool = True,
) -> plt.Figure:
    """AO % vs time with optional fault shading and TV callout at first fault=True."""
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
        if annotate_tv_at_fault:
            t0 = _first_fault_index(metrics.reindex(series.index))
            if t0 is not None and "total_variation_1h" in metrics.columns:
                tv = float(metrics.loc[t0, "total_variation_1h"])
                y = float(series.loc[t0])
                ax.axvline(t0, color="#dc2626", ls="--", lw=1.3, label="First fault=True")
                ax.scatter([t0], [y], color="#dc2626", s=40, zorder=5)
                ax.annotate(
                    f"First hunting flag\nrolling 1h TV = {tv:.0f}\n(threshold 500)",
                    xy=(t0, y),
                    xytext=(18, 18),
                    textcoords="offset points",
                    fontsize=9,
                    color="#7f1d1d",
                    fontweight="600",
                    arrowprops={"arrowstyle": "->", "color": "#dc2626"},
                    bbox={
                        "boxstyle": "round,pad=0.35",
                        "facecolor": "#fee2e2",
                        "edgecolor": "#dc2626",
                        "alpha": 0.95,
                    },
                )
    ax.set_ylim(0, 100)
    ax.set_ylabel("Valve command (%)")
    ax.set_xlabel("Time")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper right", fontsize=8)
    return fig


def plot_valve_zoom_with_tv(
    df: pd.DataFrame,
    metrics: pd.DataFrame | None = None,
    *,
    column: str = COLUMN,
    start_sample: int = 30,
    n_cycles: int = 3,
    period_samples: int = 6,
    title: str = "Zoom: a few hunting cycles — what TV means",
) -> plt.Figure:
    """Zoom cycles; label Δ% and running TV at every step; clear high−low span bracket."""
    series = df[column]
    width = max(period_samples * n_cycles + 1, 8)
    end = min(len(series), start_sample + width)
    start = max(0, start_sample)
    zoom = series.iloc[start:end]
    if len(zoom) < 4:
        raise ValueError("not enough samples for zoom window")

    deltas = zoom.diff().fillna(0.0)
    step_abs = deltas.abs()
    # Running odometer inside this zoom — makes “add every Δ” obvious on labels
    tv_zoom = step_abs.cumsum()

    # Open-FDD rolling 1h TV on the twin axis when metrics are provided
    use_roll = metrics is not None and "total_variation_1h" in metrics.columns
    if use_roll:
        tv_plot = metrics["total_variation_1h"].reindex(zoom.index).astype(float)
        tv_label = "Rolling 1h TV (Open-FDD)"
    else:
        tv_plot = tv_zoom
        tv_label = "Totalized TV on this zoom (Σ|Δ|)"

    fig, ax = plt.subplots(figsize=(12, 5.0), constrained_layout=True)
    ax.plot(zoom.index, zoom.values, color="#0d9b8c", lw=2.0, marker="o", ms=5, label="Valve %", zorder=3)

    zmin = float(zoom.min())
    zmax = float(zoom.max())
    span = zmax - zmin
    # Clear span: high/low lines + side bracket (not a floating mid-plot badge)
    ax.axhline(zmax, color="#c47b08", ls="--", lw=1.0, alpha=0.85)
    ax.axhline(zmin, color="#c47b08", ls="--", lw=1.0, alpha=0.85)
    ax.text(
        zoom.index[0],
        zmax + 1.5,
        f"high {zmax:.0f}%",
        color="#c47b08",
        fontsize=8,
        fontweight="600",
        ha="left",
        va="bottom",
    )
    ax.text(
        zoom.index[0],
        zmin - 1.5,
        f"low {zmin:.0f}%",
        color="#c47b08",
        fontsize=8,
        fontweight="600",
        ha="left",
        va="top",
    )
    ax.annotate(
        "",
        xy=(zoom.index[-1], zmax),
        xytext=(zoom.index[-1], zmin),
        arrowprops={"arrowstyle": "<->", "color": "#c47b08", "lw": 1.6},
    )
    ax.text(
        zoom.index[-1],
        (zmin + zmax) / 2,
        f"  SPAN\n  = high − low\n  = {span:.0f}%",
        color="#c47b08",
        fontsize=8,
        fontweight="600",
        va="center",
        ha="left",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "#fffbeb", "edgecolor": "#c47b08", "alpha": 0.95},
    )

    # Every timestep: Δ from last sample + running Σ|Δ| on this zoom
    for i in range(1, len(zoom)):
        step = float(deltas.iloc[i])
        if abs(step) < 0.05:
            continue
        x0, x1 = zoom.index[i - 1], zoom.index[i]
        y0, y1 = float(zoom.iloc[i - 1]), float(zoom.iloc[i])
        ax.annotate(
            "",
            xy=(x1, y1),
            xytext=(x0, y0),
            arrowprops={"arrowstyle": "->", "color": "#2563eb", "lw": 1.2, "alpha": 0.85},
        )
        mid_t = x0 + (x1 - x0) / 2
        mid_y = (y0 + y1) / 2
        sign = "+" if step >= 0 else "−"
        ax.text(
            mid_t,
            mid_y + (4.5 if step > 0 else -7.5),
            f"Δ {sign}{abs(step):.0f}%\nΣ|Δ| {float(tv_zoom.iloc[i]):.0f}",
            color="#1e3a5f",
            fontsize=7,
            ha="center",
            va="center",
            fontweight="600",
            linespacing=1.15,
            bbox={
                "boxstyle": "round,pad=0.15",
                "facecolor": "white",
                "edgecolor": "#93c5fd",
                "alpha": 0.92,
            },
            zorder=4,
        )

    ax2 = ax.twinx()
    ax2.plot(
        zoom.index,
        tv_plot.values,
        color="#7c3aed",
        lw=1.8,
        ls="--",
        marker="s",
        ms=3.5,
        label=tv_label,
        zorder=2,
    )
    ax2.set_ylabel(tv_label, color="#7c3aed")
    ax2.tick_params(axis="y", labelcolor="#7c3aed")
    ax2.set_ylim(bottom=0)

    if use_roll:
        mzoom = metrics.reindex(zoom.index)
        if "fault" in mzoom.columns and bool(mzoom["fault"].fillna(False).any()):
            t_show = _first_fault_index(mzoom)
            if t_show is not None:
                ax.axvline(t_show, color="#dc2626", ls=":", lw=1.2, label="First fault=True")
                ax.scatter([t_show], [float(series.loc[t_show])], color="#dc2626", s=40, zorder=5)

    note = (
        "Each step label:\n"
        "  Δ = change since last sample\n"
        "  Σ|Δ| = add those |Δ|s\n"
        "         (odometer on this zoom)\n"
        "Purple line = rolling 1h TV\n"
        "SPAN = high − low (swing height)"
    )
    ax.text(
        0.01,
        0.99,
        note,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=8,
        color="#1e3a5f",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "#e8f1fb", "edgecolor": "#2563eb", "alpha": 0.95},
        zorder=6,
    )

    ax.set_ylim(-2, 102)
    ax.set_ylabel("Valve command (%)")
    ax.set_xlabel("Time (zoomed)")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower right", fontsize=8)
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
