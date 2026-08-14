"""Random-walk sampler + report bundle (no EnergyPlus)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from eplus_gym.rl.plots import plot_reward_violin
from eplus_gym.rl.report_bundle import build_report, load_jsonl_episodes
from eplus_gym.rl.spaces import (
    END_HI,
    END_LO,
    OCC_F_HI,
    OCC_F_LO,
    REC_HI,
    REC_LO,
    SETBACK_HI,
    SETBACK_LO,
    START_HI,
    START_LO,
    UNOCC_F_HI,
    UNOCC_F_LO,
    sample_random_params,
)
from eplus_gym.six_zone_daily_controller import ACTION_KEYS
import numpy as np


def test_sample_random_params_in_bounds():
    rng = np.random.default_rng(0)
    for _ in range(20):
        p = sample_random_params(rng)
        assert OCC_F_LO <= p.occupied_heating_f <= OCC_F_HI
        assert UNOCC_F_LO <= p.unoccupied_heating_f <= UNOCC_F_HI
        assert START_LO <= p.occupancy_start_step <= START_HI
        assert END_LO <= p.occupancy_end_step <= END_HI
        assert p.occupancy_end_step > p.occupancy_start_step
        assert REC_LO <= p.recovery_start_minutes_before_occupancy <= REC_HI
        for k in ACTION_KEYS:
            sb = p.zone_offsets[k].setback_offset_f
            assert SETBACK_LO <= sb <= SETBACK_HI


def test_load_jsonl_and_report_schema(tmp_path: Path):
    run = tmp_path / "run"
    run.mkdir()
    (run / "episodes.jsonl").write_text(
        '{"reward": -4000, "day": "2026-01-26", "daily_kwh": 3000, "peak_kw": 200, "pre8_violations": 0}\n',
        encoding="utf-8",
    )
    rows = load_jsonl_episodes(run / "episodes.jsonl")
    assert rows[0]["policy"] == "PPO"

    def fake_run_day(**kwargs):
        day = kwargs["day"]
        params = kwargs["ctrl"].params.to_dict()
        return {
            "reward": -4100.0,
            "daily_kwh": 3100.0,
            "peak_kw": 210.0,
            "pre8_violations": 1,
            "failed": False,
            "params": params,
            "day": day,
        }

    site = tmp_path / "site"
    site.mkdir()
    dummy = tmp_path / "dummy.epw"
    dummy.write_text("dummy\n", encoding="utf-8")
    out = build_report(
        site_root=site,
        epw=dummy,
        champion_idf=dummy,
        run_root=run,
        days=["2026-01-26"],
        random_timesteps=2,
        heuristic_days=False,
        repo_copy=tmp_path / "repo_copy",
        run_day=fake_run_day,
    )
    csv = run / "report" / "episodes.csv"
    assert csv.is_file()
    df = pd.read_csv(csv)
    assert "policy" in df.columns and "reward" in df.columns
    assert (df["policy"] == "random_walk").sum() == 2
    assert (tmp_path / "repo_copy" / "comparison.json").is_file()
    assert out["scientific_claim"].startswith("ENERGYPLUS")


def test_violin_plot_toy(tmp_path: Path):
    df = pd.DataFrame(
        {
            "policy": ["PPO", "PPO", "random_walk", "random_walk"],
            "reward": [-4000.0, -4100.0, -4500.0, -4300.0],
        }
    )
    p = plot_reward_violin(df, tmp_path)
    assert p.is_file()
