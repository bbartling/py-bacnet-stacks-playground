"""Unit tests for timing_utils.format_hms / TimingReport."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

_ML = Path(__file__).resolve().parents[1] / "ml"
sys.path.insert(0, str(_ML))

from timing_utils import TimingReport, Stopwatch, format_hms  # noqa: E402


def test_format_hms_zero():
    assert "0h" in format_hms(0)
    assert "00m" in format_hms(0)


def test_format_hms_65_seconds():
    out = format_hms(65)
    assert "0h" in out
    assert "01m" in out


def test_format_hms_3661_seconds():
    out = format_hms(3661)
    assert out.startswith("1h")
    assert "01m" in out


def test_stopwatch_and_report():
    rep = TimingReport()
    with rep.time("sleep_tiny"):
        time.sleep(0.01)
    assert len(rep.entries) == 1
    assert rep.entries[0][0] == "sleep_tiny"
    assert rep.entries[0][1] >= 0.005
    sw = Stopwatch("x").start()
    time.sleep(0.005)
    sw.stop()
    assert sw.elapsed >= 0.004
    rep.record("manual", sw.elapsed)
    rep.print_summary("test")
