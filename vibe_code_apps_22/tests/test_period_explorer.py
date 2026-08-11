"""Tests for BOPTEST-style period explorer."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eplus_gym_app.period_explorer import days_for_period, facility_kw_for_days
from eplus_gym_app.site_bundle import load_site_ui_bundle


def _bas_frame() -> pd.DataFrame:
    rows = []
    for day in ("2026-01-20", "2026-01-26", "2026-01-27", "2025-12-15", "2026-02-01"):
        for h in range(24):
            rows.append(
                {
                    "hour_utc": pd.Timestamp(f"{day}T{h:02d}:00:00+00:00"),
                    "day_type": "Weekday",
                    "kw_avg": 100.0 + h,
                    "oat_f": 0.0,
                    "local_day": day,
                    "hod": float(h),
                }
            )
    return pd.DataFrame(rows)


def test_days_peak_week_contains_peak():
    bas = _bas_frame()
    days = days_for_period(bas, preset="Peak week", peak_day="2026-01-26")
    assert "2026-01-26" in days
    assert len(days) >= 1
    assert len(days) <= 7


def test_days_winter_includes_dec_jan_feb():
    bas = _bas_frame()
    days = days_for_period(bas, preset="Winter (Dec–Feb)", peak_day="2026-01-26")
    assert any(d.startswith("2025-12") for d in days)
    assert any(d.startswith("2026-01") for d in days)
    assert any(d.startswith("2026-02") for d in days)


def test_facility_kw_for_days_strict_md(tmp_path: Path):
    sim = tmp_path / "sim"
    sim.mkdir()
    lines = [
        "Date/Time,Electricity:Facility [J](Hourly)",
        " 11/26  01:00:00,3600000",
        " 01/26  01:00:00,720000000",
        " 01/27  01:00:00,360000000",
    ]
    (sim / "eplusout.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    df = facility_kw_for_days(sim, ["2026-01-26", "2026-01-27"])
    assert df is not None
    assert set(df["local_day"]) == {"2026-01-26", "2026-01-27"}
    assert float(df.loc[df["local_day"] == "2026-01-26", "kw"].iloc[0]) == pytest.approx(
        200.0
    )


@pytest.mark.skipif(
    not Path(
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside\reports\demand_vs_web_weather_hourly.csv"
    ).is_file(),
    reason="site not present",
)
def test_period_overlay_a04_peak_day_smoke(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "LAKESIDE_SITE_ROOT",
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
    )
    from eplus_gym_app.period_explorer import period_overlay

    b = load_site_ui_bundle()
    active = b.get_model("A04")
    ov = period_overlay(b, active, preset="Peak day")
    assert ov["n_days"] == 1
    assert ov["sim_id"] == "A04"
    assert ov["actual_peak_kw"] < 400
    if ov["sim"] is not None and not ov["sim"].empty:
        assert ov["sim_peak_kw"] < 400  # not IdealLoads 500+ farm junk
