"""ESCO economics: payback, ROI, NPV, escalated cash flows, capital-plan rollup.

Every ESCO proposal boils down to the same table: per measure — implementation
cost, annual kWh/therm/cost savings, simple payback, ROI over measure life,
and NPV at a discount rate with utility escalation. :func:`measure_economics`
computes one row, :func:`capital_plan` rolls a portfolio up (sorted by
payback) and can be exported with :func:`plan_to_csv` / JSON.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any

DEFAULT_DISCOUNT_RATE = 0.05
DEFAULT_ESCALATION_RATE = 0.025
DEFAULT_MEASURE_LIFE_YEARS = 15

# Screening-grade emissions factors. Grid factor is the EPA eGRID 2022 U.S.
# national average output emission rate (~852 lb CO2e/MWh ≈ 0.386 kg/kWh);
# gas factor from EPA GHG Emission Factors Hub (0.0053 metric tons CO2e/therm).
# Pass building-specific factors for anything beyond screening.
DEFAULT_GRID_CO2E_KG_PER_KWH = 0.386
DEFAULT_GAS_CO2E_KG_PER_THERM = 5.3

KWH_PER_THERM = 29.307
"""Site-energy conversion for kWh-equivalent rollups (1 therm = 29.307 kWh)."""

OM_PROVENANCE_TIERS = ("measured", "facility_validated", "modeled", "speculative")
"""How trustworthy the O&M savings figure is:

- ``measured``            — from maintenance invoices / CMMS history
- ``facility_validated``  — estimated, but reviewed by facility staff
- ``modeled``             — engineering estimate, no site confirmation
- ``speculative``         — placeholder; exclude from bankable numbers
"""


def escalated_cash_flows(
    annual_savings_usd: float,
    years: int,
    escalation_rate: float = DEFAULT_ESCALATION_RATE,
) -> list[float]:
    """Year-by-year savings with utility escalation (year 1 = no escalation)."""
    return [annual_savings_usd * (1.0 + escalation_rate) ** y for y in range(int(years))]


def npv(
    cash_flows: list[float],
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    initial_cost: float = 0.0,
) -> float:
    """Net present value: flows discounted from end of year 1, minus cost at t=0."""
    return sum(cf / (1.0 + discount_rate) ** (y + 1) for y, cf in enumerate(cash_flows)) - initial_cost


def simple_payback_years(cost: float, annual_savings_usd: float) -> float | None:
    if annual_savings_usd <= 0:
        return None
    return cost / annual_savings_usd


def measure_economics(
    *,
    measure_id: str,
    title: str | None = None,
    implementation_cost_usd: float,
    kwh_saved: float = 0.0,
    therms_saved: float = 0.0,
    elec_rate_usd_per_kwh: float = 0.12,
    gas_rate_usd_per_therm: float = 0.80,
    cost_saved_usd: float | None = None,
    measure_life_years: int = DEFAULT_MEASURE_LIFE_YEARS,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    escalation_rate: float = DEFAULT_ESCALATION_RATE,
) -> dict[str, Any]:
    """One capital-plan row for a measure.

    ``cost_saved_usd`` overrides the rate-based savings when the caller
    already has a dollar figure (e.g. from EnergyPlus utility tariffs).
    """
    if cost_saved_usd is None:
        cost_saved_usd = kwh_saved * elec_rate_usd_per_kwh + therms_saved * gas_rate_usd_per_therm
    flows = escalated_cash_flows(cost_saved_usd, measure_life_years, escalation_rate)
    lifetime_savings = sum(flows)
    value = npv(flows, discount_rate, implementation_cost_usd)
    payback = simple_payback_years(implementation_cost_usd, cost_saved_usd)
    roi = (
        (lifetime_savings - implementation_cost_usd) / implementation_cost_usd
        if implementation_cost_usd > 0
        else None
    )
    return {
        "measure_id": measure_id,
        "title": title or measure_id,
        "implementation_cost_usd": round(implementation_cost_usd, 2),
        "kwh_saved": round(kwh_saved, 1),
        "therms_saved": round(therms_saved, 1),
        "annual_cost_saved_usd": round(cost_saved_usd, 2),
        "measure_life_years": measure_life_years,
        "simple_payback_years": None if payback is None else round(payback, 2),
        "roi_over_life": None if roi is None else round(roi, 3),
        "npv_usd": round(value, 2),
        "lifetime_savings_usd": round(lifetime_savings, 2),
        "assumptions": {
            "discount_rate": discount_rate,
            "escalation_rate": escalation_rate,
            "elec_rate_usd_per_kwh": elec_rate_usd_per_kwh,
            "gas_rate_usd_per_therm": gas_rate_usd_per_therm,
        },
    }


def irr(
    cash_flows: list[float],
    initial_cost: float,
    *,
    lo: float = -0.99,
    hi: float = 10.0,
    tol: float = 1e-7,
    max_iter: int = 200,
) -> float | None:
    """Internal rate of return by bisection (approximate; screening-grade).

    Returns the discount rate where NPV crosses zero, or None when no sign
    change exists in [lo, hi] (e.g. savings never repay the cost).
    """
    if initial_cost <= 0 or not cash_flows:
        return None

    def f(rate: float) -> float:
        return npv(cash_flows, rate, initial_cost)

    f_lo, f_hi = f(lo), f(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        f_mid = f(mid)
        if abs(f_mid) < tol or (hi - lo) / 2.0 < tol:
            return mid
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2.0


def discounted_payback_years(
    cash_flows: list[float],
    initial_cost: float,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
) -> float | None:
    """Years until cumulative discounted savings recover the cost (linear
    interpolation inside the crossing year); None if never recovered."""
    if initial_cost <= 0:
        return 0.0
    cumulative = 0.0
    for year, cf in enumerate(cash_flows, start=1):
        pv = cf / (1.0 + discount_rate) ** year
        if cumulative + pv >= initial_cost and pv > 0:
            return year - 1 + (initial_cost - cumulative) / pv
        cumulative += pv
    return None


def lifecycle_metrics(
    *,
    measure_id: str,
    title: str | None = None,
    implementation_cost_usd: float,
    kwh_saved: float = 0.0,
    therms_saved: float = 0.0,
    elec_rate_usd_per_kwh: float = 0.12,
    gas_rate_usd_per_therm: float = 0.80,
    energy_cost_saved_usd: float | None = None,
    om_savings_usd_per_year: float = 0.0,
    om_provenance: str = "modeled",
    measure_life_years: int = DEFAULT_MEASURE_LIFE_YEARS,
    discount_rate: float = DEFAULT_DISCOUNT_RATE,
    escalation_rate: float = DEFAULT_ESCALATION_RATE,
    floor_area_ft2: float | None = None,
    grid_co2e_kg_per_kwh: float = DEFAULT_GRID_CO2E_KG_PER_KWH,
    gas_co2e_kg_per_therm: float = DEFAULT_GAS_CO2E_KG_PER_THERM,
) -> dict[str, Any]:
    """Full lifecycle economics for one measure (additive to measure_economics).

    Energy savings escalate at ``escalation_rate``; O&M savings are held flat
    (labor/parts do not track utility tariffs). ``om_provenance`` must be one
    of :data:`OM_PROVENANCE_TIERS` and is stamped on the output so speculative
    O&M lines can never silently launder into bankable paybacks.

    Cost of conserved energy annualizes the capital cost with the capital
    recovery factor at ``discount_rate`` over ``measure_life_years`` and
    divides by annual site kWh-equivalent saved (therms folded in at
    29.307 kWh/therm).
    """
    if om_provenance not in OM_PROVENANCE_TIERS:
        raise ValueError(
            f"om_provenance must be one of {OM_PROVENANCE_TIERS}, got {om_provenance!r}"
        )
    if energy_cost_saved_usd is None:
        energy_cost_saved_usd = (
            kwh_saved * elec_rate_usd_per_kwh + therms_saved * gas_rate_usd_per_therm
        )
    total_annual_usd = energy_cost_saved_usd + om_savings_usd_per_year

    energy_flows = escalated_cash_flows(energy_cost_saved_usd, measure_life_years, escalation_rate)
    flows = [ef + om_savings_usd_per_year for ef in energy_flows]
    lifetime_savings = sum(flows)
    value = npv(flows, discount_rate, implementation_cost_usd)
    pv_savings = value + implementation_cost_usd
    sir = pv_savings / implementation_cost_usd if implementation_cost_usd > 0 else None
    roi = (
        (lifetime_savings - implementation_cost_usd) / implementation_cost_usd
        if implementation_cost_usd > 0
        else None
    )
    rate_of_return = irr(flows, implementation_cost_usd)
    disc_payback = discounted_payback_years(flows, implementation_cost_usd, discount_rate)

    kwh_equiv = kwh_saved + therms_saved * KWH_PER_THERM
    if implementation_cost_usd > 0 and kwh_equiv > 0 and measure_life_years > 0:
        if discount_rate > 0:
            crf = (
                discount_rate
                * (1.0 + discount_rate) ** measure_life_years
                / ((1.0 + discount_rate) ** measure_life_years - 1.0)
            )
        else:
            crf = 1.0 / measure_life_years
        cce = implementation_cost_usd * crf / kwh_equiv
        cost_per_annual_kwh = implementation_cost_usd / kwh_equiv
    else:
        cce = None
        cost_per_annual_kwh = None

    co2e_kg_per_year = kwh_saved * grid_co2e_kg_per_kwh + therms_saved * gas_co2e_kg_per_therm

    return {
        "measure_id": measure_id,
        "title": title or measure_id,
        "implementation_cost_usd": round(implementation_cost_usd, 2),
        "kwh_saved": round(kwh_saved, 1),
        "therms_saved": round(therms_saved, 1),
        "annual_energy_cost_saved_usd": round(energy_cost_saved_usd, 2),
        "annual_om_saved_usd": round(om_savings_usd_per_year, 2),
        "annual_cost_saved_usd": round(total_annual_usd, 2),
        "measure_life_years": measure_life_years,
        "simple_payback_years": _round_opt(
            simple_payback_years(implementation_cost_usd, total_annual_usd), 2
        ),
        "energy_only_payback_years": _round_opt(
            simple_payback_years(implementation_cost_usd, energy_cost_saved_usd), 2
        ),
        "discounted_payback_years": _round_opt(disc_payback, 2),
        "roi_over_life": _round_opt(roi, 3),
        "sir": _round_opt(sir, 3),
        "npv_usd": round(value, 2),
        "irr": _round_opt(rate_of_return, 4),
        "lifetime_savings_usd": round(lifetime_savings, 2),
        "cost_of_conserved_energy_usd_per_kwh": _round_opt(cce, 4),
        "cost_usd_per_annual_kwh_saved": _round_opt(cost_per_annual_kwh, 4),
        "cost_usd_per_ft2": (
            round(implementation_cost_usd / floor_area_ft2, 4)
            if floor_area_ft2 and floor_area_ft2 > 0
            else None
        ),
        "co2e_avoided_kg_per_year": round(co2e_kg_per_year, 1),
        "co2e_avoided_metric_tons_over_life": round(
            co2e_kg_per_year * measure_life_years / 1000.0, 2
        ),
        "om_provenance": om_provenance,
        "assumptions": {
            "discount_rate": discount_rate,
            "escalation_rate": escalation_rate,
            "elec_rate_usd_per_kwh": elec_rate_usd_per_kwh,
            "gas_rate_usd_per_therm": gas_rate_usd_per_therm,
            "grid_co2e_kg_per_kwh": grid_co2e_kg_per_kwh,
            "gas_co2e_kg_per_therm": gas_co2e_kg_per_therm,
            "kwh_per_therm": KWH_PER_THERM,
            "om_escalated": False,
        },
    }


def _round_opt(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def capital_plan(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Portfolio rollup: sort measures by payback and total the plan."""
    def sort_key(r: dict[str, Any]) -> float:
        pb = r.get("simple_payback_years")
        return float("inf") if pb is None else float(pb)

    ordered = sorted(rows, key=sort_key)
    total_cost = sum(float(r.get("implementation_cost_usd") or 0.0) for r in ordered)
    total_savings = sum(float(r.get("annual_cost_saved_usd") or 0.0) for r in ordered)
    total_npv = sum(float(r.get("npv_usd") or 0.0) for r in ordered)
    blended = simple_payback_years(total_cost, total_savings)
    return {
        "measures": ordered,
        "totals": {
            "implementation_cost_usd": round(total_cost, 2),
            "annual_cost_saved_usd": round(total_savings, 2),
            "kwh_saved": round(sum(float(r.get("kwh_saved") or 0.0) for r in ordered), 1),
            "therms_saved": round(sum(float(r.get("therms_saved") or 0.0) for r in ordered), 1),
            "npv_usd": round(total_npv, 2),
            "blended_simple_payback_years": None if blended is None else round(blended, 2),
        },
    }


_PLAN_COLUMNS = [
    "measure_id",
    "title",
    "implementation_cost_usd",
    "kwh_saved",
    "therms_saved",
    "annual_cost_saved_usd",
    "measure_life_years",
    "simple_payback_years",
    "roi_over_life",
    "npv_usd",
    "lifetime_savings_usd",
]


def plan_to_csv(plan: dict[str, Any], path: str | Path | None = None) -> str:
    """Render a capital plan as CSV (measures + a TOTAL row); optionally write it."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_PLAN_COLUMNS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for row in plan.get("measures", []):
        writer.writerow(row)
    totals = plan.get("totals", {})
    writer.writerow({
        "measure_id": "TOTAL",
        "title": "",
        "implementation_cost_usd": totals.get("implementation_cost_usd"),
        "kwh_saved": totals.get("kwh_saved"),
        "therms_saved": totals.get("therms_saved"),
        "annual_cost_saved_usd": totals.get("annual_cost_saved_usd"),
        "simple_payback_years": totals.get("blended_simple_payback_years"),
        "npv_usd": totals.get("npv_usd"),
    })
    text = buf.getvalue()
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text


def plan_to_json(plan: dict[str, Any], path: str | Path | None = None) -> str:
    text = json.dumps(plan, indent=2)
    if path is not None:
        Path(path).write_text(text, encoding="utf-8")
    return text
