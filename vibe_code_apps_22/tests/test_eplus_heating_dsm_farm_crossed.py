"""Crossed farm scenario builder + pair integrity."""
from __future__ import annotations

from eplus_heating_dsm_farm import build_scenarios, pair_integrity_hashes


def test_crossed_farm_day_count_and_no_prbs():
    sc = build_scenarios(crossed=True, n_weather_days=40)
    info = pair_integrity_hashes(sc)
    assert info["n_days"] >= 30
    assert info["n_days"] <= 60
    assert info["n_baseline"] == info["n_days"]
    assert info["n_dsm"] > info["n_baseline"]
    assert all(not str(s["strategy_id"]).startswith("prbs") for s in sc if s["arm"] == "dsm")


def test_smoke_still_small():
    sc = build_scenarios(smoke=True)
    info = pair_integrity_hashes(sc)
    assert info["n_days"] == 6
    assert info["n_scenarios"] == 12
