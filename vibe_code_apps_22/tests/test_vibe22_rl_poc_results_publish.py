"""Unit tests for Vibe22 RL PoC results publisher (no EnergyPlus)."""
from __future__ import annotations

from eplus_gym.rl.poc_results_publish import (
    DEC_FLOOR_DISCLOSURE,
    arm_totals,
    december_floor_audit,
    readiness_stats_for_arm,
    school_occupied_from_row,
)


def _row(day: str, arm: str, *, school: bool, ready: bool, opening: float = 0.0) -> dict:
    return {
        "day": day,
        "arm": arm,
        "readiness_ok": ready,
        "energy_cost": 10.0,
        "incremental_demand_cost": 5.0,
        "peak_kw": 100.0,
        "daily_kwh": 50.0,
        "opening_mtd_kw": opening,
        "schedule_proof": {
            "school_occupancy_window": {
                "start_step": 30,
                "end_step": 59,
                "school_occupied": school,
            }
        },
    }


def test_readiness_stats_checked_school_only():
    rows = [
        _row("2025-12-15", "a", school=True, ready=True),
        _row("2025-12-16", "a", school=True, ready=True),
        _row("2025-12-17", "a", school=True, ready=True),
        _row("2025-12-18", "a", school=True, ready=True),
        _row("2025-12-19", "a", school=True, ready=False),
        _row("2025-12-20", "a", school=False, ready=True),  # auto-pass weekend
        _row("2025-12-21", "a", school=False, ready=True),
    ]
    stats = readiness_stats_for_arm(rows)
    assert stats["checked_school_days"] == 5
    assert stats["ready_checked_school_days"] == 4
    assert stats["unchecked_non_school_days"] == 2
    assert stats["all_validation_rows"] == 7
    assert abs(stats["readiness_rate_checked_school_days"] - 0.8) < 1e-9
    assert "4/5 checked school days" in stats["wording"]
    assert "2 non-school days were not subject" in stats["wording"]
    # Misleading legacy count would be 6/7 — must not be used as school readiness.
    assert stats["legacy_misleading_readiness_ok_rows"] == 6


def test_school_occupied_missing_proof_is_unchecked():
    assert school_occupied_from_row({"schedule_proof": {}}) is False


def test_december_floor_disclosure_when_zero():
    rows = [
        _row("2025-12-15", "incumbent", school=True, ready=True, opening=0.0),
        _row("2025-12-15", "trained_ppo_seed0", school=True, ready=True, opening=0.0),
    ]
    audit = december_floor_audit(rows)
    assert audit["all_opening_mtd_kw_zero"] is True
    assert audit["corrected_scores_published"] is False
    assert audit["disclosure"] == DEC_FLOOR_DISCLOSURE


def test_arm_totals_include_readiness_block():
    rows = [
        _row("2025-12-15", "incumbent", school=True, ready=True),
        _row("2025-12-20", "incumbent", school=False, ready=True),
    ]
    totals = arm_totals(rows)
    assert totals["incumbent"]["total_cost"] == 30.0
    assert totals["incumbent"]["readiness"]["checked_school_days"] == 1
    assert totals["incumbent"]["readiness"]["ready_checked_school_days"] == 1
