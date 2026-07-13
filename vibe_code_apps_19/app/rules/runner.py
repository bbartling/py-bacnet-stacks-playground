"""Run the 50-rule pandas cookbook with explicit skip / not-applicable behavior."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.rules import cookbook_catalog as cb
from app.rules.base import RuleResult, equipment_off, error_result, finalize_result, not_applicable, skipped
from app.rules.operational_gate import RULE_GATES, resolve_operational_mask, should_skip_equipment_off
from app.site_model import equipment_type_from_id, resolve_equipment_type


def infer_equipment_kind(
    equipment_id: str = "",
    *,
    equipment_type: str = "",
    df: pd.DataFrame | None = None,
    role_map: dict | None = None,
) -> str:
    """Map equipment to cookbook kind using resolved type (attrs / map / id)."""
    t = resolve_equipment_type(
        equipment_id or (str(df.attrs.get("equipment_id", "")) if df is not None else ""),
        df=df,
        role_map=role_map,
        explicit=equipment_type or None,
    )
    return {
        "AHU": "ahu",
        "VAV": "vav",
        "CHW_PLANT": "chiller",
        "CHILLER": "chiller",
        "COOLING_TOWER": "cooling_tower",
        "BOILER": "boiler",
        "HP": "heatpump",
        "WEATHER": "weather",
        "METER": "meter",
        "UNKNOWN": "unknown",
    }.get(t, "unknown")


def merge_weather(df: pd.DataFrame, weather: pd.DataFrame | None) -> pd.DataFrame:
    """Align/enrich web weather onto an equipment frame, then resolve effective OAT.

    Adds ``oa_t_effective`` / ``oa_t_effective_source`` / optional ``bas_oa_t`` before
    missing-role checks. Never overwrites a real BAS ``oa_t`` column.
    """
    from app.weather_psychrometrics import dewpoint_f_from_db_rh, enrich_weather_frame, wetbulb_f_stull
    from app.weather_resolver import apply_effective_oat_columns

    out = df.copy()
    if weather is not None and not weather.empty:
        wx = enrich_weather_frame(weather).reindex(out.index)
        for col in wx.columns:
            if col not in out.columns:
                out[col] = wx[col]
            elif col.startswith("wx_") and out[col].notna().sum() == 0:
                out[col] = wx[col]
    # Derive dewpoint / wet-bulb on the equipment frame when RH landed
    if ("web-outside-air-dewpoint" not in out.columns or out["web-outside-air-dewpoint"].notna().sum() == 0) and {
        "web-outside-air-temp",
        "web-outside-air-humidity",
    }.issubset(out.columns):
        out["web-outside-air-dewpoint"] = dewpoint_f_from_db_rh(out["web-outside-air-temp"], out["web-outside-air-humidity"])
    if ("web-outside-air-wetbulb" not in out.columns or out["web-outside-air-wetbulb"].notna().sum() == 0) and {
        "web-outside-air-temp",
        "web-outside-air-humidity",
    }.issubset(out.columns):
        out["web-outside-air-wetbulb"] = wetbulb_f_stull(out["web-outside-air-temp"], out["web-outside-air-humidity"])
    return apply_effective_oat_columns(out)


def weather_available(df: pd.DataFrame) -> bool:
    """True when web weather can support free-cool (dewpoint present or derivable)."""
    if "web-outside-air-dewpoint" in df.columns and df["web-outside-air-dewpoint"].notna().any():
        return True
    if "web-outside-air-temp" in df.columns and "web-outside-air-humidity" in df.columns:
        return df["web-outside-air-temp"].notna().any() and df["web-outside-air-humidity"].notna().any()
    return False


def econ3_compute(d: pd.DataFrame, p: dict, poll: float, wx_ok: bool) -> pd.Series:
    """Mech cooling while free cooling is available (web OAT + dewpoint by default).

    Free-cool window: web dry-bulb between db_min/db_max AND dewpoint < dp_max.
    Optional: when sat / sat_sp present, also require SAT near setpoint
    (free cooling is keeping up — no need for mechanical cooling).
    """
    from app.weather_psychrometrics import dewpoint_f_from_db_rh

    if not {"outside-air-damper", "cooling-valve"}.issubset(d.columns):
        return cb._false(d.index)
    econ = cb.norm_cmd(d["outside-air-damper"]).fillna(0)
    clg = cb.norm_cmd(d["cooling-valve"]).fillna(0)
    damper_thr = cb._f(p, "econ3_damper", 0.32)
    mech = (clg > 0.01) & (econ < damper_thr)

    if "oa_t_effective" in d.columns and d["oa_t_effective"].notna().any():
        oadb = d["oa_t_effective"]
    elif "web-outside-air-temp" in d.columns and d["web-outside-air-temp"].notna().any():
        oadb = d["web-outside-air-temp"]
    elif "outside-air-temp" in d.columns:
        oadb = d["outside-air-temp"]
    else:
        return cb._false(d.index)

    dewpoint = d["web-outside-air-dewpoint"] if "web-outside-air-dewpoint" in d.columns else None
    if (dewpoint is None or dewpoint.notna().sum() == 0) and "web-outside-air-humidity" in d.columns:
        dewpoint = dewpoint_f_from_db_rh(oadb, d["web-outside-air-humidity"])

    if (wx_ok or (dewpoint is not None and dewpoint.notna().any())) and dewpoint is not None:
        db_min = cb._f(p, "econ3_db_min", 35.0)
        db_max = cb._f(p, "econ3_db_max", 72.0)
        dp_max = cb._f(p, "econ3_dp_max", 60.0)
        econ_available = (oadb > db_min) & (oadb < db_max) & (dewpoint < dp_max)
        raw = oadb.notna() & dewpoint.notna() & econ_available & mech
    else:
        oat_cut = cb._f(p, "econ3_oat_fallback", 63.0)
        bas = d["outside-air-temp"] if "outside-air-temp" in d.columns else oadb
        raw = bas.notna() & (bas < oat_cut) & mech

    require_zone = bool(p.get("econ3_require_zone_ok", True))
    zone_band = cb._f(p, "econ3_zone_band", 2.0)
    if require_zone and "discharge-air-temp" in d.columns and "discharge-air-temp-sp" in d.columns:
        raw = raw & ((d["discharge-air-temp"] - d["discharge-air-temp-sp"]).abs() <= zone_band)

    return raw.fillna(False)


def _confirm_seconds(rule: cb.CookbookRule, params: dict) -> float:
    if "confirm_min" in params:
        return float(params["confirm_min"]) * 60.0
    return rule.confirm_seconds


def _missing_roles(rule: cb.CookbookRule, df: pd.DataFrame) -> list[str]:
    from app.weather_resolver import oat_meteo_availability

    if rule.id == "OAT-METEO":
        ok, reasons = oat_meteo_availability(df)
        return [] if ok else reasons
    if rule.sensor_sweep:
        present = [r for r in cb.SWEEP_SENSOR_ROLES if r in df.columns and df[r].notna().any()]
        return [] if present else ["any sensor role from sweep list"]
    if rule.control_output_sweep:
        from app.rules.pid_hunting import control_outputs_present

        return [] if control_outputs_present(df) else ["any 0-100% control output (valve/damper/fan/pump cmd)"]
    missing = []
    for role in rule.required_roles:
        if role == "outside-air-temp":
            # Physics rules may use oa_t_effective (web primary / BAS fallback)
            if "outside-air-temp" in df.columns and df["outside-air-temp"].notna().any():
                continue
            if "oa_t_effective" in df.columns and df["oa_t_effective"].notna().any():
                continue
            missing.append(role)
            continue
        if role == "web-outside-air-temp":
            if role not in df.columns or df[role].notna().sum() == 0:
                missing.append(role)
            continue
        if role not in df.columns or df[role].notna().sum() == 0:
            missing.append(role)
    if rule.id in {"CW-OPT-1", "CW-APR-1", "CW-FAN-1"} and (
        "web-outside-air-wetbulb" not in df.columns or df["web-outside-air-wetbulb"].notna().sum() == 0
    ):
        missing.append("web-outside-air-wetbulb")
    if rule.id in {"CW-APR-1", "CW-FAN-1"}:
        fan_ok = any(
            r in df.columns and df[r].notna().any()
            for r in ("tower-fan-cmd", "cw-fan-cmd", "fan-cmd")
        )
        if not fan_ok:
            missing.append("tower_fan_cmd|cw_fan_cmd|fan_cmd")
    return missing


def _plot_series_for_rule(rule: cb.CookbookRule, d: pd.DataFrame) -> dict[str, pd.Series]:
    """Attach rule input columns for plotting (unit-separated in the chart layer)."""
    out: dict[str, pd.Series] = {}
    if rule.control_output_sweep:
        from app.rules.pid_hunting import iter_control_output_series

        for label, series in iter_control_output_series(d):
            out[label] = series
        return out
    roles = list(rule.required_roles)
    if rule.sensor_sweep:
        roles = [r for r in cb.SWEEP_SENSOR_ROLES if r in d.columns]
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

    from app.weather_resolver import inject_oa_t_for_physics, weather_source_metrics

    d = merge_weather(df, weather)
    # OAT-METEO needs both real sources — never inject web into oa_t for the compare.
    if rule.id != "OAT-METEO":
        d = inject_oa_t_for_physics(d)
    missing = _missing_roles(rule, d)
    if missing:
        notes = ""
        if rule.id == "OAT-METEO":
            notes = "SKIPPED — OAT-METEO requires both BAS oa_t and web wx_oa_t: " + "; ".join(missing)
        return skipped(
            rule.id,
            equipment_id,
            missing,
            notes=notes,
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
                metrics={**gate_meta, **weather_source_metrics(d)},
                notes=(
                    f"SKIPPED_EQUIPMENT_OFF — operational gate '{gate_meta.get('gate_kind')}' "
                    f"via {gate_meta.get('gate_source')}: no proven-on samples."
                ),
            )

        if rule.id == "ECON-3":
            raw = econ3_compute(d, params, poll_seconds, wx_ok)
        elif rule.id == "OAT-METEO":
            # Compare real BAS vs web — restore bas_oa_t into oa_t if needed
            if "bas-outside-air-temp" in d.columns and d["bas-outside-air-temp"].notna().any():
                d = d.copy()
                d["outside-air-temp"] = d["bas-outside-air-temp"]
            raw = rule.compute(d, params, poll_seconds)
        else:
            raw = rule.compute(d, params, poll_seconds)
        raw = raw.reindex(d.index).fillna(False).astype(bool)
        metrics: dict[str, Any] = {**dict(gate_meta), **weather_source_metrics(d)}
        if rule.sensor_sweep:
            metrics["sensors_checked"] = [r for r in cb.SWEEP_SENSOR_ROLES if r in d.columns]
        if rule.control_output_sweep:
            metrics["outputs_checked"] = [r for r in cb.CONTROL_OUTPUT_ROLES if r in d.columns]
        if rule.id == "ECON-3":
            metrics["weather_gate"] = "open-meteo dew point" if wx_ok else "imperial OAT fallback"
        if d.attrs.get("oa_t_injected_from"):
            metrics["oa_t_injected_from"] = d.attrs["oa_t_injected_from"]
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
    eq_type = resolve_equipment_type(
        equipment_id, df=df, explicit=equipment_type or None
    )
    kind = infer_equipment_kind(equipment_id, equipment_type=eq_type, df=df)
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
            equipment_type=eq_type,
            require_operational_gates=require_operational_gates,
        )
        for rule in RULES  # canonical + CUSTOM-* (assigned below via active_rules)
    ]


def run_batch(
    equipment_frames: dict[str, pd.DataFrame],
    *,
    params_by_rule: dict[str, dict] | None = None,
    weather: pd.DataFrame | None = None,
    equipment_filter: set[str] | None = None,
    building_filter: str | None = None,
    site_filter: str | None = None,
    vav_to_ahu: dict[str, str] | None = None,
) -> list[RuleResult]:
    """Run all cookbook rules for each equipment in scope — no silent omission."""
    from app.topology_enrich import enrich_frames_with_ahu_feeds, stamp_feed_attrs

    # Optional topology: copy parent AHU SAT onto VAV frames as ahu_sat
    if vav_to_ahu:
        stamp_feed_attrs(equipment_frames, vav_to_ahu)
        # Collect role maps from attrs if present
        rm: dict = {}
        for eq_id, raw_df in equipment_frames.items():
            block = (raw_df.attrs.get("_role_map") or {}).get(eq_id)
            if isinstance(block, dict):
                rm[eq_id] = block
        enrich_frames_with_ahu_feeds(equipment_frames, vav_to_ahu, role_map=rm)

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
        # Preserve topology-enriched ahu_sat if apply_role_map dropped it
        if "ahu-discharge-air-temp" in raw_df.columns and "ahu-discharge-air-temp" not in mapped.columns:
            mapped["ahu-discharge-air-temp"] = raw_df["ahu-discharge-air-temp"]
        poll = float(raw_df.attrs.get("poll_seconds") or 300.0)
        eq_type = resolve_equipment_type(eq_id, df=raw_df, role_map=role_map)
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


from app.rules.custom_registry import active_rules, active_rules_by_id

RULES = active_rules()
RULES_BY_ID = active_rules_by_id()
catalog = cb.catalog
