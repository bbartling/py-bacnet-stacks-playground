"""Unit tests for wattlab.energyplus.timeseries (eplusout.csv parser)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from wattlab.energyplus.timeseries import (
    downsample_frame,
    find_eplusout_csv,
    load_sim_timeseries,
    parse_eplusout_timeseries,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "eplusout" / "eplusout.csv"


def test_parse_eplusout_discovers_zones_oa_hvac():
    ts = parse_eplusout_timeseries(FIXTURE)
    assert not ts.outdoor.empty
    assert list(ts.outdoor.columns) == ["timestamp", "outdoor_db_c"]
    assert abs(float(ts.outdoor.iloc[0]["outdoor_db_c"]) - 5.0) < 1e-9

    assert not ts.zones.empty
    zones = sorted(ts.zones["zone"].unique())
    assert zones == ["SPACE1-1", "SPACE2-1", "SPACE3-1"]

    assert not ts.hvac.empty
    assert float(ts.hvac.iloc[0]["fan_w"]) == 1200.0
    assert float(ts.hvac.iloc[3]["cooling_w"]) == 25000.0

    assert not ts.facility.empty
    assert ts.columns_discovered["zone_mean_air_temp"]
    assert ts.columns_discovered["outdoor_drybulb"]


def test_zone_mean_temps_summary():
    ts = parse_eplusout_timeseries(FIXTURE)
    summary = ts.zone_mean_temps()
    assert len(summary) == 3
    row = summary.set_index("zone").loc["SPACE1-1"]
    assert row["n"] == 5
    assert row["min_c"] <= row["mean_c"] <= row["max_c"]


def test_find_and_load_sim_dir(tmp_path: Path):
    dest = tmp_path / "sim"
    dest.mkdir()
    (dest / "eplusout.csv").write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    assert find_eplusout_csv(dest) == dest / "eplusout.csv"
    loaded = load_sim_timeseries(dest)
    assert loaded is not None
    assert len(loaded.outdoor) == 5


def test_missing_file_returns_empty():
    ts = parse_eplusout_timeseries(Path("/nonexistent/eplusout.csv"))
    assert ts.outdoor.empty and ts.zones.empty


def test_downsample_frame():
    df = pd.DataFrame({"x": range(100)})
    out = downsample_frame(df, max_points=10)
    assert len(out) <= 10
    assert len(downsample_frame(df, max_points=200)) == 100
