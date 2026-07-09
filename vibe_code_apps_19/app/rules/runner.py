"""Run the 50-rule pandas cookbook with skip-on-missing-role behavior."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.rules import cookbook_catalog as cb
from app.rules.base import RuleResult, error_result, finalize_result, skipped


def infer_equipment_kind(equipment_id: str) -> str:
    u = equipment_id.upper().replace("\\", "/")
    if "WEATHER" in u:
        return "weather"
    if "VAV" in u:
        return "vav"
    if u.startswith("AHU") or "/AHU" in u:
        return "ahu"
    if "CHILLER" in u or u.startswith("CHW"):
        return "chiller"
    if "BOILER" in u:
        return "boiler"
    if "HEAT" in u and "PUMP" in u:
        return "heatpump"
    if "ZONE" in u:
        return "zone"
    return "unknown"


def merge_weather(df: pd.DataFrame, weather: pd.DataFrame | None) -> pd.DataFrame:
    if weather is None or weather.empty:
        return df
    out = df.copy()
    wx = weather.reindex(out.index)
    for col in wx.columns:
        if col not in out.columns:
            out[col] = wx[col]
    return out


def weather_available(df: pd.DataFrame) -> bool:
    return "wx_oa_dewpoint" in df.columns and df["wx_oa_dewpoint"].notna().any()


def econ3_compute(d: pd.DataFrame, p: dict, poll: float, wx_ok: bool) -> pd.Series:
    if not {"oa_t", "oa_damper_pct", "clg_valve_pct"}.issubset(d.columns):
        return cb._false(d.index)
    econ = cb.norm_cmd(d["oa_damper_pct"]).fillna(0)
    clg = cb.norm_cmd(d["clg_valve_pct"]).fillna(0)
    damper_thr = cb._f(p, "econ3_damper", 0.32)
    mech = (clg > 0.01) & (econ < damper_thr)
    dewpoint = d["wx_oa_dewpoint"] if "wx_oa_dewpoint" in d.columns else None
    if wx_ok and dewpoint is not None and dewpoint.notna().any():
        db_min = cb._f(p, "econ3_db_min", 35.0)
        db_max = cb._f(p, "econ3_db_max", 72.0)
        dp_max = cb._f(p, "econ3_dp_max", 60.0)
        oadb = d["wx_oa_t"] if "wx_oa_t" in d.columns else d["oa_t"]
        econ_available = (oadb > db_min) & (oadb < db_max) & (dewpoint < dp_max)
        return oadb.notna() & dewpoint.notna() & econ_available & mech
    oat_cut = cb._f(p, "econ3_oat_fallback", 63.0)
    return d["oa_t"].notna() & (d["oa_t"] < oat_cut) & mech


def _confirm_seconds(rule: cb.CookbookRule, params: dict) -> float:
    if "confirm_min" in params:
        return float(params["confirm_min"]) * 60.0
    return rule.confirm_seconds


def _missing_roles(rule: cb.CookbookRule, df: pd.DataFrame) -> list[str]:
    if rule.sensor_sweep:
        present = [r for r in cb.SWEEP_SENSOR_ROLES if r in df.columns and df[r].notna().any()]
        return [] if present else ["any sensor role from sweep list"]
    missing = []
    for role in rule.required_roles:
        if role not in df.columns or df[role].notna().sum() == 0:
            missing.append(role)
    if rule.id == "OAT-METEO" and "wx_oa_t" not in df.columns:
        missing.append("wx_oa_t")
    return missing


def _params_for_rule(rule: cb.CookbookRule, params_by_rule: dict[str, dict]) -> dict:
    p = dict(rule.defaults())
    p.update(params_by_rule.get(rule.id, {}))
    return p


def run_cookbook_rule(
    rule: cb.CookbookRule,
    df: pd.DataFrame,
    *,
    equipment_id: str,
    equipment_kind: str,
    poll_seconds: float,
    params_by_rule: dict[str, dict] | None = None,
    weather: pd.DataFrame | None = None,
) -> RuleResult:
    params_by_rule = params_by_rule or {}
    if equipment_kind != "unknown" and equipment_kind not in rule.equipment_kinds:
        return skipped(rule.id, equipment_id, [], notes=f"SKIPPED — rule not applicable to equipment kind '{equipment_kind}'")

    d = merge_weather(df, weather)
    missing = _missing_roles(rule, d)
    if missing:
        return skipped(rule.id, equipment_id, missing)

    params = _params_for_rule(rule, params_by_rule)
    confirm_s = _confirm_seconds(rule, params)
    wx_ok = weather_available(d)

    try:
        if rule.id == "ECON-3":
            raw = econ3_compute(d, params, poll_seconds, wx_ok)
        else:
            raw = rule.compute(d, params, poll_seconds)
        raw = raw.reindex(d.index).fillna(False).astype(bool)
        metrics: dict[str, Any] = {}
        if rule.sensor_sweep:
            metrics["sensors_checked"] = [r for r in cb.SWEEP_SENSOR_ROLES if r in d.columns]
        if rule.id == "ECON-3":
            metrics["weather_gate"] = "open-meteo dew point" if wx_ok else "imperial OAT fallback"
        return finalize_result(rule.id, equipment_id, raw, poll_seconds, confirm_s, metrics=metrics)
    except Exception as exc:
        return error_result(rule.id, equipment_id, exc)


def run_all_cookbook_rules(
    df: pd.DataFrame,
    *,
    equipment_id: str,
    poll_seconds: float,
    params_by_rule: dict[str, dict] | None = None,
    weather: pd.DataFrame | None = None,
) -> list[RuleResult]:
    kind = infer_equipment_kind(equipment_id)
    return [
        run_cookbook_rule(
            rule,
            df,
            equipment_id=equipment_id,
            equipment_kind=kind,
            poll_seconds=poll_seconds,
            params_by_rule=params_by_rule,
            weather=weather,
        )
        for rule in cb.RULES
    ]


# Public aliases
RULES = cb.RULES
RULES_BY_ID = cb.RULES_BY_ID
catalog = cb.catalog
