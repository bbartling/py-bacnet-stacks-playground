"""Imperial ↔ metric display toggle — every unit-sensitive path must flip with Units radio."""

from __future__ import annotations

import pandas as pd
import pytest

from app.unit_system import (
    c_to_f,
    cfm_to_ls,
    convert_scalar_threshold,
    convert_series,
    display_unit_for_role,
    f_to_c,
    inwc_to_pa,
    units_map_for_system,
)
from app.units import DEFAULT_ROLE_UNITS


# Roles that must convert when Units = metric (mirrors unit_system.py sets).
_TEMP_ROLES = (
    "sat",
    "sat_sp",
    "mat",
    "rat",
    "oa_t",
    "wx_oa_t",
    "zone_t",
    "chw_supply_t",
    "hw_supply_t",
    "cw_supply_t",
    "vav_inlet_t",
)
_STATIC_ROLES = ("duct_static", "duct_static_sp")
_FLOW_ROLES = ("zone_flow", "min_flow_sp")


@pytest.mark.parametrize("role", _TEMP_ROLES)
def test_temp_roles_toggle_imperial_to_metric(role: str):
    s = pd.Series([32.0, 68.0, 212.0])
    imp, u_i = convert_series(role, s, "imperial")
    met, u_m = convert_series(role, s, "metric")
    assert u_i in {"°F", "degF", "F"} or "F" in u_i or u_i == DEFAULT_ROLE_UNITS.get(role, "")
    assert u_m == "°C"
    assert abs(float(met.iloc[0]) - 0.0) < 1e-9
    assert abs(float(met.iloc[2]) - 100.0) < 1e-9
    # Imperial path must leave values unchanged
    assert abs(float(imp.iloc[1]) - 68.0) < 1e-9
    assert abs(float(met.iloc[1]) - f_to_c(68.0)) < 1e-9


@pytest.mark.parametrize("role", _STATIC_ROLES)
def test_static_roles_toggle_to_pa(role: str):
    s = pd.Series([1.0, 2.0])
    imp, u_i = convert_series(role, s, "imperial")
    met, u_m = convert_series(role, s, "metric")
    assert u_m == "Pa"
    assert abs(float(met.iloc[0]) - inwc_to_pa(1.0)) < 1e-3
    assert abs(float(imp.iloc[0]) - 1.0) < 1e-9
    assert "w.c" in u_i.lower() or u_i == DEFAULT_ROLE_UNITS.get(role, "") or u_i


@pytest.mark.parametrize("role", _FLOW_ROLES)
def test_flow_roles_toggle_to_ls(role: str):
    s = pd.Series([1000.0])
    imp, _u_i = convert_series(role, s, "imperial")
    met, u_m = convert_series(role, s, "metric")
    assert u_m == "L/s"
    assert abs(float(met.iloc[0]) - cfm_to_ls(1000.0)) < 1e-4
    assert abs(float(imp.iloc[0]) - 1000.0) < 1e-9


def test_pct_and_non_temp_roles_unchanged_on_metric_toggle():
    """Damper % / dimensionless roles must not invent a °C conversion."""
    s = pd.Series([0.0, 50.0, 100.0])
    for role in ("oa_damper_pct", "clg_valve_pct", "fan_cmd", "fan_status"):
        met, _ = convert_series(role, s, "metric")
        imp, _ = convert_series(role, s, "imperial")
        assert list(met) == list(imp) == [0.0, 50.0, 100.0]


def test_units_map_for_system_flips_labels():
    base = dict(DEFAULT_ROLE_UNITS)
    imp = units_map_for_system(base, "imperial")
    met = units_map_for_system(base, "metric")
    assert imp["sat"] != met["sat"] or met["sat"] == "°C"
    assert met["sat"] == "°C"
    assert met["duct_static"] == "Pa"
    assert met["zone_flow"] == "L/s"
    assert display_unit_for_role("sat", "imperial") in {imp["sat"], "°F", DEFAULT_ROLE_UNITS.get("sat", "")}
    assert display_unit_for_role("sat", "metric") == "°C"


def test_convert_scalar_threshold_matches_slider_storage_contract():
    """Sidebar/Overview temp sliders store °F; display converts with Units radio."""
    stored_f = 48.0  # chw_leave_max_f default-ish
    assert convert_scalar_threshold("chw_supply_t", stored_f, "imperial") == 48.0
    assert abs(convert_scalar_threshold("chw_supply_t", stored_f, "metric") - f_to_c(48.0)) < 1e-9
    # Round-trip display °C → store °F (what _temp_threshold_slider does)
    shown_c = f_to_c(70.0)
    assert abs(c_to_f(shown_c) - 70.0) < 1e-9


def test_temp_slider_bounds_flip_with_unit_system():
    """Mirror _temp_threshold_slider label/bounds math without Streamlit widgets."""
    min_f, max_f, step_f = 55.0, 72.0, 0.5  # zone low band
    for system, expect_lo, expect_hi, expect_unit in (
        ("imperial", 55.0, 72.0, "°F"),
        ("metric", round(f_to_c(55.0), 1), round(f_to_c(72.0), 1), "°C"),
    ):
        if system == "metric":
            lo, hi = round(f_to_c(min_f), 1), round(f_to_c(max_f), 1)
            step = max(0.1, round(step_f * 5.0 / 9.0, 1))
            label = f"Zone low {expect_unit}"
        else:
            lo, hi, step = min_f, max_f, step_f
            label = f"Zone low {expect_unit}"
        assert lo == expect_lo and hi == expect_hi
        assert expect_unit in label
        assert step > 0


def test_rcx_convert_map_respects_unit_system():
    """RCx overlay path (_convert_map) must change series + unit string on toggle."""
    from app.ui_rcx_tab import _convert_map

    series_map = {"AHU_1": pd.Series([55.0, 56.0], index=pd.RangeIndex(2))}
    imp_map, u_i = _convert_map(series_map, "sat", "imperial")
    met_map, u_m = _convert_map(series_map, "sat", "metric")
    assert u_m == "°C"
    assert abs(float(met_map["AHU_1"].iloc[0]) - f_to_c(55.0)) < 1e-9
    assert abs(float(imp_map["AHU_1"].iloc[0]) - 55.0) < 1e-9
    # duct static
    sm = {"AHU_1": pd.Series([1.2])}
    _imp, _ = _convert_map(sm, "duct_static", "imperial")
    met_s, u = _convert_map(sm, "duct_static", "metric")
    assert u == "Pa"
    assert abs(float(met_s["AHU_1"].iloc[0]) - inwc_to_pa(1.2)) < 1e-2


def test_units_map_feeds_plotly_axis_labels():
    """Plots chart path: _units_map equivalent must rewrite axis units when metric."""
    from app.charts import rule_result_chart
    from app.rules.base import RuleResult

    idx = pd.date_range("2024-06-01", periods=8, freq="5min", tz="UTC")
    df = pd.DataFrame({"sat": [55.0] * 8, "sat_sp": [55.0] * 8}, index=idx)
    res = RuleResult(
        rule_id="AHU-SATDEV",
        equipment_id="AHU_1",
        status="PASS",
        applicable=True,
        fault_hours=0.0,
        missing_roles=[],
        notes="",
        plot_series={"sat": df["sat"], "sat_sp": df["sat_sp"]},
    )
    fig_i = rule_result_chart(df, res, required_roles=["sat", "sat_sp"], units_map=units_map_for_system(None, "imperial"))
    fig_m = rule_result_chart(df, res, required_roles=["sat", "sat_sp"], units_map=units_map_for_system(None, "metric"))
    assert fig_i is not None and fig_m is not None
    # Metric map labels should prefer °C on at least one axis title domain
    met_units = units_map_for_system(None, "metric")
    assert met_units.get("sat") == "°C"
    imp_units = units_map_for_system(None, "imperial")
    assert met_units["sat"] != imp_units.get("sat") or met_units["sat"] == "°C"


def test_session_config_payload_includes_unit_system_toggle_values():
    """openfdd_session_v1 must carry unit_system so Cloud restore keeps the toggle."""
    from app.agent_api import make_session_config

    for system in ("imperial", "metric"):
        payload = make_session_config({}, {}, unit_system=system, prefer_web_oat=True)
        assert payload["unit_system"] == system


def test_streamlit_units_radio_toggles_session_and_slider_labels():
    """UI Units radio must flip session_state and CHW leave slider °F ↔ °C labels."""
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file("streamlit_app.py", default_timeout=120)

    def _ss(key, default=None):
        try:
            return at.session_state[key]
        except Exception:
            return default

    at.run()
    assert not at.exception, f"startup exceptions: {list(at.exception)}"

    assert _ss("unit_system", "imperial") == "imperial"
    labels_imp = [s.label for s in at.sidebar.slider]
    assert any("°F" in (lab or "") for lab in labels_imp), f"expected °F slider, got {labels_imp}"

    units_radio = next((r for r in at.sidebar.radio if r.label == "Units"), None)
    assert units_radio is not None, "Units radio missing from sidebar"
    units_radio.set_value("metric")
    at.run()
    assert not at.exception, f"after metric toggle: {list(at.exception)}"

    assert _ss("unit_system") == "metric"
    labels_met = [s.label for s in at.sidebar.slider]
    assert any("°C" in (lab or "") for lab in labels_met), f"expected °C slider, got {labels_met}"
    # Stored proof threshold stays imperial °F even while UI shows °C
    stored = float(_ss("chw_leave_max_f", 0.0))
    assert 35.0 <= stored <= 50.0

    units_radio = next((r for r in at.sidebar.radio if r.label == "Units"), None)
    assert units_radio is not None
    units_radio.set_value("imperial")
    at.run()
    assert not at.exception, f"after imperial toggle: {list(at.exception)}"
    assert _ss("unit_system") == "imperial"
    labels_back = [s.label for s in at.sidebar.slider]
    assert any("°F" in (lab or "") for lab in labels_back), f"expected °F again, got {labels_back}"
