"""Synthetic golden tests for independently implemented HVAC calculations.

Target values are synthetic numerical anchors and hand-computed checks. A pass
means WattLab's bin-method calculators retain their public engineering behavior
to floating-point tolerance.
"""

from __future__ import annotations

import pytest

from wattlab.bench.registry import get
from wattlab.bench import runner  # noqa: F401  (registers algorithms + esco)
from wattlab.weather.bins import (
    OperatingSchedule,
    WeatherBins,
    hours_reduction_fraction,
    sat_enthalpy_btu_lb,
    washington_dc_noaa,
)

# Enthalpy at MCWB per bin as computed by the source workbooks (Btu/lb).
SHEET_ENTHALPY = {
    97: 37.06225718971611,
    92: 36.09970854842834,
    87: 34.89498799961852,
    82: 34.41522769835886,
    77: 33.51433509279598,
    72: 31.651715391025803,
    67: 28.66924710005472,
    62: 25.582625307994817,
    57: 22.213841490001684,
    52: 19.639832127078666,
    47: 17.1923539299521,
    42: 15.129870859880842,
    37: 13.212845886467914,
    32: 11.269982106557778,
    27: 9.29477257645605,
    22: 7.191209934453946,
    17: 5.647162750976882,
    12: 4.532413643881386,
    7: 3.3066615626174967,
}


def dc_bins_with_sheet_enthalpy() -> WeatherBins:
    """Washington DC NOAA table with the sheets' exact enthalpy values."""
    rows = []
    for r in washington_dc_noaa().rows:
        rows.append({
            "temp": r.temp,
            "shift_hours": list(r.shift_hours),
            "mcwb": r.mcwb,
            "enthalpy": SHEET_ENTHALPY.get(int(r.temp)),
        })
    return WeatherBins.from_rows(rows, source="NOAA Washington DC (sheet enthalpies)")


# ---------------------------------------------------------------------------
# Weather bins / psychrometrics
# ---------------------------------------------------------------------------

def test_washington_dc_table_totals_match_weather_man():
    bins = washington_dc_noaa()
    # Weather Man sheet: 2920 hours in each of the three shifts.
    for shift in range(3):
        assert sum(r.shift_hours[shift] for r in bins.rows) == pytest.approx(2920.0)
    assert bins.total_hours == pytest.approx(8760.0)


def test_sat_enthalpy_close_to_sheet_values():
    # Our Hyland-Wexler psychrometrics should track the sheets' enthalpy
    # column within 0.2 Btu/lb across the full MCWB range.
    checks = {73.5: 37.06225718971611, 63.1: 28.66924710005472, 53.4: 22.213841490001684,
              25.9: 9.29477257645605, 8.4: 3.3066615626174967}
    for twb, want in checks.items():
        assert sat_enthalpy_btu_lb(twb) == pytest.approx(want, abs=0.2)


def test_schedule_shift_weighting_matches_sheet():
    # Synthetic CV scheduling: shifts 2/8/3, 5 days -> bin 97 (0,42,2) gives
    # 30.535714... total operating bin hours.
    sched = OperatingSchedule(shifts=(2, 8, 3), days_per_week=5)
    assert sched.total_operating_hours((0, 42, 2)) == pytest.approx(30.535714285714285)
    assert sched.weekly_hours == pytest.approx(65.0)
    proposed = OperatingSchedule(shifts=(1, 8, 1.5), days_per_week=5, override_allowance=0.10)
    assert proposed.weekly_hours == pytest.approx(57.75)
    assert hours_reduction_fraction(sched, proposed) == pytest.approx(0.11153846153846143)


# ---------------------------------------------------------------------------
# Synthetic CV scheduling (fan + cooling)
# ---------------------------------------------------------------------------

def test_scheduling_fan_bins_matches_synthetic_cv_fixture():
    result = get("scheduling_fan_bins")({
        "fan_kw_total": 8.579000000000002,
        "existing_schedule": {"shifts": [2, 8, 3], "days_per_week": 5},
        "proposed_schedule": {"shifts": [1, 8, 1.5], "days_per_week": 5, "override_allowance": 0.10},
        "bins": washington_dc_noaa(),
    })
    by_temp = {row["temp"]: row for row in result["bins"]}
    # Bin 97 F: existing 261.966 kWh, saved 29.219 kWh.
    assert by_temp[97]["existing_kwh"] == pytest.approx(261.96589285714293)
    assert by_temp[97]["saved_kwh"] == pytest.approx(29.21927266483516)
    # Sheet totals row 60.
    assert result["baseline_kwh"] == pytest.approx(29076.682142857153)
    assert result["savings_kwh"] == pytest.approx(3243.1683928571415)
    assert result["hours_reduction_fraction"] == pytest.approx(0.11153846153846143)


def test_scheduling_cooling_bins_matches_synthetic_cv_fixture():
    result = get("scheduling_cooling_bins")({
        "oa_cfm_total": 20060,
        "supply_enthalpy": 23.2,
        "kw_per_ton": 1.0526315789473684,
        "existing_schedule": {"shifts": [2.25, 8, 2.5], "days_per_week": 5},
        "proposed_schedule": {"shifts": [1, 8, 1.5], "days_per_week": 5, "override_allowance": 0.10},
        "bins": dc_bins_with_sheet_enthalpy(),
    })
    by_temp = {row["temp"]: row for row in result["bins"]}
    # Bin 97 F: 104.279 ton/hr vent cooling, 3342.019 kWh existing, 314.543 saved.
    assert by_temp[97]["vent_cooling_ton_hr"] == pytest.approx(104.27882970963942)
    assert by_temp[97]["existing_kwh"] == pytest.approx(3342.0188844912636)
    assert by_temp[97]["saved_kwh"] == pytest.approx(314.5429538344715)
    # Sheet totals row 51.
    assert result["baseline_kwh"] == pytest.approx(112117.08353068295)
    assert result["savings_kwh"] == pytest.approx(10552.196097005435)
    assert result["hours_reduction_fraction"] == pytest.approx(0.09411764705882342)


# ---------------------------------------------------------------------------
# Synthetic CV scheduling (heating)
# ---------------------------------------------------------------------------

def test_scheduling_heating_bins_matches_synthetic_cv_fixture():
    result = get("scheduling_heating_bins")({
        "oa_cfm_total": 30655,
        "balance_point_f": 55,
        "boiler_efficiency": 0.95,
        "existing_schedule": {"shifts": [1.25, 8, 4], "days_per_week": 5},
        "proposed_schedule": {"shifts": [0.5, 8, 2], "days_per_week": 5, "override_allowance": 0.10},
        "bins": washington_dc_noaa(),
    })
    by_temp = {row["temp"]: row for row in result["bins"]}
    # Bin 52 F: 99.3222 kBtu/h vent heat, saved 3.36695 MMBtu.
    assert by_temp[52]["vent_heat_kbtu_hr"] == pytest.approx(99.3222)
    assert by_temp[52]["saved_mmbtu"] == pytest.approx(3.3669542422684025)
    # Bin 42 F: saved 16.27296 MMBtu.
    assert by_temp[42]["saved_mmbtu"] == pytest.approx(16.27296343218895)
    # Sheet totals row 57: 106.239 MMBtu saved.
    assert result["savings_mmbtu"] == pytest.approx(106.23935810792295)
    assert result["hours_reduction_fraction"] == pytest.approx(0.12830188679245272)


# ---------------------------------------------------------------------------
# Synthetic VAV unoccupied outdoor-air cooling
# ---------------------------------------------------------------------------

def test_oad_unoccupied_closed_cooling_matches_synthetic_vav_fixture():
    result = get("oad_unoccupied_closed")({
        "mode": "cooling",
        "oa_cfm_total": 5400,
        "supply_enthalpy": 23.2,
        "kw_per_ton": 1.0526315789473684,
        "vent_hours_schedule": {"shifts": [1, 0, 0], "days_per_week": 5},
        "bins": dc_bins_with_sheet_enthalpy(),
    })
    by_temp = {row["temp"]: row for row in result["bins"]}
    # Sheet rows: bin 77 saved 247.34 kWh, bin 72 saved 517.95 kWh,
    # bin 67 saved 348.70 kWh.
    assert by_temp[77]["saved_kwh"] == pytest.approx(247.3404698239563)
    assert by_temp[72]["saved_kwh"] == pytest.approx(517.9455846539826)
    assert by_temp[67]["saved_kwh"] == pytest.approx(348.70305465221986)
    # Warm bins with no unoccupied hours save nothing.
    assert by_temp[97]["saved_kwh"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Synthetic VAV static pressure reset
# ---------------------------------------------------------------------------

def test_static_pressure_reset_matches_synthetic_fixture():
    hours = 3289.0000000000005
    result = get("static_pressure_reset")({
        "pressure_ratio": 0.7,
        "units": [
            {"tag": "RTU 7", "motor_kw": 4.476, "avg_speed_fraction": 0.70, "annual_hours": hours},
            {"tag": "RTU 1", "motor_kw": 3.3569999999999998, "avg_speed_fraction": 0.90, "annual_hours": hours},
            {"tag": "RTU 2", "motor_kw": 2.238, "avg_speed_fraction": 0.80, "annual_hours": hours},
            {"tag": "RTU 3", "motor_kw": 3.3569999999999998, "avg_speed_fraction": 0.60, "annual_hours": hours},
            {"tag": "RTU 4", "motor_kw": 3.3569999999999998, "avg_speed_fraction": 0.60, "annual_hours": hours},
            {"tag": "RTU 6", "motor_kw": 3.3569999999999998, "avg_speed_fraction": 0.75, "annual_hours": hours},
        ],
    })
    by_tag = {u["tag"]: u for u in result["units"]}
    # RTU 7: 70% -> 58.57% speed, 2,092.198 kWh saved.
    assert by_tag["RTU 7"]["reduced_speed_fraction"] == pytest.approx(0.5856620185738529)
    assert by_tag["RTU 7"]["savings_kwh"] == pytest.approx(2092.1981671401704)
    assert by_tag["RTU 1"]["savings_kwh"] == pytest.approx(3335.012676046325)
    # Sheet total J16: 10,895.02 kWh.
    assert result["savings_kwh"] == pytest.approx(10895.02283520689)


# ---------------------------------------------------------------------------
# Synthetic VAV discharge-air-temperature reset cooling
# ---------------------------------------------------------------------------

def test_dat_reset_bins_matches_synthetic_fixture():
    result = get("dat_reset_bins")({
        "total_cfm": 5400,
        "oa_cfm": 5400,
        "return_enthalpy": 28.3,
        "supply_enthalpy": 23.2,
        "kw_per_ton": 1.0526315789473684,
        "schedule": {"shifts": [1, 8, 2.5], "days_per_week": 5},
        "bins": dc_bins_with_sheet_enthalpy(),
        "reset": [
            {"temp": 97, "proposed_supply_enthalpy": 23.2, "vav_fraction": 1.0},
            {"temp": 92, "proposed_supply_enthalpy": 23.63, "vav_fraction": 0.925},
            {"temp": 87, "proposed_supply_enthalpy": 24.03, "vav_fraction": 0.8},
            {"temp": 82, "proposed_supply_enthalpy": 24.5, "vav_fraction": 0.7},
            {"temp": 77, "proposed_supply_enthalpy": 25.0, "vav_fraction": 0.7},
            {"temp": 72, "proposed_supply_enthalpy": 25.5, "vav_fraction": 0.7},
        ],
    })
    by_temp = {row["temp"]: row for row in result["bins"]}
    # Sheet column V (saved kWh per bin).
    assert by_temp[97]["saved_kwh"] == pytest.approx(0.0)
    assert by_temp[92]["saved_kwh"] == pytest.approx(83.30741042058291)
    assert by_temp[87]["saved_kwh"] == pytest.approx(344.5537500000008, rel=1e-6)
    assert by_temp[82]["saved_kwh"] == pytest.approx(501.47393092105324, rel=1e-6)
    assert by_temp[77]["saved_kwh"] == pytest.approx(607.1802631578953, rel=1e-6)
    assert by_temp[72]["saved_kwh"] == pytest.approx(841.8737664473682, rel=1e-6)


# ---------------------------------------------------------------------------
# Synthetic hot-water reset
# ---------------------------------------------------------------------------

def test_hydronic_reset_bins_matches_synthetic_hot_water_fixture():
    result = get("hydronic_reset_bins")({
        "mode": "hot_water",
        "capacity_mbh": 9515.789473684212,
        "on_point_f": 55,
        "design_temp_f": 0,
        "max_savings_fraction": 0.05,
        "n_reset_bins": 6,
        "boiler_efficiency": 0.95,
        "schedule": {"shifts": [0.5, 8, 3.5], "days_per_week": 5},
        "bins": washington_dc_noaa(),
    })
    by_temp = {row["temp"]: row for row in result["bins"]}
    # Sheet: bin 52 load 5.45%, savings pct 4.167%, R = 5.2156 MMBtu.
    assert by_temp[52]["load_fraction"] == pytest.approx(0.05454545454545454)
    assert by_temp[52]["savings_pct"] == pytest.approx(0.04166666666666667)
    assert by_temp[52]["saved_mmbtu"] == pytest.approx(5.215634780731732)
    # Bin 47: R = 11.1657 MMBtu; bin 42: R = 14.9928 MMBtu.
    assert by_temp[47]["saved_mmbtu"] == pytest.approx(11.165713326378123)
    assert by_temp[42]["saved_mmbtu"] == pytest.approx(14.992815771486102)
    # Sheet total R45: 49.736 MMBtu.
    assert result["savings_mmbtu"] == pytest.approx(49.73607103884107)


# ---------------------------------------------------------------------------
# DCV + economizer sanity (hand-computed; no direct sheet analogue)
# ---------------------------------------------------------------------------

def test_dcv_bins_hand_computed():
    bins = [
        {"temp": 87, "shift_hours": [0, 8, 0], "enthalpy": 34.0},
        {"temp": 37, "shift_hours": [0, 8, 0], "enthalpy": 13.0},
    ]
    result = get("dcv_bins")({
        "baseline_oa_cfm": 10000,
        "proposed_oa_cfm": 6000,
        "kw_per_ton": 1.0,
        "supply_enthalpy": 23.2,
        "balance_point_f": 55,
        "boiler_efficiency": 0.8,
        "schedule": {"shifts": [0, 8, 0], "days_per_week": 7},
        "bins": bins,
    })
    # Operating hours per bin = 8 * 8/8 * 7/7 = 8 h.
    # Cooling (87 F): 4000 * (34 - 23.2) * 4.5 / 12000 = 16.2 ton -> 129.6 kWh.
    assert result["savings_kwh"] == pytest.approx(16.2 * 8 * 1.0)
    # Heating (37 F): (55-37) * 4000 * 1.08 / 1000 = 77.76 kBtu/h
    # -> 77.76 * 8 / 0.8 / 1000 = 0.7776 MMBtu.
    assert result["savings_mmbtu"] == pytest.approx(0.7776)


def test_dewpoint_economizer_hand_computed():
    bins = [
        # Warm + humid: not eligible (OA enthalpy above return).
        {"temp": 87, "shift_hours": [0, 8, 0], "enthalpy": 34.0},
        # Mild + dry: eligible free cooling.
        {"temp": 62, "shift_hours": [0, 8, 0], "enthalpy": 25.0},
        # Cold: no mechanical cooling to save.
        {"temp": 42, "shift_hours": [0, 8, 0], "enthalpy": 15.0},
    ]
    result = get("dewpoint_economizer")({
        "unit_cfm_total": 10000,
        "oa_cfm_total": 2000,
        "return_enthalpy": 28.3,
        "discharge_enthalpy": 24.5,
        "discharge_temp_f": 57,
        "kw_per_ton": 0.9,
        "unit_type": "cv",
        "schedule": {"shifts": [0, 8, 0], "days_per_week": 7},
        "bins": bins,
    })
    by_temp = {row["temp"]: row for row in result["bins"]}
    assert by_temp[87]["saved_kwh"] == pytest.approx(0.0)
    assert by_temp[42]["saved_kwh"] == pytest.approx(0.0)
    # 8000 * 4.5 * (28.3-24.5) / 12000 = 11.4 tons * 8 h * 0.9 kW/ton = 82.08 kWh.
    assert by_temp[62]["saved_kwh"] == pytest.approx(82.08)
    assert result["savings_kwh"] == pytest.approx(82.08)


def test_weather_bins_from_hourly_roundtrip():
    import pandas as pd

    ts = pd.date_range("2025-06-01", periods=48, freq="h")
    oat = [70.0] * 24 + [90.0] * 24
    bins = WeatherBins.from_hourly(ts, oat)
    by_temp = {r.temp: r for r in bins.rows}
    assert by_temp[72.0].annual_hours == 24
    assert by_temp[92.0].annual_hours == 24
    # Shift split: 8 hours per shift per day.
    assert by_temp[72.0].shift_hours == (8.0, 8.0, 8.0)
    assert bins.total_hours == 48
