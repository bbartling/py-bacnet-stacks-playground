"""Homeowner BESS lifecycle economics — NPV / payback / LCOS (no hardcoded ITC)."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

TaxCreditEvidence = Literal["NONE", "ILLUSTRATIVE", "VERIFIED"]


@dataclass(frozen=True)
class LifecycleAssumptions:
    net_capex_usd: float
    annual_arbitrage_usd: float
    discount_rate: float = 0.07
    lifetime_years: int = 10
    warranty_years: int = 10
    annual_om_usd: float = 0.0
    annual_degradation_frac: float = 0.025
    throughput_kwh_per_year: float = 0.0
    tax_credit_frac: float = 0.0
    tax_credit_evidence: TaxCreditEvidence = "NONE"
    tax_credit_reference: str = ""

    def __post_init__(self) -> None:
        if self.net_capex_usd < 0:
            raise ValueError("net_capex_usd must be non-negative")
        if self.lifetime_years < 1 or self.warranty_years < 1:
            raise ValueError("lifetime/warranty years must be >= 1")
        if not 0 <= self.discount_rate < 1:
            raise ValueError("discount_rate out of range")
        if self.tax_credit_frac < 0 or self.tax_credit_frac > 1:
            raise ValueError("tax_credit_frac must be in [0, 1]")
        if self.tax_credit_frac > 0 and self.tax_credit_evidence == "NONE":
            raise ValueError("non-zero tax credit requires ILLUSTRATIVE or VERIFIED evidence")
        if self.tax_credit_evidence == "VERIFIED" and not self.tax_credit_reference.strip():
            raise ValueError("VERIFIED tax credit requires tax_credit_reference (statute + period)")


def effective_capex(assumptions: LifecycleAssumptions) -> float:
    return float(assumptions.net_capex_usd) * (1.0 - float(assumptions.tax_credit_frac))


def annual_cashflows(assumptions: LifecycleAssumptions) -> list[float]:
    """Year-1..N cashflows after CapEx at t=0 (returned separately)."""
    years = min(int(assumptions.lifetime_years), int(assumptions.warranty_years))
    flows: list[float] = []
    fade = 1.0
    for _ in range(years):
        arb = float(assumptions.annual_arbitrage_usd) * fade
        flows.append(arb - float(assumptions.annual_om_usd))
        fade *= 1.0 - float(assumptions.annual_degradation_frac)
    return flows


def npv(assumptions: LifecycleAssumptions) -> float:
    capex = effective_capex(assumptions)
    r = float(assumptions.discount_rate)
    total = -capex
    for t, cf in enumerate(annual_cashflows(assumptions), start=1):
        total += cf / ((1.0 + r) ** t)
    return float(total)


def simple_payback_years(assumptions: LifecycleAssumptions) -> float | None:
    """Undiscounted payback; None if never recovers within warranty/lifetime."""
    capex = effective_capex(assumptions)
    cum = 0.0
    for t, cf in enumerate(annual_cashflows(assumptions), start=1):
        if cf <= 0:
            continue
        cum += cf
        if cum >= capex:
            # interpolate within year
            prev = cum - cf
            need = capex - prev
            return float(t - 1) + float(need / cf)
    return None


def lcos_usd_per_kwh(assumptions: LifecycleAssumptions) -> float | None:
    """Levelized cost of storage $/kWh-cycled (ILLUSTRATIVE)."""
    thr = float(assumptions.throughput_kwh_per_year)
    years = min(int(assumptions.lifetime_years), int(assumptions.warranty_years))
    if thr <= 0 or years < 1:
        return None
    r = float(assumptions.discount_rate)
    capex = effective_capex(assumptions)
    pv_om = sum(float(assumptions.annual_om_usd) / ((1.0 + r) ** t) for t in range(1, years + 1))
    # Discounted throughput with degradation of capacity ≈ fade on cycles
    fade = 1.0
    pv_kwh = 0.0
    for t in range(1, years + 1):
        pv_kwh += thr * fade / ((1.0 + r) ** t)
        fade *= 1.0 - float(assumptions.annual_degradation_frac)
    if pv_kwh <= 0:
        return None
    return float((capex + pv_om) / pv_kwh)


def lifecycle_report(assumptions: LifecycleAssumptions) -> dict[str, Any]:
    payback = simple_payback_years(assumptions)
    return {
        "schema": "vibe23.bess_lifecycle.v1",
        "claim": "ILLUSTRATIVE",
        "assumptions": asdict(assumptions),
        "effective_capex_usd": effective_capex(assumptions),
        "npv_usd": npv(assumptions),
        "simple_payback_years": payback,
        "lcos_usd_per_kwh": lcos_usd_per_kwh(assumptions),
        "cashflows_usd": annual_cashflows(assumptions),
        "warning": (
            "Retail TOU arbitrage alone often does not pay back residential BESS "
            "inside warranty; resilience value is not in this cashflow."
        ),
    }
