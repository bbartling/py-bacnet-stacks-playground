"""Compact scored-day scorecards for mega physics-repair audits."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from eplus_gym.control_v2 import ACTION_KEYS
from eplus_gym.objective import BAS_ZONE_COLS
from eplus_gym.rl.reward_v2 import occupied_zone_degree_hours, readiness_all_six
from eplus_gym.trackb_scored_run import (
    FROZEN_RAMP_THRESHOLD_F_PER_15MIN,
    frozen_six_zone_ramp,
    rows_from_continuity_payload,
    trajectory_sha256,
    validate_scored_trackb_run,
)

from eplus_gym.mega.physics_champion_gates import evaluate_day_physics_gates

PHYSICS_REPAIR_FAILED = "PHYSICS_REPAIR_FAILED_NOT_RL_ELIGIBLE"


def idf_byte_and_lf_sha256(raw: bytes) -> tuple[str, str]:
    byte_sha = hashlib.sha256(raw).hexdigest()
    lf = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    lf_sha = hashlib.sha256(lf).hexdigest()
    return byte_sha, lf_sha


def slim_trajectory_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    slim: list[dict[str, Any]] = []
    for row in rows:
        rec: dict[str, Any] = {
            "local_step": int(row.get("local_step", len(slim))),
            "facility_kw": round(float(row["facility_kw"]), 4),
        }
        for key, col in zip(ACTION_KEYS, BAS_ZONE_COLS):
            if key in row:
                rec[key] = round(float(row[key]), 4)
            elif col in row:
                rec[key] = round(float(row[col]), 4)
        slim.append(rec)
    return slim


def _zone_min_max(zone_series: Mapping[str, Sequence[float]]) -> dict[str, Any]:
    mins: dict[str, float] = {}
    maxs: dict[str, float] = {}
    for key in ACTION_KEYS:
        vals = [float(x) for x in (zone_series.get(key) or [])]
        if not vals:
            continue
        mins[key] = float(min(vals))
        maxs[key] = float(max(vals))
    all_vals = [v for vs in zone_series.values() for v in vs]
    return {
        "per_zone_min_f": mins,
        "per_zone_max_f": maxs,
        "six_zone_min_f": float(min(all_vals)) if all_vals else None,
        "six_zone_max_f": float(max(all_vals)) if all_vals else None,
    }


def build_compact_scorecard(
    *,
    label: str,
    day: str,
    arm: str,
    child_name: str,
    child_idf_byte_sha256: str,
    child_idf_lf_normalized_sha256: str,
    gate: Mapping[str, Any],
    returncode: int,
    payload: Mapping[str, Any] | None = None,
    physics_status: str = PHYSICS_REPAIR_FAILED,
    rl_eligible: bool = False,
) -> dict[str, Any]:
    rows = rows_from_continuity_payload(payload or {}, expected_day=day) if payload else []
    scored = validate_scored_trackb_run(
        gate=gate,
        returncode=returncode,
        rows=rows,
        expected_day=day,
    )
    zone_series = (payload or {}).get("zone_temps_series_f") or {}
    ramp = frozen_six_zone_ramp(zone_series) if zone_series else {
        "max_f_per_15min": None,
        "threshold_f_per_15min": FROZEN_RAMP_THRESHOLD_F_PER_15MIN,
        "passed": False,
        "n_delta_samples": 0,
    }
    readiness = readiness_all_six(zone_series, day=day) if zone_series else {
        "readiness_ok": False,
        "checked": False,
        "degree_violation": None,
    }
    comfort_dh = (
        float(occupied_zone_degree_hours(zone_series, day=day))
        if zone_series
        else None
    )
    facility = list((payload or {}).get("facility_kw") or [])
    peak_kw = float(max(facility)) if facility else (payload or {}).get("peak_kw")
    daily_kwh = float(sum(facility) * 0.25) if facility else (payload or {}).get("daily_kwh")
    w2a_phase = dict(gate.get("w2a_low_airflow_by_phase") or {})
    severe = int(gate.get("severe_count") or 0)
    fatal = int(gate.get("fatal_count") or 0)
    traj_sha = trajectory_sha256(rows) if rows else None
    slim = slim_trajectory_rows(rows) if rows else []
    physics_gates = evaluate_day_physics_gates(
        day=day,
        gate=gate,
        returncode=returncode,
        rows=rows,
        payload=payload,
        require_monthly_gl14=True,
    )
    physics_champion = bool(physics_gates.get("physics_champion_eligible"))
    gate_summary = dict(physics_gates.get("gate_summary") or {})

    return {
        "schema": "vibe22.mega.compact_scorecard.v2",
        "label": label,
        "day": day,
        "arm": arm,
        "child_name": child_name,
        "physics_status": physics_status,
        "physics_champion_eligible": physics_champion,
        "research_training_eligible": False,
        "rl_eligible": bool(rl_eligible),
        "rl_eligible_deprecated": bool(rl_eligible),
        "child_idf_byte_sha256": child_idf_byte_sha256,
        "child_idf_lf_normalized_sha256": child_idf_lf_normalized_sha256,
        "n_rows": len(rows),
        "trajectory_sha256": traj_sha,
        "slim_trajectory": slim,
        "peak_kw": round(float(peak_kw), 2) if peak_kw is not None else None,
        "daily_kwh": round(float(daily_kwh), 1) if daily_kwh is not None else None,
        "zone_temps": _zone_min_max(zone_series) if zone_series else {},
        "max_ramp_f_per_15min": ramp.get("max_f_per_15min"),
        "ramp_threshold_f_per_15min": ramp.get("threshold_f_per_15min"),
        "ramp_passed": bool(ramp.get("passed")),
        "readiness": readiness,
        "comfort_occupied_degree_hours": comfort_dh,
        "severe_count": severe,
        "fatal_count": fatal,
        "w2a_low_airflow_by_phase": w2a_phase,
        "scored_runtime_w2a_count": w2a_phase.get("scored_runtime"),
        "returncode": int(returncode),
        "scored_runperiod_valid": bool(scored.get("scored_runperiod_valid")),
        "scored_runperiod_status": scored.get("status"),
        "engine_returncode_is_not_sufficient": True,
        "gate_summary": gate_summary,
        "physics_gates": physics_gates,
    }


def write_slim_artifacts(out_dir, scorecard: dict[str, Any]) -> None:
    from pathlib import Path

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "compact_scorecard.json").write_text(
        json.dumps(scorecard, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    slim = scorecard.get("slim_trajectory") or []
    if slim:
        (out / "slim_trajectory.json").write_text(
            json.dumps(slim, indent=2) + "\n",
            encoding="utf-8",
        )
