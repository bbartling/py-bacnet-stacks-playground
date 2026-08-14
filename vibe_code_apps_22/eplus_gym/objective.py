"""Billing-floor objective + hard comfort gates for DSM screening."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd

from .tariff_contract import TariffContract, latex_cost_equations

BAS_ZONE_COLS = (
    "zone_temp_1F_A_f",
    "zone_temp_1F_B_f",
    "zone_temp_1F_C_f",
    "zone_temp_1F_D_f",
    "zone_temp_2F_A_f",
    "zone_temp_2F_B_f",
)

DT_H = 0.25


@dataclass
class ComfortGates:
    occupied_min_f: float = 68.0
    occupied_max_f: float = 76.0
    unoccupied_min_f: float = 55.0
    unoccupied_max_f: float = 85.0
    max_violation_intervals: int = 0  # hard gate: any excess → infeasible


@dataclass
class ObjectiveResult:
    daily_kwh: float
    peak_kw: float
    energy_cost: float
    incremental_demand_kw: float
    incremental_demand_cost: float
    new_billing_peak_kw: float
    total_incremental_cost: float
    comfort_degree_hours: float
    comfort_violations: int
    feasible: bool
    money_mode: str
    physical_rank_key: tuple
    reject_reason: Optional[str] = None
    delta_kwh: float | None = None
    delta_peak_kw: float | None = None
    delta_cost: float | None = None
    extras: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["physical_rank_key"] = list(self.physical_rank_key)
        return d


def incremental_demand(
    existing_billing_peak_kw: float,
    simulated_day_peak_kw: float,
    demand_rate_per_kw: float,
) -> tuple[float, float, float]:
    """Billing-floor: charge only kW above month-to-date peak."""
    new_peak = max(float(existing_billing_peak_kw), float(simulated_day_peak_kw))
    incremental_kw = max(0.0, new_peak - float(existing_billing_peak_kw))
    incremental_cost = incremental_kw * float(demand_rate_per_kw)
    return new_peak, incremental_kw, incremental_cost


def _facility_series(df: pd.DataFrame) -> pd.Series:
    if "facility_kw" in df.columns:
        return df["facility_kw"].astype(float)
    if "facility_j" in df.columns:
        return df["facility_j"].astype(float) / 900_000.0
    raise ValueError("trajectory missing facility_kw / facility_j")


def comfort_metrics(
    df: pd.DataFrame,
    *,
    occupied_mask: Sequence[bool] | None = None,
    gates: ComfortGates | None = None,
) -> tuple[float, int]:
    """Degree-hours below occupied min (heating) + violation interval count."""
    gates = gates or ComfortGates()
    cols = [c for c in BAS_ZONE_COLS if c in df.columns]
    if len(cols) < 6:
        raise ValueError(f"need six BAS zone cols; have {cols}")
    n = len(df)
    if occupied_mask is None:
        # Default weekday-ish: steps 28..68 occupied when step column present
        if "step" in df.columns:
            occupied_mask = [
                28 <= int(s) % 96 < 68 for s in df["step"].tolist()
            ]
        else:
            occupied_mask = [28 <= (i % 96) < 68 for i in range(n)]
    if len(occupied_mask) != n:
        raise ValueError("occupied_mask length mismatch")

    dh = 0.0
    viol = 0
    for i in range(n):
        occ = bool(occupied_mask[i])
        lo = gates.occupied_min_f if occ else gates.unoccupied_min_f
        hi = gates.occupied_max_f if occ else gates.unoccupied_max_f
        row_viol = False
        for c in cols:
            t = float(df.iloc[i][c])
            if t != t:
                row_viol = True
                continue
            if t < lo:
                dh += (lo - t) * DT_H
                row_viol = True
            elif t > hi:
                dh += (t - hi) * DT_H
                row_viol = True
        if row_viol:
            viol += 1
    return dh, viol


def score_trajectory(
    df: pd.DataFrame,
    tariff: TariffContract,
    *,
    baseline: "ObjectiveResult | None" = None,
    occupied_mask: Sequence[bool] | None = None,
    gates: ComfortGates | None = None,
) -> ObjectiveResult:
    """Score one day. Fail closed on empty/NaN facility."""
    gates = gates or ComfortGates()
    if df is None or len(df) == 0:
        raise ValueError("empty trajectory — refuse zero-cost")
    fac = _facility_series(df)
    if fac.isna().all():
        raise ValueError("non-finite facility series — refuse zero-cost")
    peak = float(fac.max())
    kwh = float(fac.sum() * DT_H)
    if peak != peak or kwh != kwh:
        raise ValueError("NaN peak/kwh — refuse zero-cost")

    energy_cost = 0.0
    if tariff.money_mode != "PHYSICAL_ONLY":
        energy_cost = kwh * float(tariff.energy_rate_per_kwh)

    new_peak, inc_kw, inc_cost = incremental_demand(
        tariff.existing_billing_peak_kw,
        peak,
        tariff.demand_rate_per_kw if tariff.money_mode != "PHYSICAL_ONLY" else 0.0,
    )
    if tariff.money_mode == "PHYSICAL_ONLY":
        energy_cost = 0.0
        inc_cost = 0.0

    dh, viol = comfort_metrics(df, occupied_mask=occupied_mask, gates=gates)
    feasible = viol <= int(gates.max_violation_intervals)
    reject = None if feasible else f"comfort violations={viol}"

    total = energy_cost + inc_cost
    delta_kwh = (baseline.daily_kwh - kwh) if baseline else None
    delta_peak = (baseline.peak_kw - peak) if baseline else None
    delta_cost = (baseline.total_incremental_cost - total) if baseline else None

    # Lower is better for physical rank: (-ΔE approx via kwh, peak, comfort DH)
    physical_rank_key = (kwh, peak, dh, 0 if feasible else 1)

    return ObjectiveResult(
        daily_kwh=kwh,
        peak_kw=peak,
        energy_cost=energy_cost,
        incremental_demand_kw=inc_kw,
        incremental_demand_cost=inc_cost,
        new_billing_peak_kw=new_peak,
        total_incremental_cost=total,
        comfort_degree_hours=dh,
        comfort_violations=viol,
        feasible=feasible,
        money_mode=tariff.money_mode,
        physical_rank_key=physical_rank_key,
        reject_reason=reject,
        delta_kwh=delta_kwh,
        delta_peak_kw=delta_peak,
        delta_cost=delta_cost,
        extras={"latex": latex_cost_equations()},
    )
