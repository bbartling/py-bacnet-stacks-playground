"""Const-model hybrid walk must stay inside plant sanity band."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "ml"))

from hybrid_rollout import HybridModels, make_fixture_contract, rollout_96  # noqa: E402
from hybrid_sanity import PLANT_PEAK_CAP_KW  # noqa: E402


class _Const7:
    def __init__(self, vec):
        self.vec = np.asarray(vec, dtype=float)

    def predict(self, X):
        n = len(X)
        return np.tile(self.vec, (n, 1))


def _cols():
    return [
        "step_15", "sin_step", "cos_step", "hour_ending", "month", "doy",
        "is_weekend", "occupied", "oat_f", "oat_lag1", "hdd65", "hdd65_cum_night",
        "hours_to_occupy", "rh_pct", "ghi",
        "occ_frac_1F_A", "occ_frac_1F_B", "occ_frac_1F_C", "occ_frac_1F_D",
        "occ_frac_2F_A", "occ_frac_2F_B",
        "hp_on_1F_A", "hp_on_1F_B", "hp_on_1F_C", "hp_on_1F_D", "hp_on_2F_A", "hp_on_2F_B",
        "sum_occ_frac", "sum_hp_on", "preheat_lead_h", "stagger_min",
        "unocc_htg_sp_f", "occ_htg_sp_f", "facility_kw_lag1", "facility_kw_lag2",
        "strategy_baseline", "strategy_stagger_preheat", "strategy_flat_24_7",
        "strategy_deep_setback", "strategy_morning_all_on",
        "zone_temp_1F_A_f_lag1", "zone_temp_1F_B_f_lag1", "zone_temp_1F_C_f_lag1",
        "zone_temp_1F_D_f_lag1", "zone_temp_2F_A_f_lag1", "zone_temp_2F_B_f_lag1",
    ]


def test_const_walk_within_plant_cap():
    base = _Const7([30.0, 68, 68, 68, 68, 68, 68])
    delta = _Const7([-2.0, -0.5, -0.5, -0.5, -0.5, -0.5, -0.5])
    models = HybridModels(baseline=base, delta=delta, feature_cols=_cols())
    out = rollout_96(models, make_fixture_contract())
    assert out["summary"]["sane"] is True
    assert 0.0 <= out["summary"]["min_kw_hybrid"] <= out["summary"]["max_kw_hybrid"]
    assert out["summary"]["max_kw_hybrid"] <= PLANT_PEAK_CAP_KW


def test_spike_const_model_marked_insane():
    base = _Const7([800.0, 68, 68, 68, 68, 68, 68])
    delta = _Const7([300.0, 0, 0, 0, 0, 0, 0])
    models = HybridModels(baseline=base, delta=delta, feature_cols=_cols())
    out = rollout_96(models, make_fixture_contract())
    assert out["summary"]["sane"] is False
    assert out["summary"]["max_kw_hybrid"] > PLANT_PEAK_CAP_KW
