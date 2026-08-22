"""Anytime regret analysis for preregistered candidate order."""
from __future__ import annotations

from typing import Any, Mapping, Sequence


def best_fully_ready_cost(rows: Sequence[Mapping[str, Any]]) -> float | None:
    ready = [
        float(r["score"]["total_modeled_objective"])
        for r in rows
        if r.get("score", {}).get("fully_ready_eligible") and r.get("status") == "OK"
    ]
    return min(ready) if ready else None


def anytime_curve(
    ordered_results: Sequence[Mapping[str, Any]],
    *,
    markers: Sequence[int] = (10, 25, 50, 100),
) -> dict[str, Any]:
    """ordered_results must follow the preregistered anytime evaluation order."""
    exhaustive = best_fully_ready_cost(ordered_results)
    points = []
    best_so_far: float | None = None
    best_id = None
    for i, row in enumerate(ordered_results, start=1):
        score = row.get("score") or {}
        if row.get("status") == "OK" and score.get("fully_ready_eligible"):
            cost = float(score["total_modeled_objective"])
            if best_so_far is None or cost < best_so_far:
                best_so_far = cost
                best_id = row.get("candidate_id")
        if i in markers or i == len(ordered_results):
            regret = None
            if exhaustive is not None and best_so_far is not None:
                regret = best_so_far - exhaustive
            points.append(
                {
                    "n": i,
                    "best_fully_ready_cost": best_so_far,
                    "best_candidate_id": best_id,
                    "regret": regret,
                }
            )
    within_1pct = None
    within_10usd = None
    if exhaustive is not None:
        running = None
        for i, row in enumerate(ordered_results, start=1):
            score = row.get("score") or {}
            if row.get("status") == "OK" and score.get("fully_ready_eligible"):
                cost = float(score["total_modeled_objective"])
                running = cost if running is None else min(running, cost)
            if running is None:
                continue
            if within_1pct is None and running <= exhaustive * 1.01:
                within_1pct = i
            if within_10usd is None and running <= exhaustive + 10.0:
                within_10usd = i
    return {
        "exhaustive_best_fully_ready_cost": exhaustive,
        "points": points,
        "candidates_within_1pct": within_1pct,
        "candidates_within_10_usd": within_10usd,
        "n_evaluated": len(ordered_results),
    }


def recommend_budget(curve: Mapping[str, Any], *, wall_by_n: Mapping[int, float], hard_s: float = 1800.0) -> str:
    """Pick 25/50/100/exhaustive from regret vs wall."""
    pts = {int(p["n"]): p for p in curve.get("points") or []}
    exhaustive_n = int(curve.get("n_evaluated") or 0)
    # Prefer smallest n with regret ~0 and wall under hard deadline.
    for n in (25, 50, 100, exhaustive_n):
        if n not in pts and n != exhaustive_n:
            continue
        p = pts.get(n) or pts.get(exhaustive_n)
        if not p:
            continue
        wall = float(wall_by_n.get(n) or wall_by_n.get(exhaustive_n) or 1e18)
        regret = p.get("regret")
        if regret is not None and regret <= 1e-6 and wall <= hard_s:
            return "exhaustive" if n == exhaustive_n else str(n)
        if regret is not None and regret <= abs(float(curve.get("exhaustive_best_fully_ready_cost") or 0)) * 0.01:
            if wall <= hard_s:
                return "exhaustive" if n == exhaustive_n else str(n)
    # Fallback: largest affordable marker
    for n in (100, 50, 25):
        wall = float(wall_by_n.get(n) or 1e18)
        if wall <= hard_s:
            return str(n)
    return "25"
