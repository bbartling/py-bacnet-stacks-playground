"""Midnight forecast + pickle policy pack (no EnergyPlus)."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from eplus_gym.rl.field_sidecar import midnight_tick
from eplus_gym.rl.midnight_forecast import FORECAST_HOURS, forecast_from_hourly, load_midnight_forecast
from eplus_gym.rl.policy_pack import DailyPolicyPack
from eplus_gym.rl.spaces import build_day_observation


def test_forecast_features_cold_morning():
    fc = forecast_from_hourly("2026-01-26", [-12.0] * 8 + [0.0] * 16)
    _mean_c, min_c, _max_c, morn, h0, hm10 = fc.features()
    assert fc.temps_c[0] == -12.0
    assert len(fc.temps_c) == FORECAST_HOURS
    assert morn == -12.0
    assert h0 == 8
    assert hm10 == 8
    assert min_c == -12.0


def test_heuristic_pack_pickle_roundtrip(tmp_path: Path):
    pack = DailyPolicyPack(algo="HEURISTIC")
    p = tmp_path / "daily_policy.pkl"
    pack.save(p)
    again = DailyPolicyPack.load(p)
    obs = build_day_observation(
        month=1,
        dow=0,
        doy=26,
        oat_mean_c=-8.0,
        oat_min_c=-15.0,
        oat_max_c=0.0,
        morning_min_c=-15.0,
        hours_below_0c=18,
        hours_below_m10c=6,
    )
    params = again.predict_params(obs)
    assert params.recovery_start_minutes_before_occupancy == 180
    assert params.unoccupied_heating_f <= 65.0


def test_midnight_tick_advisory_no_bacnet(tmp_path: Path):
    pack = DailyPolicyPack()
    pack_path = tmp_path / "pack.pkl"
    pack.save(pack_path)
    out = tmp_path / "proposed.json"
    hourly = [-8.0] * 24
    proposal = midnight_tick(
        pack_path=pack_path,
        day="2026-01-26",
        forecast_source="pretend_owm",
        out_path=out,
        hourly_override=hourly,
    )
    assert proposal["bacnet_writes"] is False
    assert proposal["advisory_only"] is True
    assert out.is_file()
    assert proposal["params"]["occupancy_start_step"] >= 20


def test_load_forecast_override_not_network():
    fc = load_midnight_forecast(
        day="2026-01-26",
        source="pretend_owm",
        hourly_override=list(np.linspace(-10, 5, 24)),
    )
    assert fc.provider == "pretend_openweathermap_hourly_midnight"
    assert len(fc.temps_c) == 24
