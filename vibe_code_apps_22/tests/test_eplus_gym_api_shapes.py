"""API-shape tests for eplus_gym (no live EnergyPlus required)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_honesty_constants():
    from eplus_gym.honesty import HONESTY_IDEALLOADS, HONESTY_W2A, LOOKUP_EMULATOR, PROMOTE

    assert HONESTY_IDEALLOADS == "STRUCTURAL_LOAD_DIAGNOSTIC"
    assert HONESTY_W2A == "W2A_PHYSICAL_DSM"
    assert LOOKUP_EMULATOR == "FARM_LOOKUP_EMULATOR"
    assert PROMOTE is False


def test_list_strategies_and_controller():
    from eplus_gym.controllers import RuleController, list_strategies, f_to_c

    strats = list_strategies()
    assert "baseline" in strats
    ctrl = RuleController("baseline")
    assert len(ctrl.series_f()) == 96
    assert 10.0 < ctrl.action_c(0) < 30.0
    assert abs(f_to_c(68.0) - 20.0) < 0.01


def test_farm_lookup_env_synthetic(tmp_path):
    """Lookup env works against a tiny synthetic paired parquet."""
    import pandas as pd

    from eplus_gym.lookup_emulator import FarmLookupEnv, STEPS

    farm = tmp_path / "eplus" / "dsm_farm_paired"
    farm.mkdir(parents=True)
    rows = []
    for strategy in ("baseline", "deep_setback"):
        for q in range(STEPS):
            rows.append(
                {
                    "day": "2026-01-11",
                    "strategy_id": strategy,
                    "timestamp_utc": f"2026-01-11T{q // 4:02d}:{(q % 4) * 15:02d}:00Z",
                    "quarter_index": q,
                    "facility_kw": 100.0 + q + (10.0 if strategy == "deep_setback" else 0.0),
                    "oat_f": 20.0,
                }
            )
    pd.DataFrame(rows).to_parquet(farm / "heating_dsm_eplus_paired_15min_v1.parquet", index=False)

    env = FarmLookupEnv(
        site_root=tmp_path,
        day="2026-01-11",
        strategy_id="baseline",
        htg_setpoints_f=[68.0] * STEPS,
    )
    obs, info = env.reset()
    assert info["provenance"] == "FARM_LOOKUP_EMULATOR"
    assert obs["facility_kw"] == pytest.approx(100.0)
    obs2, reward, done, _, _ = env.step(20.0)
    assert obs2["step"] == 1.0
    assert done is False
    # drain
    while not done:
        obs2, reward, done, _, _ = env.step(20.0)
    assert done is True


def test_run_rule_episode_lookup(tmp_path):
    import pandas as pd

    from eplus_gym.simulate import run_rule_episode, trajectory_frame
    from eplus_gym.lookup_emulator import STEPS

    # minimal contract
    contracts = ROOT / "contracts" / "control_strategies_v1" / "baseline.json"
    assert contracts.is_file()

    farm = tmp_path / "eplus" / "dsm_farm_paired"
    farm.mkdir(parents=True)
    rows = []
    for q in range(STEPS):
        rows.append(
            {
                "day": "2026-01-11",
                "strategy_id": "baseline",
                "timestamp_utc": f"2026-01-11T{q // 4:02d}:{(q % 4) * 15:02d}:00Z",
                "quarter_index": q,
                "facility_kw": 50.0 + 0.1 * q,
                "oat_f": 10.0,
            }
        )
    pd.DataFrame(rows).to_parquet(farm / "heating_dsm_eplus_paired_15min_v1.parquet", index=False)

    result = run_rule_episode(
        site_root=tmp_path,
        strategy_id="baseline",
        day="2026-01-11",
        mode="lookup",
    )
    df = trajectory_frame(result)
    assert len(df) == STEPS
    assert result["meta"]["mode"] == "lookup"
    assert result["meta"]["promote"] is False
    assert "facility_kw" in df.columns
    assert "htg_sp_f" in df.columns


def test_train_rllib_stub():
    from eplus_gym.train_rllib import train_ppo_stub

    with pytest.raises(NotImplementedError):
        train_ppo_stub(env_config={})


def test_energyplus_available_bool():
    from eplus_gym.discover import energyplus_available

    assert isinstance(energyplus_available(), bool)
