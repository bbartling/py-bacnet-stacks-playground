"""Coordinate-descent DSM optimization study (recommendation proposal only)."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from eplus_gym.objective import ComfortGates, ObjectiveResult, score_trajectory
from eplus_gym.parametric_daily_controller import (
    ParametricDailyController,
    ParametricDailyParams,
    controller_from_site_and_params,
)
from eplus_gym.tariff_contract import TariffContract

STUDY_SCHEMA = "eplus_gym_optimization_study_v1"
SCREENING_LABEL = "ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY"


@dataclass
class CandidateParams:
    unoccupied_heating_f: float
    recovery_start_minutes_before_occupancy: int
    recovery_ramp_minutes: int
    hvac_start_minutes_before_occupancy: int
    occupied_setpoint_offset_f: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def hash(self) -> str:
        blob = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def study_root(site_root: Path, study_id: str) -> Path:
    return Path(site_root) / "reports" / "eplus_gym" / "optimization" / study_id


def new_study_id(prefix: str = "study") -> str:
    return f"{prefix}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"


def ensure_study_tree(root: Path) -> Path:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    (root / "candidates").mkdir(exist_ok=True)
    (root / "plots").mkdir(exist_ok=True)
    return root


def write_json(path: Path, doc: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")


def coordinate_descent_grid(
    *,
    unocc_f: Sequence[float] = (65.0, 60.0, 55.0),
    recovery_leads_min: Sequence[int] = (0, 60, 120, 180),
    ramps_min: Sequence[int] = (0, 30, 60),
    hvac_leads_min: Sequence[int] = (0, 30, 60),
) -> List[CandidateParams]:
    """Low-dimensional global search order: unocc → recovery → ramp → HVAC lead."""
    out: List[CandidateParams] = []
    seen: set[str] = set()
    # Phase A: freeze recovery/ramp/hvac at 0, sweep unocc
    for u in unocc_f:
        c = CandidateParams(u, 0, 0, 0)
        if c.hash() not in seen:
            seen.add(c.hash())
            out.append(c)
    # Phase B: fix best-unocc placeholder (full grid for small studies)
    for u in unocc_f:
        for lead in recovery_leads_min:
            for ramp in ramps_min:
                for hvac in hvac_leads_min:
                    c = CandidateParams(float(u), int(lead), int(ramp), int(hvac))
                    h = c.hash()
                    if h in seen:
                        continue
                    seen.add(h)
                    out.append(c)
    return out


def pareto_front(
    rows: List[Dict[str, Any]],
    *,
    money_mode: str,
) -> List[Dict[str, Any]]:
    """Minimize kwh, peak, comfort DH among feasible candidates."""
    feas = [r for r in rows if r.get("feasible")]
    front: List[Dict[str, Any]] = []
    for a in feas:
        dominated = False
        for b in feas:
            if a is b:
                continue
            better_or_eq = (
                float(b["daily_kwh"]) <= float(a["daily_kwh"])
                and float(b["peak_kw"]) <= float(a["peak_kw"])
                and float(b["comfort_degree_hours"]) <= float(a["comfort_degree_hours"])
            )
            strictly = (
                float(b["daily_kwh"]) < float(a["daily_kwh"])
                or float(b["peak_kw"]) < float(a["peak_kw"])
                or float(b["comfort_degree_hours"]) < float(a["comfort_degree_hours"])
            )
            if better_or_eq and strictly:
                dominated = True
                break
        if not dominated:
            front.append(a)
    # PHYSICAL_ONLY: never rank by illustrative dollars
    if money_mode != "VERIFIED_TARIFF":
        front.sort(
            key=lambda r: (
                float(r["daily_kwh"]),
                float(r["peak_kw"]),
                float(r["comfort_degree_hours"]),
            )
        )
    else:
        front.sort(key=lambda r: float(r.get("total_incremental_cost", 1e18)))
    return front


def build_recommendation(
    *,
    study_id: str,
    day: str,
    baseline: Dict[str, Any],
    frontier: List[Dict[str, Any]],
    tariff: TariffContract,
) -> Dict[str, Any]:
    winner = frontier[0] if frontier else None
    return {
        "schema": "eplus_gym_recommendation_v1",
        "scientific_claim": SCREENING_LABEL,
        "study_id": study_id,
        "day": day,
        "proposal_only": True,
        "auto_promote_site_config": False,
        "auto_promote_bacnet": False,
        "money_mode": tariff.money_mode,
        "baseline": baseline,
        "recommended": winner,
        "pareto_size": len(frontier),
        "note": (
            "Approve writes approved_recommendation.json only — never Site Config "
            "or BACnet."
        ),
    }


@dataclass
class StudyState:
    study_id: str
    root: Path
    seen_hashes: set[str] = field(default_factory=set)
    candidates: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load_or_create(cls, root: Path, study_id: str) -> "StudyState":
        ensure_study_tree(root)
        state = cls(study_id=study_id, root=root)
        jl = root / "candidates.jsonl"
        if jl.is_file():
            for line in jl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                state.candidates.append(row)
                h = (row.get("params") or {}).get("hash") or row.get("candidate_hash")
                if h:
                    state.seen_hashes.add(str(h))
        return state
