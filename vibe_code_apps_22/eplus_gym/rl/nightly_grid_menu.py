"""One-day unique candidate menu + preregistered anytime order for nightly grid."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Sequence

from eplus_gym.control_v2 import (
    continuous_params,
    deep_setback_params,
    observed_bas_incumbent_params,
    shallow_setback_params,
)
from eplus_gym.rl.grid_search_menu import (
    build_candidate_menu,
    day_fingerprint,
)
from eplus_gym.rl.research_spaces import (
    decode_discrete_research_v3,
    research_build_six_schedules_f,
)


def load_nightly_contract(app_root: Path) -> dict[str, Any]:
    path = Path(app_root) / "contracts" / "nightly_grid_compute_v1.json"
    return json.loads(path.read_text(encoding="utf-8"))


def build_one_day_menu(*, day: str) -> dict[str, Any]:
    """146 declared → unique fingerprints for a single target day."""
    menu = build_candidate_menu(days=[day])
    # For one day, sequence fingerprint collapses to day fingerprint uniqueness.
    unique = []
    seen: set[str] = set()
    for g in menu["unique_fixed_policies"]:
        fp = g["sequence_fingerprint"]
        if fp in seen:
            continue
        seen.add(fp)
        unique.append(g)
    menu["n_unique_one_day"] = len(unique)
    menu["unique_one_day"] = unique
    return menu


def preregistered_anytime_order(
    menu: dict[str, Any],
    *,
    seed_indices: Sequence[int],
) -> list[int]:
    """Frozen order: seed indices first (unique), then remaining uniques ascending."""
    unique_reps = [int(g["representative_index"]) for g in menu["unique_one_day"]]
    unique_set = set(unique_reps)
    # Map any seed index to its unique representative for this day.
    fp_to_rep = {
        day_fingerprint(int(g["representative_index"]), menu["days"][0]): int(g["representative_index"])
        for g in menu["unique_one_day"]
    }
    order: list[int] = []
    used: set[int] = set()
    day = menu["days"][0]
    for idx in seed_indices:
        fp = day_fingerprint(int(idx), day)
        rep = fp_to_rep.get(fp, int(idx) if int(idx) in unique_set else None)
        if rep is None:
            continue
        if rep in used:
            continue
        order.append(int(rep))
        used.add(int(rep))
    for rep in sorted(unique_reps):
        if rep not in used:
            order.append(rep)
            used.add(rep)
    return order


def reference_arm_specs(*, day: str) -> list[dict[str, Any]]:
    """Reference candidates logged but not crowned operational winners."""
    specs = [
        {
            "candidate_id": "a04_native_sch_htgsp",
            "label": "A04_NATIVE_CALIBRATION_REFERENCE",
            "rank_eligible": False,
            "kind": "scalar_sch_htgsp",
        },
        {
            "candidate_id": "observed_bas_incumbent_v2",
            "label": "OBSERVED_BAS_INCUMBENT_V2_HISTORICAL",
            "rank_eligible": True,
            "kind": "params",
            "params": observed_bas_incumbent_params(),
        },
        {
            "candidate_id": "continuous_68_heat_sensitivity",
            "label": "CONTINUOUS_DUALSP_68_74_SENSITIVITY_UNVERIFIED",
            "rank_eligible": True,
            "kind": "params",
            "params": continuous_params(68.0),
        },
        {
            "candidate_id": "shallow_setback",
            "label": "SHALLOW_SETBACK_REFERENCE",
            "rank_eligible": True,
            "kind": "params",
            "params": shallow_setback_params(),
        },
        {
            "candidate_id": "deep_setback",
            "label": "DEEP_SETBACK_REFERENCE",
            "rank_eligible": True,
            "kind": "params",
            "params": deep_setback_params(),
        },
        {
            "candidate_id": "grid_flat_discrete_42",
            "label": "PRIOR_GRID_LEADER_DISCRETE_42",
            "rank_eligible": True,
            "kind": "discrete",
            "action_index": 42,
            "params": decode_discrete_research_v3(42, day=day),
        },
        {
            "candidate_id": "grid_tou_discrete_43",
            "label": "PRIOR_GRID_LEADER_DISCRETE_43",
            "rank_eligible": True,
            "kind": "discrete",
            "action_index": 43,
            "params": decode_discrete_research_v3(43, day=day),
        },
        {
            "candidate_id": "previous_night_winner",
            "label": "PREVIOUS_NIGHT_WINNER",
            "rank_eligible": False,
            "kind": "stub",
            "status": "NOT_AVAILABLE",
        },
    ]
    return specs


def menu_sha256(menu: dict[str, Any]) -> str:
    body = {
        "declared": menu["declared_action_count"],
        "n_unique": menu.get("n_unique_one_day") or menu["n_unique_fixed_policies"],
        "reps": [int(g["representative_index"]) for g in menu.get("unique_one_day") or menu["unique_fixed_policies"]],
    }
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode("utf-8")).hexdigest()


def schedule_for_index(index: int, day: str) -> dict[str, list[float]]:
    return research_build_six_schedules_f(decode_discrete_research_v3(int(index), day=day), day)


def fingerprint_for_index(index: int, day: str) -> str:
    return day_fingerprint(int(index), day)
