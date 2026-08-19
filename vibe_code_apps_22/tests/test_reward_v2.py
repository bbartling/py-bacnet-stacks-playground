"""Reward contract v2: utility / paycheck / train layers. Does not reinterpret v1."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eplus_gym.control_v2 import ACTION_KEYS, SixZoneDailyParamsV2, build_six_schedules_f
from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.reward_v2 import (
    COST_SCALE,
    ENERGY_RATE,
    IntegrityFailure,
    MissingBaselineError,
    PAYCHECK_CAP,
    TRAIN_CLIP,
    TRAIN_FAIL_BASE,
    action_movement,
    display_paycheck,
    load_reward_contract_v2,
    occupied_zone_degree_hours,
    readiness_all_six,
    score_day_v2,
    train_reward,
    utility_accounting,
)

APP = Path(__file__).resolve().parents[1]
SCHOOL = "2026-01-12"  # Monday
WEEKEND = "2026-01-17"


def _flat(v: float, n: int = 96) -> list[float]:
    return [float(v)] * n


def _zones(v: float) -> dict[str, list[float]]:
    return {k: _flat(v) for k in ACTION_KEYS}


def _zones_one_cold(cold_key: str = "1F_A", cold: float = 66.0, warm: float = 70.0) -> dict[str, list[float]]:
    out = _zones(warm)
    out[cold_key] = _flat(cold)
    return out


def test_contract_frozen_defaults():
    body = load_reward_contract_v2()
    d = body["frozen_defaults"]
    assert d["energy_rate_per_kwh"] == 0.12
    assert d["demand_rate_per_kw"] == 15.0
    assert d["cost_scale"] == 100.0
    assert d["lambda_occ"] == 0.05
    assert d["lambda_move"] == 0.02
    assert d["readiness_band_f"] == [68.0, 74.0]
    assert d["readiness_check_steps"] == [30, 31]
    assert d["never_mean_of_six"] is True
    assert (APP / "contracts" / "reward_contract_v2.json").is_file()


def test_kwh_vs_demand_tradeoff():
    high_kwh = _flat(200.0)
    low_kwh_high_peak = [100.0] * 95 + [260.0]
    cheap_energy = utility_accounting(high_kwh, mtd_peak_kw=260.0)
    peaky = utility_accounting(low_kwh_high_peak, mtd_peak_kw=200.0)
    assert cheap_energy["energy_cost"] > peaky["energy_cost"]
    assert peaky["demand_increment"] > cheap_energy["demand_increment"]
    assert cheap_energy["demand_increment"] == pytest.approx(0.0)
    assert peaky["demand_increment"] == pytest.approx(15.0 * 60.0)


def test_floors_ratchet_contract_and_month_reset():
    bill = BillingState(floor_kw=180.0, ratchet_kw=220.0, contract_kw=150.0)
    assert bill.start_of_day("2026-01-12") == pytest.approx(220.0)
    assert bill.mtd_peak_kw == pytest.approx(180.0)
    assert bill.billing_floor_kw() != bill.mtd_peak_kw
    acct = utility_accounting(_flat(200.0), mtd_peak_kw=180.0, ratchet_kw=220.0, contract_kw=150.0)
    assert acct["old_floor_kw"] == pytest.approx(220.0)
    assert acct["demand_increment"] == pytest.approx(0.0)
    acct2 = utility_accounting(_flat(250.0), mtd_peak_kw=180.0, ratchet_kw=220.0, contract_kw=150.0)
    assert acct2["new_floor_kw"] == pytest.approx(250.0)
    assert acct2["demand_increment"] == pytest.approx(15.0 * 30.0)
    bill.observe_peak(250.0)
    floor_feb = bill.start_of_day("2026-02-01")
    assert bill.mtd_peak_kw == pytest.approx(0.0)
    assert floor_feb == pytest.approx(220.0)


def test_all_six_pass_and_one_zone_fail():
    ok = readiness_all_six(_zones(70.0), day=SCHOOL)
    assert ok["readiness_ok"] is True
    assert ok["never_mean_of_six"] is True
    meanish = _zones(72.0)
    meanish["1F_A"] = _flat(66.0)
    # Mean of six would be > 68, but all-six must fail.
    fail = readiness_all_six(meanish, day=SCHOOL)
    assert fail["readiness_ok"] is False
    assert any("1F_A" in x for x in fail["failed_zones"])


def test_upper_and_lower_band():
    low = readiness_all_six(_zones(67.9), day=SCHOOL)
    high = readiness_all_six(_zones(74.1), day=SCHOOL)
    mid = readiness_all_six(_zones(68.0), day=SCHOOL)
    top = readiness_all_six(_zones(74.0), day=SCHOOL)
    assert low["readiness_ok"] is False
    assert high["readiness_ok"] is False
    assert mid["readiness_ok"] is True
    assert top["readiness_ok"] is True
    weekend = readiness_all_six(_zones(50.0), day=WEEKEND)
    assert weekend["school_day"] is False
    assert weekend["readiness_ok"] is True


def test_occupied_degree_hours_and_movement():
    cold = _zones(60.0)
    dh = occupied_zone_degree_hours(cold, day=SCHOOL)
    assert dh > 0
    weekend_dh = occupied_zone_degree_hours(cold, day=WEEKEND)
    assert weekend_dh == pytest.approx(0.0)
    params = SixZoneDailyParamsV2(
        occupied_heating_f=70.0,
        unoccupied_heating_f=58.0,
        heating_setpoint_start_step=28,
        heating_setpoint_end_step=68,
        recovery_lead_minutes=0,
    )
    move = action_movement(build_six_schedules_f(params))
    assert move > 0
    cc = action_movement(build_six_schedules_f(SixZoneDailyParamsV2(70.0, 70.0, continuous_conditioning=True)))
    assert cc == pytest.approx(0.0)


def test_paycheck_clip_and_train_not_paycheck_capped():
    pay = display_paycheck(savings=1000.0, readiness_ok=True, k=2.0)
    assert pay["display_paycheck_usd"] == PAYCHECK_CAP
    pay0 = display_paycheck(savings=1000.0, readiness_ok=False, k=2.0)
    assert pay0["display_paycheck_usd"] == 0.0
    with pytest.raises(ValueError):
        display_paycheck(savings=1.0, readiness_ok=True, k=2.5)
    tr = train_reward(savings=1000.0, readiness_ok=True)
    assert tr == pytest.approx(TRAIN_CLIP[1])
    assert tr != PAYCHECK_CAP


def test_readiness_fail_strictly_worse_than_any_feasible():
    fail = train_reward(savings=1e6, readiness_ok=False, degree_violation=0.0)
    fail_v = train_reward(savings=1e6, readiness_ok=False, degree_violation=12.0)
    best = train_reward(savings=1e6, readiness_ok=True, occupied_dh=0.0, movement=0.0)
    worst_feas = train_reward(savings=-1e6, readiness_ok=True, occupied_dh=1e6, movement=1e6)
    assert fail == pytest.approx(TRAIN_FAIL_BASE)
    assert fail_v < fail
    assert fail < worst_feas
    assert worst_feas == pytest.approx(TRAIN_CLIP[0])
    assert best == pytest.approx(TRAIN_CLIP[1])
    assert fail_v < TRAIN_CLIP[0]


def test_missing_baseline_and_invalid_eplus():
    with pytest.raises(MissingBaselineError):
        score_day_v2(
            day=SCHOOL,
            candidate_facility_kw=_flat(100.0),
            candidate_zone_temps_f=_zones(70.0),
            baseline_facility_kw=None,
            baseline_zone_temps_f=None,
        )
    with pytest.raises(IntegrityFailure, match="energyplus_crash"):
        score_day_v2(
            day=SCHOOL,
            candidate_facility_kw=_flat(100.0),
            candidate_zone_temps_f=_zones(70.0),
            baseline_facility_kw=_flat(100.0),
            baseline_zone_temps_f=_zones(70.0),
            failed=True,
        )
    with pytest.raises(IntegrityFailure, match="timestep"):
        score_day_v2(
            day=SCHOOL,
            candidate_facility_kw=_flat(100.0, n=90),
            candidate_zone_temps_f=_zones(70.0),
            baseline_facility_kw=_flat(100.0),
            baseline_zone_temps_f=_zones(70.0),
        )
    missing = {k: _flat(70.0) for k in ACTION_KEYS if k != "2F_B"}
    with pytest.raises(IntegrityFailure, match="missing zones"):
        score_day_v2(
            day=SCHOOL,
            candidate_facility_kw=_flat(100.0),
            candidate_zone_temps_f=missing,
            baseline_facility_kw=_flat(100.0),
            baseline_zone_temps_f=_zones(70.0),
        )
    nan_kw = _flat(100.0)
    nan_kw[3] = float("nan")
    with pytest.raises(IntegrityFailure, match="NaN"):
        score_day_v2(
            day=SCHOOL,
            candidate_facility_kw=nan_kw,
            candidate_zone_temps_f=_zones(70.0),
            baseline_facility_kw=_flat(100.0),
            baseline_zone_temps_f=_zones(70.0),
        )


def test_score_day_savings_and_layers():
    cand = _flat(80.0)
    base = _flat(120.0)
    scored = score_day_v2(
        day=SCHOOL,
        candidate_facility_kw=cand,
        candidate_zone_temps_f=_zones(70.0),
        baseline_facility_kw=base,
        baseline_zone_temps_f=_zones(70.0),
        paycheck_k=2.0,
    )
    assert scored.savings > 0
    assert scored.display_paycheck_usd > 100.0
    assert scored.training_reward != scored.display_paycheck_usd
    assert abs(scored.training_reward) <= COST_SCALE
    assert json.dumps(load_reward_contract_v2()["does_not_reinterpret"])


def test_tou_vs_flat_energy_cost_differs():
    kw = _flat(100.0)
    flat = score_day_v2(
        day=SCHOOL,
        candidate_facility_kw=kw,
        candidate_zone_temps_f=_zones(70.0),
        baseline_facility_kw=kw,
        baseline_zone_temps_f=_zones(70.0),
        rate_kwh=0.12,
    )
    tou_rates = [0.08 if i < 48 else 0.20 for i in range(96)]
    tou = score_day_v2(
        day=SCHOOL,
        candidate_facility_kw=kw,
        candidate_zone_temps_f=_zones(70.0),
        baseline_facility_kw=kw,
        baseline_zone_temps_f=_zones(70.0),
        rate_kwh=tou_rates,
    )
    assert flat.candidate["energy_cost"] != tou.candidate["energy_cost"]


def test_shift_load_to_cheap_hours_improves_reward():
    rates = [0.05 if i < 48 else 0.30 for i in range(96)]
    expensive = [90.0 if i >= 48 else 60.0 for i in range(96)]
    cheap = [60.0 if i >= 48 else 90.0 for i in range(96)]
    base = _flat(75.0)
    exp_scored = score_day_v2(
        day=SCHOOL,
        candidate_facility_kw=expensive,
        candidate_zone_temps_f=_zones(70.0),
        baseline_facility_kw=base,
        baseline_zone_temps_f=_zones(70.0),
        rate_kwh=rates,
    )
    cheap_scored = score_day_v2(
        day=SCHOOL,
        candidate_facility_kw=cheap,
        candidate_zone_temps_f=_zones(70.0),
        baseline_facility_kw=base,
        baseline_zone_temps_f=_zones(70.0),
        rate_kwh=rates,
    )
    assert cheap_scored.training_reward > exp_scored.training_reward
