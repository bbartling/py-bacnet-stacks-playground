"""Causal 24h multi-target building walk (facility_kW + zone temps).

Used by notebooks to demonstrate forecast-day rollout. Models must accept
FEATURE_COLS_MULTITARGET and emit TARGET_COLS (7 outputs).
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd

from feature_compile_heating_dsm import (
    FEATURE_COLS_MULTITARGET,
    HP_ON_COLS,
    OCC_FRAC_COLS,
    STRATEGY_IDS,
    TARGET_COLS,
    ZONE_TEMP_COLS,
    compile_features,
    warm_by_start_flags,
)


PredictFn = Callable[[np.ndarray], np.ndarray]  # (1, n_feat) → (n_targets,)


def default_strategy_hp_grid(strategy_id: str, *, weekend: bool = False) -> np.ndarray:
    """Return (24, 6) hp_on floats for a named strategy (weekday K12-ish).

    Schedule shapes only — not facility_kw labels. Labels come from native E+.
    """
    out = np.zeros((24, 6), dtype=float)
    if weekend:
        return out
    for h in range(24):
        if strategy_id == "flat_24_7":
            out[h, :] = 1.0
        elif strategy_id == "deep_setback":
            out[h, :] = 1.0 if 8 <= h < 16 else 0.0
        elif strategy_id == "morning_all_on":
            out[h, :] = 1.0 if 5 <= h < 16 else 0.0
        elif strategy_id == "stagger_preheat":
            if h >= 8 and h < 16:
                out[h, :] = 1.0
            elif 5 <= h < 8:
                n_on = min(6, max(0, (h - 4)))
                out[h, :n_on] = 1.0
        else:  # baseline
            out[h, :] = 1.0 if 7 <= h < 16 else 0.0
    return out


def walk_24h_multitarget(
    *,
    model_predict: PredictFn,
    oat_f_24: np.ndarray,
    midnight_zone_f: np.ndarray | float,
    strategy_id: str = "stagger_preheat",
    hp_on_24x6: np.ndarray | None = None,
    occ_frac_24x6: np.ndarray | None = None,
    month: float = 1.0,
    doy: float = 15.0,
    is_weekend: float = 0.0,
    rh_pct: float = 55.0,
    preheat_lead_h: float = 2.0,
    stagger_min: float = 30.0,
    unocc_htg_sp_f: float = 60.0,
    occ_htg_sp_f: float = 68.0,
    facility_kw0: float | None = None,
) -> dict[str, Any]:
    """Autoregressive 24h sim: each hour predicts kW + 6 temps jointly.

    ``facility_kw0`` must be measured midnight kW — no hardcoded 80 kW default.
    """
    if facility_kw0 is None or not np.isfinite(float(facility_kw0)):
        raise ValueError("facility_kw0 must be measured midnight facility kW (no hardcoded default)")
    oat = np.asarray(oat_f_24, dtype=float).reshape(24)
    if hp_on_24x6 is None:
        hp_on_24x6 = default_strategy_hp_grid(strategy_id, weekend=bool(is_weekend))
    hp = np.asarray(hp_on_24x6, dtype=float).reshape(24, 6)
    if occ_frac_24x6 is None:
        occ_frac_24x6 = hp.copy()  # demo: occupied when HP commanded
    occ = np.asarray(occ_frac_24x6, dtype=float).reshape(24, 6)

    if np.isscalar(midnight_zone_f):
        z = np.full(6, float(midnight_zone_f), dtype=float)
    else:
        z = np.asarray(midnight_zone_f, dtype=float).reshape(6)

    kw_lag1 = float(facility_kw0)
    kw_lag2 = float(facility_kw0)
    z_lag = z.copy()
    cum_hdd = 0.0

    pred_kw = np.zeros(24, dtype=float)
    pred_z = np.zeros((24, 6), dtype=float)
    feature_rows: list[dict[str, float]] = []

    for h in range(24):
        oat_h = float(oat[h])
        oat_lag1 = float(oat[h - 1]) if h else oat_h
        hdd = max(0.0, 65.0 - oat_h)
        if h < 5 or h >= 20:
            cum_hdd += hdd
        occupied = 1.0 if (is_weekend < 0.5 and 7 <= h < 16) else 0.0
        ghi = 200.0 if 8 <= h < 17 else 0.0

        row: dict[str, Any] = {
            "day": "forecast",
            "simulation_id": f"forecast__{strategy_id}",
            "hour_ending": float(h),
            "month": float(month),
            "doy": float(doy),
            "is_weekend": float(is_weekend),
            "occupied": occupied,
            "oat_f": oat_h,
            "rh_pct": float(rh_pct),
            "ghi": ghi,
            "strategy_id": strategy_id,
            "facility_kw": kw_lag1,  # placeholder for compile; overwritten by model
            "preheat_lead_h": float(preheat_lead_h),
            "stagger_min": float(stagger_min),
            "unocc_htg_sp_f": float(unocc_htg_sp_f),
            "occ_htg_sp_f": float(occ_htg_sp_f),
        }
        for i, c in enumerate(OCC_FRAC_COLS):
            row[c] = float(occ[h, i])
        for i, c in enumerate(HP_ON_COLS):
            row[c] = float(hp[h, i])
        for i, c in enumerate(ZONE_TEMP_COLS):
            row[c] = float(z_lag[i])  # seed compile lag path; model predicts new

        # Build a 1-row frame and compile — then override lags explicitly for causality
        feat = compile_features(pd.DataFrame([row]), multitarget=True)
        feat.loc[0, "facility_kw_lag1"] = kw_lag1
        feat.loc[0, "facility_kw_lag2"] = kw_lag2
        feat.loc[0, "oat_lag1"] = oat_lag1
        feat.loc[0, "hdd65_cum_night"] = cum_hdd
        for i, c in enumerate(ZONE_TEMP_COLS):
            feat.loc[0, f"{c}_lag1"] = float(z_lag[i])
        for sid in STRATEGY_IDS:
            feat.loc[0, f"strategy_{sid}"] = 1.0 if sid == strategy_id else 0.0

        x = feat[FEATURE_COLS_MULTITARGET].to_numpy(dtype=float)
        yhat = np.asarray(model_predict(x), dtype=float).reshape(-1)
        if yhat.shape[0] != len(TARGET_COLS):
            raise ValueError(f"model returned {yhat.shape[0]} outputs; expected {len(TARGET_COLS)}")

        kw = float(max(5.0, yhat[0]))
        zt = np.clip(yhat[1:7], 45.0, 85.0)
        pred_kw[h] = kw
        pred_z[h] = zt
        feature_rows.append({c: float(feat.loc[0, c]) for c in FEATURE_COLS_MULTITARGET})

        kw_lag2 = kw_lag1
        kw_lag1 = kw
        z_lag = zt

    flags = warm_by_start_flags(pred_z, occ_sp_f=occ_htg_sp_f, start_hour=7)
    return {
        "hour_ending": np.arange(24, dtype=float),
        "oat_f": oat,
        "facility_kw": pred_kw,
        "zone_temps": pred_z,
        "zone_temp_cols": list(ZONE_TEMP_COLS),
        "warm_by_start": flags,
        "strategy_id": strategy_id,
        "feature_rows": feature_rows,
        "target_cols": list(TARGET_COLS),
    }
