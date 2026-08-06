"""15-minute multi-target feature contract for hybrid real baseline / E+ delta."""
from __future__ import annotations

import numpy as np
import pandas as pd

from feature_compile_heating_dsm import (
    HP_ON_COLS,
    OCC_FRAC_COLS,
    STRATEGY_IDS,
    TARGET_COL,
    TARGET_COLS,
    ZONE_TEMP_COLS,
    ZONE_TEMP_LAG1_COLS,
)

GROUP_COL = "day"
STEPS_PER_DAY = 96

FEATURE_COLS_15MIN = [
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
    *OCC_FRAC_COLS,
    *HP_ON_COLS,
    "sum_occ_frac",
    "sum_hp_on",
    "preheat_lead_h",
    "stagger_min",
    "unocc_htg_sp_f",
    "occ_htg_sp_f",
    "facility_kw_lag1",
    "facility_kw_lag2",
    *[f"strategy_{s}" for s in STRATEGY_IDS],
]

FEATURE_COLS_15MIN_MT = [
    *FEATURE_COLS_15MIN,
    *ZONE_TEMP_LAG1_COLS,
]


def ensure_strategy_onehots(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "strategy_id" not in out.columns:
        out["strategy_id"] = "baseline"
    for sid in STRATEGY_IDS:
        col = f"strategy_{sid}"
        if col not in out.columns:
            out[col] = (out["strategy_id"] == sid).astype(float)
    return out


def matrix_xy_15min_multi(
    df: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str], list[str], pd.DataFrame]:
    feat = ensure_strategy_onehots(df)
    # fill causal lags within day for first steps (measured midnight init elsewhere)
    for c in FEATURE_COLS_15MIN_MT:
        if c not in feat.columns:
            if c.startswith("strategy_"):
                feat[c] = 0.0
            else:
                raise ValueError(f"missing feature column {c}")
    # first step of day may lack lags — seed from same-row targets (midnight measured)
    for c in ["facility_kw_lag1", "facility_kw_lag2", "oat_lag1", *ZONE_TEMP_LAG1_COLS]:
        if c in feat.columns and TARGET_COL in feat.columns:
            if c == "oat_lag1" and "oat_f" in feat.columns:
                feat[c] = feat[c].fillna(feat["oat_f"])
            elif c.startswith("facility_kw"):
                feat[c] = feat[c].fillna(feat[TARGET_COL])
            else:
                base = c.replace("_lag1", "")
                if base in feat.columns:
                    feat[c] = feat[c].fillna(feat[base])
    feat = feat.dropna(subset=FEATURE_COLS_15MIN_MT + TARGET_COLS).reset_index(drop=True)
    X = feat[FEATURE_COLS_15MIN_MT].to_numpy(dtype=float)
    Y = feat[TARGET_COLS].to_numpy(dtype=float)
    groups = feat[GROUP_COL].astype(str).to_numpy()
    return X, Y, groups, list(FEATURE_COLS_15MIN_MT), list(TARGET_COLS), feat



def morning_peak_mask_15min(df: pd.DataFrame) -> np.ndarray:
    """Local HE 05–09 → step_15 in [20, 36] inclusive (05:00–09:00 endings)."""
    step = pd.to_numeric(df["step_15"], errors="coerce").to_numpy(dtype=float)
    return (step >= 20) & (step <= 36)


def recursive_rollout_day(
    model,
    day_df: pd.DataFrame,
    feature_cols: list[str],
    target_cols: list[str],
    *,
    init_row: pd.Series | None = None,
) -> np.ndarray:
    """Teacher-forced exogenous + recursive lags for one day (96 steps).

    Lag init = measured midnight state (first row lags / values), never hardcoded.
    """
    day = day_df.sort_values("step_15").reset_index(drop=True)
    if day.empty:
        return np.zeros((0, len(target_cols)))
    preds = np.zeros((len(day), len(target_cols)), dtype=float)
    # seed lags from measured first row (or explicit init)
    seed = init_row if init_row is not None else day.iloc[0]
    lag_kw1 = float(seed.get("facility_kw_lag1", seed[TARGET_COL]))
    lag_kw2 = float(seed.get("facility_kw_lag2", lag_kw1))
    if not np.isfinite(lag_kw1):
        lag_kw1 = float(seed[TARGET_COL])
    if not np.isfinite(lag_kw2):
        lag_kw2 = lag_kw1
    zone_lags = []
    for c in ZONE_TEMP_COLS:
        v = seed.get(f"{c}_lag1", seed[c])
        v = float(v) if np.isfinite(v) else float(seed[c])
        zone_lags.append(v)

    for i, row in day.iterrows():
        feat = row[feature_cols].to_numpy(dtype=float).copy()
        # overwrite lag slots
        names = {n: j for j, n in enumerate(feature_cols)}
        if "facility_kw_lag1" in names:
            feat[names["facility_kw_lag1"]] = lag_kw1
        if "facility_kw_lag2" in names:
            feat[names["facility_kw_lag2"]] = lag_kw2
        for zc, zv in zip(ZONE_TEMP_COLS, zone_lags):
            lc = f"{zc}_lag1"
            if lc in names:
                feat[names[lc]] = zv
        yhat = np.asarray(model.predict(feat.reshape(1, -1)), dtype=float).reshape(-1)
        if yhat.size < len(target_cols):
            raise ValueError(f"model returned {yhat.size} outputs, need {len(target_cols)}")
        preds[i] = yhat[: len(target_cols)]
        lag_kw2 = lag_kw1
        lag_kw1 = float(preds[i, 0])
        zone_lags = [float(preds[i, 1 + k]) for k in range(6)]
    return preds
