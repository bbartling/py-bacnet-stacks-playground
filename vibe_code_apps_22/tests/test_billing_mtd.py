"""MTD demand increment: independent candidate/baseline floors and month reset."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eplus_gym.control_v2 import ACTION_KEYS, build_six_schedules_f, continuous_params
from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.gallery_mtd import rescore_utility_table_mtd
from eplus_gym.rl.multiday_env import FakeContinuityPlant, MultiDayDailyEnv
from eplus_gym.rl.reward_v2 import utility_accounting
from eplus_gym.rl.spaces_v2 import encode_continuous_v2


def test_day_below_mtd_has_zero_demand_increment():
    acct = utility_accounting([100.0] * 96, mtd_peak_kw=160.0, demand_rate=15.0)
    assert acct["day_peak_kw"] == pytest.approx(100.0)
    assert acct["demand_increment"] == pytest.approx(0.0)


def test_new_peak_charges_only_the_increase():
    acct = utility_accounting([180.0] * 96, mtd_peak_kw=160.0, demand_rate=15.0)
    assert acct["demand_increment"] == pytest.approx(15.0 * 20.0)


def test_month_boundary_resets_mtd_not_ratchet():
    bill = BillingState(floor_kw=160.0, ratchet_kw=50.0)
    bill.start_of_day("2026-01-14")
    bill.observe_peak(160.0)
    floor = bill.start_of_day("2026-02-01")
    assert bill.mtd_peak_kw == pytest.approx(0.0)
    assert floor == pytest.approx(50.0)


def _oat(*days: str) -> dict[str, list[float]]:
    return {d: [-18.0] * 24 for d in days}


def test_candidate_and_baseline_mtd_remain_independent():
    days = ["2026-01-12", "2026-01-13"]
    oat = _oat(*days)
    plant = FakeContinuityPlant()
    plant.start_episode()
    base_sched = build_six_schedules_f(continuous_params(70.0))
    payloads = {}
    for day in days:
        rec = plant.simulate_day(base_sched, oat_c=oat[day])
        rec["TEST_DOUBLE"] = True
        payloads[day] = rec
    env = MultiDayDailyEnv(
        {
            "n_days": 2,
            "start_day": "2026-01-12",
            "plant": FakeContinuityPlant(),
            "hourly_oat": oat,
            "baseline_payloads": payloads,
        }
    )
    env.reset()
    action = encode_continuous_v2(continuous_params(68.0))
    _o, _r, _d, _t, info1 = env.step(action)
    cand_mtd = float(info1["mtd_peak_kw"])
    base_close = float(info1["baseline_new_floor_kw"])
    _o, _r, _d, _t, info2 = env.step(action)
    assert info2["candidate_old_floor_kw"] == pytest.approx(cand_mtd)
    assert info2["baseline_old_floor_kw"] == pytest.approx(base_close)
    assert ACTION_KEYS


def test_committed_gallery_mtd_rescore_is_illustrative():
    path = (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "audits"
        / "figures"
        / "vibe22_repair"
        / "a04_multiday_continuity"
        / "manifest.json"
    )
    body = json.loads(path.read_text(encoding="utf-8"))
    scored = rescore_utility_table_mtd(body["utility_table"])
    cont = scored["totals"]["continuous_70"]
    inc = scored["totals"]["observed_bas_incumbent"]
    deep = scored["totals"]["deep_setback"]
    assert scored["illustrative_not_billed"] is True
    assert cont["final_peak_kw"] == pytest.approx(160.62, abs=0.02)
    assert cont["three_day_total_usd"] == pytest.approx(3480.08, abs=0.5)
    assert inc["final_peak_kw"] == pytest.approx(165.57, abs=0.02)
    assert inc["three_day_total_usd"] == pytest.approx(3426.71, abs=0.5)
    assert inc["savings_vs_continuous_usd"] == pytest.approx(53.37, abs=0.5)
    assert deep["final_peak_kw"] == pytest.approx(185.49, abs=0.02)
    assert deep["three_day_total_usd"] == pytest.approx(3666.56, abs=0.5)
    assert deep["savings_vs_continuous_usd"] == pytest.approx(-186.48, abs=0.5)
    day2 = scored["days"][1]["arms"]["continuous_70"]
    assert day2["demand_increment"] == pytest.approx(0.0)
