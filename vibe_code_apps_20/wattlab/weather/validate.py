"""Shared weather validation helpers for Open-Meteo downloads and AMY EPW builds.

Used by :mod:`wattlab.weather.open_meteo` and :mod:`wattlab.weather.epw` so
physical bounds and hourly-index checks stay consistent.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

# One hour as a Timedelta — compare deltas to this instead of magic nanoseconds.
ONE_HOUR = pd.Timedelta(hours=1)

# Inclusive physical bounds for EPW-builder column names (Fahrenheit / mph / hPa / W/m2).
EPW_COLUMN_BOUNDS: dict[str, tuple[float, float]] = {
    "dry_bulb_f": (-130.0, 140.0),
    "dew_point_f": (-130.0, 110.0),
    "relative_humidity_pct": (0.0, 100.0),
    "surface_pressure_hpa": (300.0, 1100.0),
    "shortwave_radiation_wm2": (0.0, 1500.0),
    "direct_normal_irradiance_wm2": (0.0, 1400.0),
    "diffuse_radiation_wm2": (0.0, 1000.0),
    "wind_speed_mph": (0.0, 250.0),
    "wind_direction_deg": (0.0, 360.0),
}


def assert_consecutive_hourly_index(
    index: pd.DatetimeIndex,
    *,
    context: str = "timestamps",
) -> None:
    """Reject empty, duplicate, non-hourly, or gappy datetime indexes."""
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError(f"{context} must be a DatetimeIndex")
    if len(index) == 0:
        raise ValueError(f"{context} is empty")
    if index.has_duplicates:
        dupes = index[index.duplicated()].unique()
        raise ValueError(
            f"{context} contain duplicate timestamps: "
            + ", ".join(str(t) for t in dupes[:5])
        )
    off_hour = (index.minute != 0) | (index.second != 0) | (index.microsecond != 0)
    if off_hour.any():
        raise ValueError(f"{context} contain non-hourly timestamp {index[off_hour][0]}")
    if len(index) > 1:
        deltas = index.to_series().diff().iloc[1:]
        bad_mask = deltas != ONE_HOUR
        if bad_mask.any():
            pos = int(np.flatnonzero(bad_mask.to_numpy())[0])
            raise ValueError(
                f"{context} are not consecutive hourly steps "
                f"(gap or disorder between {index[pos]} and {index[pos + 1]})"
            )


def assert_finite_in_bounds(
    name: str,
    values: Any,
    bounds: tuple[float, float],
) -> np.ndarray:
    """Coerce to float array; reject non-finite or out-of-bounds values."""
    try:
        arr = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} contains non-numeric values: {exc}") from exc
    arr = np.asarray(arr, dtype=float).reshape(-1)
    if not np.isfinite(arr).all():
        pos = int(np.argmin(np.isfinite(arr)))
        raise ValueError(f"{name} contains missing or non-finite value at index {pos}")
    lo, hi = bounds
    if (arr < lo).any() or (arr > hi).any():
        bad = arr[(arr < lo) | (arr > hi)][0]
        raise ValueError(f"{name} value {bad} outside physical bounds [{lo}, {hi}]")
    return arr


def assert_epw_frame_physical_bounds(df: pd.DataFrame) -> None:
    """Validate present EPW-builder columns against shared physical bounds."""
    for column, bounds in EPW_COLUMN_BOUNDS.items():
        if column not in df.columns:
            continue
        assert_finite_in_bounds(column, df[column].to_numpy(), bounds)
