"""ASHRAE Guideline 14 monthly NMBE / CVRMSE helpers (vibe20-compatible)."""
from __future__ import annotations

import math
from typing import Iterable

NMBE_PASS = 5.0
CVRMSE_PASS = 15.0


def nmbe_cvrmse(observed: Iterable[float], simulated: Iterable[float]) -> dict[str, float]:
    """NMBE and CVRMSE in percent (ASHRAE Guideline 14)."""
    pairs = [
        (float(o), float(s))
        for o, s in zip(observed, simulated)
        if o is not None and s is not None
    ]
    pairs = [(o, s) for o, s in pairs if not (math.isnan(o) or math.isnan(s))]
    if not pairs:
        return {"n": 0, "nmbe_pct": float("nan"), "cvrmse_pct": float("nan"), "mean_obs": float("nan")}
    n = len(pairs)
    mean_obs = sum(o for o, _ in pairs) / n
    if abs(mean_obs) < 1e-12:
        return {"n": n, "nmbe_pct": float("nan"), "cvrmse_pct": float("nan"), "mean_obs": mean_obs}
    nmbe = sum(o - s for o, s in pairs) / (n * mean_obs) * 100.0
    denom = n - 1 if n > 1 else n
    mse = sum((o - s) ** 2 for o, s in pairs) / denom
    cvrmse = math.sqrt(mse) / abs(mean_obs) * 100.0
    return {
        "n": n,
        "nmbe_pct": round(nmbe, 3),
        "cvrmse_pct": round(cvrmse, 3),
        "mean_obs": round(mean_obs, 3),
    }


def pass_fail(stats: dict[str, float]) -> str:
    if stats.get("n", 0) == 0 or math.isnan(stats.get("nmbe_pct", float("nan"))):
        return "insufficient_data"
    if abs(stats["nmbe_pct"]) <= NMBE_PASS and stats["cvrmse_pct"] <= CVRMSE_PASS:
        return "pass"
    return "fail"


def gl14_distance(stats: dict[str, float]) -> float:
    """Scalar 'how far from pass' for progress plots (0 = at/inside gate)."""
    if stats.get("n", 0) == 0 or math.isnan(stats.get("nmbe_pct", float("nan"))):
        return float("nan")
    nmbe_over = max(0.0, abs(stats["nmbe_pct"]) - NMBE_PASS)
    cv_over = max(0.0, stats["cvrmse_pct"] - CVRMSE_PASS)
    return round(nmbe_over + cv_over, 3)
