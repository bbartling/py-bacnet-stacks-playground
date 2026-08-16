"""Operator-pay experiment: equations, refuse full, exclude historical invalid runs."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from eplus_gym.objective import BAS_ZONE_COLS, incremental_demand
from eplus_gym.rl.experiment_ledger import A04_SHA256
from eplus_gym.rl.operator_pay_experiment import (
    OperatorPayExperimentError,
    assert_reward_name,
    assert_run_id,
    filter_operator_pay_rows,
    flatten_payload,
    refuse_full_campaign,
    run_operator_pay_experiment,
    summarize_rows,
    validate_scored_episode,
)
from eplus_gym.rl.reward import INFEASIBLE_TRAIN_REWARD, MONEY_ILLUSTRATIVE, operator_paycheck, score_day
from eplus_gym.site_pins import sha256_file


def _toy_df(*, peak=100.0, kwh_steps=96, school_ok=True):
    kw = [peak] + [10.0] * (kwh_steps - 1)
    rows = []
    t = 70.0 if school_ok else 60.0
    for i, p in enumerate(kw):
        row = {"local_step": i, "facility_kw": p}
        for c in BAS_ZONE_COLS:
            row[c] = t
        rows.append(row)
    return pd.DataFrame(rows)


def test_run_id_and_reward_reject_legacy_and_year2xsyn():
    with pytest.raises(OperatorPayExperimentError):
        assert_run_id("year2xsyn")
    with pytest.raises(OperatorPayExperimentError):
        assert_reward_name("legacy_reward_v1")
    with pytest.raises(OperatorPayExperimentError):
        assert_reward_name("operator_pay_v1")
    assert assert_reward_name("operator_pay_2x_v1") == "operator_pay_2x_v1"


def test_2x_paycheck_equation_and_readiness_minus_ten():
    two = operator_paycheck(
        baseline_cost=200.0, candidate_cost=150.0, readiness_ok=True, savings_multiplier=2
    )
    assert two["savings_usd"] == 50.0
    assert two["raw_pay_usd"] == 200.0
    assert two["money_mode"] == MONEY_ILLUSTRATIVE
    df = _toy_df(school_ok=False)
    br = score_day(
        df,
        reward_name="operator_pay_2x_v1",
        school_day=True,
        baseline_kwh=200.0,
        baseline_peak_kw=120.0,
    )
    assert br.extras["display_paycheck_usd"] == 0.0
    assert br.reward == INFEASIBLE_TRAIN_REWARD
    assert br.reward == -10.0
    assert br.extras["infeasible"] is True


def test_reject_missing_paired_baseline():
    df = _toy_df()
    with pytest.raises(ValueError, match="baseline"):
        score_day(df, reward_name="operator_pay_2x_v1", school_day=True)


def test_filter_drops_year2xsyn_legacy_and_jan26_pair():
    rows = [
        {"run_id": "year2xsyn", "reward_name": "operator_pay_2x_v1", "arm": "ppo"},
        {"run_id": "oppay", "reward_name": "legacy_reward_v1", "arm": "ppo"},
        {"run_id": "oppay", "reward_name": "operator_pay_2x_v1", "kind": "manual_control_perturbation"},
        {"run_id": "oppay2x_smoke_20260816", "reward_name": "operator_pay_2x_v1", "arm": "incumbent"},
    ]
    kept = filter_operator_pay_rows(rows)
    assert len(kept) == 1
    assert kept[0]["arm"] == "incumbent"


def test_validate_episode_96_192():
    with pytest.raises(OperatorPayExperimentError, match="96"):
        validate_scored_episode(
            {
                "failed": False,
                "n_rows": 192,
                "n_all_rows": 192,
                "extras": {"reward_name": "operator_pay_2x_v1", "money_mode": MONEY_ILLUSTRATIVE},
            }
        )
    validate_scored_episode(
        {
            "failed": False,
            "n_rows": 96,
            "n_all_rows": 192,
            "extras": {"reward_name": "operator_pay_2x_v1", "money_mode": MONEY_ILLUSTRATIVE},
        }
    )


def test_full_campaign_refuses_when_ramp_failed(tmp_path: Path):
    app = Path(__file__).resolve().parents[1]
    decision = refuse_full_campaign(app)
    assert decision["allowed"] is False
    assert "NO_GO" in str(decision["verdict"])
    site = Path(__file__).resolve().parents[1]
    # site_root only needs to exist as a dir; full refuses before A04
    out = run_operator_pay_experiment(
        app_root=app,
        site_root=tmp_path,
        run_id="must_fail_full",
        reward_name="operator_pay_2x_v1",
        mode="full",
        simulator="LIVE_ENERGYPLUS",
    )
    assert out["exit_code"] == 4
    assert out["ppo_dqn_learned"] is False


def test_summarize_does_not_treat_year2xsyn_as_valid():
    rows = filter_operator_pay_rows(
        [
            {
                "run_id": "year2xsyn",
                "arm": "ppo",
                "failed": False,
                "reward_name": "legacy_reward_v1",
                "display_paycheck_usd": 400,
            }
        ]
    )
    summary = summarize_rows(rows)
    assert summary["valid_operator_pay_episodes"] == 0


def test_smoke_mocked_worker_writes_package(tmp_path: Path):
    app = Path(__file__).resolve().parents[1]
    site = tmp_path / "site"
    models = site / "eplus" / "models"
    weather = site / "eplus" / "weather"
    models.mkdir(parents=True)
    weather.mkdir(parents=True)
    pin = app / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    if pin.is_file():
        data = pin.read_bytes()
        (models / "lakeside_w2a_a04_dual_champion.idf").write_bytes(data)
        assert sha256_file(models / "lakeside_w2a_a04_dual_champion.idf") == A04_SHA256
    else:
        pytest.skip("A04 idf not in repo")
    (weather / "amy.epw").write_text("EPW\n", encoding="utf-8")

    extras = {
        "reward_name": "operator_pay_2x_v1",
        "money_mode": MONEY_ILLUSTRATIVE,
        "display_paycheck_usd": 100.0,
        "training_reward": 1.0,
        "readiness_ok": True,
        "infeasible": False,
        "baseline_kwh": 4000.0,
        "baseline_peak_kw": 240.0,
        "claim": "screening_only",
    }

    def fake_worker(**kwargs):
        return {
            "failed": False,
            "day": kwargs["day"],
            "reward": 1.0,
            "daily_kwh": 4000.0,
            "peak_kw": 240.0,
            "n_rows": 96,
            "n_all_rows": 192,
            "extras": extras,
        }

    out = run_operator_pay_experiment(
        app_root=app,
        site_root=site,
        run_id="oppay2x_unit",
        reward_name="operator_pay_2x_v1",
        mode="smoke",
        simulator="LIVE_ENERGYPLUS",
        run_day=fake_worker,
        repo_figures_dir=tmp_path / "repo_out",
        plots_dir=tmp_path / "plots",
    )
    assert out["exit_code"] == 0
    assert out["summary"]["valid_operator_pay_episodes"] == 15
    assert out["summary"]["ppo_dqn_learned"] is False
    assert (Path(out["repo_out"]) / "summary.json").is_file()


def test_incremental_demand_same_floor_for_pair():
    floor = 180.0
    _, _, c_cost = incremental_demand(floor, 200.0, 15.0)
    _, _, b_cost = incremental_demand(floor, 190.0, 15.0)
    pay = operator_paycheck(
        baseline_cost=100 + b_cost, candidate_cost=100 + c_cost, readiness_ok=True, savings_multiplier=2
    )
    assert pay["savings_usd"] == (b_cost - c_cost)
