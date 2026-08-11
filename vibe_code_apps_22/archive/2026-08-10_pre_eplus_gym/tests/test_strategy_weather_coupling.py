"""Strategy schedules and weather forecast share contract lengths."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP / "ml"))

from feature_compile_heating_dsm import STRATEGY_IDS  # noqa: E402
from hybrid_rollout import HybridModels, make_fixture_contract, rollout_96, schedule_from_strategy_fixture  # noqa: E402
from weather_forecast_48h import synthetic_hourly_48, weather_forecast_from_hourly48  # noqa: E402


class _Const7:
    def __init__(self, vec):
        self.vec = np.asarray(vec, dtype=float)

    def predict(self, X):
        return np.tile(self.vec, (len(X), 1))


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


def test_each_strategy_weather_length_matches_control():
    wx = weather_forecast_from_hourly48(synthetic_hourly_48(seed=3), hours=24)
    for sid in STRATEGY_IDS:
        if str(sid).startswith("prbs"):
            continue
        sched = schedule_from_strategy_fixture(sid)
        assert len(sched["occ_frac_1F_A"]) == 96
        assert len(wx["oat_f"]) == 96


def test_colder_forecast_changes_walk_peak_with_oat_sensitive_model():
    """Const base + delta that scales with first feature proxy via oat in init path."""

    class _OatAware:
        def predict(self, X):
            # X columns include oat near index 8 in FEATURE order — use mean of row
            x = np.asarray(X, dtype=float)
            oat = x[:, 8] if x.shape[1] > 8 else np.zeros(len(x))
            kw = 200.0 - 2.0 * oat  # colder → higher kW
            zones = np.full((len(x), 6), 68.0)
            return np.column_stack([kw, zones])

    models = HybridModels(
        baseline=_OatAware(),
        delta=_Const7([0.0, 0, 0, 0, 0, 0, 0]),
        feature_cols=_cols(),
    )
    warm = weather_forecast_from_hourly48(synthetic_hourly_48(seed=0, mean_f=40.0), hours=24)
    cold = weather_forecast_from_hourly48(synthetic_hourly_48(seed=0, mean_f=-10.0), hours=24)
    c_warm = make_fixture_contract()
    c_cold = make_fixture_contract()
    c_warm["weather_forecast_96"] = {k: warm[k] for k in ("oat_f", "rh_pct", "ghi")}
    c_cold["weather_forecast_96"] = {k: cold[k] for k in ("oat_f", "rh_pct", "ghi")}
    c_warm["dsm_control_96"] = schedule_from_strategy_fixture("flat_24_7")
    c_cold["dsm_control_96"] = schedule_from_strategy_fixture("flat_24_7")
    p_warm = rollout_96(models, c_warm)["summary"]["peak_kw_hybrid"]
    p_cold = rollout_96(models, c_cold)["summary"]["peak_kw_hybrid"]
    assert p_cold > p_warm
