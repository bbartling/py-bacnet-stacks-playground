"""Interval meter loader: DST handling, missing/duplicate detection, coverage."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from wattlab.existing_building.interval_meters import (
    IntervalLoadError,
    convert_cumulative,
    load_interval_csv,
)


def _write_csv(path, rows, header="timestamp,electric_kwh,electric_kw,gas_therms,quality"):
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def _hourly_rows(start: datetime, n: int, skip=(), duplicate=()):
    rows = []
    for i in range(n):
        ts = start + timedelta(hours=i)
        if i in skip:
            continue
        stamp = ts.strftime("%Y-%m-%dT%H:%M:%S")
        row = f"{stamp},10.0,10.0,0.5,good"
        rows.append(row)
        if i in duplicate:
            rows.append(row)
    return rows


def test_basic_load_and_coverage(tmp_path):
    csv = _write_csv(tmp_path / "m.csv", _hourly_rows(datetime(2025, 6, 1), 48))
    ds = load_interval_csv(csv, timezone="America/Chicago")
    assert ds.stats.interval_minutes == 60
    assert ds.stats.expected_intervals == 48
    assert ds.stats.missing_intervals == 0
    assert ds.stats.coverage_fraction == pytest.approx(1.0)
    assert str(ds.frame.index.tz) == "America/Chicago"


def test_missing_intervals_are_reported_not_invented(tmp_path):
    csv = _write_csv(
        tmp_path / "m.csv", _hourly_rows(datetime(2025, 6, 1), 48, skip={5, 6, 7})
    )
    ds = load_interval_csv(csv, timezone="UTC")
    assert ds.stats.expected_intervals == 48
    assert ds.stats.missing_intervals == 3
    assert ds.frame["electric_kwh"].isna().sum() == 3
    assert len(ds.missing_timestamps) == 3


def test_exact_duplicates_collapse_conflicting_duplicates_raise(tmp_path):
    csv = _write_csv(
        tmp_path / "m.csv", _hourly_rows(datetime(2025, 6, 1), 24, duplicate={3})
    )
    ds = load_interval_csv(csv, timezone="UTC")
    assert ds.stats.duplicate_rows_dropped == 1
    assert ds.stats.expected_intervals == 24

    rows = _hourly_rows(datetime(2025, 6, 1), 24)
    rows.insert(4, "2025-06-01T03:00:00,999.0,10.0,0.5,good")  # same time, new value
    csv2 = _write_csv(tmp_path / "m2.csv", rows)
    with pytest.raises(IntervalLoadError, match="conflicting duplicate"):
        load_interval_csv(csv2, timezone="UTC")


def test_dst_fall_back_repeated_hour_loads(tmp_path):
    """US fall-back 2025-11-02: local 01:00 occurs twice; both must load."""
    rows = []
    for stamp in [
        "2025-11-02T00:00:00",
        "2025-11-02T01:00:00",  # first pass (CDT)
        "2025-11-02T01:00:00",  # second pass (CST)
        "2025-11-02T02:00:00",
        "2025-11-02T03:00:00",
    ]:
        rows.append(f"{stamp},10.0,10.0,0.5,good")
    csv = _write_csv(tmp_path / "dst.csv", rows)
    ds = load_interval_csv(csv, timezone="America/Chicago")
    assert ds.stats.expected_intervals == 5
    assert ds.stats.missing_intervals == 0
    # The two 01:00 stamps resolve to distinct UTC instants one hour apart.
    utc = ds.frame.index.tz_convert("UTC")
    assert (pd.Series(utc).diff().dropna() == pd.Timedelta(hours=1)).all()


def test_dst_spring_forward_nonexistent_time_rejected(tmp_path):
    """US spring-forward 2025-03-09: local 02:00 does not exist."""
    rows = [
        "2025-03-09T01:00:00,10.0,10.0,0.5,good",
        "2025-03-09T02:00:00,10.0,10.0,0.5,good",
        "2025-03-09T03:00:00,10.0,10.0,0.5,good",
    ]
    csv = _write_csv(tmp_path / "dst.csv", rows)
    with pytest.raises(IntervalLoadError, match="localize"):
        load_interval_csv(csv, timezone="America/Chicago")


def test_bad_quality_rows_are_masked_and_counted(tmp_path):
    rows = _hourly_rows(datetime(2025, 6, 1), 6)
    rows[2] = rows[2].replace(",good", ",estimated")
    csv = _write_csv(tmp_path / "q.csv", rows)
    ds = load_interval_csv(csv, timezone="UTC")
    assert ds.stats.bad_quality_rows == 1
    assert ds.stats.missing_intervals == 1  # masked row has no usable values


def test_cumulative_conversion_handles_resets():
    idx = pd.date_range("2025-06-01", periods=5, freq="h", tz="UTC")
    register = pd.Series([100.0, 110.0, 125.0, 5.0, 20.0], index=idx)  # reset at #3
    diffs = convert_cumulative(register)
    assert diffs.iloc[0] != diffs.iloc[0]  # first interval NaN
    assert diffs.iloc[1] == pytest.approx(10.0)
    assert diffs.iloc[3] != diffs.iloc[3]  # reset is NaN, never negative
    assert diffs.iloc[4] == pytest.approx(15.0)
    with pytest.raises(IntervalLoadError, match="decreased"):
        convert_cumulative(register, allow_resets=False)


def test_cumulative_column_conversion_in_loader(tmp_path):
    rows = [
        f"2025-06-01T{h:02d}:00:00,{100 + 10 * h}.0,10.0,0.5,good" for h in range(4)
    ]
    csv = _write_csv(tmp_path / "c.csv", rows)
    ds = load_interval_csv(csv, timezone="UTC", cumulative_columns=["electric_kwh"])
    got = ds.frame["electric_kwh"].tolist()
    assert got[0] != got[0]  # NaN
    assert got[1:] == pytest.approx([10.0, 10.0, 10.0])


def test_irregular_spacing_rejected(tmp_path):
    rows = [
        "2025-06-01T00:00:00,10.0,10.0,0.5,good",
        "2025-06-01T01:00:00,10.0,10.0,0.5,good",
        "2025-06-01T01:20:00,10.0,10.0,0.5,good",
    ]
    csv = _write_csv(tmp_path / "bad.csv", rows)
    with pytest.raises(IntervalLoadError, match="spacing|interval"):
        load_interval_csv(csv, timezone="UTC")


def test_resample_sums_energy_and_averages_demand(tmp_path):
    rows = []
    for i in range(8):  # 2 hours of 15-minute data
        ts = datetime(2025, 6, 1) + timedelta(minutes=15 * i)
        rows.append(f"{ts.strftime('%Y-%m-%dT%H:%M:%S')},2.5,{10 + i}.0,0.1,good")
    csv = _write_csv(tmp_path / "r.csv", rows)
    ds = load_interval_csv(csv, timezone="UTC")
    assert ds.stats.interval_minutes == 15
    hourly = ds.resample(60)
    assert len(hourly) == 2
    assert hourly["electric_kwh"].tolist() == pytest.approx([10.0, 10.0])
    assert hourly["electric_kw"].tolist() == pytest.approx([11.5, 15.5])
    with pytest.raises(IntervalLoadError, match="multiple"):
        ds.resample(40)


def test_resample_never_hides_missing_data(tmp_path):
    rows = []
    for i in range(8):
        if i == 5:
            continue
        ts = datetime(2025, 6, 1) + timedelta(minutes=15 * i)
        rows.append(f"{ts.strftime('%Y-%m-%dT%H:%M:%S')},2.5,10.0,0.1,good")
    csv = _write_csv(tmp_path / "r.csv", rows)
    hourly = load_interval_csv(csv, timezone="UTC").resample(60)
    assert hourly["electric_kwh"].iloc[0] == pytest.approx(10.0)
    assert pd.isna(hourly["electric_kwh"].iloc[1])  # hour with the hole stays NaN


def test_monthly_totals_are_multi_year_safe(tmp_path):
    rows = _hourly_rows(datetime(2024, 12, 31, 22), 6)  # spans a year boundary
    csv = _write_csv(tmp_path / "y.csv", rows)
    ds = load_interval_csv(csv, timezone="UTC")
    totals = ds.monthly_totals("electric_kwh")
    assert set(totals) == {"2024-12", "2025-01"}
