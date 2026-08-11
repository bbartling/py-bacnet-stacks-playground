"""W2A gym family routing — no silent IdealLoads fallback."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eplus_gym.lookup_emulator import STEPS
from eplus_gym.simulate import run_rule_episode, trajectory_frame


def _write_w2a_farm(site: Path, *, day: str = "2026-01-26", peak: float = 280.0) -> None:
    farm = site / "eplus" / "dsm_farm_w2a"
    farm.mkdir(parents=True)
    rows = [
        {
            "day": day,
            "strategy_id": "baseline",
            "timestamp_utc": f"{day}T{q // 4:02d}:{(q % 4) * 15:02d}:00Z",
            "quarter_index": q,
            "facility_kw": peak + 0.1 * q,
            "oat_f": 10.0,
        }
        for q in range(STEPS)
    ]
    pd.DataFrame(rows).to_parquet(farm / "heating_dsm_w2a_15min_v1.parquet", index=False)


def _write_ideal_farm(site: Path) -> None:
    farm = site / "eplus" / "dsm_farm_paired"
    farm.mkdir(parents=True)
    rows = [
        {
            "day": "2026-01-11",
            "strategy_id": "baseline",
            "quarter_index": q,
            "facility_kw": 500.0 + q,
            "oat_f": 10.0,
        }
        for q in range(STEPS)
    ]
    pd.DataFrame(rows).to_parquet(
        farm / "heating_dsm_eplus_paired_15min_v1.parquet", index=False
    )


def test_honesty_w2a_constant():
    from eplus_gym.honesty import HONESTY_W2A, PROMOTE

    assert HONESTY_W2A == "W2A_PHYSICAL_DSM"
    assert PROMOTE is False


def test_w2a_env_module_contract():
    from eplus_gym.envs.lakeside_w2a import DEFAULT_IDF, HONESTY, LakesideW2AEnv
    from eplus_gym.honesty import HONESTY_W2A

    assert HONESTY == HONESTY_W2A
    assert DEFAULT_IDF.name == "lakeside_w2a_a04_dual_champion.idf"
    assert LakesideW2AEnv.__name__ == "LakesideW2AEnv"


def test_w2a_lookup_uses_w2a_farm_not_idealloads(tmp_path: Path):
    _write_w2a_farm(tmp_path, peak=280.0)
    _write_ideal_farm(tmp_path)
    result = run_rule_episode(
        site_root=tmp_path,
        strategy_id="baseline",
        day="2026-01-26",
        mode="lookup",
        family="w2a",
    )
    df = trajectory_frame(result)
    assert len(df) == STEPS
    assert result["meta"]["honesty"] == "W2A_PHYSICAL_DSM"
    assert result["meta"]["provenance"] == "FARM_LOOKUP_EMULATOR"
    assert result["meta"]["family"] == "w2a"
    assert float(df["facility_kw"].max()) < 400.0


def test_w2a_lookup_does_not_fall_back_to_idealloads_farm(tmp_path: Path):
    _write_ideal_farm(tmp_path)
    with pytest.raises(FileNotFoundError, match="dsm_farm_w2a"):
        run_rule_episode(
            site_root=tmp_path,
            strategy_id="baseline",
            day="2026-01-11",
            mode="lookup",
            family="w2a",
        )


def test_w2a_auto_without_farm_or_live_is_explicit(tmp_path: Path, monkeypatch):
    _write_ideal_farm(tmp_path)
    monkeypatch.setattr("eplus_gym.simulate.energyplus_available", lambda: False)
    with pytest.raises(FileNotFoundError, match="will not fall back to IdealLoads"):
        run_rule_episode(
            site_root=tmp_path,
            strategy_id="baseline",
            mode="auto",
            family="w2a",
        )
