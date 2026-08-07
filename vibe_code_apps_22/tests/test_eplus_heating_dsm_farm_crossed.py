"""Crossed farm scenario builder + pair integrity."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT / "ml"))

from eplus_heating_dsm_farm import build_scenarios, pair_integrity_hashes  # noqa: E402


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
