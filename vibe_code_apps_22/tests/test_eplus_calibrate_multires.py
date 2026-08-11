"""Tests for calibration registry + ranking helpers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
_ML = _ROOT / "archive" / "ml"
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_ML))

from eplus_calibrate_multires import (  # noqa: E402
    _multi_param_smoke_plan,
    _promotion_gate,
    _rank_candidate,
    _sensitivity_screen,
)
from eplus_multires_metrics import resolution_block  # noqa: E402

REGISTRY = _ROOT / "contracts" / "eplus_calib_param_registry_v1.json"


def test_registry_has_stages_a_b_c():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    stages = {p["stage"] for p in reg["parameters"]}
    assert {"A", "B", "C"}.issubset(stages)
    assert reg["champion_protection"]["never_overwrite_staged_without_promote"] is True


def test_sensitivity_screen_stage_a_bounds():
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    trials = _sensitivity_screen(reg, "A")
    assert trials
    assert all(t["stage"] == "A" for t in trials)
    # Non-executable schedule knobs are rejected; executable ones stay planned
    assert all(t["status"] in {"planned", "rejected"} for t in trials)
    assert any(t["status"] == "rejected" for t in trials)


def test_rank_monthly_gate_outranks_hourly():
    monthly_pass = resolution_block([100] * 11, [102] * 11, resolution="monthly")
    monthly_fail = {
        **monthly_pass,
        "status": "fail",
        "nmbe_pct": 20.0,
        "cvrmse_pct": 40.0,
    }
    interv = resolution_block([100] * 11, [102] * 11, resolution="monthly")
    hourly_bad = resolution_block([50.0] * 50, [90.0] * 50, resolution="hourly")
    hourly_ok = resolution_block([50.0] * 50, [51.0] * 50, resolution="hourly")
    r_fail = _rank_candidate(monthly_fail, interv, hourly_ok)
    r_pass = _rank_candidate(monthly_pass, interv, hourly_bad)
    assert r_fail["rank_key"][0] > r_pass["rank_key"][0]


def test_q15_promotion_fail_closed_even_if_n_large():
    metrics = {
        "monthly_utility": {"status": "pass"},
        "monthly_interval": {"status": "pass"},
        "hourly_chronological_validation": {"status": "pass"},
        "hourly_locked_winter_holdout": {"status": "pass"},
        "q15": {"status": "fail", "n": 500},
        "zone_temperature": {"status": "pass"},
        "provenance": {"measured": {}, "modeled": {}},
    }
    gate = _promotion_gate(metrics)
    assert any("q15" in r for r in gate["promote_block_reasons"])
    assert gate["promote_allowed"] is False


def test_multi_param_respects_max_trials_slice():
    plan = _multi_param_smoke_plan()
    assert len(plan) == 3
    assert len(plan[:1]) == 1

