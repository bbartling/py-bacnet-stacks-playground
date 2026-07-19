"""Unified calibration metrics for monthly and interval comparisons.

One set of formulas used everywhere in the investigation pipeline so that
"NMBE" always means the same thing:

- residual = actual − modeled (positive NMBE ⇒ model under-predicts)
- NMBE%    = 100 · Σr / (n · mean(actual))            — denominator ``n``
- CV(RMSE)% = 100 · sqrt(Σr² / (n−1)) / mean(actual)  — ``n−1`` when n>1,
  falling back to ``n`` for a single point instead of dividing by zero
- MAE, Pearson correlation, and peak (maximum-value) error round it out

Plus time-based splits (nighttime / occupied / weekend / hot / cold) that
score the same series over diagnostic subsets — a model that matches monthly
totals but is wrong at night gets caught here.
"""

from __future__ import annotations

from datetime import datetime
from math import sqrt
from typing import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_OCCUPIED_HOURS: tuple[int, int] = (8, 18)
DEFAULT_NIGHTTIME_HOURS: tuple[int, int] = (22, 6)
DEFAULT_HOT_THRESHOLD_F = 80.0
DEFAULT_COLD_THRESHOLD_F = 40.0


class MetricSet(BaseModel):
    """One bundle of comparison metrics for a (actual, modeled) pair."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    n: int = Field(ge=1)
    mean_actual: float
    nmbe_percent: float
    cvrmse_percent: float
    mae: float
    correlation: float | None
    peak_error_percent: float | None


def _validate(actual: Sequence[float], modeled: Sequence[float]) -> tuple[list[float], list[float]]:
    if len(actual) != len(modeled):
        raise ValueError(
            f"actual and modeled must be the same length "
            f"(got {len(actual)} vs {len(modeled)})"
        )
    if not actual:
        raise ValueError("cannot compute metrics on empty series")
    return [float(x) for x in actual], [float(x) for x in modeled]


def nmbe_percent(actual: Sequence[float], modeled: Sequence[float]) -> float:
    """Normalized mean bias error, percent, with denominator ``n``."""
    a, m = _validate(actual, modeled)
    avg = sum(a) / len(a)
    if avg == 0:
        return float("nan")
    return 100.0 * sum(x - y for x, y in zip(a, m)) / (len(a) * avg)


def cvrmse_percent(actual: Sequence[float], modeled: Sequence[float]) -> float:
    """CV(RMSE), percent, with denominator ``n−1`` (``n`` when n == 1)."""
    a, m = _validate(actual, modeled)
    avg = sum(a) / len(a)
    if avg == 0:
        return float("nan")
    denom = len(a) - 1 if len(a) > 1 else 1
    rmse = sqrt(sum((x - y) ** 2 for x, y in zip(a, m)) / denom)
    return 100.0 * rmse / avg


def mae(actual: Sequence[float], modeled: Sequence[float]) -> float:
    a, m = _validate(actual, modeled)
    return sum(abs(x - y) for x, y in zip(a, m)) / len(a)


def pearson_correlation(
    actual: Sequence[float], modeled: Sequence[float]
) -> float | None:
    """Pearson r; None when either series has zero variance or n < 2."""
    a, m = _validate(actual, modeled)
    n = len(a)
    if n < 2:
        return None
    mean_a = sum(a) / n
    mean_m = sum(m) / n
    var_a = sum((x - mean_a) ** 2 for x in a)
    var_m = sum((x - mean_m) ** 2 for x in m)
    if var_a == 0 or var_m == 0:
        return None
    cov = sum((x - mean_a) * (y - mean_m) for x, y in zip(a, m))
    return cov / sqrt(var_a * var_m)


def peak_error_percent(
    actual: Sequence[float], modeled: Sequence[float]
) -> float | None:
    """Signed error of the modeled peak vs the actual peak, percent.

    Positive means the model over-predicts the peak. None when the actual
    peak is zero (nothing to normalize against).
    """
    a, m = _validate(actual, modeled)
    peak_actual = max(a)
    if peak_actual == 0:
        return None
    return 100.0 * (max(m) - peak_actual) / peak_actual


def compute_metrics(actual: Sequence[float], modeled: Sequence[float]) -> MetricSet:
    a, m = _validate(actual, modeled)
    return MetricSet(
        n=len(a),
        mean_actual=sum(a) / len(a),
        nmbe_percent=nmbe_percent(a, m),
        cvrmse_percent=cvrmse_percent(a, m),
        mae=mae(a, m),
        correlation=pearson_correlation(a, m),
        peak_error_percent=peak_error_percent(a, m),
    )


def _in_hour_band(hour: int, band: tuple[int, int]) -> bool:
    start, end = band
    if start <= end:
        return start <= hour < end
    return hour >= start or hour < end  # wraps midnight, e.g. (22, 6)


def split_masks(
    timestamps: Sequence[datetime],
    *,
    oat_f: Sequence[float] | None = None,
    occupied_hours: tuple[int, int] = DEFAULT_OCCUPIED_HOURS,
    nighttime_hours: tuple[int, int] = DEFAULT_NIGHTTIME_HOURS,
    hot_threshold_f: float = DEFAULT_HOT_THRESHOLD_F,
    cold_threshold_f: float = DEFAULT_COLD_THRESHOLD_F,
) -> dict[str, list[bool]]:
    """Boolean masks for the diagnostic time splits.

    ``hot`` / ``cold`` splits are only produced when outdoor air temperature
    (``oat_f``, aligned with ``timestamps``) is supplied.
    """
    if oat_f is not None and len(oat_f) != len(timestamps):
        raise ValueError(
            f"oat_f length {len(oat_f)} must match timestamps length {len(timestamps)}"
        )
    masks: dict[str, list[bool]] = {
        "nighttime": [_in_hour_band(t.hour, nighttime_hours) for t in timestamps],
        "occupied": [
            t.weekday() < 5 and _in_hour_band(t.hour, occupied_hours)
            for t in timestamps
        ],
        "weekend": [t.weekday() >= 5 for t in timestamps],
    }
    if oat_f is not None:
        masks["hot"] = [temp >= hot_threshold_f for temp in oat_f]
        masks["cold"] = [temp <= cold_threshold_f for temp in oat_f]
    return masks


def split_metrics(
    timestamps: Sequence[datetime],
    actual: Sequence[float],
    modeled: Sequence[float],
    *,
    oat_f: Sequence[float] | None = None,
    min_points: int = 2,
    occupied_hours: tuple[int, int] = DEFAULT_OCCUPIED_HOURS,
    nighttime_hours: tuple[int, int] = DEFAULT_NIGHTTIME_HOURS,
    hot_threshold_f: float = DEFAULT_HOT_THRESHOLD_F,
    cold_threshold_f: float = DEFAULT_COLD_THRESHOLD_F,
    mask_overrides: Mapping[str, Sequence[bool]] | None = None,
) -> dict[str, MetricSet]:
    """Metrics per diagnostic split; splits with < ``min_points`` are omitted."""
    a, m = _validate(actual, modeled)
    if len(timestamps) != len(a):
        raise ValueError(
            f"timestamps length {len(timestamps)} must match series length {len(a)}"
        )
    masks: dict[str, Sequence[bool]] = dict(
        split_masks(
            timestamps,
            oat_f=oat_f,
            occupied_hours=occupied_hours,
            nighttime_hours=nighttime_hours,
            hot_threshold_f=hot_threshold_f,
            cold_threshold_f=cold_threshold_f,
        )
    )
    if mask_overrides:
        masks.update(mask_overrides)
    out: dict[str, MetricSet] = {}
    for name, mask in masks.items():
        sel_a = [x for x, keep in zip(a, mask) if keep]
        sel_m = [y for y, keep in zip(m, mask) if keep]
        if len(sel_a) < min_points:
            continue
        out[name] = compute_metrics(sel_a, sel_m)
    return out
