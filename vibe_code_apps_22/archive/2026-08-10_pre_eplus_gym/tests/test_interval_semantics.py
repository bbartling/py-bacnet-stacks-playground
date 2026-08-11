"""Interval semantics: no weather leak, determinism, contract immutability."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
sys.path.insert(0, str(_ML))

from hybrid_rollout import (  # noqa: E402
    HybridModels,
    build_row,
    init_state_from_contract,
    make_fixture_contract,
    rollout_96,
)

_WEATHER_FEATURE_KEYS = ("oat_f", "rh_pct", "ghi", "hdd65")


class _Const7:
    def __init__(self, vec):
        self.vec = np.asarray(vec, dtype=float)

    def predict(self, X):
        n = len(X)
        return np.tile(self.vec, (n, 1))


def _dummy_models() -> HybridModels:
    cols = [
        "step_15",
        "sin_step",
        "cos_step",
        "hour_ending",
        "month",
        "doy",
        "is_weekend",
        "occupied",
        "oat_f",
        "oat_lag1",
        "hdd65",
        "hdd65_cum_night",
        "hours_to_occupy",
        "rh_pct",
        "ghi",
        "occ_frac_1F_A",
        "occ_frac_1F_B",
        "occ_frac_1F_C",
        "occ_frac_1F_D",
        "occ_frac_2F_A",
        "occ_frac_2F_B",
        "hp_on_1F_A",
        "hp_on_1F_B",
        "hp_on_1F_C",
        "hp_on_1F_D",
        "hp_on_2F_A",
        "hp_on_2F_B",
        "sum_occ_frac",
        "sum_hp_on",
        "preheat_lead_h",
        "stagger_min",
        "unocc_htg_sp_f",
        "occ_htg_sp_f",
        "facility_kw_lag1",
        "facility_kw_lag2",
        "strategy_baseline",
        "strategy_stagger_preheat",
        "strategy_flat_24_7",
        "strategy_deep_setback",
        "strategy_morning_all_on",
        "zone_temp_1F_A_f_lag1",
        "zone_temp_1F_B_f_lag1",
        "zone_temp_1F_C_f_lag1",
        "zone_temp_1F_D_f_lag1",
        "zone_temp_2F_A_f_lag1",
        "zone_temp_2F_B_f_lag1",
    ]
    base = _Const7([30.0, 68, 68, 68, 68, 68, 68])
    delta = _Const7([-2.0, -0.5, -0.5, -0.5, -0.5, -0.5, -0.5])
    return HybridModels(baseline=base, delta=delta, feature_cols=cols)


def test_contract_documents_interval_semantics():
    doc = json.loads((_APP / "contracts" / "hybrid_dsm_96_v1.json").read_text(encoding="utf-8"))
    sem = doc["interval_semantics"]
    assert "hour-ending" in sem["timestamp"].lower() or "interval end" in sem["timestamp"].lower()
    assert "00:00" in sem["init"] or "midnight" in sem["init"].lower()
    assert "00:15" in sem["predictions"] and "24:00" in sem["predictions"]


def test_build_row_uses_weather_at_t_not_t_plus_1():
    """Feature-availability: oat/rh/ghi/hdd at step t index weather[t], never t+1."""
    contract = make_fixture_contract(seed=7)
    weather = contract["weather_forecast_96"]
    # Distinct fingerprints so t vs t+1 cannot accidentally match.
    weather["oat_f"] = [float(i) for i in range(96)]
    weather["rh_pct"] = [100.0 + float(i) for i in range(96)]
    weather["ghi"] = [1000.0 + float(i) for i in range(96)]
    state = init_state_from_contract(contract["init"])
    schedule = contract["baseline_control_96"]
    meta = contract["calendar"]
    hdd_acc = 0.0
    for t in range(95):
        row, hdd_acc = build_row(
            step=t,
            weather=weather,
            schedule=schedule,
            state=state,
            meta=meta,
            hdd_acc=hdd_acc,
        )
        assert row["oat_f"] == pytest.approx(float(t))
        assert row["oat_f"] != pytest.approx(float(t + 1))
        assert row["rh_pct"] == pytest.approx(100.0 + t)
        assert row["ghi"] == pytest.approx(1000.0 + t)
        assert row["hdd65"] == pytest.approx(max(0.0, 65.0 - float(t)))
        # Lag is prior-step state, not future weather.
        assert "oat_lag1" in row
        for k in _WEATHER_FEATURE_KEYS:
            assert k in row


def test_make_fixture_same_seed_rollout_deterministic():
    models = _dummy_models()
    c1 = make_fixture_contract(seed=21)
    c2 = make_fixture_contract(seed=21)
    out1 = rollout_96(models, c1)
    out2 = rollout_96(models, c2)
    assert out1["summary"] == out2["summary"]
    kw1 = [s["hybrid_facility_kw"] for s in out1["steps"]]
    kw2 = [s["hybrid_facility_kw"] for s in out2["steps"]]
    np.testing.assert_allclose(kw1, kw2, rtol=0.0, atol=0.0)
    peak1 = [s["running_peak_kw_hybrid"] for s in out1["steps"]]
    peak2 = [s["running_peak_kw_hybrid"] for s in out2["steps"]]
    np.testing.assert_allclose(peak1, peak2, rtol=0.0, atol=0.0)


def test_rollout_does_not_mutate_contract_or_inject_hdd_acc():
    models = _dummy_models()
    contract = make_fixture_contract(seed=21)
    wx_before = copy.deepcopy(contract["weather_forecast_96"])
    before = json.dumps(contract, sort_keys=True)
    rollout_96(models, contract)
    after = json.dumps(contract, sort_keys=True)
    assert before == after
    assert "_hdd_acc" not in contract
    assert contract["weather_forecast_96"] == wx_before
