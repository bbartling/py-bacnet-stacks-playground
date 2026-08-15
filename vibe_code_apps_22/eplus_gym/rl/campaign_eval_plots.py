"""Fail-closed campaign plots. Refuse year2xsyn / empty eval as performance."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

REQUIRED_EVAL_COLS = {"policy", "day", "peak_kw", "daily_kwh", "failed"}


class NoValidEvalError(FileNotFoundError):
    """No deterministic post-fix validation table exists."""


def load_valid_eval(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise NoValidEvalError(f"missing deterministic eval table {path}")
    df = pd.read_csv(path)
    if df.empty:
        raise NoValidEvalError("eval table is empty")
    missing = REQUIRED_EVAL_COLS - set(df.columns)
    if missing:
        raise NoValidEvalError(f"eval table missing {sorted(missing)}")
    if (df.get("artifact_kind") == "train").any():
        raise NoValidEvalError("train rows are not deterministic eval")
    return df


def _watermark(ax, text: str = "NO VALID POST-FIX EVAL") -> None:
    ax.text(0.5, 0.5, text, ha="center", va="center", transform=ax.transAxes, fontsize=14, color="#a33")


def plot_fail_closed(plots_dir: Path, filename: str, title: str) -> Path:
    out = Path(plots_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / filename
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_title(title)
    _watermark(ax)
    ax.set_xticks([])
    ax.set_yticks([])
    fig.tight_layout()
    fig.savefig(path, dpi=100)
    plt.close(fig)
    return path


def require_eval_or_watermark(eval_csv: Path | None, plots_dir: Path) -> pd.DataFrame | None:
    if eval_csv is None:
        plot_fail_closed(plots_dir, "NO_VALID_EVAL.png", "Campaign plots")
        return None
    try:
        return load_valid_eval(eval_csv)
    except NoValidEvalError:
        plot_fail_closed(plots_dir, "NO_VALID_EVAL.png", "Campaign plots")
        return None


def plot_validation_return_vs_eplus_calls(*_a: Any, **_k: Any) -> Path:
    raise NoValidEvalError("validation return plot requires real eval_episodes.csv")


def plot_paired_delta_bootstrap(*_a: Any, **_k: Any) -> Path:
    raise NoValidEvalError("paired delta plot requires real eval_episodes.csv")


def plot_pareto_peak_kwh(*_a: Any, **_k: Any) -> Path:
    raise NoValidEvalError("pareto plot requires real eval_episodes.csv")


def plot_readiness_rates(*_a: Any, **_k: Any) -> Path:
    raise NoValidEvalError("readiness plot requires real eval_episodes.csv")


def plot_ppo_bound_saturation(*_a: Any, **_k: Any) -> Path:
    raise NoValidEvalError("PPO saturation plot requires real eval_episodes.csv")


def plot_action_vs_weather(*_a: Any, **_k: Any) -> Path:
    raise NoValidEvalError("action vs weather plot requires real eval_episodes.csv")


def plot_matched_comparators(*_a: Any, **_k: Any) -> Path:
    raise NoValidEvalError("matched comparator plot requires real eval_episodes.csv")


def plot_dqn_q_bars(*_a: Any, **_k: Any) -> Path:
    raise NoValidEvalError("DQN Q bars require a specified eval context")
