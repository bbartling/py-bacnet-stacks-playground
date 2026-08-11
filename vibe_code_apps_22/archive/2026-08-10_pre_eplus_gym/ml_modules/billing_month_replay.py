"""Billing-month counterfactual replay (illustrative tariff only).

``existing_billing_peak`` for day D is the peak established before D.
Hardcoded $/kW and $/kWh are ILLUSTRATIVE — never claim verified Lakeside rates.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Sequence

from billing_counterfactual import mtd_peak_before_day
from simulation_contract import incremental_demand

ILLUSTRATIVE_DEMAND_RATE_PER_KW = 12.0
ILLUSTRATIVE_ENERGY_RATE_PER_KWH = 0.08


@dataclass(frozen=True)
class DayBill:
    day: str
    daily_kwh: float
    day_peak_kw: float
    peak_to_date_before: float
    peak_to_date_after: float
    incremental_demand_kw: float
    energy_cost: float
    incremental_demand_cost: float
    total_incremental_cost: float


@dataclass(frozen=True)
class MonthReplay:
    month: str  # YYYY-MM
    tariff_note: str
    days: list[DayBill]
    total_energy_cost: float
    total_incremental_demand_cost: float
    total_cost: float
    month_peak_kw: float
    ratchet_stub: str

    def to_dict(self) -> dict:
        return asdict(self)


def replay_month(
    daily_kwh: Mapping[str, float],
    daily_peaks: Mapping[str, float],
    *,
    month: str,
    energy_rate: float = ILLUSTRATIVE_ENERGY_RATE_PER_KWH,
    demand_rate: float = ILLUSTRATIVE_DEMAND_RATE_PER_KW,
    days: Sequence[str] | None = None,
) -> MonthReplay:
    """Chronological month replay with peak-to-date demand accounting."""
    if len(month) != 7 or month[4] != "-":
        raise ValueError(f"expected YYYY-MM, got {month!r}")
    day_list = sorted(
        d for d in (days if days is not None else daily_peaks.keys()) if str(d)[:7] == month
    )
    bills: list[DayBill] = []
    running: dict[str, float] = {}
    for d in day_list:
        before = mtd_peak_before_day(running, d)
        pk = float(daily_peaks[d])
        kwh = float(daily_kwh.get(d, 0.0))
        new_p, inc_kw, inc_cost = incremental_demand(before, pk, demand_rate)
        energy_cost = kwh * energy_rate
        bills.append(
            DayBill(
                day=d,
                daily_kwh=kwh,
                day_peak_kw=pk,
                peak_to_date_before=before,
                peak_to_date_after=new_p,
                incremental_demand_kw=inc_kw,
                energy_cost=energy_cost,
                incremental_demand_cost=inc_cost,
                total_incremental_cost=energy_cost + inc_cost,
            )
        )
        running[d] = pk
    te = sum(b.energy_cost for b in bills)
    td = sum(b.incremental_demand_cost for b in bills)
    return MonthReplay(
        month=month,
        tariff_note=(
            f"ILLUSTRATIVE energy=${energy_rate:g}/kWh demand=${demand_rate:g}/kW — "
            "not verified Lakeside utility tariff"
        ),
        days=bills,
        total_energy_cost=te,
        total_incremental_demand_cost=td,
        total_cost=te + td,
        month_peak_kw=max((b.day_peak_kw for b in bills), default=0.0),
        ratchet_stub="NOT_IMPLEMENTED — ratchet/minimum demand not configured",
    )
