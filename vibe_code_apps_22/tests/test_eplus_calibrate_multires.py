"""Tests for calibration registry + ranking helpers."""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
_ML = _ROOT / "ml"
sys.path.insert(0, str(_SCRIPTS))
sys.path.insert(0, str(_ML))

from eplus_calibrate_multires import _rank_candidate, _sensitivity_screen  # noqa: E402
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
    assert all(t["status"] == "planned" for t in trials)


def test_rank_monthly_gate_outranks_hourly():
    monthly_pass = resolution_block([100] * 11, [102] * 11, resolution="monthly")
    monthly_fail = {
        **monthly_pass,
        "status": "fail",
        "nmbe_pct": 20.0,
        "cvrmse_pct": 40.0,
    }
    hourly_bad = resolution_block([50.0] * 50, [90.0] * 50, resolution="hourly")
    hourly_ok = resolution_block([50.0] * 50, [51.0] * 50, resolution="hourly")
    r_fail = _rank_candidate(monthly_fail, hourly_ok)
    r_pass = _rank_candidate(monthly_pass, hourly_bad)
    assert r_fail["rank_key"][0] > r_pass["rank_key"][0]
