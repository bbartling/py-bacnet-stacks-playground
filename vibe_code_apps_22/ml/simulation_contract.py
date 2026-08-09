"""Shared simulation contracts for ML hybrid and nearest-day engines.

Optimization readiness (no general optimizer in this pass):
- SimulationRequest / SimulationResult are the stable API surface
- ControlSchedule96 carries actual 96-step controls; strategy_id is provenance
- Strategy enumeration ranks named strategies; not mathematical optimization
- Annual rollups remain HEURISTIC until Annual Replay exists

Future objective (documented only):
  total_cost =
      sum(interval_kw * interval_hours * energy_rate)
    + incremental_monthly_demand_cost
    + comfort_penalty
    + equipment_cycling_penalty
  Comfort limits should normally be hard feasibility constraints.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

UNSUPPORTED_CONTROL_SCHEDULE = "UNSUPPORTED_CONTROL_SCHEDULE"

FUTURE_OBJECTIVE_DOC = (
    "total_cost = sum(interval_kw * interval_hours * energy_rate) "
    "+ incremental_monthly_demand_cost + comfort_penalty + equipment_cycling_penalty; "
    "comfort limits are hard feasibility constraints."
)

ANNUAL_REPLAY_STUB = (
    "FUTURE Annual Replay: 365 weather/init days, chronological sim, "
    "monthly peak-to-date, verified tariff/ratchet, baseline vs DSM bills. "
    "Current annual rollup is HEURISTIC only."
)


@dataclass
class ControlSchedule96:
    """Actual control values at every 15-min step; strategy_id is a label."""

    strategy_id: str
    steps: list[dict[str, Any]]
    # Each step should include setpoints/offsets, equipment enables, occupancy.


@dataclass
class SimulationRequest:
    midnight_facility_kw: float
    midnight_zone_temps_f: list[float]  # len 6
    oat_f_96: list[float]
    rh_pct_96: list[float]
    ghi_96: list[float]
    month: float
    doy: float
    is_weekend: bool
    schedule: ControlSchedule96
    tariff: Any
    existing_billing_peak_kw: float
    billed_demand_kw: Optional[float] = None
    honesty_note: str = "simulation request — screening / playground"


@dataclass
class SimulationResult:
    facility_kw: list[float]
    zone_temperatures_f: list[list[float]]
    daily_kwh: float
    peak_kw: float
    peak_timestep: int
    energy_cost: float
    incremental_demand_kw: float
    incremental_demand_cost: float
    new_billing_peak_kw: float
    comfort_violations: int
    ood: bool
    ood_status: Optional[str]
    recommend: bool
    honesty: str
    provenance: str
    strategy_id: str
    unsupported_reason: Optional[str] = None
    outcome_flags: list[str] = field(default_factory=list)


@dataclass
class StrategyEnumRow:
    strategy_id: str
    peak_kw: float
    daily_kwh: float
    energy_cost: float
    incremental_demand_kw: float
    incremental_demand_cost: float
    total_incremental_cost: float
    comfort_violations: int
    ood: bool
    feasible: bool
    reject_reason: Optional[str] = None


def incremental_demand(
    existing_billing_peak_kw: float,
    simulated_day_peak_kw: float,
    demand_rate_per_kw: float,
) -> tuple[float, float, float]:
    """One-day incremental demand cost — never charge full monthly demand alone."""
    new_peak = max(existing_billing_peak_kw, simulated_day_peak_kw)
    incremental_kw = max(0.0, new_peak - existing_billing_peak_kw)
    incremental_cost = incremental_kw * demand_rate_per_kw
    return new_peak, incremental_kw, incremental_cost
