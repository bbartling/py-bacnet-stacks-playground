"""Behavior tests for GL36 VAV-AHU AFDD tunable parameters."""

from __future__ import annotations

import pandas as pd

from app.rules.cookbook_catalog import fc5, fc6, fc7, fc8


def _frame(**columns: list[float]) -> pd.DataFrame:
    n = len(next(iter(columns.values())))
    return pd.DataFrame(
        columns,
        index=pd.date_range("2026-01-01", periods=n, freq="5min", tz="UTC"),
    )


def test_fc5_delta_supply_fan_slider_changes_fault_mask() -> None:
    df = _frame(
        **{
            "discharge-air-temp": [56.5] * 3,
            "mixed-air-temp": [56.0] * 3,
            "fan-cmd": [1.0] * 3,
            "heating-valve": [1.0] * 3,
        }
    )
    strict = fc5(
        df,
        {"eps_sat": 0.25, "eps_mat": 0.25, "delta_supply_fan": 0.55, "htg_on_min": 0.01},
        300,
    )
    permissive = fc5(
        df,
        {"eps_sat": 0.25, "eps_mat": 0.25, "delta_supply_fan": 2.0, "htg_on_min": 0.01},
        300,
    )
    assert not strict.any()
    assert permissive.all()


def test_fc6_delta_t_min_slider_changes_fault_mask() -> None:
    df = _frame(
        **{
            "mixed-air-temp": [60.0] * 3,
            "outside-air-temp": [50.0] * 3,
            "return-air-temp": [60.0] * 3,
            "vav-total-airflow": [10000.0] * 3,
            "fan-cmd": [1.0] * 3,
        }
    )
    detects = fc6(df, {"eps_airflow": 0.30, "delta_t_min": 5.0, "min_cfm_design": 5000}, 300)
    suppresses = fc6(df, {"eps_airflow": 0.30, "delta_t_min": 12.0, "min_cfm_design": 5000}, 300)
    assert detects.all()
    assert not suppresses.any()


def test_fc7_full_heating_threshold_is_tunable() -> None:
    df = _frame(
        **{
            "discharge-air-temp": [50.0] * 3,
            "discharge-air-temp-sp": [55.0] * 3,
            "fan-cmd": [1.0] * 3,
            "heating-valve": [0.95] * 3,
        }
    )
    detects = fc7(df, {"eps_sat": 2.0, "htg_full_min": 0.90}, 300)
    suppresses = fc7(df, {"eps_sat": 2.0, "htg_full_min": 0.99}, 300)
    assert detects.all()
    assert not suppresses.any()


def test_fc8_independent_sensor_errors_change_combined_tolerance() -> None:
    df = _frame(
        **{
            "discharge-air-temp": [58.0] * 3,
            "mixed-air-temp": [55.0] * 3,
            "outside-air-damper": [1.0] * 3,
            "cooling-valve": [0.0] * 3,
        }
    )
    detects = fc8(
        df,
        {
            "eps_sat": 1.0,
            "eps_mat": 1.0,
            "delta_supply_fan": 0.55,
            "econ_min_pos": 0.05,
            "clg_inactive_max": 0.10,
        },
        300,
    )
    suppresses = fc8(
        df,
        {
            "eps_sat": 3.0,
            "eps_mat": 3.0,
            "delta_supply_fan": 0.55,
            "econ_min_pos": 0.05,
            "clg_inactive_max": 0.10,
        },
        300,
    )
    assert detects.all()
    assert not suppresses.any()


def test_mode_delay_suspends_fault_after_operating_state_change() -> None:
    df = _frame(
        **{
            "discharge-air-temp": [58.0] * 5,
            "mixed-air-temp": [55.0] * 5,
            "outside-air-damper": [0.0, 1.0, 1.0, 1.0, 1.0],
            "cooling-valve": [0.0] * 5,
            "fan-cmd": [1.0] * 5,
        }
    )
    params = {
        "eps_sat": 1.0,
        "eps_mat": 1.0,
        "delta_supply_fan": 0.55,
        "econ_min_pos": 0.05,
        "clg_inactive_max": 0.10,
    }
    immediate = fc8(df, {**params, "mode_delay_min": 0.0}, 300)
    delayed = fc8(df, {**params, "mode_delay_min": 10.0}, 300)
    assert immediate.iloc[1:].all()
    assert not delayed.iloc[1:3].any()
    assert delayed.iloc[3:].all()


def test_new_canonical_defaults_match_legacy_fc8_behavior() -> None:
    df = _frame(
        **{
            "discharge-air-temp": [58.0, 56.0, 54.0],
            "mixed-air-temp": [55.0] * 3,
            "outside-air-damper": [1.0] * 3,
            "cooling-valve": [0.0] * 3,
        }
    )
    legacy = fc8(df, {"mix_tol": 1.15, "supply_tol": 1.15}, 300)
    canonical = fc8(
        df,
        {
            "eps_mat": 1.15,
            "eps_sat": 1.15,
            "delta_supply_fan": 0.55,
            "econ_min_pos": 0.05,
            "clg_inactive_max": 0.10,
            "mode_delay_min": 0.0,
        },
        300,
    )
    pd.testing.assert_series_equal(canonical, legacy)
