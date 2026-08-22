"""Unit tests for two-month frozen-policy replay (no LIVE EnergyPlus)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eplus_gym.eplus_err import parse_eplus_err
from eplus_gym.mega.obs_tariff_v4 import N_OBS_V4
from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.research_eval import PolicyReloadError
from eplus_gym.rl.two_month_calendar import (
    EXPECTED_INTERVALS_PER_STRATEGY,
    EXPECTED_SCORED_DAYS,
    scored_days,
    validate_day_list,
)
from eplus_gym.rl.two_month_cost import (
    build_flat_cost_table,
    build_tou_cost_table,
    rank_strategies,
    score_flat_plus_demand,
    verify_rescore_identity,
)
from eplus_gym.rl.two_month_metrics import build_decision_table, compare_vs_continuous_68
from eplus_gym.rl.two_month_obs import assert_obs_nonzero, build_policy_observation_v4
from eplus_gym.rl.two_month_provenance import NOT_AVAILABLE, load_actual_utility_evidence


def test_calendar_62_days_5952_intervals():
    days = scored_days()
    assert len(days) == EXPECTED_SCORED_DAYS == 62
    assert days[0] == "2025-12-01"
    assert days[-1] == "2026-01-31"
    assert len(days) * 96 == EXPECTED_INTERVALS_PER_STRATEGY == 5952
    validate_day_list(days)
    with pytest.raises(ValueError):
        validate_day_list(days[:-1])


def test_billing_dec_carries_jan_resets_mtd_not_ratchet():
    b = BillingState(floor_kw=0.0, ratchet_kw=50.0, contract_kw=0.0)
    b.start_of_day("2025-12-01")
    b.observe_peak(200.0)
    b.observe_peak(180.0)
    assert b.mtd_peak_kw == 200.0
    b.start_of_day("2025-12-15")
    b.observe_peak(210.0)
    assert b.mtd_peak_kw == 210.0
    floor_before_jan = b.billing_floor_kw()
    assert floor_before_jan == max(210.0, 50.0)
    b.start_of_day("2026-01-01")
    assert b.mtd_peak_kw == 0.0
    assert b.billing_floor_kw() == 50.0
    b.observe_peak(120.0)
    assert b.mtd_peak_kw == 120.0
    assert b.billing_floor_kw() == max(120.0, 50.0)


def test_obs_v4_dim_206_nonzero():
    obs, ctx = build_policy_observation_v4(
        day="2025-12-01",
        hourly_oat_c=[5.0] * 24,
        zone_temps_f=[70.0] * 6,
        billing_floor_kw=100.0,
        mtd_peak_kw=100.0,
        ratchet_floor_kw=0.0,
        contract_floor_kw=0.0,
        previous_action=[0.0] * 11,
        continuous_conditioning_state=0.0,
        tariff_mode="flat_illustrative",
    )
    assert obs.shape == (N_OBS_V4,) == (206,)
    assert float(np.linalg.norm(obs)) > 0
    assert ctx["forecast_source"] == "PERFECT_EPISODE_FORECAST_RETROSPECTIVE"


def test_obs_rejects_zero_vector():
    with pytest.raises(PolicyReloadError):
        assert_obs_nonzero(np.zeros(206), context="test")


def test_cost_energy_plus_demand_equals_total():
    fac = [100.0] * 96
    rows = score_flat_plus_demand(fac)
    for r in rows:
        assert r["total_usd"] == pytest.approx(r["energy_charge_usd"] + r["demand_charge_usd"])


def test_flat_vs_tou_separate_rankings():
    results = {
        "a": {"facility_kw": [80.0] * 96 * 62, "trajectory_hash": "x"},
        "b": {"facility_kw": [120.0] * 96 * 62, "trajectory_hash": "y"},
    }
    flat = build_flat_cost_table(results)
    tou = build_tou_cost_table(results)
    flat_rank = rank_strategies(flat, period="two_month")
    tou_rank = rank_strategies(tou, period="two_month")
    assert flat_rank[0]["strategy"] == "a"
    assert tou_rank[0]["strategy"] == "a"


def test_trajectory_hash_rescore_identical():
    fac = [90.0 + (i % 10) for i in range(96 * 62)]
    p = {"facility_kw": fac, "n_intervals": len(fac)}
    assert verify_rescore_identity(p, dict(p))


def test_actual_utility_component_charges_na(tmp_path: Path):
    util_dir = tmp_path / "utilities"
    util_dir.mkdir()
    csv = util_dir / "utility_bills_raw.csv"
    csv.write_text(
        "account,billing_period,kwh,billed_demand_kw,meter_cost_usd\n"
        "CS 351075,202512,67328,232.38,6683.62\n"
        "CS 351075,202601,81491,284.82,8269.37\n",
        encoding="utf-8",
    )
    ev = load_actual_utility_evidence(tmp_path)
    assert ev["dec_2025"]["actual_energy_charge_usd"] == NOT_AVAILABLE
    assert ev["dec_2025"]["actual_demand_charge_usd"] == NOT_AVAILABLE


def test_decision_table_physical_only():
    results = {
        "good": {
            "facility_kw": [50.0] * 96 * 62,
            "daily": [{"day": d, "daily_kwh": 1200, "peak_kw": 50} for d in scored_days()],
        },
        "bad": {
            "facility_kw": [40.0] * 96 * 62,
            "daily": [{"day": d, "daily_kwh": 960, "peak_kw": 40} for d in scored_days()],
        },
    }
    table = build_decision_table(results)
    assert all("total_usd" not in row for row in table)
    cmp = compare_vs_continuous_68(
        {
            "continuous_68_heat_sensitivity": results["good"],
            "frozen_ppo_flat_seed0": results["bad"],
        }
    )
    assert cmp["comparisons"][0]["days_both"] == 62


def test_err_parser_on_fixture(tmp_path: Path):
    err = tmp_path / "eplusout.err"
    err.write_text(
        "   ************* EnergyPlus Completed Successfully-- 10000 Warning; 0 Severe; 0 Fatal\n",
        encoding="utf-8",
    )
    q = parse_eplus_err(err)
    assert q.get("completed_successfully") is True
    assert int(q.get("severe_count") or 0) == 0


def test_policy_validation_rejects_zero_obs_pattern():
    with pytest.raises(PolicyReloadError, match="zero"):
        assert_obs_nonzero(np.zeros(N_OBS_V4), context="zero_obs_shortcut")
