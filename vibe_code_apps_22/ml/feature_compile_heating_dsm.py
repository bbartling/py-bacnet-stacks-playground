"""Feature compiler for Creekside heating DSM hourly rows (no future leakage).

Peak window for metrics: local hour-ending **05–09** (morning heating startup),
not Liberty vibe21 afternoon cooling HE 14–16.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

ZONE_IDS = [
    "1F_Area_A",
    "1F_Area_B",
    "1F_Area_C",
    "1F_Area_D",
    "2F_Area_A",
    "2F_Area_B",
]

# Stable short names: occ_frac_1F_A … occ_frac_2F_B
OCC_FRAC_COLS = [
    "occ_frac_1F_A",
    "occ_frac_1F_B",
    "occ_frac_1F_C",
    "occ_frac_1F_D",
    "occ_frac_2F_A",
    "occ_frac_2F_B",
]

STRATEGY_IDS = [
    "baseline",
    "stagger_preheat",
    "flat_24_7",
    "deep_setback",
    "morning_all_on",
]

FEATURE_COLS = [
    "hour_ending",
    "sin_hour",
    "cos_hour",
    "month",
    "doy",
    "is_weekend",
    "occupied",
    "oat_f",
    "oat_lag1",
    "hdd65",
    "rh_pct",
    "ghi",
    *OCC_FRAC_COLS,
    "sum_occ_frac",
    "preheat_lead_h",
    "stagger_min",
    "unocc_htg_sp_f",
    "occ_htg_sp_f",
    "facility_kw_lag1",
    "facility_kw_lag2",
    *[f"strategy_{s}" for s in STRATEGY_IDS],
]

TARGET_COL = "facility_kw"
GROUP_COL = "day"

MORNING_PEAK_HE_START = 5
MORNING_PEAK_HE_END = 9  # inclusive of HE 5..9 → hours ending 05..09


def _ensure_flat(df: pd.DataFrame) -> pd.DataFrame:
    if TARGET_COL not in df.columns:
        raise ValueError(f"Expected flat frame with {TARGET_COL}")
    return df.copy()


def compile_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add cyclic time, HDD, same-day lags, strategy one-hots. Sort by sim then hour."""
    out = _ensure_flat(df)
    sort_keys = [c for c in ("simulation_id", "day", "hour_ending") if c in out.columns]
    out = out.sort_values(sort_keys).reset_index(drop=True)

    he = pd.to_numeric(out["hour_ending"], errors="coerce").astype(float)
    out["hour_ending"] = he
    out["sin_hour"] = np.sin(2 * np.pi * he / 24.0)
    out["cos_hour"] = np.cos(2 * np.pi * he / 24.0)
    out["month"] = pd.to_numeric(out["month"], errors="coerce").astype(float)
    out["doy"] = pd.to_numeric(out["doy"], errors="coerce").astype(float)
    out["is_weekend"] = out["is_weekend"].astype(float)
    out["occupied"] = out["occupied"].astype(float)

    out["oat_f"] = pd.to_numeric(out["oat_f"], errors="coerce")
    out["hdd65"] = np.maximum(0.0, 65.0 - out["oat_f"].to_numpy(dtype=float))
    out["rh_pct"] = pd.to_numeric(out.get("rh_pct", 50.0), errors="coerce").fillna(50.0)
    out["ghi"] = pd.to_numeric(out.get("ghi", 0.0), errors="coerce").fillna(0.0)

    for c in OCC_FRAC_COLS:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    out["sum_occ_frac"] = out[OCC_FRAC_COLS].sum(axis=1)

    for c in ("preheat_lead_h", "stagger_min", "unocc_htg_sp_f", "occ_htg_sp_f"):
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0.0)

    gcol = "simulation_id" if "simulation_id" in out.columns else "day"
    g = out.groupby(gcol, sort=False)
    out["facility_kw_lag1"] = g[TARGET_COL].shift(1)
    out["facility_kw_lag2"] = g[TARGET_COL].shift(2)
    out["oat_lag1"] = g["oat_f"].shift(1)
    out["facility_kw_lag1"] = out["facility_kw_lag1"].fillna(out[TARGET_COL])
    out["facility_kw_lag2"] = out["facility_kw_lag2"].fillna(out["facility_kw_lag1"])
    out["oat_lag1"] = out["oat_lag1"].fillna(out["oat_f"])

    for sid in STRATEGY_IDS:
        out[f"strategy_{sid}"] = (out["strategy_id"] == sid).astype(float)

    return out


def assert_no_future_leakage(df: pd.DataFrame) -> None:
    c = compile_features(df)
    gcol = "simulation_id" if "simulation_id" in c.columns else "day"
    for sid, g in c.groupby(gcol):
        g = g.sort_values("hour_ending")
        kw = g[TARGET_COL].to_numpy(dtype=float)
        lag1 = g["facility_kw_lag1"].to_numpy(dtype=float)
        hours = g["hour_ending"].to_numpy(dtype=float)
        for i in range(1, len(g)):
            if hours[i] > hours[i - 1] and abs(float(lag1[i]) - float(kw[i - 1])) > 1e-5:
                raise AssertionError(f"leakage in {sid} at hour {hours[i]}")


def matrix_xy(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    feat = compile_features(df)
    X = feat[FEATURE_COLS].to_numpy(dtype=float)
    y = feat[TARGET_COL].to_numpy(dtype=float)
    groups = feat[GROUP_COL].astype(str).to_numpy()
    return X, y, groups, list(FEATURE_COLS)


def morning_peak_mask(df: pd.DataFrame) -> np.ndarray:
    feat = compile_features(df)
    he = feat["hour_ending"].to_numpy(dtype=float)
    return (he >= MORNING_PEAK_HE_START) & (he <= MORNING_PEAK_HE_END)


def cost_from_hourly_kw(
    kw: np.ndarray,
    *,
    energy_rate_per_kwh: float,
    demand_rate_per_kw: float,
    dt_hours: float = 1.0,
) -> dict[str, float]:
    """Simple energy + monthly-style demand charge on a 24h profile."""
    energy_kwh = float(np.sum(kw) * dt_hours)
    peak_kw = float(np.max(kw)) if len(kw) else 0.0
    energy_cost = energy_kwh * energy_rate_per_kwh
    demand_cost = peak_kw * demand_rate_per_kw
    return {
        "energy_kwh": energy_kwh,
        "peak_kw": peak_kw,
        "energy_cost": energy_cost,
        "demand_cost": demand_cost,
        "total_cost": energy_cost + demand_cost,
    }
