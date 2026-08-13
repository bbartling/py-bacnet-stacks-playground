"""Matplotlib-only RL result plots (save PNG, no UI)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd


def _ensure(plots_dir: Path) -> Path:
    p = Path(plots_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p


def plot_learning_curve(
    rewards: Sequence[float],
    plots_dir: Path,
    *,
    title: str = "RL learning curve",
    filename: str = "learning_curve.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(list(rewards), color="#1f77b4", linewidth=1.5)
    ax.set_xlabel("episode")
    ax.set_ylabel("reward")
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def plot_day_facility_kw(
    df: pd.DataFrame,
    plots_dir: Path,
    *,
    title: str = "Facility kW",
    filename: str = "facility_kw.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    fig, ax = plt.subplots(figsize=(9, 4))
    x = df["local_step"] if "local_step" in df.columns else df.get("step", range(len(df)))
    y = df["facility_kw"] if "facility_kw" in df.columns else df["facility_j"] / 900_000.0
    ax.plot(x, y, color="#d62728", linewidth=1.4)
    ax.axvline(32, color="#333333", linestyle="--", linewidth=1, label="school 08:00")
    ax.set_xlabel("step (15-min)")
    ax.set_ylabel("kW")
    ax.set_title(title)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def plot_zone_temps_vs_sp(
    df: pd.DataFrame,
    plots_dir: Path,
    *,
    title: str = "BAS zone temps",
    filename: str = "zone_temps.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    fig, ax = plt.subplots(figsize=(9, 5))
    x = df["local_step"] if "local_step" in df.columns else df.get("step", range(len(df)))
    zone_cols = [c for c in df.columns if c.startswith("zone_temp_") and c.endswith("_f")]
    for c in zone_cols:
        ax.plot(x, df[c], linewidth=1.0, label=c.replace("zone_temp_", "").replace("_f", ""))
    ax.axhline(68.0, color="#888888", linestyle=":", linewidth=1)
    ax.axvline(32, color="#333333", linestyle="--", linewidth=1)
    ax.set_xlabel("step")
    ax.set_ylabel("F")
    ax.set_title(title)
    ax.legend(loc="best", fontsize=7, ncol=3)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def plot_algo_bakeoff_bars(
    summary: Mapping[str, Mapping[str, Any]],
    plots_dir: Path,
    *,
    filename: str = "bakeoff_bars.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    algos = list(summary.keys())
    rewards = [float(summary[a].get("mean_reward", float("nan"))) for a in algos]
    peaks = [float(summary[a].get("mean_peak_kw", float("nan"))) for a in algos]
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    axes[0].bar(algos, rewards, color="#2ca02c")
    axes[0].set_title("Mean reward")
    axes[0].grid(True, axis="y", alpha=0.3)
    axes[1].bar(algos, peaks, color="#ff7f0e")
    axes[1].set_title("Mean peak kW")
    axes[1].grid(True, axis="y", alpha=0.3)
    fig.suptitle("Algorithm bakeoff (LIVE EnergyPlus)")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def plot_rl_vs_baseline(
    rows: Sequence[Mapping[str, Any]],
    plots_dir: Path,
    *,
    filename: str = "rl_vs_baseline.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    labels = [str(r.get("label", i)) for i, r in enumerate(rows)]
    peaks = [float(r.get("peak_kw", float("nan"))) for r in rows]
    kwhs = [float(r.get("daily_kwh", float("nan"))) for r in rows]
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    axes[0].bar(labels, peaks, color="#9467bd")
    axes[0].set_title("Peak kW")
    axes[0].tick_params(axis="x", rotation=20)
    axes[1].bar(labels, kwhs, color="#8c564b")
    axes[1].set_title("Daily kWh")
    axes[1].tick_params(axis="x", rotation=20)
    fig.suptitle("RL vs baseline (LIVE)")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out
