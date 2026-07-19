"""Interval duration utilities for irregular timestamps."""

from __future__ import annotations

import pytest
import pandas as pd

from app.runtime_intervals import hours_under_mask, interval_durations


def test_interval_durations_sorts_deduplicates_and_caps_gaps():
    idx = pd.DatetimeIndex([
        "2026-07-01T00:10:00Z",
        "2026-07-01T00:00:00Z",
        "2026-07-01T00:10:00Z",
        "2026-07-01T04:00:00Z",
    ])
    result = interval_durations(
        idx, nominal_seconds=600, max_gap_seconds=1800
    )
    assert result.index.is_monotonic_increasing
    assert result.index.is_unique
    assert result.tolist() == [600.0, 1800.0, 0.0]


def test_hours_under_mask_does_not_credit_final_row_or_large_gap():
    idx = pd.to_datetime([
        "2026-07-01T00:00:00Z",
        "2026-07-01T00:10:00Z",
        "2026-07-01T05:00:00Z",
    ])
    mask = pd.Series([True, True, True], index=idx)
    assert hours_under_mask(
        mask, nominal_seconds=600, max_gap_seconds=1800
    ) == pytest.approx(40 / 60)


def test_interval_durations_preserves_timezone():
    idx = pd.date_range(
        "2026-07-01T00:00:00", periods=3, freq="10min", tz="America/Chicago"
    )
    result = interval_durations(idx, nominal_seconds=600, max_gap_seconds=1800)
    assert result.index.tz is not None
    assert str(result.index.tz) == "America/Chicago"
    assert result.tolist() == [600.0, 600.0, 0.0]
