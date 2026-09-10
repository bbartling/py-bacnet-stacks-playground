"""Deterministic synthetic control-output series for PID-HUNT-1 tutorials."""

from __future__ import annotations

import numpy as np
import pandas as pd

POLL_SECONDS = 60.0
COLUMN = "cooling-valve"


def _index(hours: float = 3.0, *, start: str = "2024-07-15 08:00:00") -> pd.DatetimeIndex:
    periods = int(hours * 3600 / POLL_SECONDS)
    return pd.date_range(start, periods=periods, freq=f"{int(POLL_SECONDS)}s")


def healthy_cooling_valve(
    *,
    hours: float = 3.0,
    start_pct: float = 20.0,
    end_pct: float = 55.0,
    noise_std: float = 0.15,
    seed: int = 7,
) -> pd.DataFrame:
    """Slow ramp with sub-deadband noise — should NOT trip PID-HUNT-1 defaults."""
    idx = _index(hours)
    rng = np.random.default_rng(seed)
    ramp = np.linspace(start_pct, end_pct, len(idx))
    noise = rng.normal(0.0, noise_std, len(idx))
    series = np.clip(ramp + noise, 0.0, 100.0)
    return pd.DataFrame({COLUMN: series}, index=idx)


def hunting_cooling_valve(
    *,
    hours: float = 3.0,
    low_pct: float = 10.0,
    high_pct: float = 90.0,
    half_period_samples: int = 5,
) -> pd.DataFrame:
    """Square-wave AO chatter — trips default PID-HUNT-1 (TV/span/cycles/reversals)."""
    idx = _index(hours)
    t = np.arange(len(idx))
    period = max(2, int(half_period_samples) * 2)
    series = np.where((t % period) < half_period_samples, high_pct, low_pct).astype(float)
    return pd.DataFrame({COLUMN: series}, index=idx)


def hunting_sine_cooling_valve(
    *,
    hours: float = 3.0,
    center_pct: float = 50.0,
    amplitude_pct: float = 40.0,
    period_samples: int = 6,
) -> pd.DataFrame:
    """Sine AO hunting. Default ~10–90%. Mid-range example: center=55, amplitude=15 → ~40–70%."""
    idx = _index(hours)
    t = np.arange(len(idx), dtype=float)
    series = center_pct + amplitude_pct * np.sin(2.0 * np.pi * t / max(period_samples, 2))
    series = np.clip(series, 0.0, 100.0)
    return pd.DataFrame({COLUMN: series}, index=idx)


def hunting_midrange_sine_cooling_valve(
    *,
    hours: float = 3.0,
    period_samples: int = 6,
) -> pd.DataFrame:
    """Hunting that never goes near 0 or 100 — stays roughly 40–70% and still trips defaults."""
    return hunting_sine_cooling_valve(
        hours=hours,
        center_pct=55.0,
        amplitude_pct=15.0,
        period_samples=period_samples,
    )
