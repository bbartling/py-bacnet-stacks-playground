"""Open-FDD Pandas cookbook — full rule catalog coded against the Haystack data model.

Every rule mirrors https://bbartling.github.io/open-fdd/rules/cookbook/pandas-cookbook.html
Rules are declarative: each carries the logical point roles it needs, plain-language
(imperial) equation text, tunable slider params, and a pure compute function that
returns a RAW boolean fault mask. The cookbook_engine resolves roles against the data
model, builds a logical frame per equipment, runs applicable rules, and confirms faults.

Fault math stays canonical (°F / in.w.c.); display unit conversion happens in the UI layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Shared helpers (mirror cookbook "Setup & shared helpers")
# ---------------------------------------------------------------------------


def norm_cmd(s: pd.Series | None) -> pd.Series:
    """Normalize a command/position 0–100 → 0–1. Passthrough if already 0–1."""
    if s is None:
        return pd.Series(dtype=float)
    s = pd.to_numeric(s, errors="coerce")
    return s.where(s <= 1.0, s / 100.0)


def as_bool(s: pd.Series | None) -> pd.Series:
    if s is None:
        return pd.Series(dtype=bool)
    num = pd.to_numeric(s, errors="coerce")
    if num.notna().any():
        return num.fillna(0) > 0.5
    return s.fillna(False).astype(bool)


def _f(p: dict, key: str, default: float) -> float:
    try:
        v = p.get(key, default)
        return float(v) if v is not None else float(default)
    except (TypeError, ValueError):
        return float(default)


def _false(index) -> pd.Series:
    return pd.Series(False, index=index)


def flatline_mask(series: pd.Series, tol: float, window: int) -> pd.Series:
    window = max(2, int(window))
    roll_min = series.rolling(window, min_periods=window).min()
    roll_max = series.rolling(window, min_periods=window).max()
    return series.notna() & ((roll_max - roll_min) <= tol)


# ---------------------------------------------------------------------------
# Per-sensor validation limits (imperial primary; from sensor_fault_defaults.json)
# ---------------------------------------------------------------------------

SENSOR_LIMITS: dict[str, dict[str, float]] = {
    # role: hard low, hard high, spike per sample (°F unless noted)
    "oa_t": {"lo": -60.0, "hi": 130.0, "spike": 36.0},
    "rat": {"lo": 40.0, "hi": 100.0, "spike": 12.0},
    "mat": {"lo": -20.0, "hi": 110.0, "spike": 25.0},
    "sat": {"lo": 30.0, "hi": 150.0, "spike": 40.0},
    "zone_t": {"lo": 40.0, "hi": 100.0, "spike": 12.0},
    "chw_supply_t": {"lo": 30.0, "hi": 80.0, "spike": 20.0},
    "chw_return_t": {"lo": 30.0, "hi": 90.0, "spike": 20.0},
    "hw_supply_t": {"lo": 40.0, "hi": 220.0, "spike": 60.0},
    "hw_return_t": {"lo": 40.0, "hi": 220.0, "spike": 60.0},
    "oa_h": {"lo": 0.0, "hi": 100.0, "spike": 25.0},
    "duct_static": {"lo": -1.0, "hi": 8.0, "spike": 2.0},
}

# Sensor roles the validation sweep will check on any equipment (if present)
SWEEP_SENSOR_ROLES = list(SENSOR_LIMITS.keys())

# Flatline/stale detection targets analog temperature & humidity sensors only.
# Pressure points (e.g. duct static) legitimately rest at ~0 when equipment is off,
# so they would false-positive as "stuck" — exclude them from stuck-sensor sweeps.
_NO_FLATLINE_ROLES = {"duct_static"}
FLATLINE_SENSOR_ROLES = [r for r in SWEEP_SENSOR_ROLES if r not in _NO_FLATLINE_ROLES]

# Analog 0–100% (or 0–1) control outputs swept by PID-HUNT-1
CONTROL_OUTPUT_ROLES = [
    "oa_damper_pct",
    "clg_valve_pct",
    "htg_valve_pct",
    "damper_pct",
    "reheat_valve_pct",
    "fan_cmd",
    "control_output_pct",
]


# ---------------------------------------------------------------------------
# Rule model
# ---------------------------------------------------------------------------


@dataclass
class CookbookParam:
    key: str
    label: str
    unit: str
    min: float
    max: float
    step: float
    default: float

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "unit": self.unit,
            "min": self.min,
            "max": self.max,
            "step": self.step,
            "default": self.default,
        }


@dataclass
class CookbookRule:
    id: str
    title: str
    family: str  # sensor | ahu | vav | plant | heatpump | weather | trim
    equipment_kinds: list[str]
    required_roles: list[str]
    equation: str
    compute: Callable[[pd.DataFrame, dict, float], pd.Series]
    params: list[CookbookParam] = field(default_factory=list)
    optional_roles: list[str] = field(default_factory=list)
    confirm_seconds: float = 300.0
    sensor_sweep: bool = False
    control_output_sweep: bool = False

    def defaults(self) -> dict[str, float]:
        return {p.key: p.default for p in self.params}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "family": self.family,
            "equipment_kinds": self.equipment_kinds,
            "required_roles": self.required_roles,
            "optional_roles": self.optional_roles,
            "equation": self.equation,
            "confirm_seconds": self.confirm_seconds,
            "sensor_sweep": self.sensor_sweep,
            "control_output_sweep": self.control_output_sweep,
            "params": [p.to_dict() for p in self.params],
        }


CONFIRM_PARAM = lambda default_min=5.0, mx=60.0: CookbookParam(  # noqa: E731
    "confirm_min", "Fault confirm delay", "min", 0.0, mx, 1.0, default_min
)


# ---------------------------------------------------------------------------
# Sensor validation sweep (SV-1/2/3 range, SV-5 stale, SV-6 flatline, SV-7 spike)
# Applied to EVERY sensor present in the data model for the equipment.
# ---------------------------------------------------------------------------


def _sweep_range(d: pd.DataFrame, p: dict, poll: float) -> pd.Series:
    idx = d.index
    mask = _false(idx)
    for role in SWEEP_SENSOR_ROLES:
        if role not in d.columns:
            continue
        s = pd.to_numeric(d[role], errors="coerce")
        lim = SENSOR_LIMITS[role]
        mask = mask | (s.notna() & ((s < lim["lo"]) | (s > lim["hi"])))
    return mask


def _sweep_flatline(d: pd.DataFrame, p: dict, poll: float) -> pd.Series:
    idx = d.index
    tol = _f(p, "flatline_tol", 0.10)
    hours = _f(p, "flatline_hours", 1.0)
    window = max(2, int(round(hours * 3600 / max(poll, 1))))
    mask = _false(idx)
    for role in FLATLINE_SENSOR_ROLES:
        if role not in d.columns:
            continue
        s = pd.to_numeric(d[role], errors="coerce")
        mask = mask | flatline_mask(s, tol=tol, window=window)
    return mask


def _sweep_spike(d: pd.DataFrame, p: dict, poll: float) -> pd.Series:
    idx = d.index
    scale = _f(p, "spike_scale", 1.0)
    mask = _false(idx)
    for role in SWEEP_SENSOR_ROLES:
        if role not in d.columns:
            continue
        s = pd.to_numeric(d[role], errors="coerce")
        limit = SENSOR_LIMITS[role]["spike"] * scale
        mask = mask | (s.notna() & (s.diff().abs() > limit))
    return mask


def _sweep_stale(d: pd.DataFrame, p: dict, poll: float) -> pd.Series:
    """Flag runs where all sweep sensors are unchanged (no fresh data)."""
    idx = d.index
    hours = _f(p, "stale_hours", 2.0)
    window = max(2, int(round(hours * 3600 / max(poll, 1))))
    present = [r for r in FLATLINE_SENSOR_ROLES if r in d.columns]
    if not present:
        return _false(idx)
    stale = pd.Series(True, index=idx)
    for role in present:
        s = pd.to_numeric(d[role], errors="coerce")
        stale = stale & flatline_mask(s, tol=1e-9, window=window)
    return stale


def _pid_hunt_1(d: pd.DataFrame, p: dict, poll: float) -> pd.Series:
    """Suspected control-output hunting across any present 0–100% analog roles."""
    from app.rules.pid_hunting import PidHuntingParams, hunting_fault_mask

    params = PidHuntingParams(
        change_deadband_pct=_f(p, "change_deadband_pct", 1.0),
        minimum_span_pct=_f(p, "minimum_span_pct", 20.0),
        total_variation_fault_pct=_f(p, "total_variation_fault_pct", 500.0),
        minimum_equivalent_cycles=_f(p, "minimum_equivalent_cycles", 2.5),
        minimum_reversals=int(_f(p, "minimum_reversals", 4)),
        minimum_coverage_pct=_f(p, "minimum_coverage_pct", 80.0),
    )
    mask = _false(d.index)
    enable_col = "loop_enabled" if "loop_enabled" in d.columns else None
    for role in CONTROL_OUTPUT_ROLES:
        if role not in d.columns or d[role].notna().sum() == 0:
            continue
        enabled = d[enable_col] if enable_col else None
        fault, _ = hunting_fault_mask(
            d[role],
            params=params,
            poll_seconds=poll,
            enabled=enabled,
        )
        mask = mask | fault.reindex(d.index).fillna(False)
    return mask


# ---------------------------------------------------------------------------
# Air handling unit rules (FC1–FC15 + additional patterns)
# ---------------------------------------------------------------------------

MIX_TOL = 1.15
SUPPLY_TOL = 1.15
AHU_MIN_OA_DPR = 0.05
DELTA_SUPPLY_FAN = 0.55
FAN_ON_MIN = 0.01


def _fan(d: pd.DataFrame) -> pd.Series:
    if "fan_cmd" in d.columns:
        return norm_cmd(d["fan_cmd"]).fillna(0)
    if "fan_status" in d.columns:
        return as_bool(d["fan_status"]).astype(float)
    return pd.Series(1.0, index=d.index)


def fc1(d, p, poll):
    err = _f(p, "duct_static_err", 0.12)
    fan_hi = _f(p, "fan_hi", 0.87)
    fan = _fan(d)
    return (
        d["duct_static"].notna() & d["duct_static_sp"].notna()
        & (d["duct_static"] < d["duct_static_sp"] - err)
        & (fan >= fan_hi)
    )


def fc2(d, p, poll):
    tol = _f(p, "mix_tol", MIX_TOL)
    fan = _fan(d)
    return (
        (fan > FAN_ON_MIN)
        & d["mat"].notna() & d["oa_t"].notna() & d["rat"].notna()
        & ((d["mat"] - tol) < np.minimum(d["rat"] - tol, d["oa_t"] - tol))
    )


def fc3(d, p, poll):
    tol = _f(p, "mix_tol", MIX_TOL)
    fan = _fan(d)
    return (
        (fan > FAN_ON_MIN)
        & d["mat"].notna() & d["oa_t"].notna() & d["rat"].notna()
        & ((d["mat"] - tol) > np.maximum(d["rat"] + tol, d["oa_t"] + tol))
    )


def fc4(d, p, poll):
    """PID hunting — operating-state entry transitions per hour."""
    delta_os_max = _f(p, "delta_os_max", 5.0)
    htg = norm_cmd(d["htg_valve_pct"]).fillna(0) if "htg_valve_pct" in d else pd.Series(0.0, index=d.index)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0) if "clg_valve_pct" in d else pd.Series(0.0, index=d.index)
    fan = _fan(d)
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0) if "oa_damper_pct" in d else pd.Series(0.0, index=d.index)
    modes = pd.DataFrame(index=d.index)
    modes["heating"] = ((htg > 0) & (clg == 0) & (fan > 0) & (econ <= AHU_MIN_OA_DPR)).astype(int)
    modes["econ_only"] = ((htg == 0) & (clg == 0) & (fan > 0) & (econ > AHU_MIN_OA_DPR)).astype(int)
    modes["econ_mech"] = ((htg == 0) & (clg > 0) & (fan > 0) & (econ > AHU_MIN_OA_DPR)).astype(int)
    modes["mech_only"] = ((htg == 0) & (clg > 0) & (fan > 0) & (econ <= AHU_MIN_OA_DPR)).astype(int)
    if "timestamp" not in d.columns:
        return _false(d.index)
    ts = pd.to_datetime(d["timestamp"])
    entries = (modes.eq(1) & modes.shift().ne(1))
    entries.index = ts
    hourly = entries.resample("1h").sum()
    flagged_hours = hourly[(hourly > delta_os_max).any(axis=1)].index
    floor = ts.dt.floor("1h")
    return pd.Series(floor.isin(flagged_hours).to_numpy(), index=d.index)


def fc5(d, p, poll):
    tol = _f(p, "mix_tol", MIX_TOL)
    fan = _fan(d)
    htg = norm_cmd(d["htg_valve_pct"]).fillna(0)
    return (
        d["sat"].notna() & d["mat"].notna()
        & (fan > FAN_ON_MIN) & (htg > 0.01)
        & ((d["sat"] + SUPPLY_TOL) <= (d["mat"] - tol + DELTA_SUPPLY_FAN))
    )


def fc6(d, p, poll):
    airflow_err = _f(p, "airflow_err", 0.15)
    oat_rat_min = _f(p, "oat_rat_delta_min", 5.0)
    design_cfm = _f(p, "min_cfm_design", 5000.0)
    fan = _fan(d)
    rat_minus_oat = (d["rat"] - d["oa_t"]).abs()
    pct_oa = ((d["mat"] - d["rat"]) / (d["oa_t"] - d["rat"]).replace(0, np.nan)).clip(lower=0)
    perc_oamin = design_cfm / d["vav_total_flow"].replace(0, np.nan)
    oa_err = (pct_oa - perc_oamin).abs()
    return (
        d["mat"].notna() & d["oa_t"].notna() & d["rat"].notna() & d["vav_total_flow"].notna()
        & (rat_minus_oat >= oat_rat_min) & (oa_err > airflow_err) & (fan > FAN_ON_MIN)
    )


def fc7(d, p, poll):
    sat_err = _f(p, "sat_err", 1.0)
    fan = _fan(d)
    htg = norm_cmd(d["htg_valve_pct"]).fillna(0)
    return (
        d["sat"].notna() & d["sat_sp"].notna()
        & (fan > FAN_ON_MIN) & (d["sat"] < d["sat_sp"] - sat_err) & (htg > 0.9)
    )


def fc8(d, p, poll):
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0)
    sat_mat_err = (d["sat"] - DELTA_SUPPLY_FAN - d["mat"]).abs()
    sqrt_tol = float(np.sqrt(SUPPLY_TOL**2 + MIX_TOL**2))
    return (
        d["sat"].notna() & d["mat"].notna()
        & (econ > AHU_MIN_OA_DPR) & (clg < 0.1) & (sat_mat_err > sqrt_tol)
    )


def fc9(d, p, poll):
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0)
    return (
        d["oa_t"].notna() & d["sat_sp"].notna()
        & (econ > AHU_MIN_OA_DPR) & (clg < 0.1)
        & ((d["oa_t"] - MIX_TOL) > (d["sat_sp"] - DELTA_SUPPLY_FAN + MIX_TOL))
    )


def fc10(d, p, poll):
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0)
    abs_mat_oat = (d["mat"] - d["oa_t"]).abs()
    sqrt_tol = float(np.sqrt(MIX_TOL**2 + MIX_TOL**2))
    return d["mat"].notna() & d["oa_t"].notna() & (clg > 0.01) & (econ > 0.9) & (abs_mat_oat > sqrt_tol)


def fc11(d, p, poll):
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0)
    return (
        d["oa_t"].notna() & d["sat_sp"].notna() & (clg > 0.01) & (econ > 0.9)
        & ((d["oa_t"] + MIX_TOL) < (d["sat_sp"] - DELTA_SUPPLY_FAN - MIX_TOL))
    )


def fc12(d, p, poll):
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0)
    sat_check = d["sat"] - SUPPLY_TOL - DELTA_SUPPLY_FAN
    mat_check = d["mat"] + MIX_TOL
    return (
        d["sat"].notna() & d["mat"].notna() & (clg > 0.01)
        & (sat_check > mat_check) & ((econ <= AHU_MIN_OA_DPR) | (econ > 0.9))
    )


def fc13(d, p, poll):
    sat_err = _f(p, "sat_err", 1.0)
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0)
    return (
        d["sat"].notna() & d["sat_sp"].notna() & (clg > 0.01)
        & (d["sat"] > d["sat_sp"] + sat_err) & ((econ <= AHU_MIN_OA_DPR) | (econ > 0.9))
    )


def fc14(d, p, poll):
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0)
    htg = norm_cmd(d["htg_valve_pct"]).fillna(0) if "htg_valve_pct" in d else pd.Series(0.0, index=d.index)
    fan = _fan(d)
    delta = d["clg_coil_enter_t"] - d["clg_coil_leave_t"]
    tol = float(np.sqrt(1.15**2 + 1.15**2)) + DELTA_SUPPLY_FAN
    return (
        d["clg_coil_enter_t"].notna() & d["clg_coil_leave_t"].notna()
        & (delta >= tol)
        & (((econ > AHU_MIN_OA_DPR) & (clg < 0.1)) | ((htg > 0) & (fan > 0)))
    )


def fc15(d, p, poll):
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0)
    delta = d["htg_coil_enter_t"] - d["htg_coil_leave_t"]
    tol = float(np.sqrt(1.15**2 + 1.15**2)) + DELTA_SUPPLY_FAN
    return (
        d["htg_coil_enter_t"].notna() & d["htg_coil_leave_t"].notna()
        & (delta >= tol)
        & (((econ > AHU_MIN_OA_DPR) & (clg < 0.1)) | ((clg > 0.01) & (econ <= AHU_MIN_OA_DPR)) | ((clg > 0.01) & (econ > 0.9)))
    )


def ahu_sat_dev(d, p, poll):
    err = _f(p, "sat_dev_err", 5.0)
    return d["sat"].notna() & d["sat_sp"].notna() & (d["sat"].sub(d["sat_sp"]).abs() > err)


def ahu_duct_high(d, p, poll):
    margin = _f(p, "duct_high_margin", 0.25)
    return d["duct_static"].notna() & d["duct_static_sp"].notna() & (d["duct_static"] > d["duct_static_sp"] + margin)


def ahu_simul_heat_cool(d, p, poll):
    thr = _f(p, "valve_open_pct", 0.10)
    htg = norm_cmd(d["htg_valve_pct"]).fillna(0)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0)
    return (htg > thr) & (clg > thr)


# ---------------------------------------------------------------------------
# Economizer & ventilation (ECON-1..5) — ECON-3 handled specially in engine
# ---------------------------------------------------------------------------


def econ1(d, p, poll):
    oat_min = _f(p, "econ1_oat_min", 55.0)
    fan = _fan(d)
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0)
    return (fan > FAN_ON_MIN) & d["oa_damper_pct"].notna() & d["oa_t"].notna() & (econ < 0.05) & (d["oa_t"] > oat_min)


def econ2(d, p, poll):
    oat_hi = _f(p, "econ2_oat_hi", 63.0)
    dmpr = _f(p, "econ2_damper", 0.42)
    econ = norm_cmd(d["oa_damper_pct"]).fillna(0)
    return d["oa_t"].notna() & d["oa_damper_pct"].notna() & (d["oa_t"] > oat_hi) & (econ > dmpr)


def econ4(d, p, poll):
    oa_min_pct = _f(p, "oa_min_pct", 21.0)
    fan = _fan(d)
    oa_frac = (d["mat"] - d["rat"]) / (d["oa_t"] - d["rat"]).replace(0, np.nan) * 100.0
    return (
        (fan > FAN_ON_MIN) & d["mat"].notna() & d["rat"].notna() & d["oa_t"].notna()
        & ((d["rat"] - d["oa_t"]).abs() > 2.2) & (oa_frac < oa_min_pct)
    )


def econ5(d, p, poll):
    return (
        d["preheat_leave_t"].notna() & d["sat_sp"].notna() & d["oa_t"].notna() & d["htg_valve_pct"].notna()
        & (norm_cmd(d["htg_valve_pct"]).fillna(0) > 0.01)
        & (
            ((d["oa_t"] > d["sat_sp"]) & (d["preheat_leave_t"] - d["oa_t"] > 2.2))
            | ((d["oa_t"] < d["sat_sp"]) & (d["preheat_leave_t"] - d["sat_sp"] > 2.2))
        )
    )


# ---------------------------------------------------------------------------
# VAV zones
# ---------------------------------------------------------------------------


def _vav_air_on(d: pd.DataFrame, flow_min: float) -> pd.Series:
    """Fan/air-flow-running proxy for a VAV box.

    VAV terminals have no fan of their own; the box only sees conditioned air when the
    parent AHU supply fan runs. We use measured box airflow as that proxy: air moving
    means the fan is on. When no airflow point is modeled we can't gate, so return True.
    """
    if "zone_flow" in d.columns:
        return pd.to_numeric(d["zone_flow"], errors="coerce").fillna(0) > flow_min
    return pd.Series(True, index=d.index)


def vav1(d, p, poll):
    lo = _f(p, "zone_lo", 68.0)
    hi = _f(p, "zone_hi", 76.0)
    return d["zone_t"].notna() & ((d["zone_t"] < lo) | (d["zone_t"] > hi))


def vav3(d, p, poll):
    oat_hi = _f(p, "reheat_oat", 78.0)
    reheat_thr = _f(p, "reheat_pct", 0.52)
    flow_min = _f(p, "flow_on_min", 25.0)
    reheat = norm_cmd(d["reheat_valve_pct"]).fillna(0)
    return _vav_air_on(d, flow_min) & d["oa_t"].notna() & (d["oa_t"] > oat_hi) & (reheat > reheat_thr)


def vav4(d, p, poll):
    full_open = _f(p, "full_open_pct", 0.975)
    hours = _f(p, "sustain_hours", 1.5)
    flow_min = _f(p, "flow_on_min", 25.0)
    roll = max(2, int(round(hours * 3600 / max(poll, 1))))
    dmp = norm_cmd(d["damper_pct"]).fillna(0)
    return (
        _vav_air_on(d, flow_min) & dmp.notna() & (dmp > full_open)
        & (dmp.rolling(roll, min_periods=roll).min() > full_open)
    )


def vav5(d, p, poll):
    dmp = norm_cmd(d["damper_pct"]).fillna(0)
    return d["zone_flow"].notna() & (d["zone_flow"] > 50.0) & (dmp < 0.10)


def vav7(d, p, poll):
    """Min-flow violation OR fixed/high airflow while air is moving (mins too high / no modulate)."""
    under = (
        d["zone_flow"].notna() & d["min_flow_sp"].notna() & (d["zone_flow"] < d["min_flow_sp"])
        if "min_flow_sp" in d.columns
        else _false(d.index)
    )
    flow = pd.to_numeric(d["zone_flow"], errors="coerce") if "zone_flow" in d.columns else None
    if flow is None:
        return under
    flow_min = _f(p, "flow_on_min", 25.0)
    air_on = _vav_air_on(d, flow_min)
    window = max(6, int(round(3600.0 / max(float(poll), 1.0))))
    roll_std = flow.rolling(window, min_periods=max(3, window // 2)).std()
    roll_mean = flow.rolling(window, min_periods=max(3, window // 2)).mean()
    max_std = _f(p, "fixed_flow_max_std", 15.0)
    min_mean = _f(p, "fixed_flow_min_mean", 200.0)
    fixed_high = air_on & flow.notna() & (roll_std < max_std) & (roll_mean > min_mean)
    high_min = _false(d.index)
    if "min_flow_sp" in d.columns:
        high_min_thr = _f(p, "high_min_flow_sp", 250.0)
        high_min = (
            air_on
            & d["min_flow_sp"].notna()
            & (pd.to_numeric(d["min_flow_sp"], errors="coerce") > high_min_thr)
            & (roll_std < max_std)
        )
    return under.fillna(False) | fixed_high.fillna(False) | high_min.fillna(False)


def vav_reheat_stuck(d, p, poll):
    """Reheat valve commanded open but the box's discharge air never warms above inlet.

    Inlet temp = duct air arriving from the AHU (≈ AHU discharge). Discharge temp = air
    leaving the box after the reheat coil. Reheat open + air flowing + no rise → stuck /
    failed reheat valve or coil. Fully computed from VAV-local sensors.
    """
    cmd_thr = _f(p, "reheat_cmd", 0.30)
    min_rise = _f(p, "min_rise", 3.0)
    flow_min = _f(p, "flow_on_min", 25.0)
    reheat = norm_cmd(d["reheat_valve_pct"]).fillna(0)
    rise = d["vav_disch_t"] - d["vav_inlet_t"]
    return (
        _vav_air_on(d, flow_min)
        & d["vav_disch_t"].notna() & d["vav_inlet_t"].notna()
        & (reheat > cmd_thr) & (rise < min_rise)
    )


# ---------------------------------------------------------------------------
# Central plants
# ---------------------------------------------------------------------------


def chw1(d, p, poll):
    min_dt = _f(p, "min_dt", 4.0)
    dt = d["chw_return_t"] - d["chw_supply_t"]
    pump = as_bool(d["chw_pump_cmd"]) if "chw_pump_cmd" in d else pd.Series(True, index=d.index)
    return d["chw_supply_t"].notna() & d["chw_return_t"].notna() & pump & (dt < min_dt)


def chw2(d, p, poll):
    margin = _f(p, "dp_margin", 2.2)
    pmp_hi = _f(p, "pump_hi", 0.87)
    pump = norm_cmd(d["chw_pump_cmd"]).fillna(0)
    return (
        d["chw_dp"].notna() & d["chw_dp_sp"].notna()
        & (d["chw_dp"] < d["chw_dp_sp"] - margin) & (pump >= pmp_hi)
    )


def chw3(d, p, poll):
    band = _f(p, "sp_band", 2.2)
    pump = norm_cmd(d["chw_pump_cmd"]).fillna(0)
    return (
        (pump > 0.01) & d["chw_supply_t"].notna() & d["chw_supply_t_sp"].notna()
        & ((d["chw_supply_t"] < d["chw_supply_t_sp"] - band) | (d["chw_supply_t"] > d["chw_supply_t_sp"] + band))
    )


def chw4(d, p, poll):
    flow_hi = _f(p, "flow_hi", 1100.0)
    pmp_hi = _f(p, "pump_hi", 0.87)
    pump = norm_cmd(d["chw_pump_cmd"]).fillna(0)
    return d["chw_flow"].notna() & (d["chw_flow"] > flow_hi) & (pump >= pmp_hi)


# ---------------------------------------------------------------------------
# Heat pumps
# ---------------------------------------------------------------------------


def hp1(d, p, poll):
    min_sat = _f(p, "min_sat", 85.0)
    zone_cold = _f(p, "zone_cold", 69.0)
    fan = _fan(d)
    return (
        d["sat"].notna() & d["zone_t"].notna() & (fan > FAN_ON_MIN)
        & (d["zone_t"] < zone_cold) & (d["sat"] < min_sat)
    )


# ---------------------------------------------------------------------------
# Weather station
# ---------------------------------------------------------------------------


def wx1(d, p, poll):
    spike = _f(p, "spike_limit", 16.0)
    return d["oa_t"].notna() & (d["oa_t"].diff().abs() > spike)


def wx2(d, p, poll):
    return d["wind_gust"].notna() & d["wind_speed"].notna() & (d["wind_gust"] < d["wind_speed"])


def cw_opt(d, p, poll):
    """Condenser-water not optimized vs wet-bulb (Stull) — CW colder than WB + approach."""
    if "cw_supply_t" not in d.columns:
        return _false(d.index)
    wb = d["wx_oa_wetbulb"] if "wx_oa_wetbulb" in d.columns else None
    if wb is None or wb.notna().sum() == 0:
        return _false(d.index)
    approach = _f(p, "cw_approach", 7.0)
    slack = _f(p, "cw_slack", 2.0)
    # Over-cooled tower water: supply significantly below wet-bulb + design approach
    return (
        d["cw_supply_t"].notna()
        & wb.notna()
        & (pd.to_numeric(d["cw_supply_t"], errors="coerce") < (wb + approach - slack))
    )


def oat_vs_meteo(d, p, poll):
    """BAS outdoor-air sensor disagrees with Open-Meteo dry bulb by more than the threshold."""
    if "wx_oa_t" not in d.columns:
        return _false(d.index)
    err = _f(p, "oat_err", 5.0)
    return d["oa_t"].notna() & d["wx_oa_t"].notna() & (d["oa_t"].sub(d["wx_oa_t"]).abs() > err)


# ---------------------------------------------------------------------------
# Trim & respond advisory
# ---------------------------------------------------------------------------


def trim1(d, p, poll):
    return (
        d["duct_static"].notna() & d["vav_press_req_sum"].notna()
        & (d["duct_static"] > 0.80) & (d["vav_press_req_sum"] < 1.0) & (d["duct_static"] > 1.35)
    )


def trim3(d, p, poll):
    return (
        d["hw_supply_t"].notna() & d["hw_reset_req_sum"].notna()
        & (d["hw_supply_t"] > 160.0) & (d["hw_reset_req_sum"] < 1.0)
    )


def trim4(d, p, poll):
    return (
        d["chw_supply_t"].notna() & d["chw_reset_req_sum"].notna()
        & (d["chw_supply_t"] < 45.0) & (d["chw_reset_req_sum"] < 1.0)
    )


# ---------------------------------------------------------------------------
# Extended families
# ---------------------------------------------------------------------------


def sched1(d, p, poll):
    """Unoccupied fan runtime; optional zone comfort band when zone_t is mapped."""
    if "occ_mode" not in d or "fan_status" not in d:
        return _false(d.index)
    base = (d["occ_mode"].astype(str).str.lower() == "unoccupied") & as_bool(d["fan_status"])
    if "zone_t" not in d.columns or d["zone_t"].notna().sum() == 0:
        return base
    lo = _f(p, "comfort_low_f", 70.0)
    hi = _f(p, "comfort_high_f", 76.0)
    zt = pd.to_numeric(d["zone_t"], errors="coerce")
    in_band = zt.notna() & (zt >= lo) & (zt <= hi)
    return base & in_band


def cmd1(d, p, poll):
    cmd_on = norm_cmd(d["fan_cmd"]).fillna(0) >= 0.05
    return d["fan_status"].notna() & (cmd_on != as_bool(d["fan_status"]))


def oa1(d, p, poll):
    min_oa = _f(p, "min_oa_frac", 0.15)
    oa_frac = (d["mat"] - d["rat"]) / (d["oa_t"] - d["rat"]).replace(0, np.nan)
    fan = _fan(d)
    return (
        (fan > FAN_ON_MIN) & d["oa_t"].notna() & d["rat"].notna() & d["mat"].notna()
        & ((d["rat"] - d["oa_t"]).abs() > 0.5) & (oa_frac < min_oa)
    )


def dmp1(d, p, poll):
    leak_delta = _f(p, "leak_delta", 2.0)
    dmp = norm_cmd(d["oa_damper_pct"]).fillna(0)
    return d["oa_t"].notna() & d["mat"].notna() & (dmp <= 0.05) & (d["mat"].sub(d["oa_t"]).abs() < leak_delta)


def vlv1(d, p, poll):
    """Cooling valve leak: valve closed AND (SAT low vs SP or SAT low vs MAT).

    Fan proven-on is enforced by the VLV-1 operational gate when fan_status/fan_cmd exist.
    """
    sat_err = _f(p, "sat_err", 2.0)
    mat_delta = _f(p, "mat_leak_delta", 2.0)
    clg = norm_cmd(d["clg_valve_pct"]).fillna(0)
    closed = clg <= 0.05
    sat = pd.to_numeric(d["sat"], errors="coerce")
    sat_sp = pd.to_numeric(d["sat_sp"], errors="coerce")
    below_sp = sat.notna() & sat_sp.notna() & (sat < sat_sp - sat_err)
    below_mat = pd.Series(False, index=d.index)
    if "mat" in d.columns and d["mat"].notna().any():
        mat = pd.to_numeric(d["mat"], errors="coerce")
        below_mat = sat.notna() & mat.notna() & (sat < mat - mat_delta)
    return closed & (below_sp | below_mat)


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

RULES: list[CookbookRule] = [
    # --- Sensor validation sweep (applies to every sensor present) ---
    CookbookRule(
        "SV-RANGE", "Sensor out of hard range", "sensor",
        ["ahu", "vav", "chiller", "boiler", "weather", "zone", "heatpump"], [],
        "Any modeled sensor reads outside its physical hard range (e.g. OAT −60–130°F, SAT 30–150°F, CHWS 30–80°F).",
        _sweep_range, params=[CONFIRM_PARAM()], sensor_sweep=True, confirm_seconds=300,
    ),
    CookbookRule(
        "SV-FLATLINE", "Sensor flatline (stuck)", "sensor",
        ["ahu", "vav", "chiller", "boiler", "weather", "zone", "heatpump"], [],
        "Sensor value unchanged (Δ ≤ tolerance) across the flatline window — stuck / frozen sensor.",
        _sweep_flatline,
        params=[
            CookbookParam("flatline_tol", "Flatline tolerance", "°F", 0.02, 1.0, 0.02, 0.10),
            CookbookParam("flatline_hours", "Flatline window", "h", 0.5, 8.0, 0.5, 1.0),
            CONFIRM_PARAM(),
        ], sensor_sweep=True, confirm_seconds=300,
    ),
    CookbookRule(
        "SV-SPIKE", "Sensor rate-of-change spike", "sensor",
        ["ahu", "vav", "chiller", "boiler", "weather", "zone", "heatpump"], [],
        "Sample-to-sample jump exceeds the physical spike limit for the sensor type.",
        _sweep_spike, params=[
            CookbookParam("spike_scale", "Spike limit scale", "├ù", 0.25, 3.0, 0.25, 1.0),
            CONFIRM_PARAM(),
        ], sensor_sweep=True, confirm_seconds=300,
    ),
    CookbookRule(
        "SV-STALE", "Stale data (no fresh samples)", "sensor",
        ["ahu", "vav", "chiller", "boiler", "weather", "zone", "heatpump"], [],
        "All modeled sensors unchanged over the stale window — data feed likely dropped.",
        _sweep_stale, params=[
            CookbookParam("stale_hours", "Stale window", "h", 0.5, 12.0, 0.5, 2.0),
            CONFIRM_PARAM(),
        ], sensor_sweep=True, confirm_seconds=300,
    ),
    CookbookRule(
        "PID-HUNT-1", "Suspected control-output hunting", "control",
        ["ahu", "vav", "chiller", "boiler", "heatpump"], [],
        "Rolling 1h total variation of any 0–100% control output (dampers, valves, fan speeds, "
        "heat/cool cmds) with span ≥20%, TV ≥500 %·pts, ≥2.5 equivalent cycles, ≥4 reversals — "
        "suspected loop hunting (not proof of bad PID alone).",
        _pid_hunt_1,
        params=[
            CookbookParam("change_deadband_pct", "Ignore changes below", "% out", 0.0, 10.0, 0.5, 1.0),
            CookbookParam("minimum_span_pct", "Minimum observed span", "% out", 5.0, 100.0, 5.0, 20.0),
            CookbookParam("total_variation_fault_pct", "Total travel threshold", "%/h", 50.0, 2000.0, 50.0, 500.0),
            CookbookParam("minimum_equivalent_cycles", "Min equivalent cycles", "cyc/h", 0.5, 20.0, 0.5, 2.5),
            CookbookParam("minimum_reversals", "Min direction reversals", "count", 1, 40, 1, 4),
            CookbookParam("minimum_coverage_pct", "Minimum data coverage", "%", 25.0, 100.0, 5.0, 80.0),
            CONFIRM_PARAM(),
        ],
        optional_roles=["loop_enabled"],
        control_output_sweep=True,
        confirm_seconds=0,
    ),

    # --- AHU GL36 (FC1–FC15) ---
    CookbookRule("FC1", "Duct static below SP at full fan (GL36 A)", "ahu", ["ahu"],
        ["duct_static", "duct_static_sp", "fan_cmd"],
        "Fan ≥ 87% AND duct static < static SP − 0.12 in.w.c.",
        fc1, params=[
            CookbookParam("duct_static_err", "Duct static error", "in. w.c.", 0.02, 0.5, 0.01, 0.12),
            CookbookParam("fan_hi", "Fan high threshold", "frac", 0.5, 1.0, 0.01, 0.87),
            CONFIRM_PARAM()], confirm_seconds=300),
    CookbookRule("FC2", "MAT below OAT/RAT envelope (GL36 B)", "ahu", ["ahu"],
        ["mat", "oa_t", "rat", "fan_cmd"],
        "Fan on AND MAT − 1.15°F < min(RAT, OAT) − 1.15°F.",
        fc2, params=[CookbookParam("mix_tol", "Mixing tolerance", "°F", 0.25, 3.0, 0.05, 1.15), CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC3", "MAT above OAT/RAT envelope (GL36 C)", "ahu", ["ahu"],
        ["mat", "oa_t", "rat", "fan_cmd"],
        "Fan on AND MAT − 1.15°F > max(RAT, OAT) + 1.15°F.",
        fc3, params=[CookbookParam("mix_tol", "Mixing tolerance", "°F", 0.25, 3.0, 0.05, 1.15), CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC4", "PID hunting (operating-state oscillation)", "ahu", ["ahu"],
        ["oa_damper_pct", "clg_valve_pct", "fan_cmd"],
        "More than 5 operating-mode entry transitions in any hour (heating/econ/mech modes).",
        fc4, params=[CookbookParam("delta_os_max", "Max mode changes/hr", "count", 2, 20, 1, 5), CONFIRM_PARAM()], confirm_seconds=3600),
    CookbookRule("FC5", "SAT cold when heating commanded (GL36 D)", "ahu", ["ahu"],
        ["sat", "mat", "fan_cmd", "htg_valve_pct"],
        "Fan on AND heating > 1% AND SAT + 1.15°F ≤ MAT − 1.15°F + 0.55°F.",
        fc5, params=[CookbookParam("mix_tol", "Mixing tolerance", "°F", 0.25, 3.0, 0.05, 1.15), CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC6", "Estimated OA fraction mismatch", "ahu", ["ahu"],
        ["mat", "oa_t", "rat", "vav_total_flow"],
        "|RAT−OAT| ≥ 5°F AND |estimated OA% − design min OA%| > 15% in heating/mech-only modes.",
        fc6, params=[
            CookbookParam("airflow_err", "OA fraction error", "frac", 0.05, 0.5, 0.01, 0.15),
            CookbookParam("min_cfm_design", "Design min OA CFM", "cfm", 500, 20000, 500, 5000),
            CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC7", "SAT low with full heating (GL36 E)", "ahu", ["ahu"],
        ["sat", "sat_sp", "fan_cmd", "htg_valve_pct"],
        "Fan on AND heating > 90% AND SAT < SAT SP − 1.0°F.",
        fc7, params=[CookbookParam("sat_err", "SAT error", "°F", 0.25, 5.0, 0.25, 1.0), CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC8", "SAT/MAT mismatch in economizer (GL36 F)", "ahu", ["ahu"],
        ["sat", "mat", "oa_damper_pct", "clg_valve_pct"],
        "Economizer open, CHW < 10%, |SAT − 0.55°F − MAT| > √(1.15²+1.15²).",
        fc8, params=[CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC9", "OAT too warm for free cooling (GL36 G)", "ahu", ["ahu"],
        ["oa_t", "sat_sp", "oa_damper_pct", "clg_valve_pct"],
        "Economizer open, CHW < 10%, OAT − 1.15°F > SAT SP − 0.55°F + 1.15°F.",
        fc9, params=[CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC10", "OAT/MAT mismatch + mech cooling (GL36 H)", "ahu", ["ahu"],
        ["mat", "oa_t", "oa_damper_pct", "clg_valve_pct"],
        "CHW > 1%, economizer > 90%, |MAT − OAT| > √(1.15²+1.15²).",
        fc10, params=[CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC11", "OAT/MAT mismatch economizer-only (GL36 I)", "ahu", ["ahu"],
        ["oa_t", "sat_sp", "oa_damper_pct", "clg_valve_pct"],
        "CHW > 1%, economizer > 90%, OAT + 1.15°F < SAT SP − 0.55°F − 1.15°F.",
        fc11, params=[CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC12", "SAT above blend in cooling (GL36 J)", "ahu", ["ahu"],
        ["sat", "mat", "oa_damper_pct", "clg_valve_pct"],
        "CHW > 1%, SAT − 1.15°F − 0.55°F > MAT + 1.15°F at min or full economizer.",
        fc12, params=[CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC13", "SAT above SP at full cooling (GL36 K)", "ahu", ["ahu"],
        ["sat", "sat_sp", "oa_damper_pct", "clg_valve_pct"],
        "CHW > 1%, SAT > SAT SP + 1.0°F at min or full economizer.",
        fc13, params=[CookbookParam("sat_err", "SAT error", "°F", 0.25, 5.0, 0.25, 1.0), CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC14", "CHW coil ΔT when inactive (GL36 L)", "ahu", ["ahu"],
        ["clg_coil_enter_t", "clg_coil_leave_t", "oa_damper_pct", "clg_valve_pct"],
        "Cooling coil ΔT ≥ √(1.15²+1.15²)+0.55°F while coil should be inactive.",
        fc14, params=[CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("FC15", "HW coil ΔT when inactive (GL36 M)", "ahu", ["ahu"],
        ["htg_coil_enter_t", "htg_coil_leave_t", "oa_damper_pct", "clg_valve_pct"],
        "Heating coil ΔT ≥ √(1.15²+1.15²)+0.55°F while coil should be inactive.",
        fc15, params=[CONFIRM_PARAM()], confirm_seconds=600),

    # --- AHU additional patterns ---
    CookbookRule("AHU-SATDEV", "SAT deviation from setpoint", "ahu", ["ahu"],
        ["sat", "sat_sp"], "|SAT − SAT SP| > 5°F.",
        ahu_sat_dev, params=[CookbookParam("sat_dev_err", "SAT deviation", "°F", 1.0, 15.0, 0.5, 5.0), CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("AHU-DUCTHI", "Duct static pressure high", "ahu", ["ahu"],
        ["duct_static", "duct_static_sp"], "Duct static > static SP + 0.25 in.w.c.",
        ahu_duct_high, params=[CookbookParam("duct_high_margin", "High margin", "in. w.c.", 0.05, 1.0, 0.05, 0.25), CONFIRM_PARAM()], confirm_seconds=300),
    CookbookRule("AHU-SIMUL", "Heating and cooling simultaneous", "ahu", ["ahu"],
        ["htg_valve_pct", "clg_valve_pct"], "Heating valve > 10% AND cooling valve > 10% at once.",
        ahu_simul_heat_cool, params=[CookbookParam("valve_open_pct", "Valve open threshold", "frac", 0.05, 0.5, 0.01, 0.10), CONFIRM_PARAM()], confirm_seconds=300),
    CookbookRule("OAT-METEO", "BAS outdoor-air sensor vs Open-Meteo", "ahu", ["ahu"],
        ["oa_t", "wx_oa_t"], "BAS OAT sensor differs from Open-Meteo dry bulb by more than 5°F.",
        oat_vs_meteo, params=[
            CookbookParam("oat_err", "Max OAT disagreement", "°F", 2.0, 20.0, 0.5, 5.0),
            CONFIRM_PARAM()], confirm_seconds=900),

    # --- Economizer & ventilation ---
    CookbookRule("ECON-1", "Economizer stuck closed", "ahu", ["ahu"],
        ["fan_cmd", "oa_damper_pct", "oa_t"], "Fan on, OA damper < 5%, OAT > 55°F (should be economizing).",
        econ1, params=[CookbookParam("econ1_oat_min", "Favorable OAT", "°F", 45.0, 70.0, 1.0, 55.0), CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("ECON-2", "Economizing when outdoor unfavorable", "ahu", ["ahu"],
        ["oa_t", "oa_damper_pct"], "OAT > 63°F AND OA damper > 42% (should be at minimum).",
        econ2, params=[
            CookbookParam("econ2_oat_hi", "OAT high cutoff", "°F", 55.0, 80.0, 1.0, 63.0),
            CookbookParam("econ2_damper", "Damper open frac", "frac", 0.2, 0.9, 0.02, 0.42),
            CONFIRM_PARAM()], confirm_seconds=300),
    CookbookRule("ECON-3", "Mech cooling when econ available", "ahu", ["ahu"],
        ["oa_damper_pct", "clg_valve_pct"],
        "Free cooling available when web dry-bulb is 35–72°F AND dewpoint < 60°F (RH→dewpoint if needed); "
        "fault when cooling valve open with OA damper closed. Optional SAT≈SP means free cooling is keeping up.",
        # placeholder; engine substitutes econ3 with weather-aware compute
        econ2, params=[
            CookbookParam("econ3_db_min", "Free-cool OA dry-bulb min", "°F", 25.0, 45.0, 1.0, 35.0),
            CookbookParam("econ3_db_max", "Free-cool OA dry-bulb max", "°F", 60.0, 80.0, 1.0, 72.0),
            CookbookParam("econ3_dp_max", "Free-cool OA dew point max", "°F", 45.0, 68.0, 1.0, 60.0),
            CookbookParam("econ3_oat_fallback", "Fallback OAT cutoff", "°F", 55.0, 70.0, 1.0, 63.0),
            CookbookParam("econ3_damper", "Damper closed frac", "frac", 0.1, 0.6, 0.02, 0.32),
            CookbookParam("econ3_zone_band", "SAT≈SP band (keeping up)", "°F", 0.5, 6.0, 0.5, 2.0),
            CONFIRM_PARAM()], confirm_seconds=300),
    CookbookRule("ECON-4", "Low estimated OA fraction", "ahu", ["ahu"],
        ["mat", "rat", "oa_t", "fan_cmd"], "Fan on, |RAT−OAT| > 2.2°F, estimated OA fraction < 21%.",
        econ4, params=[CookbookParam("oa_min_pct", "Min OA fraction", "%", 5.0, 40.0, 1.0, 21.0), CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("ECON-5", "Preheat over-conditioning", "ahu", ["ahu"],
        ["preheat_leave_t", "sat_sp", "oa_t", "htg_valve_pct"], "Preheat leaving air > 2.2°F above target while preheat active.",
        econ5, params=[CONFIRM_PARAM()], confirm_seconds=600),

    # --- VAV zones ---
    CookbookRule("VAV-1", "Zone comfort band", "vav", ["vav", "zone"],
        ["zone_t"], "Zone temp < 68°F or > 76°F.",
        vav1, params=[
            CookbookParam("zone_lo", "Zone low", "°F", 55.0, 70.0, 0.5, 68.0),
            CookbookParam("zone_hi", "Zone high", "°F", 72.0, 85.0, 0.5, 76.0),
            CONFIRM_PARAM()], confirm_seconds=900),
    CookbookRule("VAV-3", "Excessive reheat during warm weather", "vav", ["vav"],
        ["oa_t", "reheat_valve_pct"], "Air flowing AND OAT > 78°F AND reheat valve > 52%.",
        vav3, params=[
            CookbookParam("reheat_oat", "Warm OAT", "°F", 65.0, 90.0, 1.0, 78.0),
            CookbookParam("reheat_pct", "Reheat frac", "frac", 0.1, 1.0, 0.02, 0.52),
            CookbookParam("flow_on_min", "Airflow-on min", "cfm", 0.0, 200.0, 5.0, 25.0),
            CONFIRM_PARAM()], confirm_seconds=300),
    CookbookRule("VAV-4", "Damper stuck at full open", "vav", ["vav"],
        ["damper_pct"], "Air flowing AND damper > 97.5% sustained across the window.",
        vav4, params=[
            CookbookParam("full_open_pct", "Full open frac", "frac", 0.8, 1.0, 0.005, 0.975),
            CookbookParam("sustain_hours", "Sustain window", "h", 0.5, 6.0, 0.5, 1.5),
            CookbookParam("flow_on_min", "Airflow-on min", "cfm", 0.0, 200.0, 5.0, 25.0),
            CONFIRM_PARAM()], confirm_seconds=900),
    CookbookRule("VAV-5", "Airflow sensor bias", "vav", ["vav"],
        ["zone_flow", "damper_pct"], "Airflow > 50 cfm while damper < 10% (implausible flow).",
        vav5, params=[CONFIRM_PARAM()], confirm_seconds=900),
    CookbookRule("VAV-REHEAT", "Reheat valve stuck / no temp rise", "vav", ["vav"],
        ["reheat_valve_pct", "vav_disch_t", "vav_inlet_t"],
        "Air flowing AND reheat valve > 30% AND box discharge temp rises < 3°F above duct inlet "
        "(air from AHU) — stuck or failed reheat valve/coil.",
        vav_reheat_stuck, params=[
            CookbookParam("reheat_cmd", "Reheat open frac", "frac", 0.1, 1.0, 0.05, 0.30),
            CookbookParam("min_rise", "Min temp rise", "°F", 0.5, 15.0, 0.5, 3.0),
            CookbookParam("flow_on_min", "Airflow-on min", "cfm", 0.0, 200.0, 5.0, 25.0),
            CONFIRM_PARAM()], confirm_seconds=900),
    CookbookRule("VAV-7", "Min airflow / fixed high flow", "vav", ["vav"],
        ["zone_flow"],
        "Flow below min SP (when mapped), OR airflow stays flat (low rolling std) at a high mean while air is on "
        "(mins too high / box never modulates), OR min_flow_sp itself is excessively high.",
        vav7, params=[
            CookbookParam("flow_on_min", "Airflow-on min", "cfm", 0.0, 200.0, 5.0, 25.0),
            CookbookParam("fixed_flow_max_std", "Fixed-flow max std", "cfm", 1.0, 80.0, 1.0, 15.0),
            CookbookParam("fixed_flow_min_mean", "Fixed-flow min mean", "cfm", 50.0, 2000.0, 10.0, 200.0),
            CookbookParam("high_min_flow_sp", "High min-flow SP", "cfm", 50.0, 2000.0, 10.0, 250.0),
            CONFIRM_PARAM()], confirm_seconds=900),

    # --- Central plants ---
    CookbookRule("CHW-1", "Low chilled-water ΔT", "plant", ["chiller"],
        ["chw_supply_t", "chw_return_t"], "Pump on AND (CHWR − CHWS) < 4°F.",
        chw1, params=[CookbookParam("min_dt", "Min ΔT", "°F", 1.0, 12.0, 0.5, 4.0), CONFIRM_PARAM()], confirm_seconds=900),
    CookbookRule("CHW-2", "DP below SP at max pump speed", "plant", ["chiller"],
        ["chw_dp", "chw_dp_sp", "chw_pump_cmd"], "Pump ≥ 87% AND CHW DP < DP SP − 2.2.",
        chw2, params=[CookbookParam("dp_margin", "DP margin", "psi", 0.5, 6.0, 0.1, 2.2), CONFIRM_PARAM()], confirm_seconds=300),
    CookbookRule("CHW-3", "Plant supply temp outside deadband", "plant", ["chiller"],
        ["chw_supply_t", "chw_supply_t_sp", "chw_pump_cmd"], "Pump on AND |CHWS − CHWS SP| > 2.2°F.",
        chw3, params=[CookbookParam("sp_band", "SP band", "°F", 0.5, 6.0, 0.1, 2.2), CONFIRM_PARAM()], confirm_seconds=300),
    CookbookRule("CHW-4", "Flow high at max pump", "plant", ["chiller"],
        ["chw_flow", "chw_pump_cmd"], "Pump ≥ 87% AND CHW flow > 1100 gpm.",
        chw4, params=[CookbookParam("flow_hi", "Flow high", "gpm", 200, 3000, 50, 1100), CONFIRM_PARAM()], confirm_seconds=300),

    # --- Heat pumps ---
    CookbookRule("HP-1", "Discharge cold when heating", "heatpump", ["heatpump"],
        ["sat", "zone_t", "fan_cmd"], "Fan on, zone < 69°F, discharge SAT < 85°F.",
        hp1, params=[
            CookbookParam("min_sat", "Min heating SAT", "°F", 70.0, 110.0, 1.0, 85.0),
            CookbookParam("zone_cold", "Zone cold", "°F", 60.0, 72.0, 0.5, 69.0),
            CONFIRM_PARAM()], confirm_seconds=600),

    # --- Weather / condenser ---
    CookbookRule("WX-1", "OA temperature spike", "weather", ["weather"],
        ["oa_t"], "OAT sample-to-sample jump > 16°F.",
        wx1, params=[CookbookParam("spike_limit", "Spike limit", "°F", 4.0, 40.0, 1.0, 16.0), CONFIRM_PARAM()], confirm_seconds=300),
    CookbookRule("CW-OPT-1", "Condenser water not optimized vs wet-bulb", "plant", ["chiller"],
        ["cw_supply_t"],
        "CW supply significantly colder than web wet-bulb + design approach (Stull WB) — tower over-cooling / not optimized.",
        cw_opt, params=[
            CookbookParam("cw_approach", "Design approach", "°F", 3.0, 15.0, 0.5, 7.0),
            CookbookParam("cw_slack", "Slack below target", "°F", 0.5, 6.0, 0.5, 2.0),
            CONFIRM_PARAM()], confirm_seconds=900),

    # --- Trim & respond advisory (lumped with AHU / plants) ---
    CookbookRule("TRIM-1", "Duct static trim advisory", "trim", ["ahu"],
        ["duct_static", "vav_press_req_sum"], "Duct static high (> 1.35 in.w.c.) while VAV pressure requests are low.",
        trim1, params=[CONFIRM_PARAM()], confirm_seconds=1800),
    CookbookRule("TRIM-3", "HWST trim advisory", "trim", ["boiler"],
        ["hw_supply_t", "hw_reset_req_sum"], "HW supply > 160°F while reset requests are low.",
        trim3, params=[CONFIRM_PARAM()], confirm_seconds=1800),
    CookbookRule("TRIM-4", "CHW plant reset advisory", "trim", ["chiller"],
        ["chw_supply_t", "chw_reset_req_sum"], "CHW supply < 45°F while reset requests are low.",
        trim4, params=[CONFIRM_PARAM()], confirm_seconds=1800),

    # --- Extended families ---
    CookbookRule(
        "SCHED-1",
        "Unoccupied runtime",
        "ahu",
        ["ahu"],
        ["occ_mode", "fan_status"],
        "Fan running while occupancy is unoccupied (Overview calendar → occ_mode). "
        "When zone_t is mapped, also require zone inside comfort_low_f…comfort_high_f "
        "(defaults 70–76°F; synced from Overview zone band).",
        sched1,
        params=[
            CookbookParam("comfort_low_f", "Comfort low", "°F", 60.0, 78.0, 0.5, 70.0),
            CookbookParam("comfort_high_f", "Comfort high", "°F", 68.0, 85.0, 0.5, 76.0),
            CONFIRM_PARAM(),
        ],
        optional_roles=["zone_t"],
        confirm_seconds=1800,
    ),
    CookbookRule("CMD-1", "Fan cmd/status mismatch", "ahu", ["ahu"],
        ["fan_cmd", "fan_status"], "Fan command and proven status disagree.",
        cmd1, params=[CONFIRM_PARAM()], confirm_seconds=600),
    CookbookRule("OA-1", "Low OA fraction", "ahu", ["ahu"],
        ["mat", "rat", "oa_t", "fan_status"], "Estimated OA fraction < 15% with adequate OAT/RAT split.",
        oa1, params=[CookbookParam("min_oa_frac", "Min OA fraction", "frac", 0.05, 0.4, 0.01, 0.15), CONFIRM_PARAM()], confirm_seconds=900),
    CookbookRule("DMP-1", "OA damper leakage", "ahu", ["ahu"],
        ["oa_t", "mat", "oa_damper_pct"], "Damper ≤ 5% but MAT tracks OAT within 2°F — leaking OA damper.",
        dmp1, params=[CookbookParam("leak_delta", "Leak ΔT", "°F", 0.5, 6.0, 0.5, 2.0), CONFIRM_PARAM()], confirm_seconds=900),
    CookbookRule(
        "VLV-1",
        "Cooling valve leakage",
        "ahu",
        ["ahu"],
        ["sat", "sat_sp", "clg_valve_pct"],
        "Cooling valve ≤ 5% AND (SAT < sat_sp − sat_err OR SAT < MAT − mat_leak_delta). "
        "Fan proven on when fan_status/fan_cmd present (operational gate).",
        vlv1,
        params=[
            CookbookParam("sat_err", "SAT vs SP leak ΔT", "°F", 0.5, 8.0, 0.5, 2.0),
            CookbookParam("mat_leak_delta", "SAT vs MAT leak ΔT", "°F", 0.5, 12.0, 0.5, 2.0),
            CONFIRM_PARAM(),
        ],
        optional_roles=["mat", "fan_status", "fan_cmd"],
        confirm_seconds=900,
    ),
]


RULES_BY_ID: dict[str, CookbookRule] = {r.id: r for r in RULES}


def rules_for_kind(kind: str) -> list[CookbookRule]:
    return [r for r in RULES if kind in r.equipment_kinds]


def catalog() -> list[dict]:
    return [r.to_dict() for r in RULES]
