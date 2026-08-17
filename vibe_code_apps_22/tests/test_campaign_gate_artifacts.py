"""Nonempty artifact paths are not campaign evidence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eplus_gym.rl.active_model import ActiveModelError, load_active_model, verify_active_model
from eplus_gym.rl.operator_pay_experiment import refuse_full_campaign

APP = Path(__file__).resolve().parents[1]


def test_active_model_points_at_reward_v2_and_stays_blocked():
    body = load_active_model(APP)
    assert body["reward_contract_version"] == "reward_v2"
    assert body["long_campaign_allowed"] is False
    with pytest.raises(ActiveModelError):
        verify_active_model(APP)
    decision = refuse_full_campaign(APP)
    assert decision["allowed"] is False


def test_nonempty_failed_ramp_artifact_does_not_unlock(tmp_path: Path):
    contracts = tmp_path / "contracts"
    contracts.mkdir()
    ramp = tmp_path / "ramp.json"
    ramp.write_text(json.dumps({"passed": False, "verdict": "NO_GO"}), encoding="utf-8")
    body = {
        "long_campaign_allowed": True,
        "idf_path": "models/eplus/missing.idf",
        "idf_sha256": "abc",
        "epw_sha256": "def",
        "energyplus_version": "26.1.0",
        "control_contract_version": "control_contract_v2",
        "observation_contract_version": "observation_contract_v3",
        "action_contract_version": "ppo_action_contract_v2",
        "reward_contract_version": "reward_v2",
        "transient_validation_artifact": "ramp.json",
        "warning_gate_artifact": "ramp.json",
        "monthly_validation_artifact": "ramp.json",
        "heldout_status": "locked_unseen",
    }
    (contracts / "active_rl_model_v1.json").write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(ActiveModelError):
        verify_active_model(tmp_path)
    decision = refuse_full_campaign(tmp_path)
    assert decision["allowed"] is False
