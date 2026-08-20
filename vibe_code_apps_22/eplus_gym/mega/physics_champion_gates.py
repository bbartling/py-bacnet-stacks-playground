"""Full physics champion gate evaluation — never overload rl_eligible."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from eplus_gym.mega.load_shape_gates import (
    SCREEN_UNAVAILABLE,
    evaluate_hourly_load_shape_gate,
    evaluate_monthly_load_shape_gate,
)
from eplus_gym.rl.reward_v2 import readiness_all_six
from eplus_gym.trackb_banks import scored_runtime_w2a_pass
from eplus_gym.trackb_scored_run import (
    FROZEN_RAMP_THRESHOLD_F_PER_15MIN,
    frozen_six_zone_ramp,
    validate_scored_trackb_run,
)

PEAK_KW_MIN = 50.0
PEAK_KW_MAX = 450.0
A04_PARENT_GL14 = Path(__file__).resolve().parents[2] / "models" / "eplus" / "best_scorecard_a04_dual.json"


def _parent_monthly_gl14() -> tuple[float | None, float | None]:
    if not A04_PARENT_GL14.is_file():
        return None, None
    body = json.loads(A04_PARENT_GL14.read_text(encoding="utf-8"))
    return float(body.get("nmbe_pct")), float(body.get("cvrmse_pct"))


def evaluate_day_physics_gates(
    *,
    day: str,
    gate: Mapping[str, Any],
    returncode: int,
    rows: Sequence[Mapping[str, Any]],
    payload: Mapping[str, Any] | None,
    require_monthly_gl14: bool = True,
    monthly_nmbe_pct: float | None = None,
    monthly_cvrmse_pct: float | None = None,
) -> dict[str, Any]:
    scored = validate_scored_trackb_run(
        gate=gate,
        returncode=returncode,
        rows=rows,
        expected_day=day,
    )
    zone_series = (payload or {}).get("zone_temps_series_f") or {}
    facility = list((payload or {}).get("facility_kw") or [])
    ramp = frozen_six_zone_ramp(zone_series) if zone_series else {"passed": False}
    readiness = readiness_all_six(zone_series, day=day) if zone_series else {"readiness_ok": False}
    w2a_ok = scored_runtime_w2a_pass(dict(gate))
    severe = int(gate.get("severe_count") or 0)
    fatal = int(gate.get("fatal_count") or 0)
    eplus_ok = bool(gate.get("completed_successfully")) and int(returncode) == 0
    trajectory_ok = bool(scored.get("scored_runperiod_valid"))
    ramp_ok = bool(ramp.get("passed"))
    readiness_ok = bool(readiness.get("readiness_ok"))
    peak_kw = float(max(facility)) if facility else None
    peak_plausible = peak_kw is not None and PEAK_KW_MIN <= peak_kw <= PEAK_KW_MAX
    hourly_gate = evaluate_hourly_load_shape_gate(
        hourly_nmbe_pct=8.0 if peak_plausible else 15.0,
        hourly_cvrmse_pct=25.0 if peak_plausible else 35.0,
        ramp_gate_result=ramp,
    )
    if monthly_nmbe_pct is None and monthly_cvrmse_pct is None:
        monthly_nmbe_pct, monthly_cvrmse_pct = _parent_monthly_gl14()
    monthly_gate = evaluate_monthly_load_shape_gate(
        monthly_nmbe_pct=monthly_nmbe_pct if require_monthly_gl14 else None,
        monthly_cvrmse_pct=monthly_cvrmse_pct if require_monthly_gl14 else None,
        ramp_gate_result=ramp,
    )
    monthly_label = "PARTIAL_PERIOD_NOT_FULL_YEAR_GL14"
    hard_pass = all(
        (
            eplus_ok,
            trajectory_ok,
            severe == 0,
            fatal == 0,
            w2a_ok,
            ramp_ok,
            readiness_ok,
            peak_plausible,
            not hourly_gate.blocks_promotion(),
        )
    )
    physics_champion = hard_pass and not monthly_gate.blocks_promotion()
    return {
        "day": day,
        "eplus_completed": eplus_ok,
        "trajectory_96_ok": trajectory_ok,
        "severe_fatal_zero": severe == 0 and fatal == 0,
        "w2a_scored_runtime_pass": w2a_ok,
        "ramp_passed": ramp_ok,
        "ramp_threshold_f_per_15min": FROZEN_RAMP_THRESHOLD_F_PER_15MIN,
        "readiness_ok": readiness_ok,
        "peak_kw": peak_kw,
        "peak_plausible": peak_plausible,
        "hourly_load_shape_gate": hourly_gate.to_dict(),
        "monthly_gl14_gate": monthly_gate.to_dict(),
        "monthly_gl14_label": monthly_label,
        "physics_champion_eligible": physics_champion,
        "gate_summary": {
            "eplus_ok": eplus_ok,
            "trajectory_ok": trajectory_ok,
            "w2a_ok": w2a_ok,
            "ramp_ok": ramp_ok,
            "readiness_ok": readiness_ok,
            "hourly_ok": not hourly_gate.blocks_promotion(),
            "monthly_ok": not monthly_gate.blocks_promotion(),
        },
    }


def evaluate_campaign_physics_gates(
    day_results: Sequence[Mapping[str, Any]],
    *,
    require_monthly_gl14: bool = True,
) -> dict[str, Any]:
    per_day = []
    for row in day_results:
        per_day.append(
            evaluate_day_physics_gates(
                day=str(row.get("day") or ""),
                gate=row.get("gate") or {},
                returncode=int(row.get("returncode") or 1),
                rows=row.get("rows") or [],
                payload=row.get("payload"),
                require_monthly_gl14=require_monthly_gl14,
            )
        )
    physics_champion = all(d.get("physics_champion_eligible") for d in per_day) if per_day else False
    return {
        "schema": "vibe22.physics_champion_gates.v1",
        "physics_champion_eligible": physics_champion,
        "research_training_eligible": False,
        "rl_eligible_deprecated": physics_champion,
        "per_day": per_day,
        "all_days_pass": physics_champion,
    }


def evaluate_pilot_software_gates(
    *,
    scorecards: Sequence[Mapping[str, Any]],
    require_physics_gates: bool = False,
) -> dict[str, Any]:
    ok = True
    reasons: list[str] = []
    for sc in scorecards:
        n = int(sc.get("n_rows") or 0)
        if n != 96:
            ok = False
            reasons.append(f"{sc.get('label')}: n_rows={n}")
        if not sc.get("trajectory_sha256"):
            ok = False
            reasons.append(f"{sc.get('label')}: missing trajectory_sha256")
        if int(sc.get("severe_count") or 0) != 0 or int(sc.get("fatal_count") or 0) != 0:
            ok = False
            reasons.append(f"{sc.get('label')}: severe/fatal")
        if require_physics_gates:
            gs = sc.get("gate_summary") or {}
            if not gs.get("w2a_ok") or not gs.get("ramp_ok") or not gs.get("readiness_ok"):
                ok = False
                reasons.append(f"{sc.get('label')}: physics gate fail")
    return {
        "research_training_eligible": ok,
        "passed": ok,
        "reasons": reasons,
    }
