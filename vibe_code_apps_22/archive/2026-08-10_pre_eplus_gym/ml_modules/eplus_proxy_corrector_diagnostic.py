"""EPLUS_PROXY_CORRECTOR_DIAGNOSTIC — IdealLoads proxy + calendar → measured kW.

DIAGNOSTIC_ONLY. Not HYBRID_SCREENING (that claim is reserved for real BAS
baseline + paired EnergyPlus treatment delta). Not a physical plant translator.

Forward chronological policy only:
  train → 2025-12-15; selection val Dec 15–31; locked January holdout after pick.
Never train/refit on Feb–Mar before evaluating January.
Not nested chronological CV.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression

from eplus_multires_metrics import resolution_block
from eplus_validation_contract import day_level_peak_metrics, period_mask

FAMILY = "EPLUS_PROXY_CORRECTOR_DIAGNOSTIC"
PRODUCT_CLAIM = "DIAGNOSTIC_ONLY"

# Back-compat alias for older imports
EPLUS_GREYBOX_PLANT_TRANSLATOR = FAMILY  # deprecated name


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


def _fit_predict(name: str, Xtr, ytr, Xte) -> np.ndarray:
    if name == "nonneg_linear":
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


def _score_pred(y_true, y_pred, aligned_slice: pd.DataFrame | None = None) -> dict[str, Any]:
    block = resolution_block(y_true, y_pred, resolution="hourly")
    block["rmse_kw"] = _rmse(y_true, y_pred)
    block["mae_kw"] = _mae(y_true, y_pred)
    if aligned_slice is not None and len(aligned_slice) >= 23:
        tmp = aligned_slice.copy()
        tmp = tmp.assign(observed_kw=np.asarray(y_true, dtype=float), simulated_kw=np.asarray(y_pred, dtype=float))
        block["day_level_peaks"] = day_level_peak_metrics(tmp)
        # Do not publish multi-month global argmax as an hourly timing metric
        block.pop("peak_timing_abs_error_h", None)
    return block


def run_proxy_corrector_bakeoff(
    aligned_hourly: pd.DataFrame,
    *,
    evaluate_winter: bool = True,
) -> dict[str, Any]:
    """Forward selection on Dec 15–31 val; January holdout only after champion pick."""
    df = build_greybox_frame(aligned_hourly)
    m_calib = period_mask(df, "calibration_development")
    m_val = period_mask(df, "chronological_validation")
    m_winter = period_mask(df, "locked_winter_holdout")
    m_post = period_mask(df, "post_holdout_generalization")
    m_summer = period_mask(df, "annual_summer_generalization")

    # Assert forward order: no train/val timestamp at or after holdout start
    ts = pd.to_datetime(df["interval_end_utc"], utc=True)
    if m_calib.any() and m_val.any():
        assert ts[m_calib].max() < ts[m_val].min(), "train must precede selection val"
    if m_val.any() and m_winter.any():
        assert ts[m_val].max() < ts[m_winter].min(), "val must precede locked holdout"
    if m_winter.any() and m_post.any():
        assert ts[m_winter].max() < ts[m_post].min(), "holdout must precede post-holdout"

    X = df[FEATURE_COLS].to_numpy(dtype=float)
    y = df["target_kw"].to_numpy(dtype=float)

    candidates = ["nonneg_linear", "extratrees", "histgbm"]
    board = []
    for name in candidates:
        if m_calib.sum() < 48 or m_val.sum() < 24:
            continue
        pred_val = _fit_predict(name, X[m_calib], y[m_calib], X[m_val])
        metrics_val = _score_pred(y[m_val], pred_val, df.loc[m_val])
        board.append(
            {
                "model": name,
                "chrono_val": metrics_val,
                "cvrmse": metrics_val.get("cvrmse_pct"),
                "nmbe": metrics_val.get("nmbe_pct"),
            }
        )

    board.sort(key=lambda r: float(r["cvrmse"]) if r["cvrmse"] == r["cvrmse"] else 1e9)
    champion = board[0]["model"] if board else None
    winter_metrics = None
    post_metrics = None
    summer_metrics = None
    if champion and evaluate_winter and m_winter.sum() >= 24:
        # Refit on calib+val ONLY (still excluding locked winter and Feb–Mar)
        train = m_calib | m_val
        assert not bool((train & m_winter).any())
        assert not bool((train & m_post).any())
        pred_w = _fit_predict(champion, X[train], y[train], X[m_winter])
        winter_metrics = _score_pred(y[m_winter], pred_w, df.loc[m_winter])
        winter_metrics["evaluated_once_after_selection"] = True
        winter_metrics["trained_on_feb_mar_before_january"] = False
        if m_post.sum() >= 24:
            pred_p = _fit_predict(champion, X[train], y[train], X[m_post])
            post_metrics = _score_pred(y[m_post], pred_p, df.loc[m_post])
            post_metrics["role"] = "external_post_holdout_generalization"
        if m_summer.sum() >= 24:
            pred_s = _fit_predict(champion, X[train], y[train], X[m_summer])
            summer_metrics = _score_pred(y[m_summer], pred_s, df.loc[m_summer])

    return {
        "family_label": FAMILY,
        "product_claim": PRODUCT_CLAIM,
        "operational_dsm_readiness": "NO-GO",
        "feature_cols": FEATURE_COLS,
        "nested_chronological_cv": False,
        "is_plant_translator": False,
        "leaderboard_chrono_val": board,
        "champion": champion,
        "selection_validation": board[0]["chrono_val"] if board else None,
        "locked_winter_holdout": winter_metrics,
        "post_holdout_generalization": post_metrics,
        "annual_summer_generalization": summer_metrics,
        "n_calib": int(m_calib.sum()),
        "n_val": int(m_val.sum()),
        "n_winter": int(m_winter.sum()),
        "n_post": int(m_post.sum()),
        "periods": {
            "train": "data_start→2025-12-15",
            "selection_val": "2025-12-15→2026-01-01",
            "locked_holdout": "2026-01-01→2026-02-01",
            "post_holdout": "2026-02-01→2026-04-01",
        },
        "note": (
            "Proxy corrector diagnostic only — fixed-COP IdealLoads kW + lags + calendar. "
            "Not a plant translator. Not HYBRID_SCREENING."
        ),
    }


# Back-compat name
run_greybox_bakeoff = run_proxy_corrector_bakeoff


def write_greybox_report(aligned_hourly: pd.DataFrame, out_dir: Path) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    doc = run_proxy_corrector_bakeoff(aligned_hourly)
    (out / "proxy_corrector_diagnostic_report.json").write_text(
        json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8"
    )
    # Legacy filename for older readers
    (out / "greybox_plant_translator_report.json").write_text(
        json.dumps(doc, indent=2, default=str) + "\n", encoding="utf-8"
    )
    return doc
