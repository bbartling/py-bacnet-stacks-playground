"""Detect historian sample interval and downsample sub-5-minute series to 5-minute means."""

from __future__ import annotations

import numpy as np
import pandas as pd

FIVE_MINUTES_SEC = 300


def infer_median_interval_seconds(ts: pd.Series | pd.DatetimeIndex) -> float | None:
    """Median positive delta between consecutive timestamps (seconds)."""
    if ts is None or len(ts) < 2:
        return None
    ordered = pd.Series(ts).sort_values()
    deltas = ordered.diff().dt.total_seconds().dropna()
    deltas = deltas[(deltas > 0) & (deltas <= 86400)]
    if deltas.empty:
        return None
    return float(deltas.median())


def effective_poll_seconds(ts: pd.Series, *, target_sec: int = FIVE_MINUTES_SEC) -> int:
    """Analysis grid in seconds: 5 min when native cadence is finer, else native median."""
    med = infer_median_interval_seconds(ts)
    if med is None:
        return target_sec
    if med < target_sec - 0.5:
        return target_sec
    return max(60, int(round(med)))


def maybe_downsample_to_5min(
    df: pd.DataFrame,
    *,
    ts_col: str = "timestamp",
    target_sec: int = FIVE_MINUTES_SEC,
) -> pd.DataFrame:
    """
    If median timestamp spacing is under 5 minutes, resample to 5-minute means.

    Coarser-than-5-minute data (e.g. 15-min manifest grid) is left unchanged.
    Sets ``df.attrs['effective_poll_seconds']`` for downstream FDD rollups.
    """
    if ts_col not in df.columns or len(df) < 2:
        poll = effective_poll_seconds(df[ts_col] if ts_col in df.columns else pd.Series(dtype="datetime64[ns, UTC]"))
        df = df.copy()
        df.attrs["effective_poll_seconds"] = poll
        return df

    med = infer_median_interval_seconds(df[ts_col])
    poll = effective_poll_seconds(df[ts_col], target_sec=target_sec)

    if med is None or med >= target_sec - 0.5:
        out = df.copy()
        out.attrs["effective_poll_seconds"] = poll
        return out

    work = df.set_index(ts_col).sort_index()
    resampled = work.resample(f"{target_sec}s").mean(numeric_only=True)
    resampled = resampled.dropna(how="all").reset_index()
    resampled.attrs["effective_poll_seconds"] = poll
    return resampled
