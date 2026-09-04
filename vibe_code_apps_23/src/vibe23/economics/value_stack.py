"""Toggleable value-stack waterfall for DSM / BESS dollars."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class ValueLayer:
    name: str
    usd: float
    enabled: bool = True
    evidence: str = "ILLUSTRATIVE"
    note: str = ""


def value_stack_total(layers: Sequence[ValueLayer]) -> dict[str, Any]:
    active = [layer for layer in layers if layer.enabled]
    total = float(sum(layer.usd for layer in active))
    waterfall = []
    running = 0.0
    for layer in active:
        running += float(layer.usd)
        waterfall.append(
            {
                "name": layer.name,
                "usd": float(layer.usd),
                "cumulative_usd": running,
                "evidence": layer.evidence,
                "note": layer.note,
            }
        )
    return {
        "schema": "vibe23.value_stack.v1",
        "total_usd": total,
        "layers": [
            {
                "name": layer.name,
                "usd": float(layer.usd),
                "enabled": layer.enabled,
                "evidence": layer.evidence,
                "note": layer.note,
            }
            for layer in layers
        ],
        "waterfall": waterfall,
    }


def residential_day_value_stack(
    *,
    tou_arbitrage_usd: float,
    demand_charge_usd: float = 0.0,
    dr_incentive_usd: float = 0.0,
    capacity_usd: float = 0.0,
    resilience_usd: float = 0.0,
    carbon_usd: float = 0.0,
    include_demand: bool = False,
    include_dr_incentive: bool = False,
    include_capacity: bool = False,
    include_resilience: bool = False,
    include_carbon: bool = False,
) -> dict[str, Any]:
    layers = (
        ValueLayer("TOU arbitrage", tou_arbitrage_usd, True, "ILLUSTRATIVE", "Retail energy bill delta"),
        ValueLayer("Demand charge", demand_charge_usd, include_demand, "ILLUSTRATIVE", "Often $0 residential"),
        ValueLayer("DR incentive", dr_incentive_usd, include_dr_incentive, "ILLUSTRATIVE", "Program pay"),
        ValueLayer("Capacity / avoided T&D", capacity_usd, include_capacity, "ILLUSTRATIVE", "Utility view"),
        ValueLayer("Resilience", resilience_usd, include_resilience, "ILLUSTRATIVE", "Not default-on"),
        ValueLayer("Carbon", carbon_usd, include_carbon, "ILLUSTRATIVE", "May conflict with $"),
    )
    return value_stack_total(layers)
