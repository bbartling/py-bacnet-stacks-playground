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
