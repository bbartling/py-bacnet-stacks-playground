"""Cooling-tower approach / full-fan rules CW-APR-1 and CW-FAN-1."""

from __future__ import annotations

import pandas as pd

from app.rules.cookbook_catalog import RULES_BY_ID
from app.rules.runner import run_cookbook_rule


def _frame(*, approach_f: float, fan_pct: float = 100.0) -> pd.DataFrame:
    idx = pd.date_range("2026-07-10 12:00", periods=8, freq="15min", tz="UTC")
    wb = 70.0
    return pd.DataFrame(
        {
            "cw_supply_t": [wb + approach_f] * len(idx),
            "wx_oa_wetbulb": [wb] * len(idx),
            "tower_fan_cmd": [fan_pct] * len(idx),
            "chw_pump_status": [1] * len(idx),
        },
        index=idx,
    )


def test_cw_apr_and_fan_rules_registered():
    assert "CW-APR-1" in RULES_BY_ID
    assert "CW-FAN-1" in RULES_BY_ID
    assert "cooling_tower" in RULES_BY_ID["CW-APR-1"].equipment_kinds


def test_cw_apr_faults_high_approach_at_full_fan():
    rule = RULES_BY_ID["CW-APR-1"]
    df = _frame(approach_f=12.0, fan_pct=100.0)
    params = {p.key: p.default for p in rule.params}
    raw = rule.compute(df, params, 900.0)
    assert bool(raw.iloc[-1])


def test_cw_apr_pass_when_fan_not_full():
    rule = RULES_BY_ID["CW-APR-1"]
    df = _frame(approach_f=12.0, fan_pct=40.0)
    params = {p.key: p.default for p in rule.params}
    raw = rule.compute(df, params, 900.0)
    assert not bool(raw.iloc[-1])


def test_cw_fan_excess_needs_beyond_design_plus_slack():
    rule = RULES_BY_ID["CW-FAN-1"]
    # design approach 7 + excess 5 = 12; approach 10 should pass, 14 fault
    params = {p.key: p.default for p in rule.params}
    mild = rule.compute(_frame(approach_f=10.0), params, 900.0)
    hot = rule.compute(_frame(approach_f=14.0), params, 900.0)
    assert not bool(mild.iloc[-1])
    assert bool(hot.iloc[-1])


def test_cw_apr_runner_skips_without_fan_role():
    rule = RULES_BY_ID["CW-APR-1"]
    idx = pd.date_range("2026-07-10", periods=4, freq="h", tz="UTC")
    df = pd.DataFrame(
        {"cw_supply_t": [85.0] * 4, "wx_oa_wetbulb": [70.0] * 4, "chw_pump_status": [1] * 4},
        index=idx,
    )
    df.attrs["equipment_type"] = "COOLING_TOWER"
    result = run_cookbook_rule(
        rule,
        df,
        equipment_id="CT_1",
        equipment_kind="cooling_tower",
        poll_seconds=900.0,
        weather=None,
        equipment_type="COOLING_TOWER",
    )
    assert result.status == "SKIPPED_MISSING_ROLES"
