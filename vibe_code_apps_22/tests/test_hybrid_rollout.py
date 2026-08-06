"""Golden / unit tests for hybrid 96-step rollout contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
sys.path.insert(0, str(_ML))

from feature_compile_heating_dsm import TARGET_COLS  # noqa: E402
from hybrid_rollout import (  # noqa: E402
    CONTRACT_VERSION,
    HybridModels,
    init_state_from_contract,
    make_fixture_contract,
    rollout_96,
)


class _Const7:
    def __init__(self, vec):
        self.vec = np.asarray(vec, dtype=float)

    def predict(self, X):
        n = len(X)
        return np.tile(self.vec, (n, 1))


def test_init_refuses_hardcoded_missing():
    with pytest.raises(ValueError, match="facility_kw"):
        init_state_from_contract({"oat_f": 20.0})


def test_rollout_96_fixture_shapes():
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
    models = HybridModels(baseline=base, delta=delta, feature_cols=cols)
    contract = make_fixture_contract()
    out = rollout_96(models, contract)
    assert out["contract_version"] == CONTRACT_VERSION
    assert len(out["steps"]) == 96
    assert out["steps"][0]["hybrid_facility_kw"] == pytest.approx(28.0)
    assert out["summary"]["peak_kw_hybrid"] == pytest.approx(28.0)
    assert "comfort_violations" in out["summary"]


def test_contract_schema_exists():
    p = _APP / "contracts" / "hybrid_dsm_96_v1.json"
    assert p.is_file()
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["contract_version"] == CONTRACT_VERSION
