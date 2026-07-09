"""Tests for pandas FDD rules."""

from __future__ import annotations

import pandas as pd
import pytest

from app.rules import RULES_BY_ID, run_rule
from app.rules.base import confirm_fault, hours_true
from app.rules.fan_rules import fan_runtime_hours


def _df(**cols: list[float]) -> pd.DataFrame:
    n = len(next(iter(cols.values())))
    idx = pd.date_range("2024-06-01", periods=n, freq="5min", tz="UTC")
    return pd.DataFrame(cols, index=idx)


def test_confirm_fault_and_hours():
    raw = pd.Series([False, True, True, True, False], index=range(5))
    confirmed = confirm_fault(raw, poll_seconds=300, confirm_seconds=600)
    assert confirmed.tolist() == [False, False, True, True, False]
    assert hours_true(confirmed, 300) == pytest.approx(2 * 300 / 3600)


def test_fan_runtime():
    df = _df(fan_cmd=[0, 1, 1, 0, 1])
    df.attrs["equipment_id"] = "AHU_1"
    r = fan_runtime_hours(df, {"fan_on_frac": 0.05}, 300, 0)
    assert r.fault_hours == pytest.approx(3 * 300 / 3600)


def test_vav_comfort():
    df = _df(zone_t=[72, 72, 65, 78, 72])
    df.attrs["equipment_id"] = "VAV_7"
    spec = RULES_BY_ID["VAV-1"]
    r = run_rule(spec, df, {"low_limit_f": 68, "high_limit_f": 76, "_confirm_minutes": 0}, 300)
    assert r.fault_hours > 0


def test_sat_high():
    df = _df(
        sat=[55, 56, 57, 55, 55],
        sat_sp=[50, 50, 50, 50, 50],
        clg_valve_pct=[50, 50, 50, 0, 50],
        oa_damper_pct=[3, 3, 3, 3, 3],
    )
    df.attrs["equipment_id"] = "AHU_1"
    spec = RULES_BY_ID["SAT-HIGH"]
    r = run_rule(spec, df, {"sat_high_delta_f": 1, "_confirm_minutes": 0}, 300)
    assert r.raw_fault.sum() >= 3
