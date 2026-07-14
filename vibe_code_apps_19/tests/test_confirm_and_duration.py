"""Confirm-default contract, dt-aware confirm/hours, and FC4 index fix."""

from __future__ import annotations

import pytest
import pandas as pd

from app.rules.base import confirm_fault, hours_true
from app.rules.cookbook_catalog import RULES, RULES_BY_ID, fc4
from app.rules import run_rule
from tests.point_names import canon_point_cols


def test_confirm_min_default_matches_confirm_seconds() -> None:
    for r in RULES:
        conf = next(p for p in r.params if p.key == "confirm_min")
        assert conf.default * 60.0 == pytest.approx(r.confirm_seconds), r.id
        assert conf.min == 0.0, r.id
        assert conf.max >= conf.default, r.id
        assert conf.direction == "fewer", r.id


def test_fc2_default_confirm_is_ten_minutes() -> None:
    rule = RULES_BY_ID["FC2"]
    assert rule.confirm_seconds == 600.0
    assert rule.defaults()["confirm_min"] == 10.0


def test_pid_hunt_default_confirm_is_zero() -> None:
    rule = RULES_BY_ID["PID-HUNT-1"]
    assert rule.confirm_seconds == 0.0
    assert rule.defaults()["confirm_min"] == 0.0


def test_confirm_fault_row_count_fallback() -> None:
    raw = pd.Series([True, True, True, False, True])
    # confirm 600s / poll 300s => 2 rows
    out = confirm_fault(raw, poll_seconds=300.0, confirm_seconds=600.0)
    assert out.tolist() == [False, True, True, False, False]


def test_confirm_fault_dt_aware_irregular() -> None:
    idx = pd.to_datetime(
        [
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:05:00Z",  # +5 min
            "2024-01-01T00:20:00Z",  # +15 min
            "2024-01-01T00:25:00Z",  # +5 min
        ],
        utc=True,
    )
    raw = pd.Series([True, True, True, False], index=idx)
    # Need 10 minutes of True run. After sample0 (owns 5min) cum=5 → not yet;
    # after sample1 (owns 15min) cum=20 → confirmed.
    out = confirm_fault(raw, poll_seconds=300.0, confirm_seconds=600.0)
    assert out.tolist() == [False, True, True, False]


def test_hours_true_dt_aware() -> None:
    idx = pd.to_datetime(
        [
            "2024-01-01T00:00:00Z",
            "2024-01-01T01:00:00Z",
            "2024-01-01T01:30:00Z",
            "2024-01-01T02:30:00Z",
        ],
        utc=True,
    )
    mask = pd.Series([True, True, False, True], index=idx)
    # True intervals: 1.0h + 0.5h + median(1,0.5,1)=1.0h for last → 2.5h
    h = hours_true(mask, poll_seconds=3600.0)
    assert abs(h - 2.5) < 1e-9


def test_fc4_works_with_datetime_index_no_timestamp_column() -> None:
    n = 120  # 2 hours at 1-min
    idx = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    damper = [0.0 if i % 2 == 0 else 0.5 for i in range(n)]
    clg = [0.0 if i % 2 == 0 else 0.5 for i in range(n)]
    data = canon_point_cols(
        {
            "oa_damper_pct": damper,
            "clg_valve_pct": clg,
            "fan_cmd": [50.0] * n,
            "htg_valve_pct": [0.0] * n,
        }
    )
    df = pd.DataFrame(data, index=idx)
    assert "timestamp" not in df.columns
    mask = fc4(df, {"delta_os_max": 5.0}, 60.0)
    assert bool(mask.any()), "FC4 must fault on oscillating modes with DatetimeIndex"


def test_fc4_run_rule_status_fault() -> None:
    n = 120
    idx = pd.date_range("2024-01-01", periods=n, freq="min", tz="UTC")
    damper = [0.0 if i % 2 == 0 else 0.5 for i in range(n)]
    clg = [0.0 if i % 2 == 0 else 0.5 for i in range(n)]
    data = canon_point_cols(
        {
            "oa_damper_pct": damper,
            "clg_valve_pct": clg,
            "fan_cmd": [50.0] * n,
            "htg_valve_pct": [0.0] * n,
        }
    )
    df = pd.DataFrame(data, index=idx)
    df.attrs["equipment_id"] = "AHU_1"
    df.attrs["equipment_type"] = "AHU"
    r = run_rule(
        "FC4",
        df,
        {"confirm_min": 0, "delta_os_max": 5.0, "startup_delay_min": 0},
        poll_seconds=60.0,
        require_operational_gates=False,
    )
    assert r.status == "FAULT"


def test_confirm_min_increase_shrinks_fault_samples() -> None:
    idx = pd.date_range("2024-01-01", periods=24, freq="5min", tz="UTC")
    data = canon_point_cols(
        {
            "mat": [46.0] * 24,
            "oa_t": [50.0] * 24,
            "rat": [70.0] * 24,
            "fan_cmd": [50.0] * 24,
        }
    )
    df = pd.DataFrame(data, index=idx)
    df.attrs["equipment_id"] = "AHU_1"
    df.attrs["equipment_type"] = "AHU"
    loose = run_rule(
        "FC2", df, {"mix_tol": 1.15, "confirm_min": 5}, 300.0, require_operational_gates=False
    )
    tight = run_rule(
        "FC2", df, {"mix_tol": 1.15, "confirm_min": 60}, 300.0, require_operational_gates=False
    )
    assert loose.fault_sample_count > tight.fault_sample_count
