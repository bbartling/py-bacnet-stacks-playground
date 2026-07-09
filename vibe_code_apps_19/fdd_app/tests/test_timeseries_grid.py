"""Tests for historian grid detection and 5-minute downsampling."""

from __future__ import annotations

import pandas as pd

from haystack_rdf.timeseries_grid import (
    effective_poll_seconds,
    infer_median_interval_seconds,
    maybe_downsample_to_5min,
)


def _series(minutes: int, n: int = 20) -> pd.Series:
    start = pd.Timestamp("2026-04-01 08:00:00", tz="UTC")
    return pd.date_range(start, periods=n, freq=f"{minutes}min", tz="UTC")


def test_infer_median_1min():
    ts = _series(1)
    assert infer_median_interval_seconds(ts) == 60.0


def test_infer_median_15min():
    ts = _series(15)
    assert infer_median_interval_seconds(ts) == 900.0


def test_effective_poll_sub_5min():
    assert effective_poll_seconds(_series(1)) == 300


def test_effective_poll_coarse_unchanged():
    assert effective_poll_seconds(_series(15)) == 900


def test_downsample_1min_to_5min():
    ts = _series(1, n=30)
    df = pd.DataFrame({"timestamp": ts, "temp_f": range(30)})
    out = maybe_downsample_to_5min(df)
    assert len(out) < len(df)
    assert out.attrs["effective_poll_seconds"] == 300
    assert infer_median_interval_seconds(out["timestamp"]) == 300.0


def test_downsample_15min_unchanged():
    ts = _series(15, n=10)
    df = pd.DataFrame({"timestamp": ts, "temp_f": range(10)})
    out = maybe_downsample_to_5min(df)
    assert len(out) == len(df)
    assert out.attrs["effective_poll_seconds"] == 900
