"""Tariff / energy helpers for 15-min hybrid DSM series."""
from __future__ import annotations

from typing import Sequence

import numpy as np

QUARTER_H = 0.25  # hours per 15-min interval


def quarter_hour_kwh(kw_series: Sequence[float]) -> float:
    """Energy from mean-power quarters: sum(kW * 0.25 h)."""
    arr = np.asarray(kw_series, dtype=float).reshape(-1)
    return float(np.sum(arr) * QUARTER_H)


def hourly_mean_from_quarters(kw96: Sequence[float]) -> list[float]:
    """Collapse 96 quarter-hour kW means into 24 hourly means (energy-preserving)."""
    arr = np.asarray(kw96, dtype=float).reshape(-1)
    if arr.size != 96:
        raise ValueError(f"expected 96 quarter-hour values, got {arr.size}")
    return [float(arr[i * 4 : (i + 1) * 4].mean()) for i in range(24)]


def peak_kw(kw_series: Sequence[float]) -> float:
    """Instantaneous peak demand (max quarter-hour mean kW)."""
    arr = np.asarray(kw_series, dtype=float).reshape(-1)
    if arr.size == 0:
        raise ValueError("empty kw series")
    return float(np.max(arr))
