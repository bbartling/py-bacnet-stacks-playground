"""VAV / zone rules."""

from __future__ import annotations

import pandas as pd

from app.rules.base import finalize


def vav_comfort_fault(df: pd.DataFrame, params: dict, poll_seconds: float, confirm_seconds: float):
    lo = float(params.get("low_limit_f", 68.0))
    hi = float(params.get("high_limit_f", 76.0))
    raw = df["zone_t"].notna() & ((df["zone_t"] < lo) | (df["zone_t"] > hi))
    return finalize("VAV-1", df.attrs.get("equipment_id", ""), raw, poll_seconds, confirm_seconds)


def avg_zone_temp(df: pd.DataFrame, params: dict, poll_seconds: float, confirm_seconds: float):
    zt = df["zone_t"].dropna()
    avg = float(zt.mean()) if len(zt) else float("nan")
    r = finalize("AVG-ZONE-TEMP", df.attrs.get("equipment_id", ""), pd.Series(False, index=df.index), poll_seconds, 0)
    r.message = f"avg={avg:.2f}°F"
    r.fault_hours = 0.0
    r.fault_pct = 0.0
    r.plot_series = {"zone_t": df["zone_t"]}
    return r


def zone_comfort_pct(df: pd.DataFrame, params: dict, poll_seconds: float, confirm_seconds: float):
    lo = float(params.get("low_limit_f", 68.0))
    hi = float(params.get("high_limit_f", 76.0))
    zt = df["zone_t"].dropna()
    in_band = ((zt >= lo) & (zt <= hi)).sum()
    pct = 100.0 * in_band / len(zt) if len(zt) else 0.0
    r = finalize("ZONE-COMFORT-PCT", df.attrs.get("equipment_id", ""), pd.Series(False, index=df.index), poll_seconds, 0)
    r.message = f"comfort={pct:.1f}%"
    r.plot_series = {"zone_t": df["zone_t"]}
    return r
