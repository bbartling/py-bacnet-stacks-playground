"""Phase 7: independent candidate/baseline billing floors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from eplus_gym.rl.billing_state import BillingState


def billing_floor_kw(*, mtd_peak_kw: float, ratchet_floor_kw: float, contract_floor_kw: float) -> float:
    return max(float(mtd_peak_kw), float(ratchet_floor_kw), float(contract_floor_kw))


@dataclass
class TrajectoryBilling:
    label: str
    mtd_peak_kw: float
    ratchet_floor_kw: float
    contract_floor_kw: float

    def floor_kw(self) -> float:
        return billing_floor_kw(
            mtd_peak_kw=self.mtd_peak_kw,
            ratchet_floor_kw=self.ratchet_floor_kw,
            contract_floor_kw=self.contract_floor_kw,
        )

    def incremental_demand_kw(self, new_peak_kw: float) -> float:
        floor = self.floor_kw()
        return max(0.0, float(new_peak_kw) - floor)


def candidate_and_baseline_floors(
    *,
    candidate_mtd_peak_kw: float,
    baseline_mtd_peak_kw: float,
    ratchet_floor_kw: float,
    contract_floor_kw: float,
) -> dict[str, Any]:
    candidate = TrajectoryBilling(
        "candidate",
        candidate_mtd_peak_kw,
        ratchet_floor_kw,
        contract_floor_kw,
    )
    baseline = TrajectoryBilling(
        "baseline",
        baseline_mtd_peak_kw,
        ratchet_floor_kw,
        contract_floor_kw,
    )
    return {
        "candidate_floor_kw": candidate.floor_kw(),
        "baseline_floor_kw": baseline.floor_kw(),
        "floors_independent": candidate.floor_kw() != baseline.floor_kw()
        or candidate_mtd_peak_kw != baseline_mtd_peak_kw,
        "formula": "max(mtd_peak, ratchet_floor, contract_floor)",
        "no_retroactive_demand_savings": True,
        "candidate": {
            "mtd_peak_kw": candidate_mtd_peak_kw,
            "floor_kw": candidate.floor_kw(),
        },
        "baseline": {
            "mtd_peak_kw": baseline_mtd_peak_kw,
            "floor_kw": baseline.floor_kw(),
        },
    }


def billing_state_from_trajectory(traj: TrajectoryBilling) -> BillingState:
    st = BillingState(
        floor_kw=traj.mtd_peak_kw,
        ratchet_kw=traj.ratchet_floor_kw,
        contract_kw=traj.contract_floor_kw,
    )
    return st
