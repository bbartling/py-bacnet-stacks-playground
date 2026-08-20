"""Research-long CLI, checkpoints, pack honesty, winner rule. No EnergyPlus."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from eplus_gym.control_v2 import build_six_schedules_f, continuous_params
from eplus_gym.rl.multiday_env import FakeContinuityPlant, MultiDayDailyEnv
from eplus_gym.mega.obs_tariff_v4 import N_OBS_V4
from eplus_gym.rl.obs_v3 import N_OBS_V3
from eplus_gym.rl.research_checkpoint import (
    SCHEMA,
    checkpoint_resumable,
    refuse_metadata_only,
    write_block_checkpoint,
    CheckpointError,
)
from eplus_gym.rl.research_eval import select_winner
from eplus_gym.rl.research_long import freeze_research_long_days, run_research_long, write_heartbeat
from eplus_gym.rl.research_spaces import (
    RESEARCH_ACTION_CONTRACT_V2,
    RESEARCH_ACTION_CONTRACT_V3,
    encode_continuous_research_v2,
)

APP = Path(__file__).resolve().parents[1]


def _tiny_epw(path: Path) -> Path:
    lines = ["LOCATION,Fake"]
    for d in range(1, 32):
        for h in range(24):
            lines.append(f"2025,11,{d},{h+1},0,0,-5.0")
    for d in range(1, 32):
        for h in range(24):
            lines.append(f"2025,12,{d},{h+1},0,0,-10.0")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_research_long_cli_missing_confirms_exit_4():
    import sys

    sys.path.insert(0, str(APP / "scripts"))
    import vibe22_rl

    rc = vibe22_rl.main(["research-long", "--max-wall-hours", "30"])
    assert rc == vibe22_rl.EXIT_INTEGRITY
    rc2 = vibe22_rl.main(
        [
            "research-long",
            "--confirm-simulation-only-physics-limits",
            "--max-wall-hours",
            "30",
        ]
    )
    assert rc2 == vibe22_rl.EXIT_INTEGRITY


def test_research_long_dry_run_keeps_gates_false():
    out = run_research_long(
        app_root=APP,
        site_root=APP,
        confirm_simulation_only_physics_limits=True,
        confirm_a04_not_transient_validated=True,
        execute_live=False,
        micro_gate=False,
    )
    assert out["allowed"] is True
    assert out["long_campaign_allowed"] is False
    assert out["SIMULATION_TRAINING_READY"] is False
    assert out["OPERATIONAL_DSM_READY"] is False
    assert out["bacnet_commands"] == 0
    assert "RESEARCH_LONG_ALLOWED" in out["claim_labels"]
    assert out["action_contract_version"] == RESEARCH_ACTION_CONTRACT_V3
    assert out["observation_dim"] == N_OBS_V4
    assert out["tariff_mode"] == "FLAT_PLUS_DEMAND"
    assert out["cooling_action_space"] is False


def test_research_long_does_not_alias_campaign():
    import sys

    sys.path.insert(0, str(APP / "scripts"))
    import vibe22_rl

    rc = vibe22_rl.main(["campaign", "--simulator", "LIVE_ENERGYPLUS", "--n-days", "3"])
    assert rc == vibe22_rl.EXIT_INTEGRITY


def test_freeze_days_excludes_january(tmp_path: Path):
    epw = _tiny_epw(tmp_path / "fake.epw")
    pool = freeze_research_long_days(epw)
    assert pool["train"][0] == "2025-11-01"
    assert pool["train"][-1] == "2025-12-14"
    assert pool["validation"][0] == "2025-12-15"
    assert pool["validation"][-1] == "2025-12-31"
    assert all(not x.startswith("2026-01") for x in pool["train"] + pool["validation"])
    assert "NO LOCKED UNSEEN" in pool["locked_unseen"]


def test_metadata_only_checkpoint_is_not_resumable(tmp_path: Path):
    body = {"schema": SCHEMA, "valid_transition_count": 3, "metadata_only": True}
    assert checkpoint_resumable(body, root=tmp_path) is False
    with pytest.raises(CheckpointError):
        refuse_metadata_only(body)


class _FakeModel:
    def save(self, path: str) -> None:
        Path(path).write_bytes(b"PK\x03\x04fakezip")

    def save_replay_buffer(self, path: str) -> None:
        Path(path).write_bytes(b"replay")


def test_real_checkpoint_requires_zip_and_v2_contract(tmp_path: Path):
    body = write_block_checkpoint(
        root=tmp_path,
        model=_FakeModel(),
        algo="PPO",
        seed=0,
        valid_transition_count=7,
        block_id="2025-11-01:2025-11-07",
        day="2025-11-07",
        idf_sha256="aa",
        epw_sha256="bb",
        rng_hex="cc",
    )
    assert body["action_contract_version"] == RESEARCH_ACTION_CONTRACT_V2
    assert body["observation_dim"] == 80
    assert body["metadata_only"] is False
    assert checkpoint_resumable(body, root=tmp_path) is True
    (tmp_path / "ppo_block.zip").unlink()
    assert checkpoint_resumable(body, root=tmp_path) is False


def test_select_winner_none_unless_trained_beats_baselines():
    rows = []
    for arm in ("incumbent", "continuous_68", "continuous_70", "shallow_setback", "random"):
        rows.append({"arm": arm, "training_reward": 1.0, "readiness_ok": True})
    rows.append({"arm": "trained_ppo_seed0", "training_reward": 0.5, "readiness_ok": True})
    assert select_winner(rows) is None
    rows.append({"arm": "trained_ppo_seed0", "training_reward": 2.0, "readiness_ok": True})
    # one seed only — cannot claim
    assert select_winner(rows) is None
    rows.append({"arm": "trained_ppo_seed1", "training_reward": 2.0, "readiness_ok": True})
    assert select_winner(rows) == "trained_ppo_seed1"


def test_research_contract_skips_dishonest_pack():
    from eplus_gym.rl.train_sb3 import should_write_policy_pack

    assert should_write_policy_pack({"action_contract_version": RESEARCH_ACTION_CONTRACT_V2}) is False
    assert should_write_policy_pack({"action_contract_version": "research_action_contract_v1"}) is False
    assert should_write_policy_pack({"write_policy_pack": False}) is False
    assert should_write_policy_pack({}) is True


def test_dqn_checkpoint_requires_replay(tmp_path: Path):
    body = write_block_checkpoint(
        root=tmp_path,
        model=_FakeModel(),
        algo="DQN",
        seed=0,
        valid_transition_count=3,
        block_id="2025-11-01:2025-11-07",
        day="2025-11-07",
        idf_sha256="aa",
        epw_sha256="bb",
        rng_hex="cc",
    )
    assert checkpoint_resumable(body, root=tmp_path) is True
    (tmp_path / "replay_buffer.pkl").unlink()
    assert checkpoint_resumable(body, root=tmp_path) is False


def test_restore_refuses_hash_mismatch(tmp_path: Path):
    write_block_checkpoint(
        root=tmp_path,
        model=_FakeModel(),
        algo="PPO",
        seed=0,
        valid_transition_count=3,
        block_id="b",
        day="2025-11-07",
        idf_sha256="aa",
        epw_sha256="bb",
        rng_hex="cc",
    )
    from eplus_gym.rl.research_checkpoint import restore_checkpoint

    with pytest.raises(CheckpointError, match="idf sha256"):
        restore_checkpoint(tmp_path, idf_sha256="other", epw_sha256="bb")


def test_persist_billing_across_blocks():
    days = ["2025-12-08", "2025-12-09", "2025-12-10", "2025-12-11"]
    oat = {d: [-10.0] * 24 for d in days}
    plant = FakeContinuityPlant()
    plant.start_episode()
    sched = build_six_schedules_f(continuous_params(70.0))
    payloads = {}
    for day in days:
        payloads[day] = plant.simulate_day(sched, oat_c=oat[day])
    env = MultiDayDailyEnv(
        {
            "days": days,
            "plant": FakeContinuityPlant(),
            "hourly_oat": oat,
            "baseline_payloads": payloads,
            "block_size": 2,
            "persist_billing": True,
            "action_contract_version": RESEARCH_ACTION_CONTRACT_V2,
            "require_live_energyplus": False,
        }
    )
    obs, _ = env.reset()
    assert obs.shape[0] == N_OBS_V3
    action = encode_continuous_research_v2(continuous_params(70.0))
    floors = []
    done = False
    while not done:
        obs, _, term, trunc, info = env.step(action)
        floors.append(info["closing_mtd_kw"])
        done = term or trunc
    first_close = floors[-1]
    obs, _ = env.reset()
    _, _, _, _, info2 = env.step(action)
    assert info2["opening_mtd_kw"] >= first_close - 1e-6


def test_heartbeat_never_unlocks_gates(tmp_path: Path):
    path = tmp_path / "hb.json"
    write_heartbeat(path, {"valid_transitions": 3, "pid": 1})
    body = json.loads(path.read_text(encoding="utf-8"))
    assert body["long_campaign_allowed"] is False
    assert body["SIMULATION_TRAINING_READY"] is False
    assert body["bacnet_commands"] == 0
    assert body["pid"]
    assert body["contaminated"] is False
