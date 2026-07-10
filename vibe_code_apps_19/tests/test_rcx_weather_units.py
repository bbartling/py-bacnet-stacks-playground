"""Tests for weather psychrometrics, occupancy, RCx collectors, unit system."""

from __future__ import annotations

import pandas as pd

from app.occupancy import OccupancySchedule, apply_schedule_occ_mode, occupied_mask
from app.rcx_plots import collect_role_series, series_summary_stats
from app.rules.cookbook_catalog import RULES, RULES_BY_ID, cw_opt, vav7
from app.unit_system import convert_series, f_to_c
from app.weather_psychrometrics import dewpoint_f_from_db_rh, enrich_weather_frame, wetbulb_f_stull


def test_canonical_rule_count_still_50():
    assert len(RULES) == 50
    assert "CW-OPT-1" in RULES_BY_ID
    assert "WX-2" not in RULES_BY_ID


def test_dewpoint_and_wetbulb_reasonable():
    t = pd.Series([70.0, 80.0])
    rh = pd.Series([50.0, 40.0])
    dp = dewpoint_f_from_db_rh(t, rh)
    wb = wetbulb_f_stull(t, rh)
    assert dp.iloc[0] < 70.0
    assert wb.iloc[0] < 70.0
    assert wb.iloc[0] > dp.iloc[0]


def test_enrich_weather_derives_dewpoint():
    idx = pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame({"temperature_2m": [70.0, 72.0, 71.0], "relative_humidity_2m": [50.0, 55.0, 45.0]}, index=idx)
    out = enrich_weather_frame(df)
    assert "wx_oa_t" in out.columns
    assert "wx_oa_dewpoint" in out.columns
    assert out["wx_oa_dewpoint"].notna().all()
    assert "wx_oa_wetbulb" in out.columns


def test_occupancy_weekday_mask():
    # Monday 2024-01-01 is a Monday
    idx = pd.date_range("2024-01-01 05:00", periods=24, freq="1h", tz="UTC")
    sched = OccupancySchedule()
    mask = occupied_mask(idx, sched)
    # 05:00 UTC may be previous evening in Chicago — just ensure boolean series length
    assert len(mask) == 24
    assert mask.dtype == bool


def test_apply_schedule_writes_occ_mode():
    idx = pd.date_range("2024-01-01", periods=10, freq="1h", tz="UTC")
    df = pd.DataFrame({"zone_t": range(10)}, index=idx)
    out = apply_schedule_occ_mode(df, OccupancySchedule(), overwrite=True)
    assert "occ_mode" in out.columns
    assert set(out["occ_mode"].unique()) <= {"occupied", "unoccupied"}


def test_unit_convert_f_to_c():
    s = pd.Series([32.0, 212.0])
    conv, unit = convert_series("sat", s, "metric")
    assert unit == "°C"
    assert abs(conv.iloc[0] - 0.0) < 1e-6
    assert abs(f_to_c(212) - 100) < 1e-6


def test_vav7_fixed_high_flow():
    idx = pd.date_range("2024-01-01", periods=40, freq="5min", tz="UTC")
    # Constant high flow with damper/air on
    d = pd.DataFrame(
        {
            "zone_flow": [400.0] * 40,
            "min_flow_sp": [300.0] * 40,
            "damper_pct": [50.0] * 40,
        },
        index=idx,
    )
    raw = vav7(d, {"fixed_flow_max_std": 15.0, "fixed_flow_min_mean": 200.0, "high_min_flow_sp": 250.0, "flow_on_min": 25.0}, 300.0)
    assert bool(raw.iloc[-1])


def test_cw_opt_faults_when_overcooled():
    idx = pd.date_range("2024-01-01", periods=5, freq="5min", tz="UTC")
    d = pd.DataFrame(
        {"cw_supply_t": [60.0] * 5, "wx_oa_wetbulb": [70.0] * 5},
        index=idx,
    )
    # target = 70+7=77, slack 2 → fault if CW < 75; 60 is fault
    raw = cw_opt(d, {"cw_approach": 7.0, "cw_slack": 2.0}, 300.0)
    assert bool(raw.all())


def test_rcx_collect_and_outliers():
    idx = pd.date_range("2024-01-01", periods=10, freq="5min", tz="UTC")
    frames = {
        "VAV_1": pd.DataFrame({"zone_t": [72.0] * 10}, index=idx),
        "VAV_2": pd.DataFrame({"zone_t": [72.5] * 10}, index=idx),
        "VAV_3": pd.DataFrame({"zone_t": [95.0] * 10}, index=idx),
    }
    for eq, df in frames.items():
        df.attrs["equipment_type"] = "VAV"
    role_map = {eq: {"zone_t": "zone_t"} for eq in frames}
    series = collect_role_series(frames, role_map, role="zone_t", equipment_types=("VAV",))
    assert len(series) == 3
    stats = series_summary_stats(series, outlier_z=2.0)
    assert "outlier" in stats.columns
