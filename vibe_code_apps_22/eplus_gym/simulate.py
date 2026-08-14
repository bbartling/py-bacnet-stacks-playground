"""LIVE EnergyPlus trajectory calendar checks (no farm lookup)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional


def day_for_step(begin: str, step: int) -> str:
    return (date.fromisoformat(str(begin)[:10]) + timedelta(days=int(step) // 96)).isoformat()


def runtime_day_from_obs(od: Dict[str, Any]) -> Optional[str]:
    try:
        y = int(float(od["ep_year"]))
        m = int(float(od["ep_month"]))
        d = int(float(od["ep_day"]))
        if y <= 0 or m <= 0 or d <= 0:
            return None
        return date(y, m, d).isoformat()
    except (KeyError, TypeError, ValueError):
        return None


def validate_live_trajectory_calendar(
    rows: List[Dict[str, Any]],
    *,
    expected_day: Optional[str] = None,
    expected_end: Optional[str] = None,
    expect_steps: int = 96,
) -> Dict[str, Any]:
    issues: List[str] = []
    if len(rows) != int(expect_steps):
        issues.append(f"expected {expect_steps} scored rows, got {len(rows)}")
    kinds = [int(float(r.get("kind_of_sim", -1))) for r in rows]
    if any(k != 3 for k in kinds):
        issues.append("non-weather kind_of_sim in scored rows (sizing contamination)")
    warm = [float(r.get("warmup", 0.0)) for r in rows]
    if any(w > 0.5 for w in warm):
        issues.append("warmup rows present in scored trajectory")
    days = [runtime_day_from_obs(r) for r in rows]
    if any(d is None for d in days):
        issues.append("missing Runtime calendar fields on scored rows")
    valid_days = [d for d in days if d]
    one_day = int(expect_steps) <= 96
    if expected_day and valid_days:
        if one_day:
            if any(d != expected_day for d in valid_days):
                issues.append(
                    f"calendar day != expected {expected_day}: {sorted(set(valid_days))}"
                )
        else:
            try:
                begin_d = date.fromisoformat(str(expected_day)[:10])
                end_s = expected_end or (
                    begin_d + timedelta(days=max(0, (int(expect_steps) - 1) // 96))
                ).isoformat()
                end_d = date.fromisoformat(str(end_s)[:10])
                out_of_range = [
                    d
                    for d in valid_days
                    if not (begin_d <= date.fromisoformat(d) <= end_d)
                ]
                if out_of_range:
                    issues.append(
                        f"Runtime dates outside {begin_d.isoformat()}..{end_d.isoformat()}"
                    )
            except ValueError as exc:
                issues.append(f"bad expected period bounds: {exc}")
    ok = not issues
    return {"ok": ok, "issues": issues}
