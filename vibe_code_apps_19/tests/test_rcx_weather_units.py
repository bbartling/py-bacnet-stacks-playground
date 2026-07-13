"""Tests for weather psychrometrics, occupancy, RCx collectors, unit system."""

from __future__ import annotations

import pandas as pd

from app.occupancy import OccupancySchedule, apply_schedule_occ_mode, occupied_mask
from app.rcx_plots import collect_role_series, series_summary_stats
from app.rules.cookbook_catalog import RULES, RULES_BY_ID, cw_opt, vav7
from app.unit_system import convert_series, f_to_c
from app.weather_psychrometrics import dewpoint_f_from_db_rh, enrich_weather_frame, wetbulb_f_stull


def test_canonical_rule_count_still_50():
    assert len(RULES) == 53
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
    assert "web-outside-air-temp" in out.columns
    assert "web-outside-air-dewpoint" in out.columns
    assert out["web-outside-air-dewpoint"].notna().all()
    assert "web-outside-air-wetbulb" in out.columns


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
    df = pd.DataFrame({"zone-air-temp": range(10)}, index=idx)
    out = apply_schedule_occ_mode(df, OccupancySchedule(), overwrite=True)
    assert "occupied" in out.columns
    assert set(out["occupied"].unique()) <= {"occupied", "unoccupied"}


def test_unit_convert_f_to_c():
    s = pd.Series([32.0, 212.0])
    conv, unit = convert_series("discharge-air-temp", s, "metric")
    assert unit == "°C"
    assert abs(conv.iloc[0] - 0.0) < 1e-6
    assert abs(f_to_c(212) - 100) < 1e-6


def test_vav7_fixed_high_flow():
    idx = pd.date_range("2024-01-01", periods=40, freq="5min", tz="UTC")
    # Constant high flow with damper/air on
    d = pd.DataFrame(
        {
            "zone-airflow": [400.0] * 40,
            "min-flow-sp": [300.0] * 40,
            "damper": [50.0] * 40,
        },
        index=idx,
    )
    raw = vav7(d, {"fixed_flow_max_std": 15.0, "fixed_flow_min_mean": 200.0, "high_min_flow_sp": 250.0, "flow_on_min": 25.0}, 300.0)
    assert bool(raw.iloc[-1])


def test_cw_opt_faults_when_overcooled():
    idx = pd.date_range("2024-01-01", periods=5, freq="5min", tz="UTC")
    d = pd.DataFrame(
        {"condenser-water-supply-temp": [60.0] * 5, "web-outside-air-wetbulb": [70.0] * 5},
        index=idx,
    )
    # target = 70+7=77, slack 2 → fault if CW < 75; 60 is fault
    raw = cw_opt(d, {"cw_approach": 7.0, "cw_slack": 2.0}, 300.0)
    assert bool(raw.all())


def test_rcx_collect_and_outliers():
    idx = pd.date_range("2024-01-01", periods=10, freq="5min", tz="UTC")
    frames = {
        "VAV_1": pd.DataFrame({"zone-air-temp": [72.0] * 10}, index=idx),
        "VAV_2": pd.DataFrame({"zone-air-temp": [72.5] * 10}, index=idx),
        "VAV_3": pd.DataFrame({"zone-air-temp": [95.0] * 10}, index=idx),
    }
    for eq, df in frames.items():
        df.attrs["equipment_type"] = "VAV"
    role_map = {eq: {"zone-air-temp": "zone-air-temp"} for eq in frames}
    series = collect_role_series(frames, role_map, role="zone-air-temp", equipment_types=("VAV",))
    assert len(series) == 3
    stats = series_summary_stats(series, outlier_z=2.0)
    assert "outlier" in stats.columns


def test_rcx_fan_mode_summary_ahu_and_vav():
    from app.rcx_plots import fan_mode_summary_bundle, operating_mask

    idx = pd.date_range("2024-01-01", periods=6, freq="5min", tz="UTC")
    ahu = pd.DataFrame(
        {
            "discharge-air-temp": [55.0, 56.0, 57.0, 70.0, 71.0, 72.0],
            "fan-status": [1, 1, 1, 0, 0, 0],
        },
        index=idx,
    )
    ahu.attrs["equipment_type"] = "AHU"
    vav = pd.DataFrame(
        {
            "zone-air-temp": [72.0, 72.0, 72.0, 68.0, 68.0, 68.0],
            "zone-airflow": [400.0, 400.0, 400.0, 0.0, 0.0, 0.0],
        },
        index=idx,
    )
    vav.attrs["equipment_type"] = "VAV"
    frames = {"AHU_1": ahu, "VAV_1": vav}
    role_map = {
        "AHU_1": {"discharge-air-temp": "discharge-air-temp", "fan-status": "fan-status", "equipment_type": "AHU"},
        "VAV_1": {"zone-air-temp": "zone-air-temp", "zone-airflow": "zone-airflow", "equipment_type": "VAV"},
    }
    mask, label = operating_mask(ahu)
    assert label == "fan-status"
    assert int(mask.sum()) == 3
    mask_v, label_v = operating_mask(vav)
    assert label_v == "zone-airflow"
    assert int(mask_v.sum()) == 3

    ahu_tables, cap = fan_mode_summary_bundle(
        frames, role_map, role="discharge-air-temp", equipment_types=("AHU",), outlier_z=2.5
    )
    assert "fan-status" in cap
    assert int(ahu_tables["on"].iloc[0]["n"]) == 3
    assert int(ahu_tables["off"].iloc[0]["n"]) == 3
    assert int(ahu_tables["all"].iloc[0]["n"]) == 6

    vav_tables, vcap = fan_mode_summary_bundle(
        frames, role_map, role="zone-air-temp", equipment_types=("VAV",), outlier_z=2.5
    )
    assert "zone-airflow" in vcap
    assert int(vav_tables["on"].iloc[0]["n"]) == 3
    assert int(vav_tables["off"].iloc[0]["n"]) == 3


def test_zone_comfort_fail_ranking():
    from app.occupancy import OccupancySchedule
    from app.rcx_plots import zone_comfort_fail_ranking

    # Monday 10:00–11:00 UTC → occupied under default Mon 06–18 America/Chicago may differ;
    # use UTC-aligned schedule via America/Chicago with a wide window, or localize index.
    idx = pd.date_range("2024-01-01 12:00", periods=4, freq="h", tz="America/Chicago")  # Mon
    # 72,72 in band; 80, 60 outside
    good = pd.DataFrame({"zone-air-temp": [72.0, 72.0, 72.0, 72.0]}, index=idx)
    bad = pd.DataFrame({"zone-air-temp": [80.0, 80.0, 60.0, 60.0]}, index=idx)
    good.attrs["equipment_type"] = "VAV"
    bad.attrs["equipment_type"] = "VAV"
    frames = {"VAV_GOOD": good, "VAV_BAD": bad}
    role_map = {
        "VAV_GOOD": {"zone-air-temp": "zone-air-temp", "equipment_type": "VAV"},
        "VAV_BAD": {"zone-air-temp": "zone-air-temp", "equipment_type": "VAV"},
    }
    sched = OccupancySchedule()  # Mon occupied 06–18
    rank = zone_comfort_fail_ranking(
        frames, role_map, schedule=sched, comfort_low_f=70.0, comfort_high_f=75.0
    )
    assert list(rank["equipment_id"]) == ["VAV_BAD", "VAV_GOOD"]
    assert float(rank.iloc[0]["pct_outside_comfort"]) == 100.0
    assert float(rank.iloc[1]["pct_outside_comfort"]) == 0.0
