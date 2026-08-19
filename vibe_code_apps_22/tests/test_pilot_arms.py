from __future__ import annotations

from pathlib import Path

from eplus_gym.mega.pilot_arms import tou_rule_params, weather_rule_params

APP = Path(__file__).resolve().parents[1]


def test_weather_rule_uses_epw_min(tmp_path: Path):
    epw = APP / "models" / "eplus" / "weather"
    candidates = list(epw.glob("*.epw"))
    if not candidates:
        return
    epw_path = candidates[0]
    p_cold = weather_rule_params(day="2026-01-12", epw=epw_path)
    assert p_cold.recovery_lead_minutes >= 45


def test_random_weekend_uses_research_schedules():
    from eplus_gym.rl.research_spaces import decode_continuous_research_v2, research_build_six_schedules_f

    rng = __import__("numpy").random.default_rng(42)
    from eplus_gym.rl.research_spaces import continuous_action_space_research_v2

    raw = rng.uniform(continuous_action_space_research_v2().low, continuous_action_space_research_v2().high)
    params = decode_continuous_research_v2(raw, day="2026-01-25")
    schedules = research_build_six_schedules_f(params, "2026-01-25")
    assert all(len(schedules[k]) == 96 for k in schedules)
