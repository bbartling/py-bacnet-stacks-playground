"""
Unit tests for AHU economizer FDD engine.
Synthetic fixtures only — clearly separated from production diagnostics.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from economizer_fdd_engine import (
    DEFAULT_PARAMS,
    run_diagnostics,
    results_to_dataframe,
    resolve_columns,
)

# ---------------------------------------------------------------------------
# Synthetic fixture builder (test-only)
# ---------------------------------------------------------------------------

COLUMNS = {
    "timestamp_utc": "timestamp_utc",
    "supply_fan_speed_pct": "fan_cmd",
    "supply_fan_status": "fan_status",
    "outside_air_temp_f": "oat",
    "return_air_temp_f": "rat",
    "mixed_air_temp_f": "mat",
    "discharge_air_temp_f": "sat",
    "dat_reset_f": "sat_sp",
    "ex_dmpr_pos_fan_enable_pct": "oa_damper",
    "oa_minimum_position_pct": "oa_min",
    "chw_valve_pct": "clg",
}


def _ts(n: int, start: str = "2026-04-01 12:00:00+00:00", step_min: int = 15) -> pd.Series:
    return pd.date_range(start, periods=n, freq=f"{step_min}min", tz="UTC")


def make_ahu_df(
    n: int = 32,
    *,
    oat: float = 55.0,
    rat: float = 74.0,
    mat: float | None = None,
    sat: float = 58.0,
    sat_sp: float = 55.0,
    oa_damper: float = 80.0,
    oa_min: float = 20.0,
    clg: float = 0.0,
    fan: float = 80.0,
) -> pd.DataFrame:
    """Build minimal AHU_1-shaped dataframe for rule testing."""
    ts = _ts(n)
    rng = np.random.default_rng(42)
    # Realistic BAS jitter (avoids false flatline on synthetic constants)
    oat_s = oat + rng.normal(0, 0.2, n)
    rat_s = rat + rng.normal(0, 0.2, n)
    sat_s = sat + rng.normal(0, 0.2, n)
    if mat is None:
        mat = rat + (oat - rat) * (oa_damper / 100.0)
    mat_s = np.full(n, mat) + rng.normal(0, 0.02, n)
    df = pd.DataFrame({
        "timestamp_utc": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "supply_fan_speed_pct": fan,
        "supply_fan_status": 1,
        "outside_air_temp_f": oat_s,
        "return_air_temp_f": rat_s,
        "mixed_air_temp_f": mat_s,
        "discharge_air_temp_f": sat_s,
        "dat_reset_f": sat_sp,
        "ex_dmpr_pos_fan_enable_pct": oa_damper,
        "oa_minimum_position_pct": oa_min,
        "chw_valve_pct": clg,
    })
    df["timestamp"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df


def fault_minutes(results, code: str) -> float:
    r = results_to_dataframe(results)
    row = r[r["fault_code"] == code]
    return float(row["total_fault_minutes"].iloc[0]) if len(row) else 0.0


def fault_status(results, code: str) -> str:
    r = results_to_dataframe(results)
    row = r[r["fault_code"] == code]
    return str(row["status"].iloc[0]) if len(row) else "missing"


FAST = {**DEFAULT_PARAMS, "confirm_minutes": 15, "poll_seconds": 900, "flatline_window_samples": 4}


def make_weather_df(df: pd.DataFrame, web_oat: float = 55.0, dew_point: float = 45.0) -> pd.DataFrame:
    """Open-Meteo reference aligned to AHU timestamps."""
    return pd.DataFrame({
        "timestamp": df["timestamp"],
        "dry_bulb_f": web_oat,
        "dew_point_f": dew_point,
    })


def run_with_weather(df: pd.DataFrame, web_oat: float = 55.0, dew_point: float = 45.0, **kwargs):
    wx = make_weather_df(df, web_oat=web_oat, dew_point=dew_point)
    return run_diagnostics("AHU_1", df, weather_df=wx, **kwargs)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_normal_economizer_operation():
    df = make_ahu_df(n=32, oat=55, rat=74, oa_damper=85, clg=0, sat=56, sat_sp=55)
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_status(results, "ECON_NOT_ECONOMIZING_WHEN_SHOULD") == "normal"
    assert fault_status(results, "ECON_DAMPER_STUCK_CLOSED") == "missing" or fault_minutes(results, "ECON_DAMPER_STUCK_CLOSED") == 0


def test_oa_damper_stuck_closed():
    df = make_ahu_df(n=32, oat=50, rat=74, oa_damper=2, clg=60, sat=58, sat_sp=55)
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_minutes(results, "ECON_NOT_ECONOMIZING_WHEN_SHOULD") > 0
    assert fault_minutes(results, "ECON_MECH_COOLING_DURING_FREE_COOLING") > 0


def test_oa_damper_stuck_open():
    df = make_ahu_df(n=32, oat=90, rat=74, oa_damper=95, clg=40, mat=88)
    _, results, _ = run_with_weather(df, web_oat=88, dew_point=65, params=FAST)
    assert fault_minutes(results, "ECON_ECONOMIZING_WHEN_SHOULD_NOT") > 0 or fault_minutes(results, "ECON_EXCESS_OA") > 0


def test_actuator_no_mat_response():
    n = 32
    oad = np.full(n, 20.0)
    oad[8:24] = np.linspace(20, 80, 16)  # command varies
    df = make_ahu_df(n=n, oat=50, rat=74, mat=72, oa_damper=20, clg=0, sat=56, sat_sp=55)
    df["ex_dmpr_pos_fan_enable_pct"] = oad
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_minutes(results, "ECON_DAMPER_NOT_MODULATING") > 0


def test_oat_sensor_flatline():
    df = make_ahu_df(n=32, oat=55)
    df.loc[:, "outside_air_temp_f"] = 55.0  # perfectly flat — intentional
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_minutes(results, "ECON_SENSOR_FAULT") > 0


def test_oat_sensor_out_of_range():
    df = make_ahu_df(n=32, oat=200)
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_minutes(results, "ECON_SENSOR_FAULT") > 0


def test_mat_sensor_implausible():
    df = make_ahu_df(n=32, oat=55, rat=74, mat=40)  # below both
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_minutes(results, "ECON_MAT_PLAUSIBILITY") > 0
    assert fault_minutes(results, "ECON_SENSOR_FAULT") > 0


def test_mech_cooling_during_free_cooling():
    df = make_ahu_df(n=32, oat=50, rat=74, oa_damper=25, clg=70, sat=58, sat_sp=55)
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_minutes(results, "ECON_MECH_COOLING_DURING_FREE_COOLING") > 0


def test_economizing_during_hot_oa():
    df = make_ahu_df(n=32, oat=88, rat=74, oa_damper=70, mat=82, clg=50)
    _, results, _ = run_with_weather(df, web_oat=88, dew_point=65, params=FAST)
    assert fault_minutes(results, "ECON_ECONOMIZING_WHEN_SHOULD_NOT") > 0


def test_excess_oa_during_heating_season():
    oat, rat, oa_pct = 30, 68, 50
    mat = rat + (oat - rat) * (oa_pct / 100.0)
    df = make_ahu_df(n=32, oat=oat, rat=rat, oa_damper=oa_pct, mat=mat, sat=mat + 1, clg=0)
    _, results, _ = run_with_weather(df, web_oat=30, dew_point=25, params=FAST)
    assert fault_minutes(results, "ECON_EXCESS_OA") > 0


def test_missing_mat_not_evaluated():
    df = make_ahu_df(n=8)
    df = df.drop(columns=["mixed_air_temp_f"])
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_status(results, "ECON_SENSOR_FAULT") == "not_evaluated"


def test_missing_rat_not_evaluated():
    df = make_ahu_df(n=8)
    df = df.drop(columns=["return_air_temp_f"])
    _, results, meta = run_diagnostics("AHU_1", df, params=FAST)
    assert "rat" in meta["missing_required"]
    assert fault_status(results, "ECON_NOT_ECONOMIZING_WHEN_SHOULD") == "not_evaluated"


def test_missing_damper_feedback_uses_command():
    df = make_ahu_df(n=32, oat=50, rat=74, oa_damper=85, clg=0)
    _, results, meta = run_diagnostics("AHU_1", df, params=FAST)
    assert meta["columns_mapped"]["oa_damper_cmd"] == "ex_dmpr_pos_fan_enable_pct"
    assert fault_status(results, "ECON_NOT_ECONOMIZING_WHEN_SHOULD") == "normal"


def test_data_gaps_no_silent_forward_fill():
    df = make_ahu_df(n=8, oat=55, oa_damper=80)
    # Jump from 12:45 to 15:00 UTC = 135 min (> 4 × 15 min poll)
    late = pd.date_range("2026-04-01T15:00:00Z", periods=4, freq="15min", tz="UTC")
    df.loc[4:, "timestamp_utc"] = late.strftime("%Y-%m-%dT%H:%M:%SZ")
    df["timestamp"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    d, _, _ = run_with_weather(df, params=FAST)
    assert d["q_gap"].any()


def test_short_transient_does_not_trigger():
    df = make_ahu_df(n=32, oat=50, rat=74, oa_damper=85, clg=0)
    df.loc[10:11, "ex_dmpr_pos_fan_enable_pct"] = 2  # 30 min only — below confirm
    _, results, _ = run_with_weather(df, params={**FAST, "confirm_minutes": 45})
    assert fault_minutes(results, "ECON_NOT_ECONOMIZING_WHEN_SHOULD") == 0


def test_persistent_event_triggers():
    df = make_ahu_df(n=32, oat=50, rat=74, oa_damper=85, clg=60, sat=58, sat_sp=55)
    # Close damper and align MAT with low OA fraction to avoid sensor false positives
    low_mat = 74 + (50 - 74) * 0.02
    df.loc[8:, "ex_dmpr_pos_fan_enable_pct"] = 2
    df.loc[8:, "mixed_air_temp_f"] = low_mat + np.random.default_rng(1).normal(0, 0.02, len(df) - 8)
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_minutes(results, "ECON_NOT_ECONOMIZING_WHEN_SHOULD") > 0


def test_low_oa_ventilation_risk():
    oat, rat, oa_pct, oa_min = 55, 74, 5, 25
    mat = rat + (oat - rat) * (oa_pct / 100.0)
    df = make_ahu_df(n=32, oat=oat, rat=rat, oa_damper=oa_pct, oa_min=oa_min, mat=mat, sat=mat + 1, clg=0)
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_minutes(results, "ECON_LOW_OA_VENTILATION_RISK") > 0


def test_enthalpy_not_evaluated():
    df = make_ahu_df(n=16)
    _, results, _ = run_with_weather(df, params=FAST)
    assert fault_status(results, "ECON_ENTHALPY_NOT_EVALUATED") == "not_evaluated"


def test_duplicate_timestamps_deduped():
    df = make_ahu_df(n=16)
    df = pd.concat([df, df.iloc[[5]]], ignore_index=True)
    d, _, _ = run_with_weather(df, params=FAST)
    assert d["timestamp"].duplicated().sum() == 0


def test_resolve_columns_ahu_2():
    df = make_ahu_df(n=4)
    cols, missing = resolve_columns("AHU_2", df)
    assert missing == []
    assert cols["oat"] == "outside_air_temp_f"


def test_results_exportable():
    df = make_ahu_df(n=16)
    d, results, _ = run_with_weather(df, params=FAST)
    from economizer_fdd_engine import export_fault_timeseries
    out = export_fault_timeseries(d, "AHU_1")
    rdf = results_to_dataframe(results)
    assert "ahu_id" in out.columns
    assert "fault_code" in rdf.columns
    assert len(rdf) >= 8
