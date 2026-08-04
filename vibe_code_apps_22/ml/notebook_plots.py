"""Plot helpers for Creekside heating DSM notebooks (Kaggle-style)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def family_cv_mae_bars(
    leaderboard: list[dict[str, Any]],
    persistence_peak: float,
    ax=None,
):
    ax = ax or plt.gca()
    names = [e["family"] for e in leaderboard]
    maes = [e["oof_metrics"]["mae_peak_05_09"] for e in leaderboard]
    colors = ["#2a9d8f" if m < persistence_peak else "#e76f51" for m in maes]
    ax.barh(names, maes, color=colors)
    ax.axvline(persistence_peak, color="#264653", ls="--", label=f"persistence {persistence_peak:.2f}")
    ax.set_xlabel("OOF morning-peak MAE (HE 05–09) [kW]")
    ax.set_title("Family bake-off — morning peak MAE (lower is better)")
    ax.legend(loc="best")
    return ax


def family_mae_rmse_grouped(
    leaderboard: list[dict[str, Any]],
    persistence: dict[str, float] | None = None,
    ax=None,
):
    ax = ax or plt.gca()
    names = [e["family"] for e in leaderboard]
    mae = [e["oof_metrics"]["mae"] for e in leaderboard]
    rmse = [e["oof_metrics"]["rmse"] for e in leaderboard]
    x = np.arange(len(names))
    w = 0.38
    ax.bar(x - w / 2, mae, w, label="OOF MAE", color="#4C78A8")
    ax.bar(x + w / 2, rmse, w, label="OOF RMSE", color="#F58518")
    if persistence:
        if "mae" in persistence:
            ax.axhline(persistence["mae"], color="#E45756", ls="--", lw=1.4, label=f"persist MAE={persistence['mae']:.1f}")
        if "rmse" in persistence:
            ax.axhline(persistence["rmse"], color="#B279A2", ls=":", lw=1.4, label=f"persist RMSE={persistence['rmse']:.1f}")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=25, ha="right")
    ax.set_ylabel("kW")
    ax.set_title("Model family accuracy — MAE vs RMSE (GroupKFold OOF)")
    ax.legend(frameon=False, fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def leaderboard_table(
    leaderboard: list[dict[str, Any]],
    persistence: dict[str, float] | None = None,
) -> pd.DataFrame:
    rows = []
    for e in leaderboard:
        m = e["oof_metrics"]
        rows.append(
            {
                "family": e["family"],
                "mae": m["mae"],
                "rmse": m["rmse"],
                "mae_peak_05_09": m["mae_peak_05_09"],
                "rmse_peak_05_09": m["rmse_peak_05_09"],
            }
        )
    out = pd.DataFrame(rows).sort_values("mae_peak_05_09").reset_index(drop=True)
    if persistence:
        out.attrs["persistence"] = persistence
    return out


def oat_vs_kw_scatter(df: pd.DataFrame, ax=None, sample: int = 8000):
    ax = ax or plt.gca()
    sub = df
    if len(sub) > sample:
        sub = sub.sample(sample, random_state=21)
    ax.scatter(sub["oat_f"], sub["facility_kw"], s=6, alpha=0.25, c="#4C78A8")
    ax.set_xlabel("OAT [°F]")
    ax.set_ylabel("facility_kw")
    ax.set_title("OAT vs facility demand (bootstrap)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def strategy_morning_peak_bars(df: pd.DataFrame, ax=None):
    ax = ax or plt.gca()
    morning = df[(df["hour_ending"] >= 5) & (df["hour_ending"] <= 9)]
    g = morning.groupby("strategy_id")["facility_kw"].mean().sort_values(ascending=False)
    ax.barh(g.index.astype(str), g.values, color="#2a9d8f")
    ax.set_xlabel("Mean facility_kw in HE 05–09")
    ax.set_title("Morning-window mean kW by strategy (proxy)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def example_day_profiles(df: pd.DataFrame, day: str, ax=None):
    ax = ax or plt.gca()
    sub = df[df["day"] == day]
    for sid, g in sub.groupby("strategy_id"):
        g = g.sort_values("hour_ending")
        ax.plot(g["hour_ending"], g["facility_kw"], label=sid, lw=1.8)
    ax.set_xlabel("Hour (local)")
    ax.set_ylabel("facility_kw")
    ax.set_title(f"Strategy shapes — {day}")
    ax.legend(fontsize=7, frameon=False, ncol=2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def residual_hist(y_true: np.ndarray, y_pred: np.ndarray, ax=None):
    ax = ax or plt.gca()
    resid = y_true - y_pred
    ax.hist(resid, bins=40, color="#4C78A8", alpha=0.85)
    ax.axvline(0, color="#E45756", ls="--")
    ax.set_xlabel("Residual (actual − pred) [kW]")
    ax.set_title("OOF residual distribution")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    return ax


def save_fig(path: Path, fig=None, dpi: int = 140) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig = fig or plt.gcf()
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return path
