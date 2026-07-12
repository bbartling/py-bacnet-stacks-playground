"""Operational gate + SKIPPED_EQUIPMENT_OFF tests."""

from __future__ import annotations

import pandas as pd

from app.rules import CANONICAL_RULES, RULES_BY_ID, run_rule
from app.rules.operational_gate import RULE_GATES, resolve_fan_running, resolve_operational_mask


def test_all_50_rules_have_gate_spec():
    assert len(RULE_GATES) == 51
    for r in CANONICAL_RULES:
        assert r.id in RULE_GATES, r.id


def test_fan_status_preferred_over_fan_cmd():
    idx = pd.date_range("2024-01-01", periods=4, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "fan_cmd": [100, 100, 100, 100],
            "fan_status": [0, 0, 1, 1],
        },
        index=idx,
    )
    mask, src = resolve_fan_running(df)
    assert src == "fan_status"
    assert list(mask.astype(int)) == [0, 0, 1, 1]


def test_fc2_skips_when_fan_off_entire_period():
    idx = pd.date_range("2024-01-01", periods=12, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "mat": [50.0] * 12,
            "rat": [70.0] * 12,
            "oa_t": [30.0] * 12,
            "fan_cmd": [0.0] * 12,
            "fan_status": [0] * 12,
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "AHU_1"
    r = run_rule(
        "FC2",
        df,
        {"confirm_min": 0, "require_operational_gate": 1, "startup_delay_min": 0},
        300.0,
        require_operational_gates=True,
    )
    assert r.status == "SKIPPED_EQUIPMENT_OFF"
    assert r.applicable is False


def test_sched1_always_evaluates_when_fan_off():
    idx = pd.date_range("2024-01-01", periods=6, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "occ_mode": ["unoccupied"] * 6,
            "fan_status": [1, 1, 1, 1, 1, 1],
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "AHU_1"
    r = run_rule("SCHED-1", df, {"confirm_min": 0}, 300.0, require_operational_gates=True)
    assert r.status in {"PASS", "FAULT"}
    assert RULE_GATES["SCHED-1"].kind == "always"


def test_gate_disabled_global_does_not_skip():
    idx = pd.date_range("2024-01-01", periods=12, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "mat": [50.0] * 12,
            "rat": [70.0] * 12,
            "oa_t": [30.0] * 12,
            "fan_cmd": [0.0] * 12,
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "AHU_1"
    r = run_rule(
        "FC2",
        df,
        {"confirm_min": 0, "startup_delay_min": 0},
        300.0,
        require_operational_gates=False,
    )
    assert r.status != "SKIPPED_EQUIPMENT_OFF"


def test_resolve_mask_meta_for_always():
    idx = pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame({"oa_t": [70, 71, 72]}, index=idx)
    active, meta = resolve_operational_mask(df, "SV-RANGE", poll_seconds=300)
    assert active.all()
    assert meta["gate_kind"] == "always"
