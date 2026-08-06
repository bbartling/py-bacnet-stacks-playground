"""Hybrid 96-step rollout: real baseline + E+ delta → DSM trajectory."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from feature_compile_15min import FEATURE_COLS_15MIN_MT, ensure_strategy_onehots
from feature_compile_heating_dsm import (
    HP_ON_COLS,
    OCC_FRAC_COLS,
    STRATEGY_IDS,
    TARGET_COLS,
    ZONE_TEMP_COLS,
)

STEPS = 96
CONTRACT_VERSION = "hybrid_dsm_96_v1"
HONESTY = "HYBRID_SCREENING"


@dataclass
class HybridModels:
    baseline: Any  # predict → (1, 7)
    delta: Any
    feature_cols: list[str]


def load_joblib_model(path: Path) -> tuple[Any, list[str], list[str]]:
    import joblib

    blob = joblib.load(path)
    return blob["model"], list(blob["feature_cols"]), list(blob["target_cols"])


def _row_features(row: dict[str, float], feature_cols: list[str]) -> np.ndarray:
    return np.array([float(row.get(c, 0.0)) for c in feature_cols], dtype=float)


def _predict7(model: Any, x: np.ndarray) -> np.ndarray:
    y = np.asarray(model.predict(x.reshape(1, -1)), dtype=float).reshape(-1)
    if y.size < 7:
        raise ValueError(f"expected 7 outputs, got {y.size}")
    return y[:7]


def init_state_from_contract(init: dict[str, Any]) -> dict[str, float]:
    """Lag init = measured midnight state from JSON — never hardcode 80/35."""
    required = ["facility_kw", "oat_f", *ZONE_TEMP_COLS]
    for k in required:
        if k not in init or init[k] is None or not np.isfinite(float(init[k])):
            raise ValueError(f"init missing finite {k} (measured midnight required)")
    state = {
        "facility_kw_lag1": float(init["facility_kw"]),
        "facility_kw_lag2": float(init.get("facility_kw_lag2", init["facility_kw"])),
        "oat_lag1": float(init["oat_f"]),
    }
    for c in ZONE_TEMP_COLS:
        state[f"{c}_lag1"] = float(init[c])
    return state


def _calendar_features(step: int, meta: dict[str, Any]) -> dict[str, float]:
    hour = step / 4.0
    occupied = float(meta.get("occupied_schedule", [0.0] * 96)[step])
    return {
        "step_15": float(step),
        "sin_step": float(np.sin(2 * np.pi * step / 96.0)),
        "cos_step": float(np.cos(2 * np.pi * step / 96.0)),
        "hour_ending": float(hour),
        "month": float(meta.get("month", 1)),
        "doy": float(meta.get("doy", 1)),
        "is_weekend": float(meta.get("is_weekend", 0)),
        "occupied": occupied,
        "hours_to_occupy": float(max(0.0, (28 - step) / 4.0)),
    }


def _control_at(schedule: dict[str, list[float]], step: int) -> dict[str, float]:
    out: dict[str, float] = {}
    for c in OCC_FRAC_COLS + HP_ON_COLS:
        series = schedule.get(c, [1.0] * 96)
        out[c] = float(series[step] if step < len(series) else series[-1])
    out["sum_occ_frac"] = float(sum(out[c] for c in OCC_FRAC_COLS))
    out["sum_hp_on"] = float(sum(out[c] for c in HP_ON_COLS))
    for k in ("preheat_lead_h", "stagger_min", "unocc_htg_sp_f", "occ_htg_sp_f"):
        series = schedule.get(k)
        if series is None:
            out[k] = {"preheat_lead_h": 0.0, "stagger_min": 0.0, "unocc_htg_sp_f": 64.0, "occ_htg_sp_f": 68.0}[k]
        else:
            out[k] = float(series[step] if isinstance(series, list) else series)
    sid = schedule.get("strategy_id", "baseline")
    if isinstance(sid, list):
        sid = sid[step] if step < len(sid) else sid[-1]
    for s in STRATEGY_IDS:
        out[f"strategy_{s}"] = 1.0 if s == sid else 0.0
    return out


def rollout_96(
    models: HybridModels,
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Run 96-step hybrid simulator from versioned JSON contract."""
    if contract.get("contract_version") not in (CONTRACT_VERSION, "hybrid_dsm_96_v1"):
        raise ValueError(f"unsupported contract_version={contract.get('contract_version')}")
    init = contract["init"]
    weather = contract["weather_forecast_96"]
    baseline_ctrl = contract["baseline_control_96"]
    dsm_ctrl = contract["dsm_control_96"]
    meta = contract.get("calendar", {})
    comfort_sp = float(contract.get("comfort_htg_sp_f", 68.0))
    comfort_band = float(contract.get("comfort_band_f", 2.0))

    state_b = init_state_from_contract(init)
    state_d = dict(state_b)  # delta lags start at 0 intervention
    for c in ZONE_TEMP_COLS:
        state_d[f"{c}_lag1"] = 0.0
    state_d["facility_kw_lag1"] = 0.0
    state_d["facility_kw_lag2"] = 0.0

    steps_out = []
    cum_kwh_b = cum_kwh_d = 0.0
    peak_b = peak_d = -1e9
    peak_b_t = peak_d_t = 0
    viol = 0

    for step in range(STEPS):
        oat = float(weather["oat_f"][step])
        rh = float(weather.get("rh_pct", [50.0] * 96)[step])
        ghi = float(weather.get("ghi", [0.0] * 96)[step])
        hdd = max(0.0, 65.0 - oat)
        cal = _calendar_features(step, meta)
        wx = {
            "oat_f": oat,
            "oat_lag1": state_b["oat_lag1"],
            "rh_pct": rh,
            "ghi": ghi,
            "hdd65": hdd,
            "hdd65_cum_night": float(contract.get("_hdd_acc", 0.0)) + (hdd if step < 28 else 0.0),
        }
        contract["_hdd_acc"] = wx["hdd65_cum_night"]

        row_b = {**cal, **wx, **_control_at(baseline_ctrl, step), **state_b}
        row_d_ctrl = {**cal, **wx, **_control_at(dsm_ctrl, step), **state_d}
        # delta model uses DSM controls with delta lags
        xb = _row_features(row_b, models.feature_cols)
        xd = _row_features(row_d_ctrl, models.feature_cols)
        base_y = _predict7(models.baseline, xb)
        delta_y = _predict7(models.delta, xd)
        hybrid_y = base_y + delta_y

        kw_b, kw_h = float(base_y[0]), float(hybrid_y[0])
        cum_kwh_b += kw_b * 0.25
        cum_kwh_d += kw_h * 0.25
        if kw_b > peak_b:
            peak_b, peak_b_t = kw_b, step
        if kw_h > peak_d:
            peak_d, peak_d_t = kw_h, step

        temps = {ZONE_TEMP_COLS[i]: float(hybrid_y[1 + i]) for i in range(6)}
        for t in temps.values():
            if t < comfort_sp - comfort_band:
                viol += 1

        steps_out.append(
            {
                "step_15": step,
                "baseline_facility_kw": kw_b,
                "delta_facility_kw": float(delta_y[0]),
                "hybrid_facility_kw": kw_h,
                "baseline_zone_temps_f": {ZONE_TEMP_COLS[i]: float(base_y[1 + i]) for i in range(6)},
                "delta_zone_temps_f": {ZONE_TEMP_COLS[i]: float(delta_y[1 + i]) for i in range(6)},
                "hybrid_zone_temps_f": temps,
                "cumulative_kwh_baseline": cum_kwh_b,
                "cumulative_kwh_hybrid": cum_kwh_d,
                "running_peak_kw_baseline": peak_b,
                "running_peak_kw_hybrid": peak_d,
                "running_peak_step_baseline": peak_b_t,
                "running_peak_step_hybrid": peak_d_t,
                "comfort_sp_f": comfort_sp,
                "comfort_violations_cum": viol,
            }
        )

        # update lags
        state_b["facility_kw_lag2"] = state_b["facility_kw_lag1"]
        state_b["facility_kw_lag1"] = kw_b
        state_b["oat_lag1"] = oat
        for i, c in enumerate(ZONE_TEMP_COLS):
            state_b[f"{c}_lag1"] = float(base_y[1 + i])

        state_d["facility_kw_lag2"] = state_d["facility_kw_lag1"]
        state_d["facility_kw_lag1"] = float(delta_y[0])
        state_d["oat_lag1"] = oat
        for i, c in enumerate(ZONE_TEMP_COLS):
            state_d[f"{c}_lag1"] = float(delta_y[1 + i])

    return {
        "contract_version": CONTRACT_VERSION,
        "honesty": HONESTY,
        "steps": steps_out,
        "summary": {
            "cumulative_kwh_baseline": cum_kwh_b,
            "cumulative_kwh_hybrid": cum_kwh_d,
            "peak_kw_baseline": peak_b,
            "peak_kw_hybrid": peak_d,
            "peak_step_baseline": peak_b_t,
            "peak_step_hybrid": peak_d_t,
            "comfort_violations": viol,
            "delta_peak_kw": peak_d - peak_b,
            "delta_kwh": cum_kwh_d - cum_kwh_b,
        },
    }


def make_fixture_contract(*, seed: int = 21) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    oat = 20.0 + 10.0 * np.sin(np.linspace(0, 2 * np.pi, 96)) + rng.normal(0, 1, 96)
    init = {
        "facility_kw": 12.0,
        "facility_kw_lag2": 12.0,
        "oat_f": float(oat[0]),
        **{c: 68.0 for c in ZONE_TEMP_COLS},
    }
    ones = [1.0] * 96
    zeros = [0.0] * 96
    occ = [1.0 if 28 <= i < 64 else 0.0 for i in range(96)]
    baseline_control = {
        "strategy_id": "baseline",
        **{c: list(occ) for c in OCC_FRAC_COLS},
        **{c: list(ones) for c in HP_ON_COLS},
        "unocc_htg_sp_f": 64.0,
        "occ_htg_sp_f": 68.0,
        "preheat_lead_h": 0.0,
        "stagger_min": 0.0,
    }
    # DSM: stagger morning HP
    dsm_hp = {c: list(ones) for c in HP_ON_COLS}
    for i, c in enumerate(HP_ON_COLS):
        dsm_hp[c] = [0.0 if (20 + i * 2) <= step < (28 + i * 2) else 1.0 for step in range(96)]
    dsm_control = {
        "strategy_id": "stagger_preheat",
        **{c: list(occ) for c in OCC_FRAC_COLS},
        **dsm_hp,
        "unocc_htg_sp_f": 62.0,
        "occ_htg_sp_f": 68.0,
        "preheat_lead_h": 2.0,
        "stagger_min": 15.0,
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "honesty": HONESTY,
        "init": init,
        "calendar": {
            "month": 1,
            "doy": 15,
            "is_weekend": 0.0,
            "occupied_schedule": occ,
        },
        "weather_forecast_96": {
            "oat_f": oat.tolist(),
            "rh_pct": (50 + rng.normal(0, 5, 96)).tolist(),
            "ghi": np.clip(800 * np.sin(np.linspace(-0.2, 3.2, 96)), 0, None).tolist(),
        },
        "baseline_control_96": baseline_control,
        "dsm_control_96": dsm_control,
        "comfort_htg_sp_f": 68.0,
        "comfort_band_f": 2.0,
    }
