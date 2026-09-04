"""Inverse economics — what price / incentive is required (not just savings)."""
from __future__ import annotations

from typing import Any


def required_incentive_per_kwh_shed(
    *,
    target_usd_per_event: float,
    kwh_shed: float,
    existing_tou_savings_usd: float = 0.0,
) -> dict[str, float]:
    """Incentive $/kWh shed on top of existing TOU savings to hit a per-event target."""
    if kwh_shed <= 0:
        raise ValueError("kwh_shed must be positive")
    gap = float(target_usd_per_event) - float(existing_tou_savings_usd)
    needed = max(0.0, gap) / float(kwh_shed)
    return {
        "target_usd_per_event": float(target_usd_per_event),
        "kwh_shed": float(kwh_shed),
        "existing_tou_savings_usd": float(existing_tou_savings_usd),
        "gap_usd": float(gap),
        "required_usd_per_kwh_shed": needed,
    }


def required_incentive_per_kw_event(
    *,
    target_usd_per_event: float,
    avg_kw_shed: float,
    existing_tou_savings_usd: float = 0.0,
) -> dict[str, float]:
    if avg_kw_shed <= 0:
        raise ValueError("avg_kw_shed must be positive")
    gap = float(target_usd_per_event) - float(existing_tou_savings_usd)
    needed = max(0.0, gap) / float(avg_kw_shed)
    return {
        "target_usd_per_event": float(target_usd_per_event),
        "avg_kw_shed": float(avg_kw_shed),
        "existing_tou_savings_usd": float(existing_tou_savings_usd),
        "required_usd_per_kw_event": needed,
    }


def required_peak_rate_for_bess_payback(
    *,
    net_capex_usd: float,
    usable_kwh_per_cycle: float,
    round_trip_efficiency: float,
    cycles_per_year: float,
    payback_years: float,
    off_peak_usd_per_kwh: float,
) -> dict[str, float]:
    """Retail arbitrage break-even peak rate assuming one deep cycle value per cycle day.

    Net value per cycle ≈ usable_kwh * (peak - off_peak / η_rt) roughly; we solve for
    the spread that yields ``net_capex / payback_years`` annual cash, then peak rate.
    """
    if usable_kwh_per_cycle <= 0 or round_trip_efficiency <= 0:
        raise ValueError("usable energy / efficiency must be positive")
    if cycles_per_year <= 0 or payback_years <= 0:
        raise ValueError("cycles_per_year and payback_years must be positive")
    annual_needed = float(net_capex_usd) / float(payback_years)
    per_cycle_needed = annual_needed / float(cycles_per_year)
    # Delivered kWh on discharge ≈ usable * sqrt(η) style; use round_trip on energy out.
    # Value ≈ E_out * peak - E_in * off_peak with E_out = usable, E_in = usable / η_rt
    # per_cycle = usable * peak - (usable / η) * off_peak
    # peak = (per_cycle / usable) + off_peak / η
    eta = float(round_trip_efficiency)
    usable = float(usable_kwh_per_cycle)
    peak = (per_cycle_needed / usable) + float(off_peak_usd_per_kwh) / eta
    net_spread = per_cycle_needed / usable
    return {
        "net_capex_usd": float(net_capex_usd),
        "payback_years": float(payback_years),
        "cycles_per_year": float(cycles_per_year),
        "usable_kwh_per_cycle": usable,
        "round_trip_efficiency": eta,
        "off_peak_usd_per_kwh": float(off_peak_usd_per_kwh),
        "annual_cash_needed_usd": annual_needed,
        "usd_per_cycle_needed": per_cycle_needed,
        "required_net_spread_usd_per_kwh": net_spread,
        "required_peak_usd_per_kwh": peak,
        "claim": "ILLUSTRATIVE_ARBITRAGE_ONLY",
    }


def bess_usable_kwh(*, capacity_kwh: float, soc_min: float = 0.1, soc_max: float = 0.95) -> float:
    return float(capacity_kwh) * (float(soc_max) - float(soc_min))


def price_discovery_summary(
    *,
    kwh_shed: float,
    event_hours: float,
    tou_savings_usd: float,
    capacity_kwh: float,
    eta_rt: float,
    net_capex_usd: float,
    off_peak: float,
    targets_usd: tuple[float, ...] = (2.0, 5.0, 10.0),
    cycles_per_year: float = 250.0,
    payback_years: float = 10.0,
) -> dict[str, Any]:
    avg_kw = float(kwh_shed) / max(float(event_hours), 1e-9)
    usable = bess_usable_kwh(capacity_kwh=capacity_kwh)
    incentives = [
        {
            **required_incentive_per_kwh_shed(
                target_usd_per_event=t,
                kwh_shed=kwh_shed,
                existing_tou_savings_usd=tou_savings_usd,
            ),
            **{
                "required_usd_per_kw_event": required_incentive_per_kw_event(
                    target_usd_per_event=t,
                    avg_kw_shed=avg_kw,
                    existing_tou_savings_usd=tou_savings_usd,
                )["required_usd_per_kw_event"]
            },
        }
        for t in targets_usd
    ]
    peak = required_peak_rate_for_bess_payback(
        net_capex_usd=net_capex_usd,
        usable_kwh_per_cycle=usable,
        round_trip_efficiency=eta_rt,
        cycles_per_year=cycles_per_year,
        payback_years=payback_years,
        off_peak_usd_per_kwh=off_peak,
    )
    return {
        "schema": "vibe23.price_discovery.v1",
        "claim": "ILLUSTRATIVE",
        "avg_kw_shed": avg_kw,
        "incentive_table": incentives,
        "bess_arbitrage_breakeven": peak,
        "note": "Extreme-day TOU savings are not annual value; cycles/yr and day-type weights matter.",
    }
