"""Track B scored-runperiod contract. Return code 0 is not sufficient."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from eplus_gym.control_v2 import ACTION_KEYS
from eplus_gym.objective import BAS_ZONE_COLS

FROZEN_RAMP_THRESHOLD_F_PER_15MIN = 2.651
W2A_SCORED_RUNTIME_BOUND = 0


def rows_from_continuity_payload(payload: Mapping[str, Any], *, expected_day: str) -> list[dict[str, Any]]:
    """Build 96 scored rows from EnergyPlusContinuityPlant.simulate_day output."""
    raw = payload.get("rows")
    if raw:
        return [dict(r) for r in raw]
    fac = list(payload.get("facility_kw") or [])
    series = payload.get("zone_temps_series_f") or {}
    n = len(fac)
    out: list[dict[str, Any]] = []
    for i in range(n):
        rec: dict[str, Any] = {
            "day": str(payload.get("day") or expected_day)[:10],
            "facility_kw": float(fac[i]),
            "local_step": i,
            "timestamp": str(payload.get("first_runtime_timestamp") if i == 0 else payload.get("last_runtime_timestamp") or ""),
        }
        for key, col in zip(ACTION_KEYS, BAS_ZONE_COLS):
            vals = series.get(key) or series.get(col) or []
            if i < len(vals):
                rec[col] = float(vals[i])
                rec[key] = float(vals[i])
        out.append(rec)
    return out


ENGINE_EXECUTED_NO_VALID_SCORED_RUNPERIOD = "ENGINE_EXECUTED_NO_VALID_SCORED_RUNPERIOD"


def validate_scored_trackb_run(
    *,
    gate: Mapping[str, Any],
    returncode: int,
    rows: Sequence[Mapping[str, Any]],
    expected_day: str,
) -> dict[str, Any]:
    issues: list[str] = []
    severe = int(gate.get("severe_count") or 0)
    fatal = int(gate.get("fatal_count") or 0)
    if fatal:
        issues.append(f"fatal_count={fatal}")
    if severe:
        issues.append(f"severe_count={severe}")
    if not rows:
        issues.append("no scored trajectory rows")
    n = len(rows)
    if n and n != 96:
        issues.append(f"n_intervals={n} expected 96")
    days = {str(r.get("day") or "")[:10] for r in rows}
    if rows and days != {str(expected_day)[:10]}:
        issues.append(f"calendar {days} != {expected_day}")
    fac: list[float] = []
    for i, row in enumerate(rows):
        try:
            kw = float(row["facility_kw"])
        except (KeyError, TypeError, ValueError):
            issues.append(f"facility_kw missing at {i}")
            continue
        if kw != kw or kw in (float("inf"), float("-inf")):
            issues.append(f"non-finite facility_kw at {i}")
        fac.append(kw)
        for col in BAS_ZONE_COLS:
            if col in row:
                val = row[col]
            else:
                # allow ACTION_KEYS mapping in compact payloads
                val = None
                for key, alt in ((col, col),):
                    if key in row:
                        val = row[key]
                if val is None:
                    issues.append(f"missing zone {col} at {i}")
                    continue
            try:
                t = float(val)
            except (TypeError, ValueError):
                issues.append(f"non-finite zone {col} at {i}")
                continue
            if t != t:
                issues.append(f"NaN zone {col} at {i}")
    first_ts = str(rows[0].get("timestamp") or rows[0].get("day") or "") if rows else ""
    last_ts = str(rows[-1].get("timestamp") or rows[-1].get("day") or "") if rows else ""
    proven = not issues and n == 96 and severe == 0 and fatal == 0
    status = "VALID_SCORED_RUNPERIOD" if proven else ENGINE_EXECUTED_NO_VALID_SCORED_RUNPERIOD
    return {
        "ok": proven,
        "status": status,
        "scored_runtime_proven": proven,
        "n_intervals": n,
        "first_runtime_timestamp": first_ts,
        "last_runtime_timestamp": last_ts,
        "returncode": int(returncode),
        "issues": issues[:20],
        "engine_returncode_is_not_sufficient": True,
        "scored_runperiod_valid": proven,
    }


def frozen_six_zone_ramp(zone_series: Mapping[str, Sequence[float]]) -> dict[str, Any]:
    max_d = 0.0
    n_samples = 0
    for key in ACTION_KEYS:
        vals = [float(x) for x in (zone_series.get(key) or [])]
        n_samples += max(0, len(vals) - 1)
        for a, b in zip(vals, vals[1:]):
            max_d = max(max_d, abs(b - a))
    passed = n_samples > 0 and max_d <= FROZEN_RAMP_THRESHOLD_F_PER_15MIN
    return {
        "max_f_per_15min": float(max_d),
        "threshold_f_per_15min": FROZEN_RAMP_THRESHOLD_F_PER_15MIN,
        "passed": passed,
        "retuned": False,
        "n_delta_samples": n_samples,
    }


def trajectory_sha256(rows: Sequence[Mapping[str, Any]]) -> str:
    body = json.dumps([dict(r) for r in rows], sort_keys=True, default=str)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def distinct_status_fields(
    *,
    engine_executed: bool,
    sizing_completed: bool,
    scored_runperiod_valid: bool,
    quality_gates_passed: bool,
    model_champion: bool,
) -> dict[str, Any]:
    return {
        "engine_executed": bool(engine_executed),
        "sizing_completed": bool(sizing_completed),
        "scored_runperiod_valid": bool(scored_runperiod_valid),
        "quality_gates_passed": bool(quality_gates_passed),
        "model_champion": bool(model_champion),
        "scored_runperiod_valid_not_derived_from_rc0": True,
    }
