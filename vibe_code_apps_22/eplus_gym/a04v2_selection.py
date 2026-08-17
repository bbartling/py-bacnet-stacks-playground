"""Compute A04-v2 selection_verdict.json from on-disk artifacts. Do not hand-write the verdict."""
from __future__ import annotations

from typing import Any

VERDICT_INCOMPLETE = "MODEL_DEVELOPMENT_INCOMPLETE_NO_CHAMPION"
VERDICT_INCOMPLETE_LEGACY = "STAGE_A_NO_CHAMPION_MODEL_DEVELOPMENT_INCOMPLETE"
VERDICT_NOGO = "NO_GO_LONG_RL_TRAINING_TRANSIENT_MODEL_NOT_VALIDATED"
VERDICT_CHAMPION = "MODEL_GO_CHAMPION_VALIDATED_LONG_RL_STILL_REQUIRES_NEW_RAMP_ARTIFACT"

STATUS_RAMP_PASS_WARNING_FAIL = "RAMP_PASS_WARNING_FAIL"
STATUS_RAMP_FAIL = "RAMP_FAIL"
STATUS_EPLUS_FAIL = "EPLUS_FAIL"
STATUS_DUAL_GATE_PASS = "DUAL_GATE_PASS"
TERMINAL_STAGE_B = frozenset(
    {
        STATUS_RAMP_PASS_WARNING_FAIL,
        STATUS_RAMP_FAIL,
        STATUS_EPLUS_FAIL,
        STATUS_DUAL_GATE_PASS,
        "success",
        "eplus_failed",
        "ramp_failed",
    }
)

ENGINEERING_MARGIN = 3.0


def classify_stage_b_status(
    *,
    eplus_ok: bool,
    ramp_passed: bool | None,
    warning_passed: bool | None,
) -> str:
    """Explicit dual-gate labels. Ramp-pass + warning-fail is not 'success'."""
    if not eplus_ok:
        return STATUS_EPLUS_FAIL
    if ramp_passed is not True:
        return STATUS_RAMP_FAIL
    if warning_passed is not True:
        return STATUS_RAMP_PASS_WARNING_FAIL
    return STATUS_DUAL_GATE_PASS


def classify_trial_record(trial: dict[str, Any]) -> str:
    status = str(trial.get("status") or "")
    if status in {
        STATUS_RAMP_PASS_WARNING_FAIL,
        STATUS_RAMP_FAIL,
        STATUS_EPLUS_FAIL,
        STATUS_DUAL_GATE_PASS,
    }:
        return status
    quality = trial.get("eplus_quality") or {}
    eplus_ok = bool(quality.get("completed_successfully", True)) and status not in {
        "eplus_failed",
        STATUS_EPLUS_FAIL,
    }
    if status == "eplus_failed" or trial.get("returncode") not in (None, 0, 4):
        eplus_ok = False
    ramp_passed = (trial.get("ramp") or {}).get("passed")
    warning_passed = (trial.get("warning_gate") or {}).get("passed")
    return classify_stage_b_status(
        eplus_ok=eplus_ok,
        ramp_passed=ramp_passed,
        warning_passed=warning_passed,
    )


def track_b_state_from_plan(plan: dict[str, Any] | None) -> dict[str, bool]:
    """A plan file is planned only. It is not executed, completed, or a failed attempt."""
    plan = plan or {}
    return {
        "track_b_planned": bool(plan.get("track_b_planned", True if plan else False)),
        "track_b_executed": bool(plan.get("track_b_executed", False)),
        "track_b_completed": bool(plan.get("track_b_completed", False)),
        "track_b_failed_honestly": bool(plan.get("track_b_failed_honestly", False)),
    }


def compute_selection_verdict(
    *,
    stage_a_summary: dict[str, Any] | None,
    peak_contract: dict[str, Any] | None,
    champion: dict[str, Any] | None = None,
    long_campaign_ramp_passed: bool = False,
    track_b_planned: bool = False,
    track_b_executed: bool = False,
    track_b_completed: bool = False,
    track_b_failed_honestly: bool = False,
    track_b_attempted: bool | None = None,
    stage_b_trials: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Derive the scientific status from artifacts.

    Long RL stays false unless a newly generated champion ramp artifact passed
    *and* this function is given long_campaign_ramp_passed=True.

    Terminal NO-GO only after Stage B *and* Track B have failed honestly.
    A Track B directory or plan file is not itself a terminal NO-GO and is not
    Track B executed.
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
    n_ramp_pass_warning_fail = sum(
        1 for t in trials if classify_trial_record(t) == STATUS_RAMP_PASS_WARNING_FAIL
    )
    stage_b_ran = len(trials) > 0
    executed = bool(track_b_executed if track_b_attempted is None else track_b_attempted)
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
        "schema": "vibe22.a04v2.selection_verdict.v2",
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
        "stage_b_n_ramp_pass_warning_fail": n_ramp_pass_warning_fail,
        "track_b_planned": bool(track_b_planned),
        "track_b_executed": bool(executed),
        "track_b_completed": bool(track_b_completed),
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
