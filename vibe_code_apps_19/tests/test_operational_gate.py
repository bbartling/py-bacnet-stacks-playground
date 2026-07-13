"""Operational gate + SKIPPED_EQUIPMENT_OFF tests."""

from __future__ import annotations

import pandas as pd

from app.rules import CANONICAL_RULES, RULES_BY_ID, run_rule
from app.rules.operational_gate import RULE_GATES, resolve_fan_running, resolve_operational_mask


def test_all_canonical_rules_have_gate_spec():
    assert len(RULE_GATES) == 53
    for r in CANONICAL_RULES:
        assert r.id in RULE_GATES, r.id


def test_fan_status_preferred_over_fan_cmd():
    idx = pd.date_range("2024-01-01", periods=4, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "fan-cmd": [100, 100, 100, 100],
            "fan-status": [0, 0, 1, 1],
        },
        index=idx,
    )
    mask, src = resolve_fan_running(df)
    assert src == "fan-status"
    assert list(mask.astype(int)) == [0, 0, 1, 1]


def test_fc2_skips_when_fan_off_entire_period():
    idx = pd.date_range("2024-01-01", periods=12, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "mixed-air-temp": [50.0] * 12,
            "return-air-temp": [70.0] * 12,
            "outside-air-temp": [30.0] * 12,
            "fan-cmd": [0.0] * 12,
            "fan-status": [0] * 12,
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


def test_sv_range_gated_by_fan_status():
    idx = pd.date_range("2024-01-01", periods=12, freq="5min", tz="UTC")
    # Out-of-range SAT but fan off entire window → skip (no active samples)
    df = pd.DataFrame(
        {
            "discharge-air-temp": [200.0] * 12,
            "fan-status": [0] * 12,
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "AHU_1"
    r = run_rule(
        "SV-RANGE",
        df,
        {"confirm_min": 0, "require_operational_gate": 1, "startup_delay_min": 0},
        300.0,
        require_operational_gates=True,
    )
    assert r.status == "SKIPPED_EQUIPMENT_OFF"
    assert RULE_GATES["SV-RANGE"].kind == "equipment_energized"


def test_chw_rule_gated_by_pump_status():
    idx = pd.date_range("2024-01-01", periods=12, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "chilled-water-supply-temp": [44.0] * 12,
            "chilled-water-return-temp": [44.0] * 12,
            "chw-pump-status": [0] * 12,
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "CHILLER_1"
    df.attrs["equipment_type"] = "CHILLER"
    r = run_rule(
        "CHW-1",
        df,
        {"confirm_min": 0, "require_operational_gate": 1, "startup_delay_min": 0},
        300.0,
        require_operational_gates=True,
    )
    assert r.status == "SKIPPED_EQUIPMENT_OFF"
    assert RULE_GATES["CHW-1"].kind == "hydronic_flow"


def test_plant_sv_uses_pump_when_no_fan():
    from app.rules.operational_gate import resolve_equipment_energized

    idx = pd.date_range("2024-01-01", periods=6, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "chilled-water-supply-temp": [44.0] * 6,
            "chw-pump-status": [1, 1, 1, 0, 0, 0],
        },
        index=idx,
    )
    mask, src = resolve_equipment_energized(df)
    assert "pump" in src or "chw_pump" in src
    assert list(mask.astype(int)) == [1, 1, 1, 0, 0, 0]


def test_mechanical_rules_not_always_except_known():
    """FDD equations must be fan- or pump-gated except intentional ALWAYS rules."""
    always_ok = {"SV-STALE", "OAT-METEO", "WX-1", "SCHED-1", "CMD-1"}
    for r in CANONICAL_RULES:
        kind = RULE_GATES[r.id].kind
        if r.id in always_ok:
            assert kind == "always", r.id
        else:
            assert kind != "always", f"{r.id} should be gated by fan/pump/energized, got {kind}"


def test_gate_disabled_global_does_not_skip():
    idx = pd.date_range("2024-01-01", periods=12, freq="5min", tz="UTC")
    df = pd.DataFrame(
        {
            "mixed-air-temp": [50.0] * 12,
            "return-air-temp": [70.0] * 12,
            "outside-air-temp": [30.0] * 12,
            "fan-cmd": [0.0] * 12,
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
    df = pd.DataFrame({"outside-air-temp": [70, 71, 72]}, index=idx)
    active, meta = resolve_operational_mask(df, "SCHED-1", poll_seconds=300)
    assert active.all()
    assert meta["gate_kind"] == "always"


def test_resolve_mask_meta_equipment_energized_without_proof_ungated():
    idx = pd.date_range("2024-01-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame({"outside-air-temp": [70, 71, 72]}, index=idx)
    active, meta = resolve_operational_mask(df, "SV-RANGE", poll_seconds=300)
    assert active.all()
    assert meta["gate_kind"] == "equipment_energized"
    assert str(meta.get("gate_source", "")).startswith("ungated")
