"""Feature compiler for vibe21 demand-management hourly rows (no future leakage)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

FEATURE_COLS = [
    "hour_ending",
    "oat_c",
    "rh_pct",
    "ghi",
    "occupied",
    "in_dr_window",
    "precool_f",
    "relax_clg_f",
    "relax_htg_f",
    "dat_delta_f",
    "chw_avail",
    "fan_avail",
    "deadband_target_f",
    "facility_kw_lag1",
    "facility_kw_lag2",
    "oat_lag1",
    "phase_baseline",
    "phase_precool",
    "phase_relax",
    "phase_shed",
    "phase_recovery",
    "strategy_baseline",
    "strategy_precool_shift",
    "strategy_deadband_10f",
    "strategy_chiller_off",
    "strategy_loadshed_p5f",
    "strategy_hvac_off",
    "strategy_precool_chiller_off",
    "is_weekend",
]

TARGET_COL = "facility_kw"
TARGET_COLS = [
    "facility_kw",
    "cooling_kw",
    "zone_temp_ahu1_mean_c",
    "zone_temp_ahu2_mean_c",
    "max_zone_temp_c",
    "ahu1_dat_c",
    "ahu1_mix_c",
    "ahu1_ra_c",
    "ahu1_oa_c",
    "ahu1_fan_plr",
    "ahu1_oa_frac",
    "ahu2_dat_c",
    "ahu2_mix_c",
    "ahu2_ra_c",
    "ahu2_oa_c",
    "ahu2_fan_plr",
    "ahu2_oa_frac",
    "chw_supply_c",
    "chw_return_c",
    "chw_pump_plr",
    "cw_pump_plr",
    "tower_fan_plr",
    "tower_leaving_c",
]
GROUP_COL = "day"


def _ensure_flat(df: pd.DataFrame) -> pd.DataFrame:
    if "facility_kw" in df.columns:
        return df.copy()
    # nested JSONL-style expansion not expected here
    raise ValueError("Expected flat farm parquet columns including facility_kw")


def compile_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add same-day lags and one-hot phase/strategy. Sort by day, hour first."""
    out = _ensure_flat(df)
    out = out.sort_values(["day", "hour_ending", "strategy_id"]).reset_index(drop=True)
    out["occupied"] = out["occupied"].astype(float)
    out["in_dr_window"] = out["in_dr_window"].astype(float)
    out["is_weekend"] = out["dow"].isin(["Saturday", "Sunday"]).astype(float)
    out["deadband_target_f"] = pd.to_numeric(out["deadband_target_f"], errors="coerce").fillna(0.0)
    out["ghi"] = out["ghi"].fillna(0.0)

    # Lags within simulation_id (same day × strategy) — never cross midnight into next day
    g = out.groupby("simulation_id", sort=False)
    out["facility_kw_lag1"] = g["facility_kw"].shift(1)
    out["facility_kw_lag2"] = g["facility_kw"].shift(2)
    out["oat_lag1"] = g["oat_c"].shift(1)
    # Drop rows without lag1 (hour 1) for supervised train; keep for inference with fill
    out["facility_kw_lag1"] = out["facility_kw_lag1"].fillna(out["facility_kw"])
    out["facility_kw_lag2"] = out["facility_kw_lag2"].fillna(out["facility_kw_lag1"])
    out["oat_lag1"] = out["oat_lag1"].fillna(out["oat_c"])

    for phase in ("baseline", "precool", "relax", "shed", "recovery"):
        out[f"phase_{phase}"] = (out["phase"] == phase).astype(float)
    for sid in (
        "baseline",
        "precool_shift",
        "deadband_10f",
        "chiller_off",
        "loadshed_p5f",
        "hvac_off",
        "precool_chiller_off",
    ):
        out[f"strategy_{sid}"] = (out["strategy_id"] == sid).astype(float)

    return out


def assert_no_future_leakage(df: pd.DataFrame) -> None:
    """Guard: lag features must not use later hours within a simulation."""
    c = compile_features(df)
    for sid, g in c.groupby("simulation_id"):
        g = g.sort_values("hour_ending")
        kw = g["facility_kw"].to_numpy()
        lag1 = g["facility_kw_lag1"].to_numpy()
        hours = g["hour_ending"].to_numpy()
        for i in range(1, len(g)):
            # lag1 at hour h must equal facility at previous row hour
            if lag1[i] != kw[i - 1] and hours[i] > hours[i - 1]:
                # allow float noise
                if abs(float(lag1[i]) - float(kw[i - 1])) > 1e-6:
                    raise AssertionError(f"leakage in {sid} at hour {hours[i]}")


def matrix_xy(
    df: pd.DataFrame,
    *,
    multi_target: bool = False,
    target_cols: list[str] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    feat = compile_features(df)
    X = feat[FEATURE_COLS].to_numpy(dtype=float)
    if multi_target:
        cols = list(target_cols) if target_cols else list(TARGET_COLS)
        missing = [c for c in cols if c not in feat.columns]
        if missing:
            raise ValueError(f"Farm missing twin I/O target columns: {missing}")
        y = feat[cols].to_numpy(dtype=float)
    else:
        y = feat[TARGET_COL].to_numpy(dtype=float)
    groups = feat[GROUP_COL].to_numpy()
    return X, y, groups, FEATURE_COLS


def available_target_cols(df: pd.DataFrame) -> list[str]:
    """Return TARGET_COLS present and non-all-null in the frame."""
    out = []
    for c in TARGET_COLS:
        if c in df.columns and df[c].notna().any():
            out.append(c)
    return out or [TARGET_COL]


def peak_mask(df: pd.DataFrame) -> np.ndarray:
    feat = compile_features(df)
    return ((feat["hour_ending"] > 14) & (feat["hour_ending"] <= 16)).to_numpy()
