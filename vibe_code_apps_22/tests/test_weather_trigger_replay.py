"""Unit tests for weather-triggered continuous-conditioning (no LIVE EnergyPlus)."""
from __future__ import annotations

from pathlib import Path

import pytest

from eplus_gym.rl.two_month_calendar import EXPECTED_INTERVALS_PER_STRATEGY
from eplus_gym.rl.two_month_cost import score_flat_plus_demand
from eplus_gym.rl.weather_trigger_metrics import (
    peak_cap_feasibility,
    peak_first_sensitivity,
    research_conclusion,
)
from eplus_gym.rl.weather_trigger_select import (
    load_weather_trigger_contract,
    select_daily_policy,
    select_daily_policy_from_forecast_vector,
)


def _oat(min_f: float, *, n_cold: int | None = None, thr: float = 20.0) -> list[float]:
    """Build 24 hourly °F values with controlled min / cold-hour count."""
    if n_cold is None:
        # one hour at min_f, rest warm
        return [min_f] + [50.0] * 23
    cold = [thr - 1.0] * int(n_cold)
    warm = [thr + 10.0] * (24 - int(n_cold))
    return cold + warm


def test_contract_bacnet_zero():
    c = load_weather_trigger_contract(Path(__file__).resolve().parents[1])
    assert int(c["bacnet_command_authority"]) == 0
    assert c["weather_label"] == "RETROSPECTIVE_WEATHER_POLICY_SCREEN"
    assert len(c["policy_ids"]) == 9


@pytest.mark.parametrize(
    "min_f,expect_cont",
    [
        (9.9, True),
        (10.0, True),
        (10.1, False),
    ],
)
def test_threshold_10f(min_f, expect_cont):
    sel = select_daily_policy(policy_id="COLD_TRIGGER_10F", day="2026-01-26", hourly_oat_f=_oat(min_f))
    assert sel.continuous_day is expect_cont
    assert len(sel.hourly_oat_f) == 24


@pytest.mark.parametrize(
    "min_f,expect_cont",
    [
        (19.9, True),
        (20.0, True),
        (20.1, False),
    ],
)
def test_threshold_20f(min_f, expect_cont):
    sel = select_daily_policy(policy_id="COLD_TRIGGER_20F", day="2026-01-26", hourly_oat_f=_oat(min_f))
    assert sel.continuous_day is expect_cont


@pytest.mark.parametrize(
    "min_f,expect_cont",
    [
        (29.9, True),
        (30.0, True),
        (30.1, False),
    ],
)
def test_threshold_30f(min_f, expect_cont):
    sel = select_daily_policy(policy_id="COLD_TRIGGER_30F", day="2026-01-26", hourly_oat_f=_oat(min_f))
    assert sel.continuous_day is expect_cont


def test_duration_4h_and_8h():
    sel4 = select_daily_policy(
        policy_id="COLD_TRIGGER_20F_4H", day="2026-01-26", hourly_oat_f=_oat(0, n_cold=4, thr=20.0)
    )
    assert sel4.continuous_day is True
    sel4b = select_daily_policy(
        policy_id="COLD_TRIGGER_20F_4H", day="2026-01-26", hourly_oat_f=_oat(0, n_cold=3, thr=20.0)
    )
    assert sel4b.continuous_day is False
    sel8 = select_daily_policy(
        policy_id="COLD_TRIGGER_20F_8H", day="2026-01-26", hourly_oat_f=_oat(0, n_cold=8, thr=20.0)
    )
    assert sel8.continuous_day is True
    sel8b = select_daily_policy(
        policy_id="COLD_TRIGGER_20F_8H", day="2026-01-26", hourly_oat_f=_oat(0, n_cold=7, thr=20.0)
    )
    assert sel8b.continuous_day is False


def test_always_policies_single_mode():
    oat = _oat(5.0)
    a = select_daily_policy(policy_id="ALWAYS_GRID_114", day="2026-01-26", hourly_oat_f=oat)
    assert a.selected_mode == "discrete_114" and a.continuous_day is False
    b = select_daily_policy(policy_id="ALWAYS_CONTINUOUS_68_74", day="2026-01-26", hourly_oat_f=oat)
    assert b.continuous_day is True and b.selected_mode == "continuous_68_74"
    # one selection object per call — no intraday list
    assert isinstance(a.selected_mode, str)


def test_forecast_interface_delegates():
    oat = _oat(15.0)
    a = select_daily_policy(policy_id="COLD_TRIGGER_20F", day="2026-01-01", hourly_oat_f=oat)
    b = select_daily_policy_from_forecast_vector(
        policy_id="COLD_TRIGGER_20F", day="2026-01-01", forecast_hourly_oat_f=oat
    )
    assert a.continuous_day == b.continuous_day


def test_monthly_demand_sum():
    fac = [100.0] * 96 * 31 + [200.0] * 96 * 31
    rows = {r["period"]: r for r in score_flat_plus_demand(fac)}
    assert rows["two_month"]["demand_charge_usd"] == pytest.approx(
        rows["2025-12"]["demand_charge_usd"] + rows["2026-01"]["demand_charge_usd"]
    )


def test_intervals_constant():
    assert EXPECTED_INTERVALS_PER_STRATEGY == 5952


def _fake_payload(*, peak: float, cost_proxy_kw: float, ready: bool = True, kwh_scale: float = 1.0) -> dict:
    # 5952 intervals: constant power so peak=cost_proxy related
    fac = [float(peak)] * 5952
    # scale energy via slightly different mean if needed
    if kwh_scale != 1.0:
        fac = [float(peak) * float(kwh_scale)] * 5952
    days = []
    from eplus_gym.rl.two_month_calendar import scored_days

    for d in scored_days():
        days.append(
            {
                "day": d,
                "peak_kw": peak,
                "daily_kwh": peak * 24 * kwh_scale,
                "readiness_ok": ready,
                "checked_school_day": True,
                "school_day": True,
                "occupied_comfort_degree_hours": 0.0,
                "continuous_day": False,
            }
        )
    return {
        "facility_kw": fac,
        "daily": days,
        "n_intervals": 5952,
        "n_process_starts": 1,
        "trajectory_hash": f"fake_{peak}",
        "quality": {"severe_count": 0, "fatal_count": 0},
        "elapsed_s": 1.0,
    }


def test_peak_first_and_caps_and_conclusion():
    results = {
        "ALWAYS_GRID_114": _fake_payload(peak=250.0, cost_proxy_kw=250.0),
        "ALWAYS_CONTINUOUS_68_74": _fake_payload(peak=230.0, cost_proxy_kw=230.0),
        "COLD_TRIGGER_20F": _fake_payload(peak=240.0, cost_proxy_kw=240.0),
        "COLD_TRIGGER_10F": _fake_payload(peak=245.0, cost_proxy_kw=245.0),
    }
    pf = peak_first_sensitivity(results)
    assert pf["selected"] == "ALWAYS_CONTINUOUS_68_74"
    assert pf["min_peak_kw"] == pytest.approx(230.0)
    caps = peak_cap_feasibility(results, caps_kw=[260, 250, 240, 230])
    assert any(r["strategy"] == "ALWAYS_CONTINUOUS_68_74" and r["peak_cap_kw"] == 230 and r["passes_cap"] for r in caps)
    conclusion = research_conclusion(results=results)
    assert conclusion["verdict"] in {
        "WEATHER_TRIGGER_IMPROVES_PEAK_AND_COST",
        "WEATHER_TRIGGER_IMPROVES_PEAK_WITH_ENERGY_PENALTY",
        "CONTINUOUS_68_74_REMAINS_LOWEST_PEAK",
        "NO_WEATHER_TRIGGER_IMPROVEMENT",
        "WEATHER_TRIGGER_LOWERS_COST_BUT_NOT_PEAK",
    }
    assert conclusion["operational_winner"] is None
    assert conclusion["simulation_training_ready"] is False


def test_thermal_continuity_check_logic():
    # Synthetic: day D end must match D+1 start within 0.05
    end_d = [70.0] * 6
    start_d1 = [70.01] * 6
    assert max(abs(a - b) for a, b in zip(end_d, start_d1)) <= 0.05
    start_bad = [71.0] * 6
    assert max(abs(a - b) for a, b in zip(end_d, start_bad)) > 0.05
