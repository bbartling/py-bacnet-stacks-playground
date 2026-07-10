"""Run the 50-rule pandas cookbook with explicit skip / not-applicable behavior."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.rules import cookbook_catalog as cb
from app.rules.base import RuleResult, equipment_off, error_result, finalize_result, not_applicable, skipped
from app.rules.operational_gate import RULE_GATES, resolve_operational_mask, should_skip_equipment_off
from app.site_model import equipment_type_from_id


def infer_equipment_kind(equipment_id: str) -> str:
    t = equipment_type_from_id(equipment_id)
    return {
        "AHU": "ahu",
        "VAV": "vav",
        "CHW_PLANT": "chiller",
        "BOILER": "boiler",
        "HP": "heatpump",
        "WEATHER": "weather",
        "METER": "meter",
        "UNKNOWN": "unknown",
    }.get(t, "unknown")


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
    if rule.control_output_sweep:
        present = [r for r in cb.CONTROL_OUTPUT_ROLES if r in df.columns and df[r].notna().any()]
        return [] if present else ["any 0-100% control output role"]
    missing = []
    for role in rule.required_roles:
        if role not in df.columns or df[role].notna().sum() == 0:
            missing.append(role)
    if rule.id == "OAT-METEO" and "wx_oa_t" not in df.columns:
        missing.append("wx_oa_t")
    return missing


def _plot_series_for_rule(rule: cb.CookbookRule, d: pd.DataFrame) -> dict[str, pd.Series]:
    """Attach rule input columns for plotting (unit-separated in the chart layer)."""
    out: dict[str, pd.Series] = {}
    roles = list(rule.required_roles)
    if rule.sensor_sweep:
        roles = [r for r in cb.SWEEP_SENSOR_ROLES if r in d.columns]
    if rule.control_output_sweep:
        roles = [r for r in cb.CONTROL_OUTPUT_ROLES if r in d.columns]
    for role in roles:
        if role in d.columns and d[role].notna().any():
            out[role] = d[role]
    return out


def _params_for_rule(rule: cb.CookbookRule, params_by_rule: dict[str, dict]) -> dict:
    p = dict(rule.defaults())
    spec = RULE_GATES.get(rule.id)
    if spec and spec.kind != "always":
        p.setdefault("require_operational_gate", 1.0)
        p.setdefault("startup_delay_min", spec.startup_delay_seconds / 60.0)
        p.setdefault("minimum_active_coverage_pct", spec.minimum_active_coverage_pct)
    else:
        p.setdefault("require_operational_gate", 0.0)
    p.update(params_by_rule.get(rule.id, {}))
    return p


def _ctx_from_df(df: pd.DataFrame, equipment_id: str, equipment_type: str) -> tuple[str, str, str]:
    site_id = str(df.attrs.get("site_id", ""))
    building_id = str(df.attrs.get("building_id", ""))
    eq_type = str(df.attrs.get("equipment_type", equipment_type))
    return site_id, building_id, eq_type


def run_cookbook_rule(
    rule: cb.CookbookRule,
    df: pd.DataFrame,
    *,
    equipment_id: str,
    equipment_kind: str,
    poll_seconds: float,
    params_by_rule: dict[str, dict] | None = None,
    weather: pd.DataFrame | None = None,
    site_id: str = "",
    building_id: str = "",
    equipment_type: str = "",
    require_operational_gates: bool = True,
) -> RuleResult:
    params_by_rule = params_by_rule or {}
    eq_type = equipment_type or equipment_type_from_id(equipment_id)
    sid, bid, _ = _ctx_from_df(df, equipment_id, eq_type)
    sid = site_id or sid
    bid = building_id or bid

    if equipment_kind != "unknown" and equipment_kind not in rule.equipment_kinds:
        return not_applicable(
            rule.id,
            equipment_id,
            equipment_kind,
            site_id=sid,
            building_id=bid,
            equipment_type=eq_type,
        )

    d = merge_weather(df, weather)
    missing = _missing_roles(rule, d)
    if missing:
        return skipped(
            rule.id,
            equipment_id,
            missing,
            site_id=sid,
            building_id=bid,
            equipment_type=eq_type,
        )

    params = _params_for_rule(rule, params_by_rule)
    confirm_s = _confirm_seconds(rule, params)
    wx_ok = weather_available(d)
    spec = RULE_GATES.get(rule.id)

    try:
        active, gate_meta = resolve_operational_mask(
            d,
            rule.id,
            poll_seconds=poll_seconds,
            params=params,
            gate_enabled=require_operational_gates,
        )
        if should_skip_equipment_off(gate_meta, params, spec):
            return equipment_off(
                rule.id,
                equipment_id,
                site_id=sid,
                building_id=bid,
                equipment_type=eq_type,
                metrics=gate_meta,
                notes=(
                    f"SKIPPED_EQUIPMENT_OFF — operational gate '{gate_meta.get('gate_kind')}' "
                    f"via {gate_meta.get('gate_source')}: no proven-on samples."
                ),
            )

        if rule.id == "ECON-3":
            raw = econ3_compute(d, params, poll_seconds, wx_ok)
        else:
            raw = rule.compute(d, params, poll_seconds)
        raw = raw.reindex(d.index).fillna(False).astype(bool)
        metrics: dict[str, Any] = dict(gate_meta)
        if rule.sensor_sweep:
            metrics["sensors_checked"] = [r for r in cb.SWEEP_SENSOR_ROLES if r in d.columns]
        if rule.control_output_sweep:
            metrics["outputs_checked"] = [r for r in cb.CONTROL_OUTPUT_ROLES if r in d.columns]
        if rule.id == "ECON-3":
            metrics["weather_gate"] = "open-meteo dew point" if wx_ok else "imperial OAT fallback"
        use_active = bool(gate_meta.get("gate_applied"))
        return finalize_result(
            rule.id,
            equipment_id,
            raw,
            poll_seconds,
            confirm_s,
            site_id=sid,
            building_id=bid,
            equipment_type=eq_type,
            metrics=metrics,
            plot_series=_plot_series_for_rule(rule, d),
            active_mask=active if use_active else None,
        )
    except Exception as exc:
        return error_result(
            rule.id,
            equipment_id,
            exc,
            site_id=sid,
            building_id=bid,
            equipment_type=eq_type,
        )


def run_all_cookbook_rules(
    df: pd.DataFrame,
    *,
    equipment_id: str,
    poll_seconds: float,
    params_by_rule: dict[str, dict] | None = None,
    weather: pd.DataFrame | None = None,
    site_id: str = "",
    building_id: str = "",
    equipment_type: str = "",
    require_operational_gates: bool = True,
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
            site_id=site_id,
            building_id=building_id,
            equipment_type=equipment_type,
            require_operational_gates=require_operational_gates,
        )
        for rule in cb.RULES
    ]


def run_batch(
    equipment_frames: dict[str, pd.DataFrame],
    *,
    params_by_rule: dict[str, dict] | None = None,
    weather: pd.DataFrame | None = None,
    equipment_filter: set[str] | None = None,
    building_filter: str | None = None,
    site_filter: str | None = None,
) -> list[RuleResult]:
    """Run all 50 rules for each equipment in scope — no silent omission."""
    results: list[RuleResult] = []
    for eq_id, raw_df in sorted(equipment_frames.items()):
        if equipment_filter is not None and eq_id not in equipment_filter:
            continue
        sid = str(raw_df.attrs.get("site_id", ""))
        bid = str(raw_df.attrs.get("building_id", ""))
        if site_filter and sid and sid != site_filter:
            continue
        if building_filter and bid and bid != building_filter:
            continue
        from app.role_map import apply_role_map

        role_map = raw_df.attrs.get("_role_map") or {}
        mapped = apply_role_map(raw_df, eq_id, role_map)
        mapped.attrs.update(raw_df.attrs)
        mapped.attrs["equipment_id"] = eq_id
        poll = float(raw_df.attrs.get("poll_seconds") or 300.0)
        eq_type = str(raw_df.attrs.get("equipment_type", equipment_type_from_id(eq_id)))
        results.extend(
            run_all_cookbook_rules(
                mapped,
                equipment_id=eq_id,
                poll_seconds=poll,
                params_by_rule=params_by_rule,
                weather=weather,
                site_id=sid,
                building_id=bid,
                equipment_type=eq_type,
            )
        )
    return results


RULES = cb.RULES
RULES_BY_ID = cb.RULES_BY_ID
catalog = cb.catalog
