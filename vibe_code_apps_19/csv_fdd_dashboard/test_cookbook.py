"""Tests for the Open-FDD cookbook rule catalog + data-model engine.

These avoid the RDF/ttl layer: they build synthetic logical frames and call the
compute functions, applicability logic, and role resolution directly.
"""

import numpy as np
import pandas as pd

import cookbook_rules as cb
import cookbook_engine as ce


def _ts(n=120, poll_s=300):
    return pd.date_range("2026-05-01", periods=n, freq=f"{poll_s}s", tz="UTC")


# ---------------------------------------------------------------------------
# Catalog integrity
# ---------------------------------------------------------------------------


def test_catalog_serializes_and_is_complete():
    cat = cb.catalog()
    ids = {r["id"] for r in cat}
    # A spread across every family must be present
    for rid in ["SV-RANGE", "SV-FLATLINE", "FC1", "FC13", "ECON-3", "VAV-1",
                "CHW-1", "HP-1", "WX-1", "TRIM-1"]:
        assert rid in ids, rid
    # Every rule exposes an equation and at least the confirm slider
    for r in cat:
        assert r["equation"]
        assert any(p["key"] == "confirm_min" for p in r["params"])


def test_rules_for_kind():
    ahu = {r.id for r in cb.rules_for_kind("ahu")}
    assert {"FC1", "ECON-3", "SV-RANGE"} <= ahu
    weather = {r.id for r in cb.rules_for_kind("weather")}
    assert "WX-1" in weather and "FC1" not in weather


# ---------------------------------------------------------------------------
# Role resolution
# ---------------------------------------------------------------------------


def test_match_physical_exact_and_substring():
    cols = ["outside_air_temp_f", "supply_fan_speed_pct", "discharge_air_temp_f"]
    assert ce._match_physical("oa_t", cols) == "outside_air_temp_f"
    assert ce._match_physical("fan_cmd", cols) == "supply_fan_speed_pct"
    assert ce._match_physical("sat", cols) == "discharge_air_temp_f"


def test_heating_does_not_collide_with_chw_valve():
    """`hw_valve` must not match inside `chw_valve_pct` (that column is cooling)."""
    cols = ["chw_valve_pct"]
    assert ce._match_physical("clg_valve_pct", cols) == "chw_valve_pct"
    assert ce._match_physical("htg_valve_pct", cols) is None


def test_resolve_role_respects_exclude():
    cols = ["chw_valve_pct"]
    used = {"chw_valve_pct"}
    # once cooling has claimed the column, nothing else may reuse it
    assert ce.resolve_role("AHU_X", "clg_valve_pct", cols, resolver=None, exclude=used) is None


# ---------------------------------------------------------------------------
# Applicability / not-in-model messaging
# ---------------------------------------------------------------------------


def test_not_applicable_reports_missing_points():
    idx = _ts()
    d = pd.DataFrame({"timestamp": idx, "sat": np.full(len(idx), 55.0)}, index=range(len(idx)))
    rule = cb.RULES_BY_ID["FC1"]  # needs duct_static, duct_static_sp, fan_cmd
    res = ce.run_rule(rule, d, {}, 300.0, {}, weather_available=False)
    assert res["applicable"] is False
    assert "duct_static" in " ".join(res["missing_roles"])
    assert res["message"].startswith("Not in data model")


def test_applicable_rule_counts_fault_hours():
    idx = _ts(n=60)
    n = len(idx)
    # duct static far below setpoint at full fan -> FC1 should confirm
    d = pd.DataFrame({
        "timestamp": idx,
        "duct_static": np.full(n, 0.5),
        "duct_static_sp": np.full(n, 1.5),
        "fan_cmd": np.full(n, 95.0),
    }, index=range(n))
    rule = cb.RULES_BY_ID["FC1"]
    res = ce.run_rule(rule, d, {}, 300.0, {}, weather_available=False)
    assert res["applicable"] is True
    assert res["fault_hours"] > 0


# ---------------------------------------------------------------------------
# ECON-3: open-meteo dew point gate vs imperial fallback
# ---------------------------------------------------------------------------


def _econ3_frame(oat, dewpoint=None, clg=50.0, damper=10.0):
    idx = _ts(n=40)
    n = len(idx)
    data = {
        "timestamp": idx,
        "oa_t": np.full(n, oat),
        "oa_damper_pct": np.full(n, damper),
        "clg_valve_pct": np.full(n, clg),
    }
    if dewpoint is not None:
        data["wx_oa_t"] = np.full(n, oat)
        data["wx_oa_dewpoint"] = np.full(n, dewpoint)
    return pd.DataFrame(data, index=range(n))


def test_econ3_open_meteo_gate_faults_when_dry_and_dewpoint_low():
    # dry-bulb 60F (35..72), dew point 50F (<60) -> economizer available, mech cooling on -> fault
    d = _econ3_frame(oat=60.0, dewpoint=50.0)
    mask = ce.econ3_compute(d, {}, 300.0, weather_available=True)
    assert mask.all()


def test_econ3_open_meteo_gate_clears_when_dewpoint_high():
    # humid: dew point 65F (>60) -> not favorable -> no fault even though dry-bulb ok
    d = _econ3_frame(oat=60.0, dewpoint=65.0)
    mask = ce.econ3_compute(d, {}, 300.0, weather_available=True)
    assert not mask.any()


def test_econ3_imperial_fallback_when_no_weather():
    # No dew point available -> fallback OAT < 63F rule
    cold = ce.econ3_compute(_econ3_frame(oat=55.0), {}, 300.0, weather_available=False)
    warm = ce.econ3_compute(_econ3_frame(oat=70.0), {}, 300.0, weather_available=False)
    assert cold.all()
    assert not warm.any()


# ---------------------------------------------------------------------------
# Representative rule masks
# ---------------------------------------------------------------------------


def test_econ2_economizing_when_unfavorable():
    idx = _ts(n=30)
    n = len(idx)
    d = pd.DataFrame({
        "timestamp": idx,
        "oa_t": np.full(n, 75.0),         # > 63F
        "oa_damper_pct": np.full(n, 60.0),  # > 42%
    }, index=range(n))
    assert cb.econ2(d, {}, 300.0).all()


def test_vav1_comfort_band():
    idx = _ts(n=20)
    n = len(idx)
    hot = pd.DataFrame({"timestamp": idx, "zone_t": np.full(n, 80.0)}, index=range(n))
    ok = pd.DataFrame({"timestamp": idx, "zone_t": np.full(n, 72.0)}, index=range(n))
    assert cb.vav1(hot, {}, 900.0).all()
    assert not cb.vav1(ok, {}, 900.0).any()


def test_sensor_sweep_range_flags_out_of_range():
    idx = _ts(n=20)
    n = len(idx)
    d = pd.DataFrame({"timestamp": idx, "oa_t": np.full(n, 300.0)}, index=range(n))  # impossible OAT
    assert cb._sweep_range(d, {}, 300.0).all()


def test_confirm_seconds_override_from_param():
    rule = cb.RULES_BY_ID["FC1"]
    assert ce._confirm_seconds(rule, {"confirm_min": 20}) == 1200.0
    assert ce._confirm_seconds(rule, {}) == rule.confirm_seconds
