from __future__ import annotations
from math import sqrt
from statistics import mean
from typing import Sequence

def calibration_metrics(actual: Sequence[float], modeled: Sequence[float], parameters: int = 1) -> dict[str, float]:
    if len(actual) != len(modeled) or not actual:
        raise ValueError("actual and modeled must have equal non-zero lengths")
    a = [float(x) for x in actual]
    m = [float(x) for x in modeled]
    n = len(a)
    denom_n = max(1, n - parameters)
    avg = mean(a)
    residuals = [x-y for x, y in zip(a, m)]
    rmse = sqrt(sum(r*r for r in residuals)/denom_n)
    nmbe = 100.0 * sum(residuals)/(denom_n*avg) if avg else 0.0
    cvrmse = 100.0 * rmse/avg if avg else 0.0
    mae = sum(abs(r) for r in residuals)/n
    return {
        "n": n,
        "mean_actual": avg,
        "nmbe_percent": nmbe,
        "cvrmse_percent": cvrmse,
        "mae": mae,
        "rmse": rmse,
    }
