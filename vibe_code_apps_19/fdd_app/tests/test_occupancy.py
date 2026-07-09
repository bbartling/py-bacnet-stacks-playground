"""Tests for occupancy schedule helpers."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from shared.occupancy import DEFAULT_SCHEDULE, is_occupied, merge_site_settings, occupancy_summary


def test_occupancy_summary_default():
    text = occupancy_summary(DEFAULT_SCHEDULE)
    assert "Mon–Fri" in text
    assert "Sun closed" in text


def test_is_occupied_weekday_morning():
    ts = pd.Series([pd.Timestamp("2026-04-07 10:00", tz="America/Chicago")])
    occ = is_occupied(ts, DEFAULT_SCHEDULE, "America/Chicago")
    assert bool(occ.iloc[0]) is True


def test_is_occupied_sunday_closed():
    ts = pd.Series(pd.date_range("2026-04-05 10:00", periods=1, tz="UTC", freq="15min"))
    occ = is_occupied(ts, DEFAULT_SCHEDULE, "America/Chicago")
    assert bool(occ.iloc[0]) is False


def test_merge_site_settings():
    merged = merge_site_settings({"comfort_setpoint_f": 70})
    assert merged["comfort_setpoint_f"] == 70
    assert "occupancy" in merged
