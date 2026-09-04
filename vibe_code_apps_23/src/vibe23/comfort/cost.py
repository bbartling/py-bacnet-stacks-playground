"""Comfort monetization for net-welfare headlines (ILLUSTRATIVE WTP)."""
from __future__ import annotations

from typing import Sequence

from ..residential.constants import DT_HOURS, MAX_COOL_F, MAX_HEAT_F


def degree_hours_abs_delta(
    candidate_f: Sequence[float],
    reference_f: Sequence[float],
    *,
    dt_hours: float = DT_HOURS,
) -> float:
    """Σ |T_cand − T_ref| · Δt  (°F·h)."""
    if len(candidate_f) != len(reference_f):
        raise ValueError("temperature series length mismatch")
    return float(sum(abs(float(c) - float(r)) * dt_hours for c, r in zip(candidate_f, reference_f, strict=True)))


def degree_hours_outside_band(
    temps_f: Sequence[float],
    *,
    low_f: float = MAX_HEAT_F,
    high_f: float = MAX_COOL_F,
    dt_hours: float = DT_HOURS,
) -> dict[str, float]:
    low_dh = 0.0
    high_dh = 0.0
    for t in temps_f:
        v = float(t)
        if v < low_f:
            low_dh += (low_f - v) * dt_hours
        elif v > high_f:
            high_dh += (v - high_f) * dt_hours
    return {
        "low_degree_hours": low_dh,
        "high_degree_hours": high_dh,
        "total_degree_hours": low_dh + high_dh,
        "low_f": float(low_f),
        "high_f": float(high_f),
    }


def comfort_cost_usd(degree_hours: float, *, wtp_usd_per_f_h: float) -> float:
    if wtp_usd_per_f_h < 0:
        raise ValueError("wtp_usd_per_f_h must be non-negative")
    return float(degree_hours) * float(wtp_usd_per_f_h)


def net_welfare_usd(
    *,
    bill_savings_usd: float,
    degree_hours: float,
    wtp_usd_per_f_h: float,
) -> dict[str, float]:
    """Net welfare = bill savings − ILLUSTRATIVE comfort cost."""
    comfort = comfort_cost_usd(degree_hours, wtp_usd_per_f_h=wtp_usd_per_f_h)
    return {
        "bill_savings_usd": float(bill_savings_usd),
        "degree_hours": float(degree_hours),
        "wtp_usd_per_f_h": float(wtp_usd_per_f_h),
        "comfort_cost_usd": comfort,
        "net_welfare_usd": float(bill_savings_usd) - comfort,
    }
