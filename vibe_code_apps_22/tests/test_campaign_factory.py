"""Campaign factory constructs MultiDayDailyEnv. Legacy env is diagnostic-only."""
from __future__ import annotations

from eplus_gym.control_v2 import build_six_schedules_f, continuous_params
from eplus_gym.rl.daily_env import DailySixZoneGymEnv
from eplus_gym.rl.multiday_env import FakeContinuityPlant, MultiDayDailyEnv
from eplus_gym.rl.train_sb3 import campaign_env_class, make_env, make_legacy_daily_env


def _oat(day: str = "2026-01-12") -> dict[str, list[float]]:
    return {day: [-10.0] * 24}


def _td_payloads(days: list[str]) -> dict:
    plant = FakeContinuityPlant()
    plant.start_episode()
    sched = build_six_schedules_f(continuous_params(70.0))
    oat = _oat()
    out = {}
    for day in days:
        rec = plant.simulate_day(sched, oat_c=oat[day] if day in oat else [-10.0] * 24)
        rec["TEST_DOUBLE"] = True
        out[day] = rec
    return out


def test_campaign_factory_constructs_multiday_env():
    assert campaign_env_class is MultiDayDailyEnv
    env = make_env(
        {
            "n_days": 1,
            "start_day": "2026-01-12",
            "plant": FakeContinuityPlant(),
            "hourly_oat": _oat(),
            "require_live_energyplus": False,
            "baseline_payloads": _td_payloads(["2026-01-12"]),
            "reward_name": "reward_v2",
        }
    )
    assert isinstance(env, MultiDayDailyEnv)
    assert not isinstance(env, DailySixZoneGymEnv)


def test_legacy_diagnostic_env_is_explicit():
    env = make_legacy_daily_env(
        {
            "site_root": ".",
            "epw": "dummy.epw",
            "champion_idf": "dummy.idf",
            "days": ["2026-01-26"],
            "simulator": "LIVE_ENERGYPLUS",
            "legacy_diagnostic": True,
        }
    )
    assert isinstance(env, DailySixZoneGymEnv)
    campaign = make_env(
        {
            "n_days": 1,
            "start_day": "2026-01-12",
            "plant": FakeContinuityPlant(),
            "hourly_oat": _oat(),
            "require_live_energyplus": False,
            "baseline_payloads": _td_payloads(["2026-01-12"]),
        }
    )
    assert type(campaign) is not type(env)
