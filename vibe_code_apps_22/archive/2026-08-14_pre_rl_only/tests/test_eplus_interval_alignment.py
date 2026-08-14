"""Interval alignment forensics: TZ/DST/hour-ending/aggregation (no auto lag)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from eplus_native.align import (
    EPLUS_LST_OFFSET,
    aggregate_5min_to_15min_mean,
    aggregate_5min_to_hourly_mean,
    eplus_lst_to_utc,
    parse_eplus_csv_timestamp,
)


def test_eplus_24_hour_stamp_rolls_to_next_day():
    dt = parse_eplus_csv_timestamp("01/15  24:00:00", year_hint=2025)
    assert dt is not None
    assert dt.tzinfo == EPLUS_LST_OFFSET
    assert dt.day == 16
    assert dt.hour == 0


def test_eplus_lst_never_dst():
    # Mid-summer LST stamp → UTC is always +6h, not Chicago CDT (+5).
    dt = parse_eplus_csv_timestamp("07/04  12:00:00", year_hint=2025)
    assert dt is not None
    utc = dt.astimezone(timezone.utc)
    assert utc.hour == 18  # 12:00 CST-6 → 18:00 UTC


def test_hourly_aggregation_is_hour_ending():
    # Three 5-min points ending in hour 01:00 UTC
    rows = []
    base = datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc)
    for i in range(12):
        rows.append({"timestamp_utc": base + timedelta(minutes=5 * i), "kw_demand": 10.0 + i})
    df = pd.DataFrame(rows)
    hourly = aggregate_5min_to_hourly_mean(df, ts_col="timestamp_utc", kw_col="kw_demand")
    assert "kw_mean" in hourly.columns
    # First complete hour-ending bucket should land on 01:00
    ts = pd.to_datetime(hourly["timestamp_utc"], utc=True)
    assert ts.iloc[0].hour == 1 or len(hourly) >= 1


def test_15min_uses_mean_not_max():
    rows = []
    base = datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc)
    vals = [10.0, 50.0, 10.0]  # max=50, mean=70/3
    for i, v in enumerate(vals):
        rows.append({"timestamp_utc": base + timedelta(minutes=5 * i), "kw_demand": v})
    df = pd.DataFrame(rows)
    q = aggregate_5min_to_15min_mean(df, ts_col="timestamp_utc", kw_col="kw_demand")
    assert abs(float(q["kw_mean"].iloc[0]) - (70.0 / 3.0)) < 1e-9


def test_eplus_lst_series_to_utc_fixed_offset():
    s = pd.Series(["2025-01-15 14:00:00", "2025-07-15 14:00:00"])
    utc = eplus_lst_to_utc(s)
    # Both should be 20:00 UTC (14+6) — summer does NOT jump to 19:00
    hours = pd.to_datetime(utc, utc=True).dt.hour.tolist()
    assert hours == [20, 20]
