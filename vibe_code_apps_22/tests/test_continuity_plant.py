"""EnergyPlusContinuityPlant is the only live_energyplus=true plant."""
from __future__ import annotations

from pathlib import Path

from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant, weather_steps_after_reset
from eplus_gym.rl.multiday_env import FakeContinuityPlant, assert_live_campaign_plant
import pytest


def test_only_energyplus_continuity_plant_is_live():
    fake = FakeContinuityPlant()
    assert fake.live_energyplus is False
    with pytest.raises(ValueError, match="FakeContinuityPlant"):
        assert_live_campaign_plant(fake)
    # Constructor requires paths; flag is the campaign gate.
    assert EnergyPlusContinuityPlant.live_energyplus is True


def test_lookback_accounts_for_reset_weather_timestep():
    """reset() already yielded RunPeriodWeather 00:15 of the lookback day."""
    assert weather_steps_after_reset(lookback_days=1) == 95
    assert weather_steps_after_reset(lookback_days=2) == 191
    with pytest.raises(ValueError, match="lookback_days"):
        weather_steps_after_reset(lookback_days=0)


def test_continuity_plant_requires_lookback():
    with pytest.raises(ValueError, match="lookback_days"):
        EnergyPlusContinuityPlant(
            site_root=Path("."),
            epw=Path("x.epw"),
            idf=Path("x.idf"),
            output=Path("out"),
            days=["2026-01-12"],
            lookback_days=0,
        )
