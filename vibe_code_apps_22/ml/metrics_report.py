"""Multi-output DSM metrics (facility_kw + zone temps) for tutorial notebooks."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from energy_math import peak_kw, quarter_hour_kwh
from feature_compile_heating_dsm import TARGET_COLS, ZONE_TEMP_COLS

MORNING_PEAK_STEPS = range(20, 36)  # HE 05–09 at 15-min (approx steps 20–35)


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y_true) - np.asarray(y_pred))))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    err = np.asarray(y_true, dtype=float) - np.asarray(y_pred, dtype=float)
    return float(np.sqrt(np.mean(err**2)))


def cv_rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    """CV(RMSE) = RMSE / mean(actual). None when mean is ~0."""
    yt = np.asarray(y_true, dtype=float)
    mean_y = float(np.mean(yt))
    if abs(mean_y) < 1e-9:
        return None
    return rmse(yt, y_pred) / mean_y


def nmbe(y_true: np.ndarray, y_pred: np.ndarray) -> float | None:
    """Normalized mean bias error. None when mean(actual) ~0."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    mean_y = float(np.mean(yt))
    if abs(mean_y) < 1e-9:
        return None
    return float(np.mean(yp - yt) / mean_y)


def scalar_block(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    yt = np.asarray(y_true, dtype=float).reshape(-1)
    yp = np.asarray(y_pred, dtype=float).reshape(-1)
    return {
        "mae": mae(yt, yp),
        "rmse": rmse(yt, yp),
        "cv_rmse": cv_rmse(yt, yp),
        "nmbe": nmbe(yt, yp),
        "mean_actual": float(np.mean(yt)),
        "max_abs_error": float(np.max(np.abs(yt - yp))) if len(yt) else None,
        "n_obs": int(len(yt)),
    }


def morning_peak_mae(y_true_kw: np.ndarray, y_pred_kw: np.ndarray, peak_mask: np.ndarray) -> float:
    m = np.asarray(peak_mask, dtype=bool)
    if not m.any():
        return mae(y_true_kw, y_pred_kw)
    return mae(np.asarray(y_true_kw)[m], np.asarray(y_pred_kw)[m])


def daily_peak_errors(
    y_true_kw: Sequence[float], y_pred_kw: Sequence[float]
) -> dict[str, float]:
    yt = np.asarray(y_true_kw, dtype=float)
    yp = np.asarray(y_pred_kw, dtype=float)
    return {
        "daily_peak_mag_error_kw": float(abs(peak_kw(yt) - peak_kw(yp))),
        "peak_timing_abs_error_steps": float(abs(int(np.argmax(yt)) - int(np.argmax(yp)))),
        "daily_kwh_error": float(abs(quarter_hour_kwh(yt) - quarter_hour_kwh(yp))),
    }


def horizon_mae_curve(
    y_true: np.ndarray, y_pred: np.ndarray, *, horizons: Sequence[int] | None = None
) -> dict[str, float]:
    """Per-step MAE along a recursive day (rows = steps, cols = targets or 1-D kw)."""
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    if yt.ndim == 1:
        yt = yt.reshape(-1, 1)
        yp = yp.reshape(-1, 1)
    n = yt.shape[0]
    hs = list(horizons or (1, 4, 12, 24, 48, 96))
    out: dict[str, float] = {}
    for h in hs:
        if h > n:
            continue
        # MAE at that horizon step (0-indexed step h-1)
        out[f"horizon_mae_step_{h}"] = float(np.mean(np.abs(yt[h - 1] - yp[h - 1])))
    return out


def per_target_table(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    target_cols: Sequence[str] | None = None,
    n_days: int | None = None,
    recursive_mae: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Rows = facility_kw + each zone; never hide worst zone behind an average."""
    cols = list(target_cols or TARGET_COLS)
    yt = np.asarray(y_true, dtype=float)
    yp = np.asarray(y_pred, dtype=float)
    if yt.ndim != 2 or yt.shape[1] != len(cols):
        raise ValueError(f"expected [n, {len(cols)}], got {yt.shape}")
    rows = []
    for i, name in enumerate(cols):
        blk = scalar_block(yt[:, i], yp[:, i])
        short = name.replace("zone_temp_", "").replace("_f", "") if name.startswith("zone") else name
        rec = None
        if recursive_mae and name in recursive_mae:
            rec = recursive_mae[name]
        elif recursive_mae and short in recursive_mae:
            rec = recursive_mae[short]
        rows.append(
            {
                "target": short if name != "facility_kw" else "facility_kw",
                "target_col": name,
                "mae": blk["mae"],
                "rmse": blk["rmse"],
                "mean_actual": blk["mean_actual"],
                "cv_rmse": blk["cv_rmse"],
                "max_abs_error": blk["max_abs_error"],
                "recursive_24h_mae": rec,
                "n_obs": blk["n_obs"],
                "n_days": n_days,
            }
        )
    return pd.DataFrame(rows)


def comfort_violations(
    zone_temps_f: np.ndarray,
    *,
    sp_f: float = 68.0,
    band_f: float = 2.0,
) -> dict[str, Any]:
    """Count 15-min intervals below comfort_lo for each zone column."""
    z = np.asarray(zone_temps_f, dtype=float)
    if z.ndim == 1:
        z = z.reshape(-1, 1)
    lo = sp_f - band_f
    per_zone = [int(np.sum(z[:, i] < lo)) for i in range(z.shape[1])]
    return {
        "comfort_sp_f": sp_f,
        "comfort_band_f": band_f,
        "comfort_lo_f": lo,
        "violations_per_zone": per_zone,
        "violations_total": int(sum(per_zone)),
        "zone_cols": list(ZONE_TEMP_COLS[: z.shape[1]]),
    }


def explain_error_metrics_markdown() -> str:
    return (
        "**MAE** (mean absolute error) is the average |actual − predicted| in engineering units "
        "(kW or °F). **RMSE** (root mean squared error) penalizes large misses more heavily; "
        "both are reported in the same units as the target — never present raw squared error as kW. "
        "**CV(RMSE)** divides RMSE by the mean of actuals when that mean is nonzero. "
        "**NMBE** is the mean bias normalized by mean actual (positive ⇒ over-prediction)."
    )
