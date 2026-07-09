"""Run the Open-FDD cookbook rule catalog against the Haystack RDF data model.

For each equipment the engine:
  1. Loads the wide historian frame.
  2. Resolves cookbook logical roles → historian columns in layers:
       RDF pointRole  ->  economizer_point_mapping.json  ->  physical-name heuristics.
  3. Merges Open-Meteo weather (dry-bulb, dew point, RH) for economizer availability.
  4. Runs every rule whose equipment_kind matches; rules missing required roles are
     reported as "not in data model" so the UI can still show the equation + sliders.
  5. Confirms faults (streak >= confirm rows) and rolls up fault hours.

Fault math is canonical/imperial (°F, in.w.c.); UI does display-unit conversion.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import cookbook_rules as cb
from rules.base import confirm_fault, hours_true

_HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Page-result cache — rule math is expensive (zones fan out to dozens of VAVs).
# Faults are computed ONCE per (page, params, data version) and reused, so a
# page revisit is a lookup, not a recompute. Invalidated when the RDF model or
# the historian feather cache changes on disk.
# ---------------------------------------------------------------------------

_RESULT_CACHE: dict[tuple[str, str], dict[str, Any]] = {}
_RESULT_LOCK = threading.Lock()


def _data_token() -> str:
    """Cheap fingerprint of the modeled data — changes when TTL or history reloads."""
    parts: list[str] = []
    for p in sorted((_HERE.parent / "data" / "rdf").glob("**/data_model.ttl")):
        try:
            parts.append(str(p.stat().st_mtime_ns))
        except OSError:
            pass
    feather_dir = _HERE / ".cache" / "feather"
    if feather_dir.is_dir():
        mtimes = [f.stat().st_mtime_ns for f in feather_dir.glob("*.feather")]
        if mtimes:
            parts.append(str(max(mtimes)))
    return "|".join(parts) or "0"


def _cache_key(page_id: str, params_by_rule: dict | None, vav_limit: int) -> tuple[str, str]:
    payload = json.dumps(params_by_rule or {}, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{vav_limit}|{payload}".encode()).hexdigest()[:16]
    return page_id, f"{_data_token()}:{digest}"


_SERIES_CACHE: dict[str, dict[str, Any]] = {}


def _disk_get(cache_key: str) -> dict[str, Any] | None:
    try:
        import fault_disk_cache as fdc
        return fdc.get(_data_token(), cache_key)
    except Exception:
        return None


def _disk_put(cache_key: str, data: dict[str, Any]) -> None:
    try:
        import fault_disk_cache as fdc
        fdc.put(_data_token(), cache_key, data)
    except Exception:
        pass


def clear_result_cache() -> None:
    with _RESULT_LOCK:
        _RESULT_CACHE.clear()
        _SERIES_CACHE.clear()
    try:
        import fault_disk_cache as fdc
        fdc.clear()
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Role resolution
# ---------------------------------------------------------------------------

# logical role -> (RDF role candidates, exact physical column candidates, substring patterns)
ROLE_CANDIDATES: dict[str, tuple[list[str], list[str], list[str]]] = {
    "oa_t": (["oat", "oa_t", "weather_oat"], ["outside_air_temp_f", "dry_bulb_f", "oat_f"], ["outside_air_temp", "outdoor_air_temp", "dry_bulb"]),
    "rat": (["rat", "ra_t"], ["return_air_temp_f"], ["return_air_temp"]),
    "mat": (["mat"], ["mixed_air_temp_f"], ["mixed_air_temp", "mix_air_temp"]),
    "sat": (["sat"], ["discharge_air_temp_f", "supply_air_temp_f"], ["discharge_air_temp", "supply_air_temp", "sat_f"]),
    "sat_sp": (["sat_sp"], ["dat_reset_f", "sat_sp_f", "sat_setpoint_f"], ["dat_reset", "sat_sp", "sat_setpoint", "dischargeairtempsp"]),
    "fan_cmd": (["fan_cmd"], ["supply_fan_speed_pct"], ["fan_speed", "fan_cmd", "supplyfan"]),
    "fan_status": (["fan_status"], ["supply_fan_status"], ["fan_status", "fan_proof", "supply_fan_stat"]),
    "oa_damper_pct": (["oa_damper_cmd", "oa_damper_pos"], ["ex_dmpr_pos_fan_enable_pct", "oa_damper_pct"], ["dmpr", "damper", "econ"]),
    "oa_min_pct": (["oa_min_pct"], ["oa_minimum_position_pct"], ["oa_min", "minimum_position"]),
    "clg_valve_pct": (["cooling_cmd"], ["chw_valve_pct", "clg_valve_pct", "cooling_valve_pct"], ["chw_valve", "cooling_valve", "clg_valve", "cool_cmd"]),
    "htg_valve_pct": (["heating_cmd"], ["hw_valve_pct", "htg_valve_pct", "heating_valve_pct"], ["heating_valve", "htg_valve", "hhw_valve", "reheat_valve"]),
    "duct_static": ([], ["da_p_inwc", "duct_static_inwc"], ["da_p_inwc", "duct_static", "duct_press"]),
    "duct_static_sp": ([], ["da_p_setpoint_inwc"], ["da_p_setpoint", "duct_static_sp", "duct_press_sp"]),
    "oa_h": (["oa_humidity"], ["relative_humidity_pct", "oa_rh_pct"], ["outdoor_humidity", "oa_humidity", "oa_rh"]),
    "oa_dewpoint": ([], ["dew_point_f", "oa_dewpoint_f"], ["dew_point", "dewpoint"]),
    "wind_speed": ([], ["wind_speed_mph"], ["wind_speed"]),
    "wind_gust": ([], ["wind_gust_mph"], ["wind_gust", "gust"]),
    "clg_coil_enter_t": ([], [], ["chw_coil_enter", "cooling_coil_enter", "clg_coil_enter", "coolentering"]),
    "clg_coil_leave_t": ([], [], ["chw_coil_leave", "cooling_coil_leave", "clg_coil_leave", "coolleaving"]),
    "htg_coil_enter_t": ([], [], ["hw_coil_enter", "heating_coil_enter", "htg_coil_enter"]),
    "htg_coil_leave_t": ([], [], ["hw_coil_leave", "heating_coil_leave", "htg_coil_leave"]),
    "preheat_leave_t": ([], [], ["preheat_leave", "preheat_leaving", "preheat_discharge"]),
    "vav_total_flow": ([], [], ["vav_total_flow", "total_airflow", "system_airflow"]),
    # VAV
    "zone_t": (["zone_temp", "space_temp"], [], ["spacetemp", "space_temp", "zone_temp", "zonetemp", "roomtemp", "room_temp"]),
    "zone_t_sp": ([], [], ["spacetempsp", "zone_temp_sp", "clg_stpt", "htg_stpt", "occ_clg_stpt", "occ_ht_stpt", "setpoint"]),
    "damper_pct": ([], [], ["vavactuatorposition_pct", "vavactuatorcommand_pct", "damper_pos", "damper_cmd", "damper_pct"]),
    "reheat_valve_pct": ([], [], ["reheat_valve", "reheatvalve", "rht_valve", "reheat_pct"]),
    "vav_disch_t": ([], [], ["vav_disch", "sa_temp_f", "sa_temp", "dischargeairtemp", "disch_air_temp", "supplyairtemp"]),
    "vav_inlet_t": ([], [], ["ductintemp", "duct_in_temp", "duct_inlet", "inlet_temp"]),
    "zone_flow": ([], [], ["airflow_cfm", "supply_flow_cfm", "airflow", "flow_cfm", "sa_flow"]),
    "min_flow_sp": ([], [], ["min_airflow", "min_flow", "minairflow", "airflow_min"]),
    "occ_mode": ([], [], ["occ_mode", "occupancy", "occupied"]),
    # Central plant
    "chw_supply_t": ([], ["chws_t_f"], ["chws_t", "chw_supply", "chwst"]),
    "chw_return_t": ([], ["chwr_t_f"], ["chwr_t", "chw_return", "chwrt"]),
    "chw_supply_t_sp": ([], [], ["chws_sp", "chw_supply_sp", "chwst_sp"]),
    "chw_pump_cmd": ([], ["chiller_1_command", "chiller_2_command"], ["chw_pump", "chwp", "pump_cmd", "pump_speed", "chiller_command"]),
    "chw_dp": ([], [], ["chw_dp", "chw_diff_press", "chwdp"]),
    "chw_dp_sp": ([], [], ["chw_dp_sp", "chwdp_sp"]),
    "chw_flow": ([], [], ["chw_flow", "chw_gpm"]),
    "chw_reset_req_sum": ([], [], ["chw_reset_req", "chw_req_sum"]),
    "hw_supply_t": ([], ["hws_t_f"], ["hws_t", "hw_supply", "hwst"]),
    "hw_return_t": ([], ["hwr_t_f"], ["hwr_t", "hw_return", "hwrt"]),
    "hw_reset_req_sum": ([], [], ["hw_reset_req", "hw_req_sum"]),
    "vav_press_req_sum": ([], [], ["vav_press_req", "press_req_sum", "static_req"]),
    "override_active": ([], [], ["override", "hand_mode", "bypass"]),
}


@lru_cache(maxsize=1)
def _ahu_point_map() -> dict[str, dict[str, str]]:
    try:
        data = json.loads((_HERE / "economizer_point_mapping.json").read_text(encoding="utf-8"))
        return data.get("ahu_mappings", {})
    except Exception:
        return {}


# logical role in our catalog -> logical key used in economizer_point_mapping.json
_POINTMAP_ALIAS = {
    "oa_t": "oat",
    "oa_damper_pct": "oa_damper_cmd",
    "clg_valve_pct": "cooling_cmd",
    "htg_valve_pct": "heating_cmd",
    "oa_h": "oa_humidity",
}


def _match_physical(role: str, columns: list[str], exclude: set[str] | None = None) -> str | None:
    exclude = exclude or set()
    exact, subs = ROLE_CANDIDATES.get(role, ([], [], []))[1:]
    lower = {c.lower(): c for c in columns if c not in exclude}
    for cand in exact:
        if cand.lower() in lower:
            return lower[cand.lower()]
    if role == "zone_t":
        for c in columns:
            if c in exclude:
                continue
            cl = c.lower()
            if "vav_" in cl and "space_temp" in cl and "sa_temp" not in cl and "duct" not in cl:
                return c
    for pat in subs:
        for c in columns:
            if c in exclude:
                continue
            if pat in c.lower():
                if role == "zone_t" and _zone_t_limit_column(c):
                    continue
                return c
    return None


def _zone_t_limit_column(column: str) -> bool:
    cl = column.lower()
    return (
        "alarm" in cl
        or "limit" in cl
        or "setpoint" in cl
        or "deadband" in cl
        or cl.endswith("_58")
        or cl.endswith("_59")
        or "sa_temp" in cl
        or "duct" in cl
        or "inlet" in cl
    )


def _score_zone_t_column(column: str) -> int:
    """Higher score wins — mirrors Rust ``role_rank::score_zone_t``."""
    if _zone_t_limit_column(column):
        return -100
    cl = column.lower()
    if "vav_" in cl and "space_temp" in cl and "sa_temp" not in cl and "duct" not in cl:
        return 100
    if "space_temp" in cl or "spacetemp" in cl or "zone_temp" in cl:
        return 70
    if "zone_t" in cl or "room_temp" in cl or "roomtemp" in cl:
        return 60
    return 0


def _resolve_zone_t(
    equipment_id: str,
    columns: list[str],
    resolver,
    exclude: set[str],
) -> str | None:
    """Rank all zone_t candidates; reject alarm/limit historian mis-tags."""
    candidates: list[str] = []
    rdf_roles = ROLE_CANDIDATES.get("zone_t", ([], [], []))[0]
    if resolver is not None:
        for rr in rdf_roles:
            try:
                col = resolver.column_for_role(equipment_id, rr)
            except Exception:
                col = None
            if col and col in columns and col not in exclude:
                candidates.append(col)
    amap = _ahu_point_map().get(equipment_id)
    if amap:
        key = _POINTMAP_ALIAS.get("zone_t", "zone_t")
        col = amap.get(key)
        if col and col in columns and col not in exclude:
            candidates.append(col)
    for c in columns:
        if c in exclude:
            continue
        if _score_zone_t_column(c) > 0:
            candidates.append(c)
    seen: set[str] = set()
    unique: list[str] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    if not unique:
        return None
    return max(unique, key=_score_zone_t_column)


def resolve_role(equipment_id: str, role: str, columns: list[str], resolver=None,
                 exclude: set[str] | None = None) -> str | None:
    """Layered resolution: RDF pointRole -> economizer_point_mapping -> physical heuristic.

    ``exclude`` holds columns already claimed by earlier (higher-priority) roles so a
    single historian column can't be double-assigned (e.g. chw_valve_pct → clg AND htg).
    """
    exclude = exclude or set()
    if role == "zone_t":
        return _resolve_zone_t(equipment_id, columns, resolver, exclude)
    rdf_roles = ROLE_CANDIDATES.get(role, ([], [], []))[0]
    # 1) RDF pointRole / fdd_input
    if resolver is not None:
        for rr in rdf_roles:
            try:
                col = resolver.column_for_role(equipment_id, rr)
            except Exception:
                col = None
            if col and col in columns and col not in exclude:
                return col
    # 2) economizer_point_mapping.json (AHUs)
    amap = _ahu_point_map().get(equipment_id)
    if amap:
        key = _POINTMAP_ALIAS.get(role, role)
        col = amap.get(key)
        if col and col in columns and col not in exclude:
            return col
    # 3) physical-name heuristic
    return _match_physical(role, columns, exclude)


# ---------------------------------------------------------------------------
# Logical frame builder
# ---------------------------------------------------------------------------

# roles worth attempting per equipment kind (keeps resolution focused)
_KIND_ROLES: dict[str, list[str]] = {
    "ahu": [
        "oa_t", "rat", "mat", "sat", "sat_sp", "fan_cmd", "fan_status",
        "oa_damper_pct", "oa_min_pct", "clg_valve_pct", "htg_valve_pct",
        "duct_static", "duct_static_sp", "clg_coil_enter_t", "clg_coil_leave_t",
        "htg_coil_enter_t", "htg_coil_leave_t", "preheat_leave_t", "vav_total_flow",
        "occ_mode", "override_active", "vav_press_req_sum",
    ],
    "vav": ["zone_t", "zone_t_sp", "damper_pct", "reheat_valve_pct", "vav_disch_t", "vav_inlet_t", "zone_flow", "min_flow_sp", "oa_t", "occ_mode"],
    "zone": ["zone_t", "zone_t_sp"],
    "chiller": ["chw_supply_t", "chw_return_t", "chw_supply_t_sp", "chw_pump_cmd", "chw_dp", "chw_dp_sp", "chw_flow", "chw_reset_req_sum", "oa_t"],
    "boiler": ["hw_supply_t", "hw_return_t", "hw_reset_req_sum", "oa_t"],
    "heatpump": ["sat", "zone_t", "fan_cmd", "oa_t"],
    "weather": ["oa_t", "oa_h", "oa_dewpoint", "wind_speed", "wind_gust"],
}


def _load(equipment_id: str, resolver):
    from haystack_rdf.data_loader import load_history_wide

    df = load_history_wide(equipment_id, resolver)
    poll = float(df.attrs.get("effective_poll_seconds", 300.0)) if hasattr(df, "attrs") else 300.0
    return df, poll


def _magnus_dewpoint_f(temp_f: pd.Series, rh_pct: pd.Series) -> pd.Series:
    """Approximate dew point (°F) from dry-bulb (°F) and RH (%) via Magnus formula."""
    t_c = (pd.to_numeric(temp_f, errors="coerce") - 32.0) * 5.0 / 9.0
    rh = pd.to_numeric(rh_pct, errors="coerce").clip(lower=1.0, upper=100.0)
    a, b = 17.62, 243.12
    gamma = np.log(rh / 100.0) + (a * t_c) / (b + t_c)
    dp_c = (b * gamma) / (a - gamma)
    return dp_c * 9.0 / 5.0 + 32.0


@lru_cache(maxsize=1)
def _weather_frame_cached_key() -> float:
    return 0.0


def load_weather(resolver) -> pd.DataFrame | None:
    try:
        wx, _ = _load("WEATHER", resolver)
    except Exception:
        return None
    if wx is None or "timestamp" not in wx.columns:
        return None
    cols = list(wx.columns)
    out = pd.DataFrame({"timestamp": pd.to_datetime(wx["timestamp"])})
    db = _match_physical("oa_t", cols)
    rh = _match_physical("oa_h", cols)
    dp = _match_physical("oa_dewpoint", cols)
    if db:
        out["wx_oa_t"] = pd.to_numeric(wx[db], errors="coerce")
    if rh:
        out["wx_oa_h"] = pd.to_numeric(wx[rh], errors="coerce")
    if dp:
        out["wx_oa_dewpoint"] = pd.to_numeric(wx[dp], errors="coerce")
    elif db and rh:
        out["wx_oa_dewpoint"] = _magnus_dewpoint_f(out["wx_oa_t"], out["wx_oa_h"])
    return out


def build_logical_frame(equipment_id: str, kind: str, resolver, weather: pd.DataFrame | None):
    """Return (logical_df, resolved_map, poll_seconds, weather_available)."""
    df, poll = _load(equipment_id, resolver)
    columns = list(df.columns)
    out = pd.DataFrame(index=df.index)
    if "timestamp" in df.columns:
        out["timestamp"] = pd.to_datetime(df["timestamp"])

    resolved: dict[str, str | None] = {}
    used: set[str] = set()
    for role in _KIND_ROLES.get(kind, []):
        col = resolve_role(equipment_id, role, columns, resolver, exclude=used)
        resolved[role] = col
        if col is not None:
            used.add(col)
            series = df[col]
            # commands/positions/temps kept numeric; occ_mode/status kept raw
            if role in ("occ_mode",):
                out[role] = series.astype(str)
            elif role == "fan_status":
                out[role] = series
            else:
                out[role] = pd.to_numeric(series, errors="coerce")

    weather_available = False
    if weather is not None and "timestamp" in out.columns and kind in ("ahu", "chiller", "boiler"):
        merged = out.merge(weather, on="timestamp", how="left")
        merged.index = out.index
        out = merged
        weather_available = bool("wx_oa_dewpoint" in out.columns and out["wx_oa_dewpoint"].notna().any())

    out.attrs["equipment_id"] = equipment_id
    return out, resolved, float(poll), weather_available


# ---------------------------------------------------------------------------
# ECON-3 weather-aware compute (open-meteo dew point gate + imperial fallback)
# ---------------------------------------------------------------------------


def econ3_compute(d: pd.DataFrame, p: dict, poll: float, weather_available: bool) -> pd.Series:
    if not {"oa_t", "oa_damper_pct", "clg_valve_pct"}.issubset(d.columns):
        return cb._false(d.index)
    econ = cb.norm_cmd(d["oa_damper_pct"]).fillna(0)
    clg = cb.norm_cmd(d["clg_valve_pct"]).fillna(0)
    damper_thr = cb._f(p, "econ3_damper", 0.32)
    mech = (clg > 0.01) & (econ < damper_thr)

    dewpoint = d["wx_oa_dewpoint"] if "wx_oa_dewpoint" in d.columns else None
    if weather_available and dewpoint is not None and dewpoint.notna().any():
        db_min = cb._f(p, "econ3_db_min", 35.0)
        db_max = cb._f(p, "econ3_db_max", 72.0)
        dp_max = cb._f(p, "econ3_dp_max", 60.0)
        oadb = d["wx_oa_t"] if "wx_oa_t" in d.columns else d["oa_t"]
        econ_available = (oadb > db_min) & (oadb < db_max) & (dewpoint < dp_max)
        return oadb.notna() & dewpoint.notna() & econ_available & mech
    # imperial fallback (no open-meteo): OAT < 63°F
    oat_cut = cb._f(p, "econ3_oat_fallback", 63.0)
    return d["oa_t"].notna() & (d["oa_t"] < oat_cut) & mech


# ---------------------------------------------------------------------------
# Rule execution
# ---------------------------------------------------------------------------


def _confirm_seconds(rule: cb.CookbookRule, params: dict) -> float:
    if "confirm_min" in params and params.get("confirm_min") is not None:
        try:
            return float(params["confirm_min"]) * 60.0
        except (TypeError, ValueError):
            pass
    return rule.confirm_seconds


def _annotate_sidecar(result: dict[str, Any], rule_id: str, d: pd.DataFrame, params: dict) -> None:
    """When open-fdd sidecar is up, attach SQL-engine fault hours for parity (pandas stays canonical for charts)."""
    import os

    if os.environ.get("OPENFDD_USE_SIDECAR", "1") != "1":
        return
    eq = d.attrs.get("equipment_id")
    if not eq:
        return
    try:
        import cookbook_sql as csql
        side = csql.try_sidecar_hours(rule_id, str(eq), params=params)
        if side and side.get("ok"):
            result["sidecar"] = side
    except Exception:
        pass


def run_rule(rule: cb.CookbookRule, d: pd.DataFrame, resolved: dict, poll: float,
             params: dict, weather_available: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": rule.id, "title": rule.title, "family": rule.family,
        "equation": rule.equation, "confirm_seconds": _confirm_seconds(rule, params),
        "params": [pp.to_dict() for pp in rule.params],
        "param_values": {**rule.defaults(), **{k: v for k, v in params.items() if k in rule.defaults()}},
    }

    # Applicability
    if rule.sensor_sweep:
        present = [r for r in cb.SWEEP_SENSOR_ROLES if r in d.columns]
        applicable = len(present) > 0
        missing = [] if applicable else ["any sensor"]
        result["sensors_checked"] = present
    else:
        missing = [r for r in rule.required_roles if r not in d.columns or d[r].notna().sum() == 0]
        applicable = len(missing) == 0

    result["applicable"] = applicable
    result["missing_roles"] = missing
    if not applicable:
        result["message"] = "Not in data model — missing points: " + ", ".join(missing)
        result["fault_hours"] = 0.0
        result["fault_pct"] = 0.0
        result["total_hours"] = 0.0
        return result

    try:
        if rule.id == "ECON-3":
            raw = econ3_compute(d, params, poll, weather_available)
            result["weather_gate"] = "open-meteo dew point" if weather_available else "imperial OAT fallback"
        else:
            raw = rule.compute(d, params, poll)
        raw = raw.reindex(d.index).fillna(False).astype(bool)
        confirmed = confirm_fault(raw, poll_seconds=poll, confirm_seconds=_confirm_seconds(rule, params))
        total_h = len(d) * poll / 3600.0
        fh = hours_true(confirmed, poll)
        result["fault_series"] = confirmed
        result["total_hours"] = round(total_h, 1)
        result["fault_hours"] = round(fh, 1)
        result["fault_pct"] = round(100.0 * fh / total_h, 2) if total_h else 0.0
        n = int(confirmed.sum())
        result["message"] = (
            f"No confirmed faults over {total_h:.0f} h." if n == 0
            else f"{fh:.1f} confirmed fault-hours ({result['fault_pct']:.1f}% of {total_h:.0f} h)."
        )
        _annotate_sidecar(result, rule.id, d, params)
    except Exception as exc:  # keep the tab resilient
        result["applicable"] = False
        result["error"] = f"{type(exc).__name__}: {exc}"
        result["message"] = "Rule error — see logs."
        result["fault_hours"] = 0.0
        result["fault_pct"] = 0.0
        result["total_hours"] = 0.0
    return result


# ---------------------------------------------------------------------------
# Chart series — per-rule signal traces + fault overlay (for the UI Plotly charts)
# ---------------------------------------------------------------------------

_ROLE_LABEL = {
    "zone_t": "Zone temp (°F)", "zone_t_sp": "Zone SP (°F)", "damper_pct": "Damper (%)",
    "reheat_valve_pct": "Reheat valve (%)", "zone_flow": "Airflow (cfm)", "min_flow_sp": "Min airflow SP (cfm)",
    "vav_disch_t": "VAV discharge (°F)", "vav_inlet_t": "Duct inlet from AHU (°F)", "wx_oa_t": "Open-Meteo OAT (°F)",
    "oa_t": "OAT (°F)", "sat": "SAT (°F)", "sat_sp": "SAT SP (°F)", "mat": "MAT (°F)", "rat": "RAT (°F)",
    "duct_static": "Duct static (in.w.c.)", "duct_static_sp": "Duct static SP (in.w.c.)",
    "clg_valve_pct": "Cooling valve (%)", "htg_valve_pct": "Heating valve (%)", "oa_damper_pct": "OA damper (%)",
    "chw_supply_t": "CHWS (°F)", "chw_return_t": "CHWR (°F)", "chw_supply_t_sp": "CHWS SP (°F)",
    "chw_flow": "CHW flow (gpm)", "chw_dp": "CHW DP", "chw_dp_sp": "CHW DP SP",
    "hw_supply_t": "HWS (°F)", "hw_return_t": "HWR (°F)", "oa_h": "OA RH (%)",
    "clg_coil_enter_t": "Clg coil enter (°F)", "clg_coil_leave_t": "Clg coil leave (°F)",
    "htg_coil_enter_t": "Htg coil enter (°F)", "htg_coil_leave_t": "Htg coil leave (°F)",
    "preheat_leave_t": "Preheat leave (°F)", "wind_speed": "Wind (mph)", "wind_gust": "Gust (mph)",
}
# signal role -> its setpoint role; the pair shares one chart panel (e.g. SAT vs SAT SP)
_PAIR_SP = {
    "sat": "sat_sp", "zone_t": "zone_t_sp", "zone_flow": "min_flow_sp",
    "duct_static": "duct_static_sp", "chw_supply_t": "chw_supply_t_sp", "chw_dp": "chw_dp_sp",
    "vav_disch_t": "vav_inlet_t", "oa_t": "wx_oa_t",
}


def _panelize(roles: list[str]) -> list[list[str]]:
    """Group signal roles into chart panels, pairing a signal with its setpoint."""
    placed: set[str] = set()
    panels: list[list[str]] = []
    for r in roles:
        if r in placed:
            continue
        grp = [r]
        placed.add(r)
        sp = _PAIR_SP.get(r)
        if sp and sp in roles:
            grp.append(sp)
            placed.add(sp)
        panels.append(grp)
    return panels


def _col_values(series: pd.Series, sl: slice) -> list:
    col = pd.to_numeric(series, errors="coerce").iloc[sl]
    return [None if pd.isna(v) else round(float(v), 3) for v in col]


def equipment_series(equipment_id: str, kind: str, *, resolver=None, weather: pd.DataFrame | None = None,
                     params_by_rule: dict[str, dict] | None = None, rule_ids: list[str] | None = None,
                     max_points: int = 500) -> dict[str, Any]:
    """Per-applicable-rule chart data: downsampled signal traces + confirmed fault mask.

    Each rule returns ``signals`` (grouped into panels via ``panel`` index) and a 0/1
    ``fault`` list aligned to the shared ``timestamps``. Kept lightweight so the UI can
    fetch it lazily (e.g. when a VAV row is expanded).
    """
    if resolver is None:
        from haystack_rdf.resolver import get_resolver

        resolver = get_resolver()
    if weather is None:
        weather = load_weather(resolver)
    params_by_rule = params_by_rule or {}

    payload = json.dumps({"p": params_by_rule, "r": sorted(rule_ids) if rule_ids else None,
                          "m": max_points}, sort_keys=True, default=str)
    ckey = hashlib.sha256(f"{equipment_id}|{kind}|{_data_token()}|{payload}".encode()).hexdigest()
    with _RESULT_LOCK:
        cached = _SERIES_CACHE.get(ckey)
    if cached is not None:
        return cached
    disk = _disk_get(ckey)
    if disk is not None:
        with _RESULT_LOCK:
            _SERIES_CACHE[ckey] = disk
        return disk

    d, resolved, poll, wx = build_logical_frame(equipment_id, kind, resolver, weather)
    n = len(d)
    step = 1 if n <= max_points else int(np.ceil(n / max_points))
    sl = slice(None, None, step)

    timestamps: list[str] = []
    if "timestamp" in d.columns:
        timestamps = [t.isoformat() for t in pd.to_datetime(d["timestamp"]).iloc[sl]]

    want = set(rule_ids) if rule_ids else None
    rules_out: list[dict[str, Any]] = []
    for rule in cb.rules_for_kind(kind):
        if want and rule.id not in want:
            continue
        res = run_rule(rule, d, resolved, poll, params_by_rule.get(rule.id, {}), wx)
        if not res.get("applicable"):
            continue

        if rule.sensor_sweep:
            base = [r for r in cb.SWEEP_SENSOR_ROLES if r in d.columns and d[r].notna().any()][:5]
            panels = [[r] for r in base]
        else:
            roles = [r for r in rule.required_roles if r in d.columns and d[r].notna().any()]
            panels = _panelize(roles)

        signals: list[dict[str, Any]] = []
        for pi, grp in enumerate(panels[:4]):
            for role in grp:
                signals.append({
                    "role": role, "label": _ROLE_LABEL.get(role, role), "panel": pi,
                    "values": _col_values(d[role], sl),
                })

        fault = res.get("fault_series")
        fault_list = [int(bool(x)) for x in fault.iloc[sl]] if fault is not None else []
        rules_out.append({
            "id": rule.id, "title": rule.title, "family": rule.family,
            "fault_hours": res.get("fault_hours", 0.0), "fault_pct": res.get("fault_pct", 0.0),
            "signals": signals, "fault": fault_list,
        })

    out = {"equipment_id": equipment_id, "kind": kind, "timestamps": timestamps, "rules": rules_out}
    with _RESULT_LOCK:
        _SERIES_CACHE[ckey] = out
    _disk_put(ckey, out)
    return out


def _rule_signals(rule: cb.CookbookRule, d: pd.DataFrame, sl: slice) -> list[dict[str, Any]]:
    if rule.sensor_sweep:
        panels = [[r] for r in cb.SWEEP_SENSOR_ROLES if r in d.columns and d[r].notna().any()][:5]
    else:
        roles = [r for r in rule.required_roles if r in d.columns and d[r].notna().any()]
        panels = _panelize(roles)
    signals: list[dict[str, Any]] = []
    for pi, grp in enumerate(panels[:4]):
        for role in grp:
            signals.append({
                "role": role, "label": _ROLE_LABEL.get(role, role), "panel": pi,
                "values": _col_values(d[role], sl),
            })
    return signals


def equipment_view(equipment_id: str, kind: str, *, resolver=None, weather: pd.DataFrame | None = None,
                   params_by_rule: dict[str, dict] | None = None, max_points: int = 500) -> dict[str, Any]:
    """Single-pass equipment payload: every rule's card metadata + sliders, plus downsampled
    chart signals and the confirmed fault series for applicable rules. One compute, one round trip.
    """
    if resolver is None:
        from haystack_rdf.resolver import get_resolver

        resolver = get_resolver()
    if weather is None:
        weather = load_weather(resolver)
    params_by_rule = params_by_rule or {}

    payload = json.dumps({"p": params_by_rule, "m": max_points, "v": 2}, sort_keys=True, default=str)
    ckey = hashlib.sha256(f"view|{equipment_id}|{kind}|{_data_token()}|{payload}".encode()).hexdigest()
    with _RESULT_LOCK:
        cached = _SERIES_CACHE.get(ckey)
    if cached is not None:
        return cached
    disk = _disk_get(ckey)
    if disk is not None:
        with _RESULT_LOCK:
            _SERIES_CACHE[ckey] = disk
        return disk

    d, resolved, poll, wx = build_logical_frame(equipment_id, kind, resolver, weather)
    n = len(d)
    step = 1 if n <= max_points else int(np.ceil(n / max_points))
    sl = slice(None, None, step)
    timestamps: list[str] = []
    if "timestamp" in d.columns:
        timestamps = [t.isoformat() for t in pd.to_datetime(d["timestamp"]).iloc[sl]]

    rules_out: list[dict[str, Any]] = []
    for rule in cb.rules_for_kind(kind):
        res = run_rule(rule, d, resolved, poll, params_by_rule.get(rule.id, {}), wx)
        fault = res.pop("fault_series", None)
        if res.get("applicable"):
            res["signals"] = _rule_signals(rule, d, sl)
            res["fault"] = [int(bool(x)) for x in fault.iloc[sl]] if fault is not None else []
        else:
            res["signals"] = []
            res["fault"] = []
        rules_out.append(res)

    applicable = [r for r in rules_out if r.get("applicable")]
    out = {
        "equipment_id": equipment_id, "kind": kind, "poll_seconds": poll,
        "weather_available": wx, "timestamps": timestamps,
        "resolved_roles": {k: v for k, v in resolved.items() if v},
        "rules": rules_out, "n_rules": len(rules_out), "n_applicable": len(applicable),
        "total_fault_hours": round(sum(r.get("fault_hours", 0.0) for r in applicable), 1),
    }
    with _RESULT_LOCK:
        _SERIES_CACHE[ckey] = out
    _disk_put(ckey, out)
    return out


def _natkey(s: str) -> list:
    """Natural sort key so VAV_2 < VAV_10 < VAV_100 (not lexical)."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", str(s))]


def page_targets(page_id: str, resolver=None, vav_limit: int = 12) -> list[tuple[str, str]]:
    """Map a dashboard page id -> [(equipment_id, cookbook_kind), ...]."""
    if resolver is None:
        from haystack_rdf.resolver import get_resolver

        resolver = get_resolver()

    def _chillers():
        return sorted((e["id"] for e in resolver.list_equipment(haystack_tag="chiller")), key=_natkey)

    def _boilers():
        return sorted((e["id"] for e in resolver.list_equipment() if "BOILER" in e["id"].upper()), key=_natkey)

    def _vavs():
        try:
            return sorted((e["id"] for e in resolver.list_equipment(haystack_tag="vav")), key=_natkey)
        except Exception:
            return []

    # AHU pages resolve to a single AHU via the page registry
    try:
        from page_registry import get_page

        pg = get_page(page_id)
    except Exception:
        pg = None
    if pg is not None and getattr(pg, "kind", "") == "ahu" and pg.equipment_ids:
        return [(pg.equipment_ids[0], "ahu")]

    if page_id in ("economizer", "airside"):
        return [(e, "ahu") for e in sorted(resolver.list_ahus(), key=_natkey)]
    if page_id in ("chiller_plant", "central_plant"):
        return [(e, "chiller") for e in _chillers()]
    if page_id == "boiler_plant":
        return [(e, "boiler") for e in _boilers()]
    if page_id == "weather":
        return [("WEATHER", "weather")]
    if page_id in ("vav", "vav_boxes", "zones"):
        vavs = _vavs()[: max(1, vav_limit)]
        return [(e, "vav") for e in vavs]
    return []


def run_equipment(equipment_id: str, kind: str, *, resolver=None, weather: pd.DataFrame | None = None,
                  params_by_rule: dict[str, dict] | None = None, include_series: bool = False) -> dict[str, Any]:
    if resolver is None:
        from haystack_rdf.resolver import get_resolver

        resolver = get_resolver()
    if weather is None:
        weather = load_weather(resolver)
    params_by_rule = params_by_rule or {}

    d, resolved, poll, wx_avail = build_logical_frame(equipment_id, kind, resolver, weather)
    rules_out = []
    for rule in cb.rules_for_kind(kind):
        params = params_by_rule.get(rule.id, {})
        res = run_rule(rule, d, resolved, poll, params, wx_avail)
        if not include_series:
            res.pop("fault_series", None)
        rules_out.append(res)

    applicable = [r for r in rules_out if r.get("applicable")]
    return {
        "equipment_id": equipment_id,
        "kind": kind,
        "poll_seconds": poll,
        "weather_available": wx_avail,
        "resolved_roles": {k: v for k, v in resolved.items() if v},
        "rules": rules_out,
        "n_rules": len(rules_out),
        "n_applicable": len(applicable),
        "total_fault_hours": round(sum(r.get("fault_hours", 0.0) for r in applicable), 1),
    }


def run_page(page_id: str, *, params_by_rule: dict[str, dict] | None = None,
             resolver=None, vav_limit: int = 12, use_cache: bool = True) -> dict[str, Any]:
    """Run every applicable cookbook rule for all equipment mapped to ``page_id``.

    Results are memoized per (page, params, data version); a revisit with the same
    sliders returns instantly instead of recomputing every rule.
    """
    key = _cache_key(page_id, params_by_rule, vav_limit)
    disk_key = f"page|{key[0]}|{key[1]}"
    if use_cache:
        with _RESULT_LOCK:
            hit = _RESULT_CACHE.get(key)
        if hit is not None:
            return {**hit, "cached": True}
        disk = _disk_get(disk_key)
        if disk is not None:
            with _RESULT_LOCK:
                _RESULT_CACHE[key] = disk
            return {**disk, "cached": True, "disk": True}

    if resolver is None:
        from haystack_rdf.resolver import get_resolver

        resolver = get_resolver()
    weather = load_weather(resolver)
    targets = page_targets(page_id, resolver, vav_limit=vav_limit)
    equipment = []
    for eq_id, kind in targets:
        try:
            equipment.append(run_equipment(
                eq_id, kind, resolver=resolver, weather=weather,
                params_by_rule=params_by_rule,
            ))
        except Exception as exc:  # keep the page resilient
            equipment.append({
                "equipment_id": eq_id, "kind": kind, "rules": [],
                "n_rules": 0, "n_applicable": 0, "total_fault_hours": 0.0,
                "error": f"{type(exc).__name__}: {exc}",
            })
    result = {
        "page_id": page_id,
        "weather_available": bool(weather is not None and "wx_oa_dewpoint" in getattr(weather, "columns", [])),
        "equipment": equipment,
        "n_equipment": len(equipment),
        "cached": False,
    }
    with _RESULT_LOCK:
        _RESULT_CACHE[key] = result
    _disk_put(disk_key, result)
    return result
