"""Phase 10: transparent GRID_SEARCH arm with bounded daily budget."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Sequence

from eplus_gym.mega._json import sha256_obj

SCHEMA = "vibe22.mega.grid_search.v1"
MAX_EXTRA_CANDIDATES_PER_DAY = 40
REQUIRED_PLOTS = (
    "grid_search_candidate_landscape",
    "grid_search_parameter_heatmap",
    "grid_search_schedule_comparison",
    "strategy_cost_comparison",
)


@dataclass
class GridCandidate:
    candidate_id: str
    params: dict[str, float]
    score: float | None = None
    energyplus_confirmed: bool = False

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.params, sort_keys=True).encode()).hexdigest()[:16]


@dataclass
class GridSearchArm:
    day: str
    coarse_grid: list[dict[str, float]] = field(default_factory=list)
    refined: list[GridCandidate] = field(default_factory=list)
    seen: set[str] = field(default_factory=set)

    def add_coarse(self, params: dict[str, float]) -> GridCandidate | None:
        cand = GridCandidate(candidate_id=f"GS_{len(self.coarse_grid):04d}", params=params)
        fp = cand.fingerprint()
        if fp in self.seen:
            return None
        self.seen.add(fp)
        self.coarse_grid.append(params)
        return cand

    def refine_local(self, seed: GridCandidate, deltas: Sequence[dict[str, float]]) -> list[GridCandidate]:
        added: list[GridCandidate] = []
        for delta in deltas:
            if len(self.refined) >= MAX_EXTRA_CANDIDATES_PER_DAY:
                break
            merged = {**seed.params, **delta}
            cand = GridCandidate(
                candidate_id=f"GS_R{len(self.refined):04d}",
                params=merged,
            )
            fp = cand.fingerprint()
            if fp in self.seen:
                continue
            self.seen.add(fp)
            self.refined.append(cand)
            added.append(cand)
        return added

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "day": self.day,
            "max_extra_candidates_per_day": MAX_EXTRA_CANDIDATES_PER_DAY,
            "coarse_count": len(self.coarse_grid),
            "refined_count": len(self.refined),
            "required_plots": list(REQUIRED_PLOTS),
            "locked_test_tuning": False,
            "candidates": [
                {"id": c.candidate_id, "params": c.params, "score": c.score, "eplus": c.energyplus_confirmed}
                for c in self.refined
            ],
        }

    def write(self, path: Path) -> dict[str, Any]:
        body = self.to_dict()
        body["grid_sha256"] = sha256_obj(body)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        return body


def default_coarse_grid() -> list[dict[str, float]]:
    return [
        {
            "occupied_heating_f": 68.0,
            "unoccupied_heating_f": 64.0,
            "recovery_lead_minutes": 45.0,
            "heating_setpoint_start_step": 28.0,
            "continuous_conditioning": 0.0,
        },
        {
            "occupied_heating_f": 70.0,
            "unoccupied_heating_f": 62.0,
            "recovery_lead_minutes": 60.0,
            "heating_setpoint_start_step": 32.0,
            "zone_offset_area_a_f": 0.5,
        },
        {
            "occupied_heating_f": 72.0,
            "unoccupied_heating_f": 60.0,
            "recovery_lead_minutes": 75.0,
            "heating_setpoint_end_step": 68.0,
            "continuous_conditioning": 0.0,
        },
    ]
