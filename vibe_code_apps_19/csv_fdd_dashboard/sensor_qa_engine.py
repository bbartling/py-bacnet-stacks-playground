"""
HVAC sensor QA engine — four-level fault detection for BAS time-series.

Levels:
  L1 hard_range_fault       — value outside physical hard limits
  L2 spike_or_roc_fault       — rate-of-change exceeds per-point max (with suppression)
  L3 stale_or_flatline_fault  — no meaningful change over persistence window
  L4 physics_plausibility     — cross-sensor consistency (MAT envelope, SAT vs MAT, etc.)

Defaults from sensor_fault_defaults.json (research-backed, site-tunable).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DEFAULTS_PATH = ROOT / "sensor_fault_defaults.json"


def load_sensor_defaults() -> dict:
    with open(DEFAULTS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _alias_map(defaults: dict) -> dict[str, tuple[str, str, dict]]:
    """Map logical column alias -> (category, sensor_key, spec)."""
    out: dict[str, tuple[str, str, dict]] = {}
    for cat in ("temperature_air", "percentage_points", "humidity", "co2", "hydronic_temperature", "pressure"):
        for key, spec in defaults.get(cat, {}).items():
            for alias in spec.get("logical_aliases", [key]):
                out[alias] = (cat, key, spec)
    return out


def roc_per_hour(series: pd.Series, ts: pd.Series) -> pd.Series:
    """Point-to-point rate of change normalized to per-hour."""
    delta = series.diff().abs()
    dt_h = ts.diff().dt.total_seconds() / 3600.0
    roc = delta / dt_h.replace(0, np.nan)
    return roc


def flatline_mask(
    s: pd.Series,
    window_samples: int,
    min_delta: float,
    *,
    require_fan_on: pd.Series | None = None,
) -> pd.Series:
    rmin = s.rolling(window_samples, min_periods=window_samples).min()
    rmax = s.rolling(window_samples, min_periods=window_samples).max()
    flat = s.notna() & ((rmax - rmin) <= min_delta)
    if require_fan_on is not None:
        flat = flat & require_fan_on.fillna(False)
    return flat


def startup_suppression_mask(
    fan_on: pd.Series,
    poll_seconds: float,
    suppress_minutes: float,
) -> pd.Series:
    """Suppress ROC faults for N minutes after fan transitions off->on."""
    n = max(1, int(round(suppress_minutes * 60 / poll_seconds)))
    started = fan_on & ~fan_on.shift(1).astype("boolean").fillna(False).astype(bool)
    groups = started.cumsum()
    since_start = fan_on.groupby(groups).cumcount()
    return fan_on & (since_start < n)


@dataclass
class SensorQAResult:
    point: str
    sensor_type: str
    level: str
    fault_code: str
    fault_name: str
    status: str
    minutes: float
    samples: int
    flag_column: str = ""
    hard_min: float | None = None
    hard_max: float | None = None
    max_roc_per_hour: float | None = None
    evidence: str = ""


def apply_temperature_qa(
    d: pd.DataFrame,
    alias: str,
    spec: dict,
    *,
    poll_seconds: float,
    confirm_n: int,
    fan_on: pd.Series | None = None,
    suppress_roc: pd.Series | None = None,
    use_imperial: bool = True,
) -> tuple[dict[str, pd.Series], list[SensorQAResult]]:
    """Apply L1–L3 QA to one temperature column already in d[alias]."""
    s = d[alias]
    flags: dict[str, pd.Series] = {}
    results: list[SensorQAResult] = []
    prefix = alias.upper()

    lo, hi = spec["hard_range_ip" if use_imperial else "hard_range_si"]
    flags[f"q_{alias}_l1_range"] = s.notna() & ((s < lo) | (s > hi))

    nrm = spec.get("normal_range_ip" if use_imperial else "normal_range_si")
    if nrm and nrm[0] is not None:
        flags[f"q_{alias}_normal_band"] = s.notna() & ((s < nrm[0]) | (s > nrm[1]))
    else:
        flags[f"q_{alias}_normal_band"] = pd.Series(False, index=d.index)

    max_roc = spec["max_roc_per_hour_ip" if use_imperial else "max_roc_per_hour_si"]
    roc = roc_per_hour(s, d["timestamp"])
    flags[f"q_{alias}_roc_raw"] = s.notna() & (roc > max_roc)
    if suppress_roc is not None:
        flags[f"q_{alias}_l2_roc"] = flags[f"q_{alias}_roc_raw"] & ~suppress_roc.fillna(False)
    else:
        flags[f"q_{alias}_l2_roc"] = flags[f"q_{alias}_roc_raw"]

    spike_key = "spike_max_delta_ip_5min" if use_imperial else "spike_max_delta_si_5min"
    if spike_key in spec:
        dt_min = d["timestamp"].diff().dt.total_seconds() / 60.0
        spike = s.diff().abs()
        flags[f"q_{alias}_l2_spike"] = (
            s.notna()
            & (dt_min <= 6)
            & (spike > spec[spike_key])
        )
        if suppress_roc is not None:
            flags[f"q_{alias}_l2_spike"] = flags[f"q_{alias}_l2_spike"] & ~suppress_roc.fillna(False)
    else:
        flags[f"q_{alias}_l2_spike"] = pd.Series(False, index=d.index)

    defaults = load_sensor_defaults()
    pers = defaults["persistence"]
    flat_win = max(4, int(round(pers["flatline_window_hours"] * 3600 / poll_seconds)))
    flat_tol = pers["flatline_min_delta_f" if use_imperial else "flatline_min_delta_c"]
    require_fan = fan_on if alias in ("mat", "sat", "rat") else None
    flags[f"q_{alias}_l3_flat"] = flatline_mask(s, flat_win, flat_tol, require_fan_on=require_fan)

    for level, key, code_suffix, name in [
        ("L1", f"q_{alias}_l1_range", "HARD_RANGE", "Hard range fault"),
        ("L2", f"q_{alias}_l2_roc", "ROC_SPIKE", "Rate-of-change spike"),
        ("L2", f"q_{alias}_l2_spike", "SHORT_SPIKE", "Short-interval spike"),
        ("L3", f"q_{alias}_l3_flat", "STALE_FLATLINE", "Stale / flatline"),
    ]:
        mask = flags[key]
        mins = float(mask.sum()) * poll_seconds / 60.0
        n = int(mask.sum())
        if n > 0:
            results.append(SensorQAResult(
                point=alias,
                sensor_type=spec.get("_sensor_key", alias),
                level=level,
                fault_code=f"SENSOR_{prefix}_{level}_{code_suffix}",
                fault_name=f"{alias.upper()} {name}",
                status="fault" if level in ("L1", "L3") else "warning",
                minutes=mins,
                samples=n,
                flag_column=key,
                hard_min=lo,
                hard_max=hi,
                max_roc_per_hour=max_roc,
                evidence=f"{n} samples ({mins:.0f} min); limits [{lo}, {hi}], max ROC {max_roc}/hr",
            ))

    warn_mask = flags[f"q_{alias}_normal_band"]
    wn = int(warn_mask.sum())
    if wn > 0:
        wm = float(wn) * poll_seconds / 60.0
        nlo, nhi = nrm
        results.append(SensorQAResult(
            point=alias,
            sensor_type=alias,
            level="L1",
            fault_code=f"SENSOR_{prefix}_NORMAL_BAND",
            fault_name=f"{alias.upper()} outside normal operating band",
            status="warning",
            minutes=wm,
            samples=wn,
            flag_column=f"q_{alias}_normal_band",
            hard_min=nlo,
            hard_max=nhi,
            evidence=f"{wn} samples outside normal band [{nlo}, {nhi}] — investigate, not hard fault",
        ))

    return flags, results


def apply_percentage_qa(
    d: pd.DataFrame,
    alias: str,
    spec: dict,
    poll_seconds: float,
) -> tuple[dict[str, pd.Series], list[SensorQAResult]]:
    s_raw = pd.to_numeric(d[alias], errors="coerce")
    mx = s_raw.max()
    if pd.notna(mx) and mx > 1.05:
        s = s_raw / 100.0 if mx <= 105 else s_raw / 100.0
    else:
        s = s_raw
    lo, hi = spec["hard_range_percent"]
    lo, hi = lo / 100.0, hi / 100.0
    flags = {f"q_{alias}_l1_range": s.notna() & ((s < lo) | (s > hi))}
    results: list[SensorQAResult] = []
    mask = flags[f"q_{alias}_l1_range"]
    n = int(mask.sum())
    if n > 0:
        results.append(SensorQAResult(
            point=alias,
            sensor_type=alias,
            level="L1",
            fault_code=f"SENSOR_{alias.upper()}_L1_HARD_RANGE",
            fault_name=f"{alias.upper()} feedback out of range",
            status="fault",
            minutes=float(n) * poll_seconds / 60.0,
            samples=n,
            flag_column=f"q_{alias}_l1_range",
            hard_min=lo * 100,
            hard_max=hi * 100,
            evidence=f"Value outside [{lo*100:.0f}, {hi*100:.0f}]%",
        ))
    return flags, results


def apply_physics_plausibility(
    d: pd.DataFrame,
    mat_spec: dict,
    sat_spec: dict,
    *,
    fan_on: pd.Series,
    stable: pd.Series,
    poll_seconds: float,
    use_imperial: bool = True,
) -> tuple[dict[str, pd.Series], list[SensorQAResult]]:
    """Level 4 cross-sensor checks for AHU air temperatures."""
    flags: dict[str, pd.Series] = {}
    results: list[SensorQAResult] = []
    db_key = "deadband_ip" if use_imperial else "deadband_si"
    split_key = "oat_rat_min_split_ip" if use_imperial else "oat_rat_min_split_si"
    pl = mat_spec.get("plausibility", {})
    db = pl.get(db_key, 4)
    split = pl.get(split_key, 5)

    oat, rat, mat = d["oat"], d["rat"], d["mat"]
    meaningful = (oat - rat).abs() > split
    env_lo = np.minimum(oat, rat) - db
    env_hi = np.maximum(oat, rat) + db
    flags["q_mat_l4_envelope"] = (
        fan_on & meaningful & mat.notna()
        & ((mat < env_lo) | (mat > env_hi))
    )

    sat_pl = sat_spec.get("plausibility", {})
    coil_off = sat_pl.get("coil_off_pct", 10) / 100.0
    sat_db = sat_pl.get("sat_mat_max_diff_when_coils_off_ip" if use_imperial else "sat_mat_max_diff_when_coils_off_si", 4)
    coils_off = (d["clg"] < coil_off) & (d.get("htg", pd.Series(0, index=d.index)) < coil_off)
    flags["q_sat_l4_mat_mismatch"] = (
        stable & coils_off & d["sat"].notna() & d["mat"].notna()
        & ((d["sat"] - d["mat"]).abs() > sat_db)
    )

    for alias, key, code, name in [
        ("mat", "q_mat_l4_envelope", "MAT_OAT_RAT_ENVELOPE", "MAT not between OAT and RAT"),
        ("sat", "q_sat_l4_mat_mismatch", "SAT_MAT_MISMATCH", "SAT inconsistent with MAT when coils off"),
    ]:
        mask = flags[key]
        n = int(mask.sum())
        if n > 0:
            results.append(SensorQAResult(
                point=alias,
                sensor_type="plausibility",
                level="L4",
                fault_code=f"SENSOR_{code}",
                fault_name=name,
                status="fault",
                minutes=float(n) * poll_seconds / 60.0,
                samples=n,
                flag_column=key,
                evidence=f"{n} samples failed physics plausibility (deadband {db})",
            ))

    return flags, results


def run_ahu_sensor_qa(
    d: pd.DataFrame,
    *,
    poll_seconds: float = 900,
    confirm_n: int = 1,
    use_imperial: bool = True,
) -> tuple[pd.DataFrame, list[SensorQAResult]]:
    """
    Enrich dataframe with sensor QA flags and return detailed results.
    Expects columns: timestamp, oat, rat, mat, sat, fan_on, stable, clg, htg (optional).
    """
    defaults = load_sensor_defaults()
    alias_map = _alias_map(defaults)
    all_flags: dict[str, pd.Series] = {}
    all_results: list[SensorQAResult] = []

    pers = defaults["persistence"]
    suppress = startup_suppression_mask(
        d["fan_on"],
        poll_seconds,
        pers["startup_suppression_minutes"],
    )

    temp_specs = defaults["temperature_air"]
    for alias in ("oat", "rat", "mat", "sat"):
        if alias not in d.columns:
            continue
        cat, key, spec = alias_map[alias]
        spec = {**spec, "_sensor_key": key}
        flags, res = apply_temperature_qa(
            d, alias, spec,
            poll_seconds=poll_seconds,
            confirm_n=confirm_n,
            fan_on=d.get("fan_on"),
            suppress_roc=suppress,
            use_imperial=use_imperial,
        )
        all_flags.update(flags)
        all_results.extend(res)

    pct_specs = defaults["percentage_points"]
    for alias in ("oad_cmd", "oad_pos", "clg"):
        if alias not in d.columns:
            continue
        _, key, spec = alias_map.get(alias, ("percentage_points", alias, pct_specs.get("valve_position", {})))
        flags, res = apply_percentage_qa(d, alias, spec, poll_seconds)
        all_flags.update(flags)
        all_results.extend(res)

    if all(c in d.columns for c in ("oat", "rat", "mat", "sat")):
        mat_spec = temp_specs["mixed_air_temp"]
        sat_spec = temp_specs["supply_air_temp"]
        flags, res = apply_physics_plausibility(
            d, mat_spec, sat_spec,
            fan_on=d["fan_on"],
            stable=d.get("stable", d["fan_on"]),
            poll_seconds=poll_seconds,
            use_imperial=use_imperial,
        )
        all_flags.update(flags)
        all_results.extend(res)

    out = d.copy()
    for k, v in all_flags.items():
        out[k] = v

    # Rollup columns for economizer hierarchy
    l1_cols = [c for c in all_flags if "_l1_range" in c]
    l2_cols = [c for c in all_flags if "_l2_" in c]
    l3_cols = [c for c in all_flags if "_l3_" in c]
    l4_cols = [c for c in all_flags if "_l4_" in c]
    out["sensor_l1_any"] = out[l1_cols].any(axis=1) if l1_cols else False
    out["sensor_l2_any"] = out[l2_cols].any(axis=1) if l2_cols else False
    out["sensor_l3_any"] = out[l3_cols].any(axis=1) if l3_cols else False
    out["sensor_l4_any"] = out[l4_cols].any(axis=1) if l4_cols else False
    out["sensor_qa_any"] = out[["sensor_l1_any", "sensor_l2_any", "sensor_l3_any", "sensor_l4_any"]].any(axis=1)

    return out, all_results


def sensor_results_summary(results: list[SensorQAResult]) -> pd.DataFrame:
    rows = []
    for r in results:
        rows.append({
            "point": r.point,
            "level": r.level,
            "fault_code": r.fault_code,
            "fault_name": r.fault_name,
            "status": r.status,
            "total_fault_minutes": r.minutes,
            "affected_samples": r.samples,
            "hard_min": r.hard_min,
            "hard_max": r.hard_max,
            "max_roc_per_hour": r.max_roc_per_hour,
            "evidence_summary": r.evidence,
        })
    return pd.DataFrame(rows)


def metric_reference_table() -> pd.DataFrame:
    """Exportable table of hard ranges and ROC limits (imperial + metric)."""
    defaults = load_sensor_defaults()
    rows = []
    for cat in ("temperature_air", "hydronic_temperature"):
        for key, spec in defaults.get(cat, {}).items():
            rows.append({
                "category": cat,
                "sensor": key,
                "hard_min_ip": spec.get("hard_range_ip", [None, None])[0],
                "hard_max_ip": spec.get("hard_range_ip", [None, None])[1],
                "hard_min_si": spec.get("hard_range_si", [None, None])[0],
                "hard_max_si": spec.get("hard_range_si", [None, None])[1],
                "normal_min_ip": (spec.get("normal_range_ip") or [None, None])[0],
                "normal_max_ip": (spec.get("normal_range_ip") or [None, None])[1],
                "max_roc_per_hour_ip": spec.get("max_roc_per_hour_ip"),
                "max_roc_per_hour_si": spec.get("max_roc_per_hour_si"),
            })
    return pd.DataFrame(rows)
