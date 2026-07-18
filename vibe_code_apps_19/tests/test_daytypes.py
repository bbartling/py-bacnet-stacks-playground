"""Day-type classification for WattLab diurnal dumps."""

from __future__ import annotations

import pandas as pd

from app.daytypes import DAY_TYPES, day_type_masks, day_type_series


def test_weekday_weekend_labels():
    # 2024-03-04 is a Monday; 2024-03-09/10 are Sat/Sun
    idx = pd.date_range("2024-03-04", periods=7, freq="D", tz="UTC")
    labels = day_type_series(idx)
    assert list(labels.iloc[:5]) == ["weekday"] * 5
    assert list(labels.iloc[5:]) == ["weekend", "weekend"]


def test_us_federal_holiday_takes_precedence():
    # 2024-07-04 is Independence Day (Thursday) — must be holiday, not weekday
    idx = pd.DatetimeIndex(
        [
            "2024-07-03 12:00",  # Wednesday
            "2024-07-04 12:00",  # Thursday holiday
            "2024-07-05 12:00",  # Friday
            "2024-07-06 12:00",  # Saturday
        ],
        tz="UTC",
    )
    labels = day_type_series(idx)
    assert labels.iloc[0] == "weekday"
    assert labels.iloc[1] == "holiday"
    assert labels.iloc[2] == "weekday"
    assert labels.iloc[3] == "weekend"


def test_day_type_masks_cover_index():
    idx = pd.date_range("2024-01-01", periods=48, freq="h", tz="America/Chicago")
    masks = day_type_masks(idx)
    assert set(masks) == set(DAY_TYPES)
    # Every timestamp belongs to exactly one day_type
    stacked = sum(m.astype(int) for m in masks.values())
    assert (stacked == 1).all()
    # New Year's Day 2024 is a holiday
    assert masks["holiday"].any()


def test_empty_index():
    labels = day_type_series(pd.DatetimeIndex([]))
    assert labels.empty
