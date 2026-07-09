"""Economizer / OAT rules."""

from __future__ import annotations

import pandas as pd

from app.rules.base import finalize, norm_cmd

FAN_ON_MIN = 0.05


def _fan(df: pd.DataFrame) -> pd.Series:
    if "fan_cmd" in df.columns:
        return norm_cmd(df["fan_cmd"]).fillna(0)
    if "fan_status" in df.columns:
        return norm_cmd(df["fan_status"]).fillna(0)
    return pd.Series(0.0, index=df.index)


def economizer_unfavorable(df: pd.DataFrame, params: dict, poll_seconds: float, confirm_seconds: float):
    oat_hi = float(params.get("oat_hi_f", 63.0))
    dmpr = float(params.get("damper_frac", 0.42))
    econ = norm_cmd(df.get("oa_damper_pct")).fillna(0)
    raw = df["oa_t"].notna() & df["oa_damper_pct"].notna() & (df["oa_t"] > oat_hi) & (econ > dmpr)
    return finalize("ECON-2", df.attrs.get("equipment_id", ""), raw, poll_seconds, confirm_seconds)


def oat_meteo_fault(df: pd.DataFrame, weather: pd.DataFrame | None, params: dict, poll_seconds: float, confirm_seconds: float):
    oat_err = float(params.get("oat_err_f", 5.0))
    if weather is None or weather.empty or "oa_t" not in df.columns:
        raw = pd.Series(False, index=df.index)
        r = finalize("OAT-METEO", df.attrs.get("equipment_id", ""), raw, poll_seconds, confirm_seconds)
        r.message = "weather not loaded"
        return r
    wx = weather.reindex(df.index, method=None)
    wx_col = "wx_oa_t" if "wx_oa_t" in wx.columns else "oa_t"
    if wx_col not in wx.columns:
        for c in wx.columns:
            if "temp" in c.lower() or c == "dry_bulb_f":
                wx_col = c
                break
    diff = (df["oa_t"] - wx[wx_col]).abs()
    raw = df["oa_t"].notna() & wx[wx_col].notna() & (diff > oat_err)
    return finalize("OAT-METEO", df.attrs.get("equipment_id", ""), raw, poll_seconds, confirm_seconds)


def econ_stuck_closed(df: pd.DataFrame, params: dict, poll_seconds: float, confirm_seconds: float):
    oat_min = float(params.get("oat_min_f", 55.0))
    fan = _fan(df)
    econ = norm_cmd(df.get("oa_damper_pct")).fillna(0)
    raw = (fan > FAN_ON_MIN) & df["oa_t"].notna() & (econ < 0.05) & (df["oa_t"] > oat_min)
    return finalize("ECON-1", df.attrs.get("equipment_id", ""), raw, poll_seconds, confirm_seconds)
