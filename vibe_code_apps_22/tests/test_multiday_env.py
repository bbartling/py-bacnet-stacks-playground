"""Multi-day env: one process, billing carryover, no fabricated fallback."""
from __future__ import annotations

import numpy as np
import pytest

from eplus_gym.control_v2 import build_six_schedules_f, continuous_params
from eplus_gym.rl.multiday_env import (
    FakeContinuityPlant,
    MultiDayDailyEnv,
    assert_live_campaign_plant,
    incremental_monthly_demand_cost,
)
from eplus_gym.rl.obs_v3 import N_OBS_V3
from eplus_gym.rl.reward_v2 import IntegrityFailure, MissingBaselineError
from eplus_gym.rl.spaces_v2 import encode_continuous_v2
from eplus_gym.eplus_err import parse_eplus_err


def _oat_map(*days: str, val: float = -18.0) -> dict[str, list[float]]:
    return {d: [val] * 24 for d in days}


def _baseline_payloads(days: list[str], oat: dict[str, list[float]]) -> dict[str, dict]:
    plant = FakeContinuityPlant()
    plant.start_episode()
    sched = build_six_schedules_f(continuous_params(70.0))
    out = {}
    for day in days:
        out[day] = plant.simulate_day(sched, oat_c=oat[day])
    return out


def test_incremental_demand_uses_billing_floor():
    c = incremental_monthly_demand_cost(
        demand_rate=15.0,
        billing_floor_kw=200.0,
        candidate_day_peak_kw=180.0,
        baseline_day_peak_kw=190.0,
    )
    assert c == pytest.approx(0.0)
    c2 = incremental_monthly_demand_cost(
        demand_rate=15.0,
        billing_floor_kw=200.0,
        candidate_day_peak_kw=220.0,
        baseline_day_peak_kw=190.0,
    )
    assert c2 == pytest.approx(15.0 * 20.0)


def test_multiday_does_not_restart_plant_at_midnight():
    days = ["2026-01-12", "2026-01-13", "2026-01-14"]
    oat = _oat_map(*days, val=-18.0)
    oat["2026-01-13"] = [-20.0] * 24
    oat["2026-01-14"] = [-12.0] * 24
    plant = FakeContinuityPlant()
    env = MultiDayDailyEnv(
        {
            "n_days": 3,
            "start_day": "2026-01-12",
            "plant": plant,
            "hourly_oat": oat,
            "baseline_payloads": _baseline_payloads(days, oat),
        }
    )
    obs, info = env.reset()
    assert info["n_process_starts"] == 1
    assert obs.shape[0] == N_OBS_V3
    action = encode_continuous_v2(continuous_params(68.0))
    _, _, term, _, info1 = env.step(action)
    assert term is False
    assert info1["n_process_starts"] == 1
    assert info1["n_days_simulated"] == 1
    assert info1["continuous_conditioning"] is True
    assert "candidate_old_floor_kw" in info1
    assert "baseline_new_floor_kw" in info1
    _, _, term, _, info2 = env.step(action)
    assert info2["n_process_starts"] == 1
    assert info2["n_days_simulated"] == 2
    assert info2["billing_floor_kw"] >= info1["peak_kw"]
    _, _, term, _, info3 = env.step(action)
    assert term is True
    assert info3["n_process_starts"] == 1
    assert plant.n_process_starts == 1


def test_cold_snap_carryover_changes_next_morning_peak():
    days = ["2026-01-12", "2026-01-13"]
    oat = _oat_map(*days, val=-18.0)

    def _run(cc: bool):
        plant = FakeContinuityPlant()
        env = MultiDayDailyEnv(
            {
                "n_days": 2,
                "start_day": "2026-01-12",
                "plant": plant,
                "hourly_oat": oat,
                "baseline_payloads": _baseline_payloads(days, oat),
            }
        )
        env.reset()
        from eplus_gym.control_v2 import deep_setback_params

        a = encode_continuous_v2(continuous_params(70.0) if cc else deep_setback_params())
        env.step(a)
        _obs, _r, _d, _tr, info = env.step(a)
        return info["peak_kw"], plant.n_process_starts

    peak_cc, starts_cc = _run(True)
    peak_sb, starts_sb = _run(False)
    assert starts_cc == starts_sb == 1
    assert peak_cc != peak_sb


def test_paired_envs_share_initial_state():
    days = ["2026-01-12", "2026-01-13", "2026-01-14"]
    oat = _oat_map(*days, val=-10.0)
    cfg = {
        "n_days": 3,
        "start_day": "2026-01-12",
        "hourly_oat": oat,
        "baseline_payloads": _baseline_payloads(days, oat),
    }
    e1 = MultiDayDailyEnv({**cfg, "plant": FakeContinuityPlant()})
    e2 = MultiDayDailyEnv({**cfg, "plant": FakeContinuityPlant()})
    o1, _ = e1.reset()
    o2, _ = e2.reset()
    np.testing.assert_allclose(o1[:24], o2[:24])
    np.testing.assert_allclose(e1.plant.zone_temps_f, e2.plant.zone_temps_f)


def test_failed_day_is_integrity_failure_not_fabricated():
    plant = FakeContinuityPlant()
    orig = plant.simulate_day

    def boom(schedules, *, oat_c):
        out = orig(schedules, oat_c=oat_c)
        out["failed"] = True
        return out

    plant.simulate_day = boom  # type: ignore[method-assign]
    days = ["2026-01-12"]
    oat = _oat_map(*days)
    env = MultiDayDailyEnv(
        {
            "n_days": 1,
            "start_day": "2026-01-12",
            "plant": plant,
            "hourly_oat": oat,
            "baseline_payloads": _baseline_payloads(days, oat),
        }
    )
    env.reset()
    with pytest.raises(IntegrityFailure):
        env.step(encode_continuous_v2(continuous_params(68.0)))


def test_missing_baseline_raises():
    oat = _oat_map("2026-01-12")
    env = MultiDayDailyEnv(
        {
            "n_days": 1,
            "start_day": "2026-01-12",
            "plant": FakeContinuityPlant(),
            "hourly_oat": oat,
        }
    )
    env.reset()
    with pytest.raises(MissingBaselineError):
        env.step(encode_continuous_v2(continuous_params(68.0)))


def test_silent_minus10c_forecast_forbidden():
    with pytest.raises(ValueError, match="silent -10C"):
        MultiDayDailyEnv({"n_days": 1, "start_day": "2026-01-12", "plant": FakeContinuityPlant()}).reset()


def test_campaign_refuses_fake_plant():
    with pytest.raises(ValueError, match="FakeContinuityPlant"):
        assert_live_campaign_plant(FakeContinuityPlant())
    with pytest.raises(ValueError, match="FakeContinuityPlant"):
        MultiDayDailyEnv({"require_live_energyplus": True, "plant": FakeContinuityPlant()})


def test_w2a_warning_phases_warmup_vs_runtime(tmp_path):
    err = tmp_path / "eplusout.err"
    err.write_text(
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **  This error occurred 10 total times;\n"
        "*************  **   ~~~   **  during Warmup 6 times;\n"
        "*************  **   ~~~   **  during Sizing 0 times.\n"
        "*************  ** Warning ** Actual air mass flow rate is smaller than 25% of water-to-air heat pump coil rated air flow rate.\n"
        "*************  **   ~~~   **  This error occurred 4 total times;\n"
        "*************  **   ~~~   **  during Warmup 0 times;\n"
        "*************  **   ~~~   **  during Sizing 0 times.\n"
        "************* EnergyPlus Completed Successfully-- 2 Warning; 0 Severe Errors\n",
        encoding="utf-8",
    )
    gate = parse_eplus_err(err)
    assert gate["w2a_low_airflow_by_phase"]["warmup"] == 6
    assert gate["w2a_low_airflow_by_phase"]["scored_runtime"] == 8
    assert gate["recurring"]["w2a_low_airflow"] == 14


def test_between_day_movement_is_not_always_zero():
    from eplus_gym.control_v2 import deep_setback_params

    days = ["2025-12-08", "2025-12-09"]
    oat = _oat_map(*days)
    env = MultiDayDailyEnv(
        {
            "n_days": 2,
            "start_day": "2025-12-08",
            "days": days,
            "plant": FakeContinuityPlant(),
            "hourly_oat": oat,
            "baseline_payloads": _baseline_payloads(days, oat),
        }
    )
    env.reset()
    _o, _r, _d, _t, info1 = env.step(encode_continuous_v2(continuous_params(70.0)))
    assert info1["between_day_action_movement"] == 0.0
    _o, _r, _d, _t, info2 = env.step(encode_continuous_v2(deep_setback_params()))
    assert info2["between_day_action_movement"] > 0.0
    env.close()
    assert env._closed is True


def test_close_does_not_insert_a_learnable_step():
    days = ["2025-12-08"]
    oat = _oat_map(*days)
    env = MultiDayDailyEnv(
        {
            "n_days": 1,
            "start_day": "2025-12-08",
            "plant": FakeContinuityPlant(),
            "hourly_oat": oat,
            "baseline_payloads": _baseline_payloads(days, oat),
        }
    )
    env.reset()
    env.close()
    assert env._day_i == 0
