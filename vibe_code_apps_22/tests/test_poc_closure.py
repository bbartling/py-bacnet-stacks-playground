"""POC closure: ledger, baseline cache, lookback temps, eval obs, 192-row, ramp, plots."""
from __future__ import annotations

from pathlib import Path

import json
import pandas as pd
import pytest

from eplus_gym.objective import BAS_ZONE_COLS
from eplus_gym.rl.baseline_cache import (
    BASELINE_INCUMBENT,
    get_or_compute_incumbent_baseline,
    key_from_paths,
    load_record,
    store_record,
)
from eplus_gym.rl.campaign_eval_plots import NoValidEvalError, load_valid_eval, plot_validation_return_vs_eplus_calls
from eplus_gym.rl.experiment_ledger import build_experiment_ledger
from eplus_gym.rl.physics_ramp_gate import VERDICT_FAIL, evaluate_ramp_gate
from eplus_gym.rl.spaces import N_OBS_V2, build_day_observation
from eplus_gym.rl.trajectory_provenance import extract_lookback_end_zone_temps, write_episode_manifest


def test_ledger_from_p1_gates():
    app = Path(__file__).resolve().parents[1]
    led = build_experiment_ledger(app_root=app)
    assert led["valid_postfix_training_episodes"] == 0
    assert led["valid_postfix_eplus_gate_calls"] == 5
    assert led["deterministic_validation_episodes"] == 0
    assert led["heldout_test_episodes"] == 0
    assert led["historical_invalid_training_episodes"]["PPO"] == 488
    assert led["jan26_pair"]["not_rl_policy"] is True
    assert "not_pristine" in led["january_status"]


def test_baseline_cache_hit_and_invalidation(tmp_path: Path):
    idf = tmp_path / "a.idf"
    epw = tmp_path / "a.epw"
    idf.write_bytes(b"idf-a")
    epw.write_bytes(b"epw-a")
    calls = {"n": 0}

    def compute():
        calls["n"] += 1
        return 100.0, 50.0

    prov = key_from_paths(
        idf=idf,
        staged_epw=epw,
        day="2026-01-26",
        lookback_days=1,
        baseline_name=BASELINE_INCUMBENT,
        energyplus_version="EnergyPlus",
        reward_name="operator_pay_2x_v1",
    )
    a = get_or_compute_incumbent_baseline(cache_dir=tmp_path / "c", provenance=prov, compute=compute)
    b = get_or_compute_incumbent_baseline(cache_dir=tmp_path / "c", provenance=prov, compute=compute)
    assert calls["n"] == 1
    assert a["cache_hit"] is False
    assert b["cache_hit"] is True
    epw.write_bytes(b"epw-b")
    prov2 = key_from_paths(
        idf=idf,
        staged_epw=epw,
        day="2026-01-26",
        lookback_days=1,
        baseline_name=BASELINE_INCUMBENT,
        energyplus_version="EnergyPlus",
        reward_name="operator_pay_2x_v1",
    )
    assert prov2["key"] != prov["key"]
    with pytest.raises(ValueError, match="mismatch"):
        load_record(tmp_path / "c", {**prov, "idf_sha256": "deadbeef"})
    bad = dict(prov)
    rec_path = tmp_path / "c2" / "x.json"
    store_record(tmp_path / "c2", {**prov, "key": "x"}, kwh=1, peak_kw=1)
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    rec["source"] = "candidate"
    rec_path.write_text(json.dumps(rec), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate-as-baseline"):
        load_record(tmp_path / "c2", {**prov, "key": "x"})


def test_lookback_end_temps_not_seventy():
    look = [{c: 65.1 for c in BAS_ZONE_COLS} | {"lookback": True} for _ in range(96)]
    scored = [{c: 70.0 for c in BAS_ZONE_COLS} | {"lookback": False} for _ in range(96)]
    temps = extract_lookback_end_zone_temps(look + scored)
    assert all(abs(t - 65.1) < 1e-6 for t in temps)
    with pytest.raises(ValueError, match="no lookback"):
        extract_lookback_end_zone_temps(scored)


def test_episode_manifest_distinguishes_96_and_192(tmp_path: Path):
    t = tmp_path / "trajectory.parquet"
    a = tmp_path / "trajectory_all.parquet"
    t.write_bytes(b"scored")
    a.write_bytes(b"allrows")
    man = write_episode_manifest(tmp_path, n_rows=96, n_all_rows=192, trajectory=t, trajectory_all=a)
    assert man["scored_is_not_full_simulation"] is True
    assert man["n_rows_scored"] == 96
    assert man["n_all_rows"] == 192
    with pytest.raises(ValueError):
        write_episode_manifest(tmp_path, n_rows=192, n_all_rows=192, trajectory=t, trajectory_all=a)


def test_obs_context_not_dummy(tmp_path: Path):
    epw = tmp_path / "x.epw"
    # Minimal EPW header + one data line is not enough for forecast; skip if parser needs more.
    from eplus_gym.rl.spaces import N_OBS_V2

    obs = build_day_observation(
        month=1,
        dow=0,
        doy=26,
        oat_mean_c=-10.0,
        oat_min_c=-15.0,
        oat_max_c=-5.0,
        zone_temps_f=[65, 65, 65, 65, 65, 65],
    )
    dummy = build_day_observation(month=1, dow=0, doy=1, oat_mean_c=0, oat_min_c=0, oat_max_c=0)
    assert obs.shape == (N_OBS_V2,)
    assert abs(float(obs[2]) - 26 / 366.0) < 1e-6
    assert abs(float(dummy[2]) - 1 / 366.0) < 1e-6
    assert float(obs[12]) == pytest.approx(0.65)


def test_campaign_plots_fail_closed(tmp_path: Path):
    with pytest.raises(NoValidEvalError):
        plot_validation_return_vs_eplus_calls()
    with pytest.raises(NoValidEvalError):
        load_valid_eval(tmp_path / "missing.csv")


def test_ramp_gate_fails_fast_sim():
    idx = pd.date_range("2024-01-01", periods=8, freq="15min")
    real = pd.DataFrame({c: [70.0 + i * 0.02 for i in range(8)] for c in BAS_ZONE_COLS}, index=idx)
    sim = pd.DataFrame({c: [65.0 + i * 4.0 for i in range(8)] for c in BAS_ZONE_COLS}, index=idx)
    out = evaluate_ramp_gate(simulated=sim, real_bas=real)
    assert out["verdict"] == VERDICT_FAIL
    assert out["passed"] is False
