"""Deterministic grid validation-leader selection (cost + readiness; not training reward)."""
from __future__ import annotations

from typing import Any, Sequence


def readiness_checked_school(
    day_rows: Sequence[dict[str, Any]],
    *,
    checked_school_days: Sequence[str],
) -> dict[str, Any]:
    checked = [r for r in day_rows if str(r.get("day"))[:10] in set(checked_school_days)]
    ready = [r for r in checked if bool(r.get("readiness_ok"))]
    n_c = len(checked)
    n_r = len(ready)
    return {
        "checked_school_days": n_c,
        "ready_checked_school_days": n_r,
        "readiness_rate_checked_school_days": (float(n_r) / float(n_c)) if n_c else None,
        "ready_on_all_checked_school_days": n_c > 0 and n_r == n_c,
        "wording": (
            f"Ready on {n_r}/{n_c} checked school days; "
            f"non-school days were not subject to the school-start readiness gate."
        ),
    }


def aggregate_candidate(
    *,
    candidate_id: str,
    action_index: int,
    day_rows: Sequence[dict[str, Any]],
    checked_school_days: Sequence[str],
    severe: int = 0,
    fatal: int = 0,
) -> dict[str, Any]:
    rows = list(day_rows)
    energy = sum(float(r.get("energy_cost") or 0.0) for r in rows)
    demand = sum(float(r.get("incremental_demand_cost") or 0.0) for r in rows)
    peak = max((float(r.get("peak_kw") or 0.0) for r in rows), default=0.0)
    kwh = sum(float(r.get("daily_kwh") or 0.0) for r in rows)
    comfort = sum(float(r.get("occupied_dh") or 0.0) for r in rows)
    movement = sum(float(r.get("movement") or 0.0) for r in rows)
    valid = all(bool(r.get("valid")) for r in rows) and len(rows) > 0
    ready = readiness_checked_school(rows, checked_school_days=checked_school_days)
    eligible = (
        valid
        and int(severe) == 0
        and int(fatal) == 0
        and bool(ready["ready_on_all_checked_school_days"])
    )
    return {
        "candidate_id": str(candidate_id),
        "action_index": int(action_index),
        "n_days": len(rows),
        "energy_cost": float(energy),
        "incremental_demand_cost": float(demand),
        "total_cost": float(energy + demand),
        "peak_kw_max": float(peak),
        "daily_kwh_sum": float(kwh),
        "occupied_comfort_dh": float(comfort),
        "schedule_movement": float(movement),
        "valid": bool(valid),
        "severe": int(severe),
        "fatal": int(fatal),
        "readiness": ready,
        "eligible": bool(eligible),
        "day_rows": rows,
    }


def select_grid_validation_leader(candidates: Sequence[dict[str, Any]]) -> dict[str, Any]:
    eligible = [c for c in candidates if c.get("eligible")]
    if not eligible:
        return {
            "status": "NO_FULLY_READY_GRID_CANDIDATE",
            "grid_validation_leader": None,
            "eligible_count": 0,
        }
    ranked = sorted(
        eligible,
        key=lambda c: (
            float(c["total_cost"]),
            float(c["peak_kw_max"]),
            float(c["occupied_comfort_dh"]),
            float(c["schedule_movement"]),
            str(c["candidate_id"]),
        ),
    )
    leader = ranked[0]
    return {
        "status": "OK",
        "grid_validation_leader": leader["candidate_id"],
        "action_index": leader["action_index"],
        "total_cost": leader["total_cost"],
        "peak_kw_max": leader["peak_kw_max"],
        "eligible_count": len(eligible),
        "leader": leader,
    }


def compare_grid_vs_rl(
    *,
    grid: dict[str, Any] | None,
    rl_total: float,
    rl_peak: float,
    rl_ready: bool,
    screen_exhaustive: bool,
) -> str:
    if not screen_exhaustive:
        # Still compute cost comparison but label may be overridden by caller
        pass
    if grid is None or not grid.get("eligible"):
        return "NO_FULLY_READY_GRID_CANDIDATE"
    if not rl_ready:
        return "NOT_COMPARABLE_CONTRACT_MISMATCH"
    g_cost = float(grid["total_cost"])
    g_peak = float(grid["peak_kw_max"])
    if abs(g_cost - float(rl_total)) < 1e-6:
        return "COST_TIE_DIFFERENT_PEAK" if abs(g_peak - float(rl_peak)) > 1e-6 else "COST_TIE_DIFFERENT_PEAK"
    if g_cost < float(rl_total):
        return "GRID_LOWER_COST_AND_READY"
    return "RL_LOWER_COST_AND_READY"
