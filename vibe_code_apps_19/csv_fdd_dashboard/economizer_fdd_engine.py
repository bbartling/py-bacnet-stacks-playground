"""
AHU economizer FDD engine — deterministic rules for real BAS time-series.
Production diagnostics for RCx; synthetic fixtures only in tests.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from sensor_qa_engine import run_ahu_sensor_qa, sensor_results_summary

ROOT = Path(__file__).resolve().parent
MAPPING_PATH = ROOT / "economizer_point_mapping.json"


def _default_poll_seconds() -> int:
    import sys

    app19 = ROOT.parent
    if str(app19) not in sys.path:
        sys.path.insert(0, str(app19))
    try:
        from shared.data_config import get_config

        return get_config().poll_seconds()
    except Exception:
        return 300


# ---------------------------------------------------------------------------
# Configurable thresholds (site-tunable)
# ---------------------------------------------------------------------------
DEFAULT_PARAMS = {
    "poll_seconds": _default_poll_seconds(),
    "confirm_minutes": 15,
    "smooth_minutes": 15,
    "temp_deadband_f": 2.0,
    "damper_deadband_pct": 8.0,
    "mat_residual_db_f": 2.5,
    "temp_min_f": -40.0,
    "temp_max_f": 140.0,
    "flatline_window_samples": 16,
    "flatline_tol_f": 0.10,
    "oat_rat_min_delta_f": 5.0,
    "economizer_high_limit_f": 75.0,
    "economizer_low_limit_f": 35.0,
    "free_cool_dp_max_f": 60.0,
    "free_cool_oat_avail_f": 72.0,
    "oat_favorable_delta_f": 3.0,
    "fan_on_pct": 5.0,
    "cooling_active_pct": 20.0,
    "oa_max_economizer_pct": 95.0,
    "oa_min_expected_pct": 20.0,
    "damper_stuck_tol_pct": 5.0,
    "hunting_reversals_per_hour": 6,
    "hunting_p2p_pct": 10.0,
    "weather_fault_f": 5.0,
    "gap_max_samples": 4,
}


@dataclass
class FaultResult:
    ahu_id: str
    fault_code: str
    fault_name: str
    status: str  # normal, warning, fault, not_evaluated
    confidence: str  # low, medium, high
    severity: str  # low, medium, high, critical
    first_seen: str | None
    last_seen: str | None
    total_fault_minutes: float
    affected_samples: int
    required_points_present: bool
    missing_points: list[str] = field(default_factory=list)
    evidence_summary: str = ""
    likely_causes: list[str] = field(default_factory=list)
    recommended_actions: list[str] = field(default_factory=list)
    rule_parameters_used: dict = field(default_factory=dict)
    notes_for_rcx_report: str = ""
    sql_rule_id: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def load_point_mapping() -> dict:
    with open(MAPPING_PATH, encoding="utf-8") as f:
        return json.load(f)


def resolve_columns(ahu_id: str, df: pd.DataFrame) -> tuple[dict[str, str | None], list[str]]:
    """Map logical points to dataframe columns via Haystack SPARQL only."""
    from haystack_rdf.resolver import get_resolver

    mapping_doc = load_point_mapping()
    logical_required = [
        k for k, v in mapping_doc["logical_points"].items()
        if v["role"] == "required"
    ]
    all_logical = list(
        dict.fromkeys(
            logical_required
            + list((mapping_doc["ahu_mappings"].get(ahu_id) or {}).keys())
        )
    )

    resolver = get_resolver()
    haystack_map = resolver.resolve_mapping(ahu_id, all_logical)

    resolved: dict[str, str | None] = {}
    missing: list[str] = []
    for logical in logical_required:
        col = haystack_map.get(logical)
        if logical == "timestamp":
            if "timestamp" in df.columns:
                resolved[logical] = "timestamp"
            elif col and col in df.columns:
                resolved[logical] = col
            elif "timestamp_utc" in df.columns:
                resolved[logical] = "timestamp_utc"
            else:
                resolved[logical] = None
                missing.append(logical)
            continue
        if col is None or col not in df.columns:
            resolved[logical] = None
            missing.append(logical)
        else:
            resolved[logical] = col
    for logical in all_logical:
        if logical not in resolved:
            col = haystack_map.get(logical)
            resolved[logical] = col if col and col in df.columns else None
    return resolved, missing


def is_occupied(ts: pd.Series, tz: str = "America/Chicago") -> pd.Series:
    local = ts.dt.tz_convert(tz)
    dow = local.dt.dayofweek
    t = local.dt.time
    wd = (dow < 5) & (t >= time(6, 0)) & (t < time(17, 0))
    sat = (dow == 5) & (t >= time(7, 0)) & (t < time(14, 0))
    return wd | sat


def norm_pct(s: pd.Series) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    return pd.Series(np.where(x > 1.0, x / 100.0, x), index=s.index)


def confirm_persist(raw: pd.Series, n_samples: int) -> pd.Series:
    raw = raw.fillna(False).astype(bool)
    groups = (raw != raw.shift()).cumsum()
    streak = raw.groupby(groups).cumcount() + 1
    return raw & (streak >= n_samples)


def flatline_mask(s: pd.Series, window: int, tol: float) -> pd.Series:
    rmin = s.rolling(window, min_periods=window).min()
    rmax = s.rolling(window, min_periods=window).max()
    return s.notna() & ((rmax - rmin) <= tol)


def prep_ahu_frame(
    df: pd.DataFrame,
    cols: dict[str, str | None],
    params: dict,
    weather_oat: pd.Series | None = None,
    weather_dewpoint: pd.Series | None = None,
    tz: str = "America/Chicago",
) -> pd.DataFrame:
    """Preprocess: sort, dedupe, quality flags, derived features."""
    p = {**DEFAULT_PARAMS, **params}
    confirm_n = max(1, int(round(p["confirm_minutes"] * 60 / p["poll_seconds"])))
    smooth_n = max(1, int(round(p["smooth_minutes"] * 60 / p["poll_seconds"])))

    d = df.copy()
    d = d.sort_values("timestamp").drop_duplicates(subset=["timestamp"], keep="last")
    d["timestamp_local"] = d["timestamp"].dt.tz_convert(tz)
    d["occupied"] = is_occupied(d["timestamp"], tz)

    def num(logical: str) -> pd.Series:
        c = cols.get(logical)
        return pd.to_numeric(d[c], errors="coerce") if c else pd.Series(np.nan, index=d.index)

    d["fan_pct"] = norm_pct(num("fan_cmd"))
    d["fan_on"] = d["fan_pct"] > (p["fan_on_pct"] / 100.0)
    if cols.get("fan_status"):
        st = pd.to_numeric(d[cols["fan_status"]], errors="coerce").fillna(0)
        d["fan_on"] = d["fan_on"] | (st > 0)

    for alias, logical in [
        ("oat", "oat"), ("rat", "rat"), ("mat", "mat"), ("sat", "sat"), ("sat_sp", "sat_sp"),
    ]:
        d[alias] = num(logical)

    d["oad_cmd"] = norm_pct(num("oa_damper_cmd"))
    d["oad_pos"] = norm_pct(num("oa_damper_pos")) if cols.get("oa_damper_pos") else d["oad_cmd"]
    d["oad_min"] = norm_pct(num("oa_min_pct")) if cols.get("oa_min_pct") else pd.Series(
        p["oa_min_expected_pct"] / 100.0, index=d.index
    )
    d["clg"] = norm_pct(num("cooling_cmd"))
    d["htg"] = pd.Series(0.0, index=d.index)  # Building 100: no heating coil in export

    # Smooth analogs
    for c in ("oat", "rat", "mat", "sat", "oad_cmd", "oad_pos", "clg"):
        d[f"{c}_s"] = d[c].rolling(smooth_n, min_periods=1, center=True).mean()

    # Gap detection
    dt_sec = d["timestamp"].diff().dt.total_seconds()
    d["q_gap"] = dt_sec > (p["poll_seconds"] * p["gap_max_samples"])

    # Stable operation: fan on, occupied, no large gap
    d["stable"] = d["fan_on"] & d["occupied"] & ~d["q_gap"]

    # Cooling load proxy
    sat_err = p["temp_deadband_f"]
    d["cooling_load"] = d["stable"] & (
        (d["sat_s"] > d["sat_sp"] + sat_err)
        | (d["clg_s"] > p["cooling_active_pct"] / 100.0)
    )

    # Open-Meteo economizer suitability (dew point + dry bulb reference — not BAS OAT)
    if weather_oat is not None:
        w_oat = weather_oat.reset_index()
        w_oat.columns = ["timestamp", "web_oat"]
        w_oat = w_oat.drop_duplicates(subset=["timestamp"], keep="last")
        d = d.merge(w_oat, on="timestamp", how="left")
    else:
        d["web_oat"] = np.nan

    if weather_dewpoint is not None:
        w_dp = weather_dewpoint.reset_index()
        w_dp.columns = ["timestamp", "web_dewpoint"]
        w_dp = w_dp.drop_duplicates(subset=["timestamp"], keep="last")
        d = d.merge(w_dp, on="timestamp", how="left")
    else:
        d["web_dewpoint"] = np.nan

    web_oat = pd.to_numeric(d["web_oat"], errors="coerce")
    web_dp = pd.to_numeric(d["web_dewpoint"], errors="coerce")
    d["web_oat"] = web_oat
    d["web_dewpoint"] = web_dp

    d["econ_ok_meteo"] = (
        d["stable"]
        & web_oat.notna()
        & web_dp.notna()
        & (web_dp < p["free_cool_dp_max_f"])
        & (web_oat < p["free_cool_oat_avail_f"])
        & (web_oat >= p["economizer_low_limit_f"])
    )

    # Legacy alias used by damper stuck-open / excess-OA helpers
    d["econ_suitable_drybulb"] = d["econ_ok_meteo"]

    # Enthalpy not evaluated — humidity from Open-Meteo used for suitability only
    d["econ_suitable_enthalpy"] = pd.Series(False, index=d.index)

    d["econ_should_enable"] = d["econ_ok_meteo"] & d["cooling_load"]

    oa_full = p["oa_max_economizer_pct"] / 100.0

    rat_oat = (d["oat_s"] - d["rat_s"]).abs()
    d["oa_fraction_est"] = np.where(
        rat_oat > p["oat_rat_min_delta_f"],
        ((d["mat_s"] - d["rat_s"]) / (d["oat_s"] - d["rat_s"])).clip(0, 1),
        np.nan,
    )

    d["mech_cool_free_cool_avail"] = (
        d["econ_ok_meteo"]
        & (d["clg_s"] > p["cooling_active_pct"] / 100.0)
        & (d["oad_pos_s"] < oa_full - p["damper_deadband_pct"] / 100.0)
    )

    d["mat_below_env"] = d["stable"] & d["mat_s"].notna() & d["oat_s"].notna() & d["rat_s"].notna() & (
        d["mat_s"] < np.minimum(d["oat_s"], d["rat_s"]) - p["mat_residual_db_f"]
    )
    d["mat_above_env"] = d["stable"] & d["mat_s"].notna() & d["oat_s"].notna() & d["rat_s"].notna() & (
        d["mat_s"] > np.maximum(d["oat_s"], d["rat_s"]) + p["mat_residual_db_f"]
    )

    if "web_oat" in d.columns and d["web_oat"].notna().any():
        d["weather_oat"] = d["web_oat"]
        d["weather_oat_fault"] = confirm_persist(
            (d["oat_s"] - d["weather_oat"]).abs() > p["weather_fault_f"], confirm_n
        )
    else:
        d["weather_oat"] = np.nan
        d["weather_oat_fault"] = False

    d["_confirm_n"] = confirm_n
    d["_params"] = [p] * len(d)
    return d


def _rollup(mask: pd.Series, d: pd.DataFrame, poll_seconds: int) -> tuple[float, int, str | None, str | None]:
    m = mask.fillna(False)
    if not m.any():
        return 0.0, 0, None, None
    idx = d.index[m]
    ts = d.loc[idx, "timestamp_local"]
    return (
        float(m.sum()) * poll_seconds / 60.0,
        int(m.sum()),
        str(ts.min())[:19] if len(ts) else None,
        str(ts.max())[:19] if len(ts) else None,
    )


def _not_evaluated(ahu_id: str, code: str, name: str, missing: list[str]) -> FaultResult:
    return FaultResult(
        ahu_id=ahu_id,
        fault_code=code,
        fault_name=name,
        status="not_evaluated",
        confidence="low",
        severity="low",
        first_seen=None,
        last_seen=None,
        total_fault_minutes=0,
        affected_samples=0,
        required_points_present=False,
        missing_points=missing,
        evidence_summary=f"Required points missing: {', '.join(missing)}",
        recommended_actions=["Export missing BAS points before evaluating this rule."],
        sql_rule_id=code,
    )


def run_diagnostics(
    ahu_id: str,
    df: pd.DataFrame,
    weather_df: pd.DataFrame | None = None,
    params: dict | None = None,
) -> tuple[pd.DataFrame, list[FaultResult], dict[str, Any]]:
    """
    Run full economizer diagnostic suite.
    Returns: enriched timeseries, fault results list, metadata dict.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    df = df.copy()
    if "timestamp" not in df.columns:
        ts_col = None
        for c in ("timestamp_utc", "timestamp_local"):
            if c in df.columns:
                ts_col = c
                break
        if ts_col:
            df["timestamp"] = pd.to_datetime(df[ts_col], utc=True)
    cols, missing_required = resolve_columns(ahu_id, df)
    meta = {
        "ahu_id": ahu_id,
        "columns_mapped": {k: v for k, v in cols.items() if v},
        "missing_required": missing_required,
        "point_mapping_notes": load_point_mapping()["ahu_mappings"].get(ahu_id, {}).get("notes", ""),
        "params": p,
    }

    if missing_required:
        results = [
            _not_evaluated(ahu_id, "ECON_SENSOR_FAULT", "Air temperature sensor fault", missing_required),
            _not_evaluated(ahu_id, "ECON_NOT_ECONOMIZING_WHEN_SHOULD", "Not economizing when should", missing_required),
            _not_evaluated(ahu_id, "ECON_ECONOMIZING_WHEN_SHOULD_NOT", "Economizing when should not", missing_required),
            _not_evaluated(ahu_id, "ECON_DAMPER_NOT_MODULATING", "Damper not modulating", missing_required),
            _not_evaluated(ahu_id, "ECON_MECH_COOLING_DURING_FREE_COOLING", "Mechanical cooling during free cooling", missing_required),
        ]
        return df, results, meta

    ts_col = cols.get("timestamp") or "timestamp"
    if ts_col != "timestamp":
        df["timestamp"] = pd.to_datetime(df[ts_col], utc=True)

    weather_oat = None
    weather_dp = None
    if weather_df is not None and "timestamp" in weather_df.columns:
        w = weather_df.set_index("timestamp")
        ts_idx = df.set_index("timestamp").index
        if "dry_bulb_f" in w.columns:
            weather_oat = w["dry_bulb_f"].reindex(ts_idx)
        if "dew_point_f" in w.columns:
            weather_dp = w["dew_point_f"].reindex(ts_idx)

    d = prep_ahu_frame(df, cols, p, weather_oat=weather_oat, weather_dewpoint=weather_dp)
    confirm_n = d["_confirm_n"].iloc[0]
    poll = p["poll_seconds"]
    d, sensor_qa_detail = run_ahu_sensor_qa(d, poll_seconds=poll, confirm_n=confirm_n)
    results: list[FaultResult] = []

    # --- A. Sensor faults (4-level QA + weather reference) ---
    weather_fault = d.get("weather_oat_fault", pd.Series(False, index=d.index))
    if isinstance(weather_fault, bool):
        weather_fault = pd.Series(weather_fault, index=d.index)
    sensor_raw = (
        d.get("sensor_l1_any", pd.Series(False, index=d.index))
        | d.get("sensor_l3_any", pd.Series(False, index=d.index))
        | weather_fault
    )
    sensor_conf = confirm_persist(sensor_raw.fillna(False), confirm_n)
    d["fault_econ_sensor"] = sensor_conf
    mins, n, t0, t1 = _rollup(sensor_conf, d, poll)

    l1_m = _rollup(confirm_persist(d.get("sensor_l1_any", False), confirm_n), d, poll)[0]
    l2_m = _rollup(confirm_persist(d.get("sensor_l2_any", False), confirm_n), d, poll)[0]
    l3_m = _rollup(confirm_persist(d.get("sensor_l3_any", False), confirm_n), d, poll)[0]
    l4_m = _rollup(confirm_persist(d.get("sensor_l4_any", False), confirm_n), d, poll)[0]
    wx_m = _rollup(confirm_persist(weather_fault, confirm_n), d, poll)[0]

    results.append(FaultResult(
        ahu_id=ahu_id, fault_code="ECON_SENSOR_FAULT", fault_name="Air temperature sensor fault (rollup)",
        status="fault" if n > 0 else "normal",
        confidence="high" if mins > 60 else ("medium" if n > 0 else "high"),
        severity="high" if mins > 120 else ("medium" if n > 0 else "low"),
        first_seen=t0, last_seen=t1, total_fault_minutes=mins, affected_samples=n,
        required_points_present=True, missing_points=[],
        evidence_summary=(
            f"L1 hard range: {l1_m:.0f} min; L2 ROC/spike: {l2_m:.0f} min; "
            f"L3 flatline: {l3_m:.0f} min; L4 plausibility: {l4_m:.0f} min; weather Δ: {wx_m:.0f} min."
        ),
        likely_causes=["Failed or miscalibrated OAT/RAT/MAT/SAT", "Stuck sensor", "Bad sensor location/stratification"],
        recommended_actions=["Verify sensor readings in field", "Compare OAT to independent weather station", "Check MAT sensor location"],
        rule_parameters_used=p, sql_rule_id="ECON_SENSOR_FAULT",
        notes_for_rcx_report="Downstream economizer faults suppressed when L1/L3/L4 sensor fault active. See granular SENSOR_* codes.",
    ))

    # Granular per-point sensor fault results
    for sq in sensor_qa_detail:
        if not sq.flag_column or sq.flag_column not in d.columns:
            continue
        sm, sn, st0, st1 = _rollup(confirm_persist(d[sq.flag_column], confirm_n), d, poll)
        if sn == 0:
            continue
        results.append(FaultResult(
            ahu_id=ahu_id,
            fault_code=sq.fault_code,
            fault_name=sq.fault_name,
            status=sq.status,
            confidence="high" if sq.level == "L1" else "medium",
            severity="high" if sq.level in ("L1", "L4") and sm > 30 else ("medium" if sn > 0 else "low"),
            first_seen=st0, last_seen=st1,
            total_fault_minutes=sm, affected_samples=sn,
            required_points_present=True,
            evidence_summary=sq.evidence,
            likely_causes=["Sensor miscalibration", "Failed sensor", "BAS mapping error"],
            recommended_actions=[f"Field-check {sq.point.upper()} sensor against reference"],
            rule_parameters_used={"hard_min": sq.hard_min, "hard_max": sq.hard_max, "max_roc_per_hour": sq.max_roc_per_hour},
            sql_rule_id=sq.fault_code,
        ))

    sensor_active = (
        confirm_persist(d.get("sensor_l1_any", False), confirm_n)
        | confirm_persist(d.get("sensor_l4_any", False), confirm_n)
        | confirm_persist(weather_fault, confirm_n)
    ).rolling(confirm_n, min_periods=1).max().astype(bool)

    # --- B. Not economizing when should (100% OA expected) ---
    oa_full = p["oa_max_economizer_pct"] / 100.0
    not_econ_raw = (
        d["econ_should_enable"]
        & (d["oad_pos_s"] < oa_full - p["damper_deadband_pct"] / 100.0)
        & ~sensor_active
    )
    not_econ = confirm_persist(not_econ_raw, confirm_n)
    d["fault_not_economizing"] = not_econ
    mins, n, t0, t1 = _rollup(not_econ, d, poll)
    mech_overlap = _rollup(not_econ & d["clg_s"] > 0.2, d, poll)[0]
    sev = "critical" if mech_overlap > 40 else ("high" if mins > 20 else ("medium" if n > 0 else "low"))
    results.append(FaultResult(
        ahu_id=ahu_id, fault_code="ECON_NOT_ECONOMIZING_WHEN_SHOULD", fault_name="Not economizing when should",
        status="fault" if n > 0 else "normal",
        confidence="medium" if sensor_active.any() and n > 0 else ("high" if n > 0 else "high"),
        severity=sev, first_seen=t0, last_seen=t1, total_fault_minutes=mins, affected_samples=n,
        required_points_present=True,
        evidence_summary=(
            f"Open-Meteo economizer OK + cooling load but OA damper below ~{p['oa_max_economizer_pct']:.0f}%: "
            f"{mins:.0f} min. Mech cooling overlap: {mech_overlap:.0f} min."
        ),
        likely_causes=["OA damper stuck closed", "Economizer disabled", "High-limit setpoint too low", "Actuator fault", "Bad OAT/RAT"],
        recommended_actions=["Inspect OA damper linkage", "Verify economizer enable in BAS", "Check high-limit and minimum OA setpoints"],
        rule_parameters_used=p, sql_rule_id="ECON_NOT_ECONOMIZING_WHEN_SHOULD",
    ))

    # --- C. Economizing when should not (ECON-2 — Open-Meteo unfavorable, damper above minimum OA) ---
    econ_when_not_raw = (
        d["stable"]
        & ~d["econ_ok_meteo"]
        & (d["oad_pos_s"] > d["oad_min"] + p["damper_deadband_pct"] / 100.0)
        & ~sensor_active
    )
    econ_when_not = confirm_persist(econ_when_not_raw, confirm_n)
    d["fault_economizing_when_not"] = econ_when_not
    mins, n, t0, t1 = _rollup(econ_when_not, d, poll)
    results.append(FaultResult(
        ahu_id=ahu_id, fault_code="ECON_ECONOMIZING_WHEN_SHOULD_NOT", fault_name="Economizing when should not",
        status="fault" if n > 0 else "normal",
        confidence="high" if n > 0 else "high",
        severity="high" if mins > 30 else ("medium" if n > 0 else "low"),
        first_seen=t0, last_seen=t1, total_fault_minutes=mins, affected_samples=n,
        required_points_present=True,
        evidence_summary=(
            f"OA damper above ~{p['oa_min_expected_pct']:.0f}% minimum when Open-Meteo economizer not OK "
            f"(DP≥{p['free_cool_dp_max_f']:.0f}°F or OAT≥{p['free_cool_oat_avail_f']:.0f}°F or OAT<{p['economizer_low_limit_f']:.0f}°F): "
            f"{mins:.0f} min."
        ),
        likely_causes=["Damper stuck open", "High-limit too high", "Minimum OA too high", "Sensor bias"],
        recommended_actions=["Verify high/low limit setpoints", "Inspect damper returns to minimum", "Check for actuator leakage"],
        rule_parameters_used=p, sql_rule_id="ECON_ECONOMIZING_WHEN_SHOULD_NOT",
    ))

    # --- D. Damper not modulating / stuck ---
    oad_range = d["oad_cmd"].rolling(p["flatline_window_samples"], min_periods=p["flatline_window_samples"]).max() - \
        d["oad_cmd"].rolling(p["flatline_window_samples"], min_periods=p["flatline_window_samples"]).min()
    cmd_varies = oad_range > p["damper_stuck_tol_pct"] / 100.0
    mat_range = d["mat_s"].rolling(p["flatline_window_samples"], min_periods=p["flatline_window_samples"]).max() - \
        d["mat_s"].rolling(p["flatline_window_samples"], min_periods=p["flatline_window_samples"]).min()
    oat_rat_sep = (d["oat_s"] - d["rat_s"]).abs() > p["oat_rat_min_delta_f"]
    mat_no_response = cmd_varies & (mat_range < 0.5) & oat_rat_sep
    stuck_closed = d["econ_should_enable"] & (d["oad_pos_s"] < 0.05) & ~sensor_active
    stuck_open = (~d["econ_ok_meteo"]) & d["occupied"] & (d["oad_pos_s"] > 0.9) & ~sensor_active
    damper_raw = confirm_persist(mat_no_response, confirm_n) | confirm_persist(stuck_closed, confirm_n) | confirm_persist(stuck_open, confirm_n)
    d["fault_damper"] = damper_raw
    mins, n, t0, t1 = _rollup(damper_raw, d, poll)
    stuck_c_mins = _rollup(confirm_persist(stuck_closed, confirm_n), d, poll)[0]
    stuck_o_mins = _rollup(confirm_persist(stuck_open, confirm_n), d, poll)[0]
    results.append(FaultResult(
        ahu_id=ahu_id, fault_code="ECON_DAMPER_NOT_MODULATING", fault_name="Damper stuck / not modulating",
        status="fault" if n > 0 else "normal",
        confidence="medium",  # cmd-only feedback limitation
        severity="high" if stuck_c_mins > 20 else ("medium" if n > 0 else "low"),
        first_seen=t0, last_seen=t1, total_fault_minutes=mins, affected_samples=n,
        required_points_present=True,
        evidence_summary=f"Stuck closed ~{stuck_c_mins:.0f} min, stuck open ~{stuck_o_mins:.0f} min. Note: no separate damper feedback — command used as proxy.",
        likely_causes=["Actuator/linkage failure", "Mechanical binding", "Pneumatic signal loss"],
        recommended_actions=["Field-verify damper movement vs command", "Install position feedback if missing"],
        rule_parameters_used=p, sql_rule_id="ECON_DAMPER_NOT_MODULATING",
        notes_for_rcx_report="Damper % is command proxy, not measured airflow.",
    ))

    if stuck_o_mins > 10:
        m, ns, a, b = _rollup(confirm_persist(stuck_open, confirm_n), d, poll)
        results.append(FaultResult(
            ahu_id=ahu_id, fault_code="ECON_DAMPER_STUCK_OPEN", fault_name="OA damper stuck open",
            status="fault", confidence="medium", severity="high",
            first_seen=a, last_seen=b, total_fault_minutes=m, affected_samples=ns,
            required_points_present=True,
            evidence_summary=f"Damper command >90% when economizer not suitable: {m:.0f} min.",
            likely_causes=["Actuator stuck", "Linkage broken", "Minimum OA set too high"],
            recommended_actions=["Manual damper exercise", "Replace actuator or repair linkage"],
            rule_parameters_used=p, sql_rule_id="ECON_DAMPER_STUCK_OPEN",
        ))
    if stuck_c_mins > 10:
        m, ns, a, b = _rollup(confirm_persist(stuck_closed, confirm_n), d, poll)
        results.append(FaultResult(
            ahu_id=ahu_id, fault_code="ECON_DAMPER_STUCK_CLOSED", fault_name="OA damper stuck closed",
            status="fault", confidence="medium", severity="high",
            first_seen=a, last_seen=b, total_fault_minutes=m, affected_samples=ns,
            required_points_present=True,
            evidence_summary=f"Damper near 0% during favorable economizer conditions: {m:.0f} min.",
            likely_causes=["Actuator failed", "Damper frozen shut", "Economizer interlock"],
            recommended_actions=["Inspect intake damper", "Verify economizer sequence enabled"],
            rule_parameters_used=p, sql_rule_id="ECON_DAMPER_STUCK_CLOSED",
        ))

    # --- E. Excess OA ---
    excess_oa_raw = (
        d["stable"] & ~d["econ_ok_meteo"]
        & (d["oad_pos_s"] > d["oad_min"] + p["damper_deadband_pct"] / 100.0)
        & ~sensor_active
    )
    excess_oa = confirm_persist(excess_oa_raw, confirm_n)
    d["fault_excess_oa"] = excess_oa
    mins, n, t0, t1 = _rollup(excess_oa, d, poll)
    results.append(FaultResult(
        ahu_id=ahu_id, fault_code="ECON_EXCESS_OA", fault_name="Excess outdoor air",
        status="warning" if n > 0 else "normal",
        confidence="medium", severity="medium" if mins > 20 else "low",
        first_seen=t0, last_seen=t1, total_fault_minutes=mins, affected_samples=n,
        required_points_present=True,
        evidence_summary=f"OA above minimum when economizer not suitable: {mins:.0f} min.",
        likely_causes=["Minimum OA too high", "Damper leakage", "Return damper issue"],
        recommended_actions=["Verify minimum OA setpoint", "Check damper seals"],
        rule_parameters_used=p, sql_rule_id="ECON_EXCESS_OA",
    ))

    # --- F. Low OA ventilation risk ---
    low_oa_raw = d["stable"] & (d["oad_pos_s"] < d["oad_min"] - p["damper_deadband_pct"] / 100.0) & ~sensor_active
    low_oa = confirm_persist(low_oa_raw, confirm_n)
    d["fault_low_oa"] = low_oa
    mins, n, t0, t1 = _rollup(low_oa, d, poll)
    results.append(FaultResult(
        ahu_id=ahu_id, fault_code="ECON_LOW_OA_VENTILATION_RISK", fault_name="Low outdoor air / ventilation risk",
        status="warning" if n > 0 else "normal",
        confidence="medium", severity="medium" if mins > 10 else "low",
        first_seen=t0, last_seen=t1, total_fault_minutes=mins, affected_samples=n,
        required_points_present=True,
        evidence_summary=f"OA damper below expected minimum during occupied fan: {mins:.0f} min.",
        likely_causes=["Damper stuck closed", "Minimum OA setpoint too low", "Actuator fault"],
        recommended_actions=["Verify ventilation code minimum OA", "Inspect intake path"],
        rule_parameters_used=p, sql_rule_id="ECON_LOW_OA_VENTILATION_RISK",
        notes_for_rcx_report="IAQ/ventilation risk — not just energy.",
    ))

    # --- G. MAT plausibility (L4 sensor QA) ---
    mat_plaus_raw = d.get("q_mat_l4_envelope", d["mat_below_env"] | d["mat_above_env"])
    mat_plaus = confirm_persist(mat_plaus_raw, confirm_n)
    d["fault_mat_plausibility"] = mat_plaus
    mins, n, t0, t1 = _rollup(mat_plaus, d, poll)
    results.append(FaultResult(
        ahu_id=ahu_id, fault_code="ECON_MAT_PLAUSIBILITY", fault_name="Mixed air temperature plausibility",
        status="fault" if n > 0 else "normal",
        confidence="high" if n > 0 else "high",
        severity="high" if mins > 60 else "low",
        first_seen=t0, last_seen=t1, total_fault_minutes=mins, affected_samples=n,
        required_points_present=True,
        evidence_summary=f"MAT outside OAT/RAT envelope: {mins:.0f} min.",
        likely_causes=["Bad MAT sensor", "Stratification at sensor", "Sensor location"],
        recommended_actions=["Relocate or replace MAT sensor before damper diagnosis"],
        rule_parameters_used=p, sql_rule_id="ECON_MAT_PLAUSIBILITY",
    ))

    # --- H. Mech cooling during free cooling ---
    mech_raw = d["mech_cool_free_cool_avail"] & ~sensor_active
    mech = confirm_persist(mech_raw, confirm_n)
    d["fault_mech_during_free_cool"] = mech
    mins, n, t0, t1 = _rollup(mech, d, poll)
    lost_h = mins
    results.append(FaultResult(
        ahu_id=ahu_id, fault_code="ECON_MECH_COOLING_DURING_FREE_COOLING", fault_name="Mechanical cooling during free cooling",
        status="fault" if n > 0 else "normal",
        confidence="high" if n > 0 else "high",
        severity="critical" if mins > 40 else ("high" if n > 0 else "low"),
        first_seen=t0, last_seen=t1, total_fault_minutes=mins, affected_samples=n,
        required_points_present=True,
        evidence_summary=(
            f"CHW/cooling active while Open-Meteo economizer OK but damper below ~{p['oa_max_economizer_pct']:.0f}%: "
            f"{lost_h:.0f} min lost economizer opportunity."
        ),
        likely_causes=["Economizer not enabled", "Damper stuck", "Sequence prioritizes mechanical cooling"],
        recommended_actions=["Enable/fix economizer sequence", "Reduce mechanical cooling lockouts", "RCx savings: quantify kWh from lost hours"],
        rule_parameters_used=p, sql_rule_id="ECON_MECH_COOLING_DURING_FREE_COOLING",
        notes_for_rcx_report=f"Primary RCx metric: {lost_h:.0f} avoidable mechanical cooling hours.",
    ))

    # Enthalpy — not evaluated
    results.append(FaultResult(
        ahu_id=ahu_id, fault_code="ECON_ENTHALPY_NOT_EVALUATED", fault_name="Enthalpy economizer logic",
        status="not_evaluated", confidence="low", severity="low",
        first_seen=None, last_seen=None, total_fault_minutes=0, affected_samples=0,
        required_points_present=False, missing_points=["oa_humidity", "ra_humidity"],
        evidence_summary="OA/RA humidity or enthalpy points not in BAS export.",
        recommended_actions=["Export OA/RA humidity to enable enthalpy economizer diagnostics."],
        sql_rule_id="ECON_ENTHALPY",
    ))

    meta["lost_economizer_minutes"] = lost_h
    meta["sensor_fault_minutes"] = _rollup(sensor_conf, d, poll)[0]
    meta["sensor_qa_summary"] = sensor_results_summary(sensor_qa_detail).to_dict(orient="records")
    return d, results, meta


def results_to_dataframe(results: list[FaultResult]) -> pd.DataFrame:
    return pd.DataFrame([r.to_dict() for r in results])


def export_fault_timeseries(d: pd.DataFrame, ahu_id: str) -> pd.DataFrame:
    """Export key columns + fault flags for CSV."""
    fault_cols = [c for c in d.columns if c.startswith("fault_")]
    base = [
        "timestamp", "timestamp_local", "occupied", "stable",
        "oat_s", "rat_s", "mat_s", "sat_s", "sat_sp",
        "web_oat", "web_dewpoint", "econ_ok_meteo",
        "oad_cmd", "oad_pos_s", "clg_s", "oa_fraction_est",
        "econ_suitable_drybulb", "econ_should_enable", "cooling_load",
    ]
    sensor_cols = [c for c in d.columns if c.startswith("q_") and ("_l1_" in c or "_l2_" in c or "_l3_" in c or "_l4_" in c)]
    sensor_cols += [c for c in ("sensor_l1_any", "sensor_l2_any", "sensor_l3_any", "sensor_l4_any") if c in d.columns]
    keep = [c for c in base + sensor_cols + fault_cols if c in d.columns]
    out = d[keep].copy()
    out.insert(0, "ahu_id", ahu_id)
    return out
