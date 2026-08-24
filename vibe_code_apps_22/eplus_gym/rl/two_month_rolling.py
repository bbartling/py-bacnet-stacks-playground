"""Rolling peak helpers for two-month replay."""
from __future__ import annotations


def rolling_max_mean(x: list[float], window: int) -> float:
    if not x:
        return 0.0
    if len(x) < window:
        return float(max(x))
    best = 0.0
    for i in range(len(x) - window + 1):
        best = max(best, float(sum(x[i : i + window]) / window))
    return best
