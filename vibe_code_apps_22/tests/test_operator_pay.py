"""operator_pay_v1 and eval-split tests (no EnergyPlus)."""
from __future__ import annotations

import pandas as pd

from eplus_gym.objective import BAS_ZONE_COLS, incremental_demand
from eplus_gym.rl.day_pool import calendar_fold_key, illustrative_school_day
from eplus_gym.rl.reward import (
    MONEY_ILLUSTRATIVE,
    compute_daily_reward,
    operator_pay_v1,
    score_day,
)


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


def test_legacy_charges_full_peak_every_day():
    df = _toy_df(peak=200.0)
    br = compute_daily_reward(df)
    assert br.peak_cost == 200.0 * 15.0


def test_operator_pay_uses_billing_floor():
    df = _toy_df(peak=200.0)
    br = operator_pay_v1(df, mtd_peak_kw=180.0, school_day=True)
    _, inc_kw, inc_cost = incremental_demand(180.0, 200.0, 15.0)
    assert inc_kw == 20.0
    assert br.peak_cost == inc_cost
    assert br.extras["money_mode"] == MONEY_ILLUSTRATIVE
    assert br.extras["readiness_ok"] is True


def test_operator_pay_zeros_on_readiness_fail():
    df = _toy_df(school_ok=False)
    br = operator_pay_v1(df, school_day=True)
    assert br.extras["readiness_ok"] is False
    assert br.reward <= 0.0
    assert br.extras["reward_name"] == "operator_pay_v1"


def test_weekend_skips_school_gates():
    assert illustrative_school_day("2026-01-24") is False
    assert illustrative_school_day("2026-01-26") is True
    df = _toy_df(school_ok=False)
    br = operator_pay_v1(df, school_day=False)
    assert br.pre8_violations == 0


def test_syn_clone_shares_fold():
    assert calendar_fold_key("2026-01-20__syn") == "2026-01-20"


def test_score_day_dispatch():
    df = _toy_df()
    a = score_day(df, reward_name="legacy_reward_v1")
    b = score_day(df, reward_name="operator_pay_v1", school_day=True, mtd_peak_kw=50.0)
    assert a.peak_cost > b.peak_cost


def test_paycheck_2x_3x_and_readiness_zero():
    from eplus_gym.rl.reward import operator_paycheck

    two = operator_paycheck(
        baseline_cost=200.0, candidate_cost=150.0, readiness_ok=True, savings_multiplier=2
    )
    three = operator_paycheck(
        baseline_cost=200.0, candidate_cost=150.0, readiness_ok=True, savings_multiplier=3
    )
    assert two["raw_pay_usd"] == 200.0
    assert three["raw_pay_usd"] == 250.0
    z = operator_paycheck(
        baseline_cost=200.0, candidate_cost=50.0, readiness_ok=False, savings_multiplier=2
    )
    assert z["raw_pay_usd"] == 0.0
    neg = operator_paycheck(
        baseline_cost=100.0, candidate_cost=180.0, readiness_ok=True, savings_multiplier=2
    )
    assert neg["raw_pay_usd"] == 0.0


def test_occupied_setpoint_alias():
    from eplus_gym.six_zone_daily_controller import SixZoneDailyParams

    p = SixZoneDailyParams(occupancy_start_step=30)
    assert p.occupied_setpoint_start_step == 30
    d = p.to_dict()
    assert d["occupied_setpoint_start_step"] == 30

