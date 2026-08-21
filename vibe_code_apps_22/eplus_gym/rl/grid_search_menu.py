"""Discrete v3 candidate menu + schedule fingerprint deduplication for grid search."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Sequence

from eplus_gym.rl.multiday_env import schedule_fingerprint
from eplus_gym.rl.research_spaces import (
    decode_discrete_research_v3,
    discrete_n_research_v3,
    emit_schedule_proof,
    research_build_six_schedules_f,
)


def validation_days() -> list[str]:
    start = date(2025, 12, 15)
    return [(start + timedelta(days=i)).isoformat() for i in range(17)]


def checked_school_days() -> list[str]:
    return validation_days()[:5]


@dataclass(frozen=True)
class CandidateParams:
    action_index: int
    continuous_conditioning: bool
    occupied_heating_f: float
    unoccupied_heating_f: float
    recovery_lead_minutes: int
    post_occupancy_extension_minutes: int
    setback_offset_f: float


def candidate_params_for_index(index: int, *, day: str = "2025-12-15") -> CandidateParams:
    p = decode_discrete_research_v3(int(index), day=day)
    off = 0.0
    if p.zone_offsets:
        first = next(iter(p.zone_offsets.values()))
        off = float(getattr(first, "setback_offset_f", 0.0) or 0.0)
    return CandidateParams(
        action_index=int(index),
        continuous_conditioning=bool(p.continuous_conditioning),
        occupied_heating_f=float(p.occupied_heating_f),
        unoccupied_heating_f=float(p.unoccupied_heating_f),
        recovery_lead_minutes=int(p.recovery_lead_minutes),
        post_occupancy_extension_minutes=int(p.post_occupancy_extension_minutes or 0),
        setback_offset_f=off,
    )


def day_fingerprint(index: int, day: str) -> str:
    params = decode_discrete_research_v3(int(index), day=day)
    schedules = research_build_six_schedules_f(params, day)
    return schedule_fingerprint(schedules)


def build_candidate_menu(*, days: Sequence[str] | None = None) -> dict[str, Any]:
    days = list(days or validation_days())
    n = discrete_n_research_v3()
    # Prove no wrap
    try:
        decode_discrete_research_v3(n, day=days[0])
        raise RuntimeError("expected OOB decode to raise")
    except ValueError:
        pass

    by_day_unique: dict[str, dict[str, Any]] = {}
    duplicate_maps: dict[str, dict[str, list[int]]] = {}
    all_candidates: list[dict[str, Any]] = []
    for idx in range(n):
        params = candidate_params_for_index(idx, day=days[0])
        fps = {d: day_fingerprint(idx, d) for d in days}
        proof = emit_schedule_proof(decode_discrete_research_v3(idx, day=days[0]), days[0])
        all_candidates.append(
            {
                **asdict(params),
                "fingerprints_by_day": fps,
                "sequence_fingerprint": hashlib.sha256(
                    json.dumps([fps[d] for d in days], separators=(",", ":")).encode("utf-8")
                ).hexdigest(),
                "schedule_proof_day0": {
                    "school_occupied": proof["school_occupancy_window"]["school_occupied"],
                    "schedule_fingerprint": proof["schedule_fingerprint"],
                    "post_occupancy_extension_minutes": proof["post_occupancy_extension_minutes"],
                    "continuous_conditioning": proof["continuous_conditioning"],
                },
            }
        )

    for d in days:
        buckets: dict[str, list[int]] = {}
        for c in all_candidates:
            buckets.setdefault(c["fingerprints_by_day"][d], []).append(int(c["action_index"]))
        unique = {fp: idxs[0] for fp, idxs in buckets.items()}
        dups = {fp: idxs for fp, idxs in buckets.items() if len(idxs) > 1}
        by_day_unique[d] = {
            "n_unique_schedules": len(unique),
            "representative_index_by_fingerprint": unique,
            "n_declared": n,
        }
        duplicate_maps[d] = dups

    seq_buckets: dict[str, list[int]] = {}
    for c in all_candidates:
        seq_buckets.setdefault(c["sequence_fingerprint"], []).append(int(c["action_index"]))
    unique_policies = [
        {"sequence_fingerprint": fp, "representative_index": idxs[0], "action_indices": idxs}
        for fp, idxs in sorted(seq_buckets.items(), key=lambda kv: min(kv[1]))
    ]
    menu_body = {
        "schema": "vibe22.grid_search_candidate_menu.v1",
        "declared_action_count": n,
        "continuous_68_index": 0,
        "continuous_70_index": 1,
        "days": days,
        "unique_by_day": {d: by_day_unique[d]["n_unique_schedules"] for d in days},
        "duplicate_mappings_by_day": {
            d: {fp: idxs for fp, idxs in duplicate_maps[d].items()} for d in days
        },
        "unique_fixed_policies": unique_policies,
        "n_unique_fixed_policies": len(unique_policies),
        "candidates": all_candidates,
    }
    raw = json.dumps(
        {k: v for k, v in menu_body.items() if k != "candidates"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    menu_body["candidate_menu_sha256"] = hashlib.sha256(raw).hexdigest()
    return menu_body


def select_indices_for_screen(
    menu: dict[str, Any],
    *,
    indices: Sequence[int] | None = None,
) -> list[dict[str, Any]]:
    """Return unique fixed-policy groups, optionally filtered to a preregistered index set."""
    wanted = set(int(i) for i in indices) if indices is not None else None
    out: list[dict[str, Any]] = []
    for g in menu["unique_fixed_policies"]:
        idxs = [int(i) for i in g["action_indices"]]
        if wanted is not None and not (wanted & set(idxs)):
            continue
        rep = int(g["representative_index"])
        if wanted is not None:
            # Prefer a wanted index as representative when present
            for i in sorted(wanted & set(idxs)):
                rep = i
                break
        out.append(
            {
                "sequence_fingerprint": g["sequence_fingerprint"],
                "representative_index": rep,
                "action_indices": idxs,
            }
        )
    return out
