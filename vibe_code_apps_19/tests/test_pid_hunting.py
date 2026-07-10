"""PID-HUNT-1 — suspected control-output hunting (replaces SV-4)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.rules.pid_hunting import PidHuntingParams, hunting_fault_mask
from app.rules.cookbook_catalog import RULES_BY_ID


def test_pid_hunt_rule_replaces_sv4():
    assert "SV-4" not in RULES_BY_ID
    assert "PID-HUNT-1" in RULES_BY_ID
    rule = RULES_BY_ID["PID-HUNT-1"]
    assert "Suspected" in rule.title or "hunting" in rule.title.lower()
    assert rule.id == "PID-HUNT-1"


def test_hunting_mask_on_full_scale_oscillation():
    # 0→100→0→100→0→100 over one hour at 12-min steps → TV≈500, cycles≈2.5
    idx = pd.date_range("2026-07-10 08:00", periods=6, freq="12min", tz="UTC")
    u = pd.Series([0.0, 100.0, 0.0, 100.0, 0.0, 100.0], index=idx)
    params = PidHuntingParams(
        window="1h",
        change_deadband_pct=1.0,
        minimum_span_pct=20.0,
        total_variation_fault_pct=500.0,
        minimum_equivalent_cycles=2.5,
        minimum_reversals=4,
        minimum_coverage_pct=80.0,
    )
    fault, metrics = hunting_fault_mask(u, params=params)
    assert fault.iloc[-1] is True or bool(fault.iloc[-1]) is True
    assert metrics["total_variation_1h"].iloc[-1] >= 499.0
    assert metrics["equivalent_cycles_1h"].iloc[-1] >= 2.4
    assert metrics["reversals_1h"].iloc[-1] >= 4


def test_hunting_mask_midrange_oscillation():
    idx = pd.date_range("2026-07-10 08:00", periods=11, freq="6min", tz="UTC")
    # 40↔60 hunting — never hits endpoints
    vals = [40, 60, 40, 60, 40, 60, 40, 60, 40, 60, 40]
    u = pd.Series([float(v) for v in vals], index=idx)
    params = PidHuntingParams(
        total_variation_fault_pct=150.0,  # lower threshold for mid-span
        minimum_span_pct=15.0,
        minimum_equivalent_cycles=2.0,
        minimum_reversals=4,
        minimum_coverage_pct=70.0,
    )
    fault, metrics = hunting_fault_mask(u, params=params)
    assert metrics["output_span_1h"].iloc[-1] >= 15.0
    assert bool(fault.iloc[-1])


def test_pid_hunt_cookbook_compute_or_across_outputs():
    rule = RULES_BY_ID["PID-HUNT-1"]
    idx = pd.date_range("2026-07-10 08:00", periods=6, freq="12min", tz="UTC")
    df = pd.DataFrame(
        {
            "damper_pct": [0, 100, 0, 100, 0, 100],
            "reheat_valve_pct": [50.0] * 6,  # stable — should not alone fault
        },
        index=idx,
    )
    params = {p.key: p.default for p in rule.params}
    raw = rule.compute(df, params, 720.0)
    assert raw.iloc[-1]
