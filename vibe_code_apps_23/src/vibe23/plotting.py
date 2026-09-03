"""Residential DSM matplotlib plots (Agg backend)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402


def _series(metrics: Mapping[str, Any], key: str) -> np.ndarray:
    return np.asarray(list(metrics.get(key) or []), dtype=float)


def save_dr_comparison_png(
    baseline: Mapping[str, Any],
    event: Mapping[str, Any],
    path: Path | str,
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    b_kw = _series(baseline, "facility_kw")
    e_kw = _series(event, "facility_kw")
    b_t = _series(baseline, "zone_temp_f")
    e_t = _series(event, "zone_temp_f")
    hours_b = np.arange(1, len(b_kw) + 1) * 24.0 / max(len(b_kw), 1)
    hours_e = np.arange(1, len(e_kw) + 1) * 24.0 / max(len(e_kw), 1)

    fig, axes = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    axes[0].plot(hours_b, b_kw, label="baseline kW", color="#1f4e79")
    axes[0].plot(hours_e, e_kw, label="DR event kW", color="#c45c26")
    axes[0].set_ylabel("Facility kW")
    axes[0].legend(loc="upper right")
    axes[0].set_title("Residential DR comparison (illustrative)")
    axes[1].plot(hours_b[: len(b_t)], b_t, label="baseline °F", color="#1f4e79")
    axes[1].plot(hours_e[: len(e_t)], e_t, label="DR event °F", color="#c45c26")
    axes[1].set_ylabel("Zone °F")
    axes[1].set_xlabel("Hour")
    axes[1].legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def save_baseline_vs_winner_png(
    baseline: Mapping[str, Any],
    winner: Mapping[str, Any],
    path: Path | str,
    *,
    title: str = "Baseline vs winner",
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    b_kw = _series(baseline, "facility_kw")
    w_kw = _series(winner, "facility_kw")
    hours_b = np.arange(1, len(b_kw) + 1) * 24.0 / max(len(b_kw), 1)
    hours_w = np.arange(1, len(w_kw) + 1) * 24.0 / max(len(w_kw), 1)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(hours_b, b_kw, label="baseline", color="#1f4e79")
    ax.plot(hours_w, w_kw, label="winner", color="#2a9d8f")
    ax.set_xlabel("Hour")
    ax.set_ylabel("Facility kW")
    ax.set_title(title)
    ax.legend(loc="upper right")
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def save_simple_series_png(
    series: Sequence[float],
    path: Path | str,
    *,
    ylabel: str = "value",
    title: str = "Series",
) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    arr = np.asarray(list(series), dtype=float)
    hours = np.arange(1, len(arr) + 1) * 24.0 / max(len(arr), 1)
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.plot(hours, arr, color="#1f4e79")
    ax.set_xlabel("Hour")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out
