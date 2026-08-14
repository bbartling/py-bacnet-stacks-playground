"""EPW DATA PERIODS year-aware + repair for multi-year AMY."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from eplus_gym_app.open_meteo_epw import (
    parse_epw_data_periods,
    parse_epw_span,
    repair_epw_data_periods,
    to_local_standard,
    write_epw,
)
from eplus_gym_app.dsm_preflight import assert_period_within_epw


def _hourly(start: str, hours: int, *, oat_f: float = 20.0) -> pd.DataFrame:
    idx = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp_utc": idx,
            "dry_bulb_f": [oat_f + i * 0.1 for i in range(hours)],
            "dew_point_f": [oat_f - 8.0] * hours,
            "relative_humidity_pct": [70.0] * hours,
            "surface_pressure_hpa": [992.0] * hours,
            "shortwave_radiation_wm2": [0.0] * hours,
            "direct_normal_irradiance_wm2": [0.0] * hours,
            "diffuse_radiation_wm2": [0.0] * hours,
            "wind_speed_mph": [5.0] * hours,
            "wind_direction_deg": [270.0] * hours,
        }
    )


def test_write_epw_data_periods_year_aware(tmp_path: Path):
    # Two full local days spanning year boundary-ish window via 48h from late Dec
    raw = _hourly("2025-08-01T06:00:00Z", 48)
    lst = to_local_standard(raw, utc_offset_hours=-6)
    out = tmp_path / "amy.epw"
    write_epw(lst, out, lat=43.0, lon=-89.0, elevation_m=261.0)
    text = out.read_text(encoding="utf-8")
    hdr = [ln for ln in text.splitlines() if ln.startswith("DATA PERIODS")][0]
    assert "2025/" in hdr or "/2025" in hdr or "2026/" in hdr or "/2026" in hdr
    parts = hdr.split(",")
    assert parts[5].count("/") == 2
    assert parts[6].count("/") == 2
    assert int(parts[5].split("/")[0]) <= 12  # mm/dd/yyyy
    dp = parse_epw_data_periods(out)
    assert dp["year_aware"] is True


def test_repair_legacy_data_periods_enables_winter(tmp_path: Path):
    # Build a tiny multi-day EPW then corrupt DATA PERIODS like production bug
    raw = _hourly("2025-08-01T06:00:00Z", 24 * 10)
    lst = to_local_standard(raw, utc_offset_hours=-6)
    epw = tmp_path / "madison_amy.epw"
    write_epw(lst, epw, lat=43.0, lon=-89.0, elevation_m=261.0)
    # Append fake winter rows so span includes Jan 2026
    lines = epw.read_text(encoding="utf-8").splitlines()
    extra = []
    for h in range(1, 25):
        extra.append(
            f"2026,1,26,{h},0,?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9?9,"
            "-10.0,-15.0,50,99200,0,0,9999,0,0,0,9999,9999,9999,9999,270,2.0,"
            "9999,9999,99999,0,0.0,0,0,0.0,0,0,0,0,0"
        )
    # Corrupt header to legacy mm/dd Aug-only
    fixed = []
    for ln in lines:
        if ln.startswith("DATA PERIODS"):
            fixed.append("DATA PERIODS,1,1,Data,Friday,8/1,8/7")
        else:
            fixed.append(ln)
    fixed.extend(extra)
    epw.write_text("\n".join(fixed) + "\n", encoding="utf-8")
    before = parse_epw_data_periods(epw)
    assert before["year_aware"] is False
    meta = repair_epw_data_periods(epw)
    assert meta["changed"] is True
    after = parse_epw_data_periods(epw)
    assert after["year_aware"] is True
    assert after["start"] == date(2025, 8, 1)
    assert after["end"] == date(2026, 1, 26)
    span = parse_epw_span(epw)
    assert span["start"] == date(2025, 8, 1)
    assert span["end"] == date(2026, 1, 26)
    # Preflight should accept winter peak after repair
    info = assert_period_within_epw("2026-01-26", "2026-01-26", epw)
    assert info["data_periods_year_aware"] is True
