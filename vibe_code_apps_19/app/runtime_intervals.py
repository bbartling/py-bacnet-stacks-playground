"""Trustworthy interval durations for irregular timestamps."""

from __future__ import annotations

import pandas as pd


def interval_durations(
    index: pd.Index,
    *,
    nominal_seconds: float,
    max_gap_seconds: float | None = None,
    final_duration_seconds: float = 0.0,
) -> pd.Series:
    if not isinstance(index, pd.DatetimeIndex) or index.empty:
        return pd.Series(dtype=float)
    clean = pd.DatetimeIndex(index).drop_duplicates().sort_values()
    seconds = clean.to_series().shift(-1).sub(clean.to_series()).dt.total_seconds()
    cap = (
        float(max_gap_seconds)
        if max_gap_seconds is not None
        else max(float(nominal_seconds) * 3.0, float(nominal_seconds))
    )
    seconds = seconds.clip(lower=0.0, upper=cap)
    if len(seconds):
        seconds.iloc[-1] = max(float(final_duration_seconds), 0.0)
    return seconds.astype(float)


def hours_under_mask(
    mask: pd.Series,
    *,
    nominal_seconds: float,
    max_gap_seconds: float | None = None,
) -> float:
    normalized = mask.groupby(level=0).max().sort_index().fillna(False).astype(bool)
    durations = interval_durations(
        normalized.index,
        nominal_seconds=nominal_seconds,
        max_gap_seconds=max_gap_seconds,
    )
    return float((normalized.reindex(durations.index).astype(float) * durations).sum() / 3600.0)
