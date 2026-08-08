"""EPLUS_GREYBOX_PLANT_TRANSLATOR — map IdealLoads physics proxies → facility kW.

Honestly labeled: not raw EnergyPlus. Uses E+ explanatory features + calendar
to predict measured facility kW. Nested chronological validation; locked winter
holdout evaluated only after model selection.

Product claim remains HYBRID_SCREENING; DSM stays blocked.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression

from eplus_multires_metrics import nmbe_cvrmse_pct, resolution_block
from eplus_validation_contract import chronological_splits, period_mask

FAMILY = "EPLUS_GREYBOX_PLANT_TRANSLATOR"


def _rmse(y, p) -> float:
    y = np.asarray(y, dtype=float)
    p = np.asarray(p, dtype=float)
    return float(np.sqrt(np.mean((y - p) ** 2)))


def _mae(y, p) -> float:
    return float(np.mean(np.abs(np.asarray(y, dtype=float) - np.asarray(p, dtype=float))))


def build_greybox_frame(aligned_hourly: pd.DataFrame) -> pd.DataFrame:
    """Features available at midnight / forecast — no future measured targets."""
    df = aligned_hourly.copy()
    df["interval_end_utc"] = pd.to_datetime(df["interval_end_utc"], utc=True)
    df = df.sort_values("interval_end_utc").reset_index(drop=True)
    df["hod"] = df["interval_end_utc"].dt.hour
    df["dow"] = df["interval_end_utc"].dt.dayofweek
    df["is_weekend"] = (df["dow"] >= 5).astype(float)
    df["month"] = df["interval_end_utc"].dt.month
    # E+ proxy as explanatory (IdealLoads electrical proxy) — lagged only for autoregressive state
    df["eplus_proxy_kw"] = df["simulated_kw"].astype(float)
    df["eplus_proxy_lag1"] = df["eplus_proxy_kw"].shift(1)
    df["eplus_proxy_lag24"] = df["eplus_proxy_kw"].shift(24)
    df["startup"] = ((df["hod"] >= 5) & (df["hod"] <= 9)).astype(float)
    df["target_kw"] = df["observed_kw"].astype(float)
    df = df.dropna().reset_index(drop=True)
    return df


FEATURE_COLS = [
    "eplus_proxy_kw",
    "eplus_proxy_lag1",
    "eplus_proxy_lag24",
    "hod",
    "dow",
    "is_weekend",
    "month",
    "startup",
]


@dataclass
class GreyboxResult:
    model_name: str
    metrics_chrono_val: dict[str, Any]
    metrics_locked_winter: dict[str, Any] | None
    family_label: str = FAMILY


def _fit_predict(name: str, Xtr, ytr, Xte) -> np.ndarray:
    if name == "nonneg_linear":
        # unconstrained then clip negatives on prediction (constrained surrogate)
        m = LinearRegression(positive=True)
        m.fit(Xtr, ytr)
        return np.maximum(m.predict(Xte), 0.0)
    if name == "extratrees":
        m = ExtraTreesRegressor(
            n_estimators=200, max_depth=16, random_state=0, n_jobs=-1, min_samples_leaf=2
        )
        m.fit(Xtr, ytr)
        return m.predict(Xte)
    if name == "histgbm":
        m = HistGradientBoostingRegressor(max_depth=8, learning_rate=0.08, random_state=0)
        m.fit(Xtr, ytr)
        return m.predict(Xte)
    raise ValueError(name)


def _score_pred(y_true, y_pred) -> dict[str, Any]:
    block = resolution_block(y_true, y_pred, resolution="hourly")
    block["rmse_kw"] = _rmse(y_true, y_pred)
    block["mae_kw"] = _mae(y_true, y_pred)
    # Peak / morning HE05-09
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    block["peak_mag_abs_error_kw"] = float(abs(yt.max() - yp.max()))
    block["peak_timing_abs_error_h"] = float(abs(int(np.argmax(yt)) - int(np.argmax(yp))))
    return block


def run_greybox_bakeoff(
    aligned_hourly: pd.DataFrame,
    *,
    evaluate_winter: bool = True,
) -> dict[str, Any]:
    """Nested chronological selection on chrono-val; winter evaluated after pick."""
    df = build_greybox_frame(aligned_hourly)
    # Rebuild masks on feature frame
    m_calib = period_mask(df, "calibration_development")
    m_val = period_mask(df, "chronological_validation")
    m_winter = period_mask(df, "locked_winter_holdout")

    X = df[FEATURE_COLS].to_numpy(dtype=float)
    y = df["target_kw"].to_numpy(dtype=float)

    candidates = ["nonneg_linear", "extratrees", "histgbm"]
    board = []
    for name in candidates:
        if m_calib.sum() < 48 or m_val.sum() < 24:
            continue
        pred_val = _fit_predict(name, X[m_calib], y[m_calib], X[m_val])
        metrics_val = _score_pred(y[m_val], pred_val)
        board.append({"model": name, "chrono_val": metrics_val, "cvrmse": metrics_val.get("cvrmse_pct")})

    board.sort(key=lambda r: float(r["cvrmse"]) if r["cvrmse"] == r["cvrmse"] else 1e9)
    champion = board[0]["model"] if board else None
    winter_metrics = None
    if champion and evaluate_winter and m_winter.sum() >= 24:
        # Refit on calib+val (still excluding locked winter), then score winter once
        train = m_calib | m_val
        pred_w = _fit_predict(champion, X[train], y[train], X[m_winter])
        winter_metrics = _score_pred(y[m_winter], pred_w)
        winter_metrics["evaluated_once_after_selection"] = True

    return {
        "family_label": FAMILY,
        "product_claim": "HYBRID_SCREENING",
        "operational_dsm_readiness": "NO-GO",
        "feature_cols": FEATURE_COLS,
        "leaderboard_chrono_val": board,
        "champion": champion,
        "locked_winter_holdout": winter_metrics,
        "n_calib": int(m_calib.sum()),
        "n_val": int(m_val.sum()),
        "n_winter": int(m_winter.sum()),
        "note": "Not raw EnergyPlus. No future measured demand features.",
    }


def write_greybox_report(aligned_hourly: pd.DataFrame, out_dir: Path) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    doc = run_greybox_bakeoff(aligned_hourly)
    (out / "greybox_plant_translator_report.json").write_text(
        json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return doc
