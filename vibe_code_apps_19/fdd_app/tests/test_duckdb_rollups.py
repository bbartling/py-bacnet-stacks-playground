"""Tests for DuckDB rollup helpers (pandas fallback always works)."""

import numpy as np
import pandas as pd

import duckdb_rollups as dr


def test_oat_bin_hours_pandas_fallback():
    idx = pd.date_range("2026-05-01", periods=12, freq="300s", tz="UTC")
    wx = pd.DataFrame({"timestamp": idx, "dry_bulb_f": np.linspace(50, 80, 12)})
    out = dr.oat_bin_hours(wx, poll_seconds=300)
    assert not out.empty
    assert "hours" in out.columns


def test_chiller_oat_bin_hours_empty_plant():
    wx = pd.DataFrame({"timestamp": [], "dry_bulb_f": []})
    out = dr.chiller_oat_bin_hours({}, wx)
    assert out.empty
