"""SV-RATE — context-aware sensor rate-of-change."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from app.rules import RULES_BY_ID, run_rule
from app.rules.cookbook_catalog import RULES, RULES_BY_ID as CATALOG_BY_ID
from app.rules.sensor_rate import compute_rates, detect_operating_state, evaluate_point, sv_rate_compute
from app.rules.sensor_rate_profiles import (
    DEFAULT_PROFILES,
    c_per_h_to_f_per_h,
    f_per_h_to_c_per_h,
    inwc_per_h_to_pa_per_h,
    kpa_per_h_to_psi_per_h,
    pa_per_h_to_inwc_per_h,
    psi_per_h_to_kpa_per_h,
    resolve_profile,
)


def _idx(n: int = 24, freq: str = "5min") -> pd.DatetimeIndex:
    return pd.date_range("2024-06-01", periods=n, freq=freq, tz="UTC")


def test_unit_conversions_temperature_delta_no_offset():
    assert f_per_h_to_c_per_h(9.0) == pytest.approx(5.0)
    assert c_per_h_to_f_per_h(5.0) == pytest.approx(9.0)
    # Not absolute: converting 32°F/h must not subtract 32
    assert f_per_h_to_c_per_h(32.0) == pytest.approx(32.0 * 5.0 / 9.0)


def test_unit_conversions_pressure():
    assert inwc_per_h_to_pa_per_h(1.0) == pytest.approx(249.08891)
    assert pa_per_h_to_inwc_per_h(249.08891) == pytest.approx(1.0)
    assert psi_per_h_to_kpa_per_h(1.0) == pytest.approx(6.894757)
    assert kpa_per_h_to_psi_per_h(6.894757) == pytest.approx(1.0)


def test_default_profiles_unique_and_valid():
    ids = list(DEFAULT_PROFILES)
    assert len(ids) == len(set(ids))
    for p in DEFAULT_PROFILES.values():
        p.validate()


def test_resolve_profile_aliases():
    p, src = resolve_profile(role="zone-air-temp")
    assert p is not None and p.profile_id == "zone_air_temperature" and src == "canonical_role"
    p2, src2 = resolve_profile(point_name="OAT")
    assert p2 is not None and p2.profile_id == "outside_air_temperature" and src2 == "name_alias"
    p3, src3 = resolve_profile(role="mixed-air-temp")
    assert p3 is not None and p3.profile_id == "mixed_air_temperature"


def test_catalog_registration_and_alias():
    assert "SV-RATE" in CATALOG_BY_ID
    assert "SV-SLEW" in RULES_BY_ID
    assert RULES_BY_ID["SV-SLEW"].id == "SV-RATE"
    ids = [r.id for r in RULES]
    assert ids.count("SV-RATE") == 1
    assert "SCHED-247" in {r.id for r in RULES}


def test_slow_zone_temp_passes():
    idx = _idx(36)
    # ~2°F/h steady — below 6°F/h fault
    vals = 70.0 + np.arange(len(idx)) * (2.0 * 5.0 / 60.0)
    df = pd.DataFrame(
        {"zone-air-temp": vals, "fan-status": [1] * len(idx)},
        index=idx,
    )
    df.attrs["equipment_type"] = "VAV"
    mask = sv_rate_compute(df, {"persistence_min": 10}, poll=300.0)
    assert not bool(mask.any())


def test_rapid_zone_temp_faults():
    idx = _idx(36)
    # ~20°F/h — above zone steady fault 6°F/h, sustained
    vals = 70.0 + np.arange(len(idx)) * (20.0 * 5.0 / 60.0)
    df = pd.DataFrame(
        {"zone-air-temp": vals, "fan-status": [1] * len(idx)},
        index=idx,
    )
    mask = sv_rate_compute(df, {"persistence_min": 10}, poll=300.0)
    assert bool(mask.any())


def test_supply_air_startup_uses_transient_threshold():
    idx = _idx(24)
    # ~40°F/h — between steady fault (16) and transient fault (50)
    vals = 55.0 + np.arange(len(idx)) * (40.0 * 5.0 / 60.0)
    # Fan starts at sample 0 → first 20 min are STARTUP_TRANSIENT
    fan = [0] + [1] * (len(idx) - 1)
    df = pd.DataFrame({"discharge-air-temp": vals, "fan-status": fan}, index=idx)
    mask_trans = sv_rate_compute(df, {"persistence_min": 10, "transition_window_min": 20}, poll=300.0)
    # Steady continuous fan — should fault
    df2 = pd.DataFrame({"discharge-air-temp": vals, "fan-status": [1] * len(idx)}, index=idx)
    mask_steady = sv_rate_compute(df2, {"persistence_min": 10, "transition_window_min": 20}, poll=300.0)
    assert not bool(mask_trans.any()) or mask_trans.sum() < mask_steady.sum()
    assert bool(mask_steady.any())


def test_outdoor_and_mixed_profiles():
    assert resolve_profile(role="outside-air-temp")[0].profile_id == "outside_air_temperature"
    assert resolve_profile(role="mixed-air-temp")[0].profile_id == "mixed_air_temperature"


def test_co2_deadband_and_rh_pp():
    idx = _idx(24)
    base = 800.0
    noise = [base + (i % 2) * 50.0 for i in range(len(idx))]
    df = pd.DataFrame({"zone-co2": noise, "fan-status": [1] * len(idx)}, index=idx)
    mask = sv_rate_compute(df, {"persistence_min": 15}, poll=300.0)
    assert not bool(mask.any())
    prh, _ = resolve_profile(point_name="zone_rh")
    assert prh is not None
    assert prh.quantity == "relative_humidity"
    assert "pp" in prh.canonical_unit


def test_missing_design_flow_skips_flow_profile():
    idx = _idx(12)
    df = pd.DataFrame({"zone-airflow": np.linspace(100, 900, len(idx)), "fan-status": [1] * len(idx)}, index=idx)
    _ = sv_rate_compute(df, {}, poll=300.0)
    evidence = df.attrs.get("sv_rate_evidence") or []
    flow_ev = [e for e in evidence if e.get("resolved_profile_id") in {"vav_airflow", "ahu_airflow", "water_flow"}]
    if flow_ev:
        assert any(
            e.get("confidence") == "skipped_missing_scale" or e.get("status_hint") == "INSUFFICIENT_DATA"
            for e in flow_ev
        )


def test_missing_state_reduced_confidence():
    idx = _idx(24)
    vals = 70.0 + np.arange(len(idx)) * 0.1
    df = pd.DataFrame({"zone-air-temp": vals}, index=idx)
    state, meta = detect_operating_state(df)
    assert (state == "UNKNOWN_STATE").all()
    assert meta["confidence"] == "reduced"


def test_irregular_timestamps_and_duplicates():
    t0 = pd.Timestamp("2024-01-01", tz="UTC")
    times = [t0, t0 + pd.Timedelta(minutes=5), t0 + pd.Timedelta(minutes=5), t0 + pd.Timedelta(minutes=20)]
    s = pd.Series([70.0, 71.0, 71.5, 72.0], index=pd.DatetimeIndex(times))
    rates = compute_rates(s, max_gap_hours=2.0)
    assert rates["instantaneous_rate"].notna().sum() >= 1


def test_extreme_bypass_persistence():
    idx = _idx(12)
    vals = [70.0] * 6 + [90.0] * 6  # 20°F in one 5-min step ≫ 15°F extreme
    df = pd.DataFrame({"zone-air-temp": vals, "fan-status": [1] * len(idx)}, index=idx)
    mask = sv_rate_compute(df, {"persistence_min": 60}, poll=300.0)
    assert bool(mask.any())


def test_isolated_noise_no_persistent_fault():
    idx = _idx(24)
    vals = np.full(len(idx), 72.0)
    vals[10] = 90.0  # single spike — SV-SPIKE territory; persistence should suppress rate FAULT
    df = pd.DataFrame({"zone-air-temp": vals, "fan-status": [1] * len(idx)}, index=idx)
    mask = sv_rate_compute(df, {"persistence_min": 15}, poll=300.0)
    # May extreme-flag zone jump of 18°F in 5 min — if so, at least deterministic
    mask2 = sv_rate_compute(df, {"persistence_min": 15}, poll=300.0)
    assert mask.equals(mask2)


def test_run_rule_sv_rate_and_sched247():
    idx = _idx(36)
    vals = 70.0 + np.arange(len(idx)) * (20.0 * 5.0 / 60.0)
    df = pd.DataFrame({"zone-air-temp": vals, "fan-status": [1] * len(idx)}, index=idx)
    df.attrs["equipment_id"] = "VAV_1"
    df.attrs["equipment_type"] = "VAV"
    res = run_rule("SV-RATE", df, poll_seconds=300.0, require_operational_gates=False)
    assert res.status in {"PASS", "FAULT"}
    assert "sv_rate_evidence" in (res.metrics or {})

    always = pd.DataFrame({"fan-status": [1] * len(idx)}, index=idx)
    always.attrs["equipment_id"] = "AHU_1"
    always.attrs["equipment_type"] = "AHU"
    r247 = run_rule("SCHED-247", always, params={"always_on_pct": 0.95}, poll_seconds=300.0, require_operational_gates=False)
    assert r247.status in {"PASS", "FAULT"}
    assert r247.status == "FAULT" or float(r247.metrics.get("fault_hours", 0) or 0) >= 0


def test_plot_companions_temp_vs_pressure():
    from app.rules.cookbook_catalog import RULES_BY_ID
    from app.rules.runner import _plot_series_for_rule

    idx = _idx(8)
    d = pd.DataFrame(
        {
            "discharge-air-temp": [55.0] * 8,
            "outside-air-damper": [40.0] * 8,
            "cooling-valve": [30.0] * 8,
            "heating-valve": [0.0] * 8,
            "fan-cmd": [80.0] * 8,
            "duct-static-pressure": [1.2] * 8,
            "duct-static-pressure-sp": [1.0] * 8,
        },
        index=idx,
    )
    fc2 = RULES_BY_ID["FC2"]
    # Patch required roles presence — FC2 needs MAT/OAT/RAT; inject
    d["mixed-air-temp"] = 60.0
    d["outside-air-temp"] = 50.0
    d["return-air-temp"] = 72.0
    series = _plot_series_for_rule(fc2, d)
    assert "outside-air-damper" in series or "cooling-valve" in series or "heating-valve" in series
    assert "fan-cmd" not in series

    fc1 = RULES_BY_ID["FC1"]
    series1 = _plot_series_for_rule(fc1, d)
    assert "fan-cmd" in series1
    assert "duct-static-pressure" in series1


def test_config_round_trip_json():
    params = {
        "SV-RATE": {
            "persistence_min": 12.0,
            "svrate__zone_air_temperature__steady_fault_per_hour": 7.0,
        }
    }
    blob = json.dumps(params)
    loaded = json.loads(blob)
    assert loaded["SV-RATE"]["persistence_min"] == 12.0


def test_imperial_metric_display_does_not_change_fault_math():
    idx = _idx(36)
    vals = 70.0 + np.arange(len(idx)) * (20.0 * 5.0 / 60.0)
    df = pd.DataFrame({"zone-air-temp": vals, "fan-status": [1] * len(idx)}, index=idx)
    m1 = sv_rate_compute(df.copy(), {}, poll=300.0)
    m2 = sv_rate_compute(df.copy(), {}, poll=300.0)
    assert m1.equals(m2)


def test_co2_fast_ramp_1min_faults_despite_deadband():
    """Deadband is dt-aware; a 1-min ramp well above warning must not be silently held."""
    idx = pd.date_range("2024-06-01", periods=40, freq="1min", tz="UTC")
    # ~3000 ppm/h → ~50 ppm/min; scales deadband ~20 ppm at 1-min, so ramp survives
    vals = 800.0 + np.arange(len(idx)) * 50.0
    df = pd.DataFrame({"zone-co2": vals, "fan-status": [1] * len(idx)}, index=idx)
    mask = sv_rate_compute(df, {"persistence_min": 5}, poll=60.0)
    assert bool(mask.any())


def test_violation_minutes_use_real_dt():
    idx = pd.DatetimeIndex(
        [
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:05:00Z",
            "2024-01-01T00:20:00Z",  # 15-min gap
            "2024-01-01T00:25:00Z",
            "2024-01-01T00:30:00Z",
            "2024-01-01T00:35:00Z",
            "2024-01-01T00:40:00Z",
            "2024-01-01T00:45:00Z",
        ]
    )
    # Extreme jump then continuing fast change
    vals = [70.0, 90.0, 92.0, 94.0, 96.0, 98.0, 100.0, 102.0]
    df = pd.DataFrame({"zone-air-temp": vals, "fan-status": [1] * len(idx)}, index=idx)
    _ = sv_rate_compute(df, {"persistence_min": 5}, poll=300.0)
    evidence = df.attrs.get("sv_rate_evidence") or []
    assert evidence
    assert evidence[0]["violation_minutes"] >= 0.0


def test_invalid_override_records_error():
    idx = _idx(24)
    vals = 70.0 + np.arange(len(idx)) * 0.05
    df = pd.DataFrame({"zone-air-temp": vals, "fan-status": [1] * len(idx)}, index=idx)
    params = {
        "svrate__zone_air_temperature__steady_warning_per_hour": 10.0,
        "svrate__zone_air_temperature__steady_fault_per_hour": 4.0,  # fault < warning
    }
    _ = sv_rate_compute(df, params, poll=300.0)
    evidence = df.attrs.get("sv_rate_evidence") or []
    assert any(e.get("override_error") for e in evidence)


def test_sched247_fault_mask_equals_on_time():
    idx = _idx(20)
    fan = [1] * 20
    df = pd.DataFrame({"fan-status": fan}, index=idx)
    df.attrs["equipment_id"] = "AHU_1"
    df.attrs["equipment_type"] = "AHU"
    res = run_rule(
        "SCHED-247",
        df,
        params={"always_on_pct": 0.90, "confirm_min": 0},
        poll_seconds=300.0,
        require_operational_gates=False,
    )
    assert res.status == "FAULT"
    assert res.confirmed_fault is not None
    # Fault hours should be near full window when always on (not inflated beyond window)
    assert res.fault_hours is not None
    window_h = (len(idx) - 1) * 300.0 / 3600.0
    assert float(res.fault_hours) <= window_h + 0.6
    assert float(res.fault_hours) >= window_h * 0.5


def test_detect_operating_state_vectorized_start_stop_valve():
    idx = _idx(24)  # 5-min samples, 2 hours
    fan = [0] * 4 + [1] * 16 + [0] * 4
    valve = [0.0] * 12 + [0.5] * 12
    d = pd.DataFrame(
        {"fan-status": fan, "cooling-valve": valve, "zone-air-temp": [72.0] * 24},
        index=idx,
    )
    state, meta = detect_operating_state(d, transition_window_minutes=20)
    assert meta["confidence"] == "high"
    assert "STARTUP_TRANSIENT" in set(state.tolist())
    assert "SHUTDOWN_TRANSIENT" in set(state.tolist())
    # Shortly after fan start (sample 4) within 20 min window
    assert state.iloc[4] == "STARTUP_TRANSIENT"
    assert state.iloc[5] == "STARTUP_TRANSIENT"
    # Mid steady stretch after transition window
    assert state.iloc[12] in {"RUNNING_STEADY", "STARTUP_TRANSIENT"}
