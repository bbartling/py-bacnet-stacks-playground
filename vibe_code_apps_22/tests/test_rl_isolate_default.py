"""Unit tests for RL worker isolation plumbing (no EnergyPlus)."""
from __future__ import annotations

from eplus_gym.rl.daily_env import DailySixZoneGymEnv
from eplus_gym.rl.live_day_worker import main as worker_main


def test_daily_env_defaults_to_isolate():
    env = DailySixZoneGymEnv(
        {
            "site_root": ".",
            "epw": "dummy.epw",
            "champion_idf": "dummy.idf",
            "days": ["2026-01-26"],
            "simulator": "LIVE_ENERGYPLUS",
        }
    )
    assert env.isolate_eplus is True
    assert env.action_space.shape == (11,)


def test_worker_main_requires_job(tmp_path):
    # argparse SystemExit when missing --job
    try:
        worker_main([])
        raised = False
    except SystemExit as exc:
        raised = True
        assert int(exc.code) != 0
    assert raised
