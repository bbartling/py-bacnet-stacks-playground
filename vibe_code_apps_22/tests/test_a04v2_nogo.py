"""A04-v2 development contracts: immutable A04, peak freeze, CapMult fail-closed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from eplus_gym.envs.lakeside_w2a import is_a04_idf_filename
from eplus_gym.rl.physics_ramp_gate import ENGINEERING_MARGIN
from eplus_gym.rl.operator_pay_experiment import refuse_full_campaign

APP = Path(__file__).resolve().parents[1]
A04_SHA = "212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683"


def test_a04_hash_immutable():
    idf = APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    assert hashlib.sha256(idf.read_bytes()).hexdigest() == A04_SHA


def test_engineering_margin_unchanged():
    assert ENGINEERING_MARGIN == 3.0


def test_refuse_full_while_committed_ramp_failed():
    decision = refuse_full_campaign(APP)
    assert decision["allowed"] is False


def test_a04v2_filename_allowed_without_overwriting_a04():
    assert is_a04_idf_filename("lakeside_w2a_a04v2_capmult_t28.idf")
    assert is_a04_idf_filename("staged_lakeside_w2a_a04v2_capmult_t28.idf")
    assert is_a04_idf_filename("lakeside_w2a_a04_dual_champion.idf")
    assert not is_a04_idf_filename("random_building.idf")


def test_selection_verdict_is_nogo():
    path = APP / "docs" / "audits" / "figures" / "a04v2" / "selection_verdict.json"
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["verdict"] == "NO_GO_LONG_RL_TRAINING_TRANSIENT_MODEL_NOT_VALIDATED"
    assert body["long_campaign_allowed"] is False
    assert body["champion"] is None
    assert body["pareto"]["conflict"] is True
    assert body["ramp_threshold_unchanged"]["engineering_margin"] == 3.0


def test_peak_tolerance_frozen_band():
    path = APP / "docs" / "audits" / "figures" / "a04v2" / "selection_verdict.json"
    peak = json.loads(path.read_text(encoding="utf-8"))["peak_tolerance_frozen_before_selection"]
    assert peak["anchor_kw"] == 284.82
    assert peak["tol_frac"] == 0.10
    assert abs(peak["hi_kw"] - 284.82 * 1.1) < 1e-6
