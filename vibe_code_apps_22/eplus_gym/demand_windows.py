"""Demand averaging windows. Same function for BAS and EnergyPlus kW series.

Utility billed-demand interval is unresolved in the site pack. Publish 5/15/30/60
minute aligned-block and rolling maxima. Do not treat a raw 15-minute EnergyPlus
max as an unqualified billed-demand gate.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from eplus_native.w2a_monthly_hold import UTILITY_JAN2026_DEMAND_KW

WINDOWS_MIN = (5, 15, 30, 60)
ALIGNMENTS = ("end", "start", "center")
UTILITY_DEMAND_INTERVAL_STATUS = "unresolved"
PEAK_TOL_FRAC = 0.10
LEGACY_BAND_KW = (250.0, 290.0)


def _as_series(values: pd.Series | pd.DataFrame, *, kw_col: str | None = None) -> pd.Series:
    if isinstance(values, pd.DataFrame):
        col = kw_col or ("facility_kw" if "facility_kw" in values.columns else values.columns[0])
        s = values[col].astype(float)
        if not isinstance(s.index, pd.DatetimeIndex):
            raise ValueError("demand windows require a DatetimeIndex")
        return s.sort_index()
    s = values.astype(float)
    if not isinstance(s.index, pd.DatetimeIndex):
        raise ValueError("demand windows require a DatetimeIndex")
    return s.sort_index()


def resample_mean(series: pd.Series, minutes: int, *, alignment: str = "end") -> pd.Series:
    rule = f"{int(minutes)}min"
    if alignment == "end":
        return series.resample(rule, label="right", closed="right").mean()
    if alignment == "start":
        return series.resample(rule, label="left", closed="left").mean()
    if alignment == "center":
        # Interval-centered: resample to end, then shift back half a window.
        mean = series.resample(rule, label="right", closed="right").mean()
        return mean.shift(freq=pd.Timedelta(minutes=-minutes / 2.0))
    raise ValueError(f"unknown alignment {alignment}")


def rolling_mean(series: pd.Series, minutes: int) -> pd.Series:
    # Infer native step; default 15 min if irregular.
    step = series.index.to_series().diff().median()
    if pd.isna(step) or step <= pd.Timedelta(0):
        step = pd.Timedelta(minutes=15)
    n = max(1, int(round(pd.Timedelta(minutes=minutes) / step)))
    return series.rolling(n, min_periods=n).mean()


def demand_window_report(
    series: pd.Series | pd.DataFrame,
    *,
    kw_col: str | None = None,
    native_minutes: int | None = None,
) -> dict[str, Any]:
    s = _as_series(series, kw_col=kw_col)
    native = int(native_minutes or 15)
    native_max = float(s.max()) if len(s) else None
    aligned: dict[str, dict[str, float | None]] = {}
    for minutes in WINDOWS_MIN:
        aligned[str(minutes)] = {}
        for alignment in ALIGNMENTS:
            mean = resample_mean(s, minutes, alignment=alignment)
            aligned[str(minutes)][alignment] = float(mean.max()) if mean.notna().any() else None
    rolling = {}
    for minutes in WINDOWS_MIN:
        rm = rolling_mean(s, minutes)
        rolling[str(minutes)] = float(rm.max()) if rm.notna().any() else None
    return {
        "schema": "vibe22.demand_windows.v1",
        "native_minutes": native,
        "native_max_kw": native_max,
        "aligned_max_kw": aligned,
        "rolling_max_kw": rolling,
        "utility_demand_interval_status": UTILITY_DEMAND_INTERVAL_STATUS,
        "utility_jan2026_billed_demand_kw": UTILITY_JAN2026_DEMAND_KW,
        "tol_frac": PEAK_TOL_FRAC,
        "billed_band_kw": [
            UTILITY_JAN2026_DEMAND_KW * (1 - PEAK_TOL_FRAC),
            UTILITY_JAN2026_DEMAND_KW * (1 + PEAK_TOL_FRAC),
        ],
        "legacy_band_kw": list(LEGACY_BAND_KW),
        "legacy_band_role": "a04_calibration_diagnostic_only",
        "hard_gate": False,
        "notes": (
            "Do not hard-fail a candidate solely on native 15-min max vs billed 284.82 kW "
            "while the utility averaging window remains unresolved."
        ),
    }


def freeze_peak_contract() -> dict[str, Any]:
    lo = UTILITY_JAN2026_DEMAND_KW * (1 - PEAK_TOL_FRAC)
    hi = UTILITY_JAN2026_DEMAND_KW * (1 + PEAK_TOL_FRAC)
    return {
        "schema": "vibe22.a04v2.peak_contract.v1",
        "frozen_before_stage_b": True,
        "utility_jan2026_billed_demand_kw": UTILITY_JAN2026_DEMAND_KW,
        "utility_demand_interval_status": UTILITY_DEMAND_INTERVAL_STATUS,
        "tol_frac": PEAK_TOL_FRAC,
        "billed_band_kw": [lo, hi],
        "windows_min": list(WINDOWS_MIN),
        "alignments": list(ALIGNMENTS),
        "hard_gate_on_15min_vs_billed": False,
        "legacy_250_290": {
            "band_kw": list(LEGACY_BAND_KW),
            "role": "a04_calibration_diagnostic_only",
            "enforced_in_a04v2_selection": False,
        },
        "same_function_for_bas_and_eplus": True,
        "guideline14_hourly": "diagnostic_until_meter_boundary_resolved",
    }
