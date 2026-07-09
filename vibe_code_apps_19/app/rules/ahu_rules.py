"""AHU fault rules — demo subset."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.rules.base import finalize, norm_cmd

FAN_ON_MIN = 0.05
AHU_MIN_OA_DPR = 0.05


def sat_high_fault(df: pd.DataFrame, params: dict, poll_seconds: float, confirm_seconds: float):
    sat_err = float(params.get("sat_high_delta_f", 1.0))
    econ = norm_cmd(df.get("oa_damper_pct")).fillna(0)
    clg = norm_cmd(df.get("clg_valve_pct")).fillna(0)
    raw = (
        df["sat"].notna() & df["sat_sp"].notna() & (clg > 0.01)
        & (df["sat"] > df["sat_sp"] + sat_err)
        & ((econ <= AHU_MIN_OA_DPR) | (econ > 0.9))
    )
    return finalize("SAT-HIGH", df.attrs.get("equipment_id", ""), raw, poll_seconds, confirm_seconds)


def fc2_mat_low(df: pd.DataFrame, params: dict, poll_seconds: float, confirm_seconds: float):
    mix_tol = float(params.get("mix_tol_f", 1.15))
    fan = norm_cmd(df.get("fan_cmd")).fillna(0)
    env = np.minimum(df["rat"], df["oa_t"])
    raw = (
        df["mat"].notna() & df["rat"].notna() & df["oa_t"].notna()
        & (fan > FAN_ON_MIN) & (df["mat"] < env - mix_tol)
    )
    return finalize("FC2-MAT-LOW", df.attrs.get("equipment_id", ""), raw, poll_seconds, confirm_seconds)
