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


OVERLAY_POLICIES = ("PPO", "DQN", "random_walk")


def plot_policy_learning_overlay(
    df: pd.DataFrame,
    plots_dir: Path,
    *,
    window: int = 5,
    filename: str = "learning_curve_smoothed.png",
) -> Path:
    """Episode index vs reward for PPO / DQN / random_walk (rolling mean)."""
    out = _ensure(plots_dir) / filename
    fig, ax = plt.subplots(figsize=(8.5, 4.4))
    colors = {"PPO": "#08519c", "DQN": "#d94801", "random_walk": "#636363"}
    plotted = False
    for policy in OVERLAY_POLICIES:
        g = df.loc[df["policy"] == policy]
        if g.empty:
            continue
        y = pd.to_numeric(g["reward"], errors="coerce").reset_index(drop=True)
        c = colors.get(str(policy), "#333333")
        ax.plot(y.index, y.values, color=c, linewidth=0.8, alpha=0.35)
        if len(y) >= 2:
            roll = y.rolling(window=min(window, len(y)), min_periods=1).mean()
            ax.plot(roll.index, roll.values, color=c, linewidth=2.0, label=str(policy))
        else:
            ax.plot(y.index, y.values, color=c, linewidth=2.0, label=str(policy))
        plotted = True
    if not plotted:
        ax.text(0.5, 0.5, "no PPO/DQN/random_walk rows", ha="center")
    ax.set_xlabel("episode")
    ax.set_ylabel("reward")
    ax.set_title("LIVE reward vs episode (random walk = no learning)")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def plot_learning_curve_smoothed(
    rewards: Sequence[float],
    plots_dir: Path,
    *,
    window: int = 5,
    title: str = "Learning curve (LIVE)",
    filename: str = "learning_curve_smoothed.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    y = pd.Series(list(rewards), dtype=float)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.plot(y.index, y.values, color="#9ecae1", linewidth=1.0, label="episode")
    if len(y) >= 2:
        roll = y.rolling(window=min(window, len(y)), min_periods=1).mean()
        ax.plot(roll.index, roll.values, color="#08519c", linewidth=2.0, label=f"rolling mean ({window})")
    ax.set_xlabel("episode")
    ax.set_ylabel("reward")
    ax.set_title(title)
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def plot_reward_violin(
    df: pd.DataFrame,
    plots_dir: Path,
    *,
    filename: str = "reward_violin.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    fig, ax = plt.subplots(figsize=(8, 4.5))
    policies = list(df["policy"].unique())
    data = [df.loc[df["policy"] == p, "reward"].dropna().astype(float).tolist() for p in policies]
    data = [d if d else [float("nan")] for d in data]
    ax.violinplot([[x for x in d if x == x] or [0.0] for d in data], showmeans=True, showmedians=True)
    ax.set_xticks(range(1, len(policies) + 1))
    ax.set_xticklabels(policies, rotation=15)
    ax.set_ylabel("episode reward")
    ax.set_title("Return distribution (LIVE day MDP)")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def plot_cumulative_reward(
    df: pd.DataFrame,
    plots_dir: Path,
    *,
    filename: str = "cumulative_reward.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for policy, g in df.groupby("policy"):
        y = pd.to_numeric(g["reward"], errors="coerce").cumsum()
        ax.plot(range(len(y)), y.values, linewidth=1.8, label=str(policy))
    ax.set_xlabel("episode (within policy)")
    ax.set_ylabel("cumulative reward")
    ax.set_title("Cumulative return")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def plot_peak_vs_kwh_scatter(
    df: pd.DataFrame,
    plots_dir: Path,
    *,
    filename: str = "peak_vs_kwh.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for policy, g in df.groupby("policy"):
        ax.scatter(
            pd.to_numeric(g["daily_kwh"], errors="coerce"),
            pd.to_numeric(g["peak_kw"], errors="coerce"),
            s=36,
            alpha=0.75,
            label=str(policy),
        )
    ax.set_xlabel("daily kWh")
    ax.set_ylabel("peak kW")
    ax.set_title("Energy vs peak (LIVE)")
    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def plot_pre8_bars(
    df: pd.DataFrame,
    plots_dir: Path,
    *,
    filename: str = "pre8_violations.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    g = df.groupby("policy")["pre8_violations"].mean()
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([str(x) for x in g.index], g.values, color="#e6550d")
    ax.set_ylabel("mean pre-8AM zone violations")
    ax.set_title("Comfort miss before school start (step 32)")
    ax.tick_params(axis="x", rotation=15)
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out


def plot_recovery_hist(
    df: pd.DataFrame,
    plots_dir: Path,
    *,
    filename: str = "recovery_lead_hist.png",
) -> Path:
    out = _ensure(plots_dir) / filename
    fig, ax = plt.subplots(figsize=(8, 4.2))
    plotted = False
    for policy, g in df.groupby("policy"):
        if "recovery_min" not in g.columns:
            continue
        vals = pd.to_numeric(g["recovery_min"], errors="coerce").dropna()
        if vals.empty:
            continue
        ax.hist(vals, bins=8, alpha=0.45, label=str(policy))
        plotted = True
    if not plotted:
        ax.text(0.5, 0.5, "no recovery_min", ha="center")
    ax.set_xlabel("recovery lead (min)")
    ax.set_ylabel("episodes")
    ax.set_title("Policy behavior: recovery lead")
    if plotted:
        ax.legend(loc="best")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=140)
    plt.close(fig)
    return out
