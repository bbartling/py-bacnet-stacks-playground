"""Compute A04-v2 selection_verdict.json from on-disk artifacts. Do not hand-write the verdict."""
from __future__ import annotations

from typing import Any

VERDICT_INCOMPLETE = "STAGE_A_NO_CHAMPION_MODEL_DEVELOPMENT_INCOMPLETE"
VERDICT_NOGO = "NO_GO_LONG_RL_TRAINING_TRANSIENT_MODEL_NOT_VALIDATED"
VERDICT_CHAMPION = "MODEL_GO_CHAMPION_VALIDATED_LONG_RL_STILL_REQUIRES_NEW_RAMP_ARTIFACT"

ENGINEERING_MARGIN = 3.0


def compute_selection_verdict(
    *,
    stage_a_summary: dict[str, Any] | None,
    peak_contract: dict[str, Any] | None,
    champion: dict[str, Any] | None = None,
    long_campaign_ramp_passed: bool = False,
    track_b_attempted: bool = False,
    track_b_failed_honestly: bool = False,
    stage_b_trials: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Derive the scientific status from artifacts.

    Long RL stays false unless a newly generated champion ramp artifact passed
    *and* this function is given long_campaign_ramp_passed=True.

    Terminal NO-GO only after Stage B *and* Track B have failed honestly.
    A Track B directory or plan file is not itself a terminal NO-GO.
    """
    a04_sha = "212a2835eabb8b3a316150815a61bc996bf1fda4191df655dbf74f1126132683"
    peak = peak_contract or {}
    trials = list(stage_b_trials or [])
    n_ramp = sum(1 for t in trials if (t.get("ramp") or {}).get("passed") is True)
    n_warn = sum(1 for t in trials if (t.get("warning_gate") or {}).get("passed") is True)
    n_both = sum(
        1
        for t in trials
        if (t.get("ramp") or {}).get("passed") is True and (t.get("warning_gate") or {}).get("passed") is True
    )
    stage_b_ran = len(trials) > 0
    if champion and champion.get("all_gates_passed"):
        verdict = VERDICT_CHAMPION
        long_ok = bool(long_campaign_ramp_passed)
    elif stage_b_ran and n_both == 0 and track_b_failed_honestly:
        verdict = VERDICT_NOGO
        long_ok = False
    else:
        verdict = VERDICT_INCOMPLETE
        long_ok = False
    return {
        "schema": "vibe22.a04v2.selection_verdict.v1",
        "verdict": verdict,
        "champion": champion,
        "long_campaign_allowed": long_ok,
        "public_line": (
            "MODEL DEVELOPMENT CONTINUES — LONG RL BLOCKED"
            if verdict == VERDICT_INCOMPLETE
            else (
                "NO_GO_LONG_RL_TRAINING_TRANSIENT_MODEL_NOT_VALIDATED"
                if verdict == VERDICT_NOGO
                else "MODEL_GO — long RL still requires committed passed ramp_gate.json"
            )
        ),
        "peak_contract": peak,
        "ramp_threshold_unchanged": {
            "engineering_margin": ENGINEERING_MARGIN,
        },
        "stage_a": stage_a_summary,
        "stage_b_n_trials": len(trials),
        "stage_b_n_ramp_passed": n_ramp,
        "stage_b_n_warning_passed": n_warn,
        "stage_b_n_ramp_and_warning_passed": n_both,
        "track_b_attempted": bool(track_b_attempted),
        "track_b_failed_honestly": bool(track_b_failed_honestly),
        "a04_immutable_sha256": a04_sha,
        "pareto": {
            "note": (
                "Stage A CapMult vs 15-min peak is not a terminal hard conflict; "
                "demand interval unresolved; incumbent schedule mismatch remains."
            ),
            "stage_a_15min_conflict_was_premature": True,
        },
    }
