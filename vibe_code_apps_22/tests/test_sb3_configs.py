"""Named SB3 configs are not smoke-sized for long_poc."""
from __future__ import annotations

from eplus_gym.rl.sb3_configs import named_config


def test_named_configs_exist():
    smoke = named_config("smoke")
    pilot = named_config("pilot")
    long_poc = named_config("long_poc")
    assert smoke["ppo"]["n_steps"] <= 8
    assert long_poc["ppo"]["n_steps"] > 8
    assert long_poc["dqn"]["learning_starts"] > 2
    assert pilot["name"] == "pilot"


def test_bakeoff_source_has_no_mean_reward_winner():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "eplus_gym" / "rl" / "train_sb3.py").read_text(encoding="utf-8")
    assert "winner = max(" not in src
    assert "not_mean_reward" in src
