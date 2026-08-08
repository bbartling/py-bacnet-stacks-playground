#!/usr/bin/env python
"""Multi-resolution EnergyPlus calibration campaign — real trial execution.

A trial is only ``succeeded`` after EnergyPlus exits, annual meters are extracted,
aligned, and post-run metrics are written. Planned trials are never counted as
executed.

Statuses: planned | running | succeeded | failed | rejected
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
for p in (_APP, _ML, _APP / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lakeside.paths import site_root  # noqa: E402
from eplus_campaign import apply_knobs  # noqa: E402
from eplus_multires_metrics import (  # noqa: E402
    build_validation_document,
    gl14_distance,
)
from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.runner import energyplus_version, run_energyplus  # noqa: E402
from eplus_validation_contract import (  # noqa: E402
    AlignmentError,
    build_hourly_and_15min,
    chronological_splits,
    interval_monthly_from_aligned_hourly,
    score_aligned,
    utility_monthly_from_scorecard,
)

REGISTRY = _APP / "contracts" / "eplus_calib_param_registry_v1.json"
POLICY = _APP / "contracts" / "eplus_dsm_acceptance_policy_v1.json"

# Knobs that apply_knobs can actually mutate on the staged IdealLoads IDF.
EXECUTABLE_KNOBS = frozenset(
    {
        "lights_mult",
        "equip_mult",
        "people_mult",
        "infil_mult",
        "window_u",
        "window_shgc",
        "wall_k_mult",
        "roof_k_mult",
        "wwr",
    }
)


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("multires_%Y%m%dT%H%M%SZ")


def _utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _sensitivity_screen(registry: dict[str, Any], stage: str) -> list[dict[str, Any]]:
    """Plan one-at-a-time bound screens. Non-executable knobs are marked rejected."""
    trials = []
    for p in registry.get("parameters", []):
        if p.get("stage") != stage:
            continue
        lo, hi = p["bounds"]
        mid = (float(lo) + float(hi)) / 2.0
        executable = p["id"] in EXECUTABLE_KNOBS
        for label, val in (("lo", lo), ("mid", mid), ("hi", hi)):
            tid = f"{stage}_{p['id']}_{label}"
            trial = {
                "trial_id": tid,
                "param_id": p["id"],
                "category": p["category"],
                "stage": stage,
                "knobs": {p["id"]: float(val)},
                "value": float(val),
                "bound_label": label,
                "approval_required": p.get("approval_required", False),
                "status": "planned" if executable else "rejected",
                "reject_reason": None
                if executable
                else f"param {p['id']} not supported by apply_knobs on IdealLoads IDF",
            }
            trials.append(trial)
    return trials


def _bounded_executable_plan(registry: dict[str, Any], *, max_trials: int) -> list[dict[str, Any]]:
    """Prefer stage B/C executable knobs for a bounded real campaign."""
    planned: list[dict[str, Any]] = []
    for stage in ("B", "C", "A"):
        for t in _sensitivity_screen(registry, stage):
            if t["status"] != "planned":
                continue
            # Skip mid duplicates that equal parent (1.0) when lo/hi exist — still keep mid
            planned.append(t)
            if len(planned) >= max_trials:
                return planned
    return planned


def _rank_candidate(monthly: dict | None, hourly: dict | None) -> dict[str, Any]:
    monthly_ok = (monthly or {}).get("status") == "pass"
    hourly_dist = (
        gl14_distance(hourly or {}, nmbe_abs_max=10.0, cvrmse_max=30.0)
        if hourly
        else float("nan")
    )
    return {
        "monthly_hard_gate": monthly_ok,
        "hourly_distance": hourly_dist,
        "hourly_status": (hourly or {}).get("status"),
        "rank_key": (
            0 if monthly_ok else 1,
            float(hourly_dist) if hourly_dist == hourly_dist else 1e9,
        ),
    }


def _score_sim(root: Path, sim_dir: Path) -> dict[str, Any]:
    products = build_hourly_and_15min(root, sim_dir)
    aligned_h = products["hourly"]
    aligned_15 = products["q15"]
    hourly = score_aligned(aligned_h, resolution="hourly")
    q15 = score_aligned(aligned_15, resolution="15min")
    util = utility_monthly_from_scorecard(root)
    interv = interval_monthly_from_aligned_hourly(aligned_h)
    periods = chronological_splits(aligned_h)
    # Holdout-only hourly slice for honesty (not used for knob selection here)
    ts = aligned_h["interval_end_utc"]
    holdout_start = ts.max() - __import__("pandas").Timedelta(days=30)
    hold = aligned_h[ts >= holdout_start]
    holdout_hourly = score_aligned(hold, resolution="hourly") if len(hold) >= 24 else None
    return {
        "hourly": hourly,
        "q15": q15,
        "monthly_utility": util,
        "monthly_interval": interv,
        "chronological_periods": periods,
        "holdout_hourly": holdout_hourly,
        "aligned_hourly_n": int(len(aligned_h)),
        "aligned_15_n": int(len(aligned_15)),
        "provenance": {
            "measured": products.get("measured_provenance"),
            "modeled": products.get("modeled_provenance"),
        },
    }


def _write_trial_result(trial_dir: Path, payload: dict[str, Any]) -> None:
    trial_dir.mkdir(parents=True, exist_ok=True)
    (trial_dir / "trial_result.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )


def execute_trial(
    *,
    root: Path,
    camp: Path,
    parent_idf: Path,
    epw: Path,
    trial: dict[str, Any],
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
) -> dict[str, Any]:
    """Apply knobs → unique IDF → EnergyPlus → align → metrics."""
    tid = trial["trial_id"]
    trial_dir = camp / "trials" / tid
    if trial_dir.exists():
        shutil.rmtree(trial_dir, ignore_errors=True)
    trial_dir.mkdir(parents=True, exist_ok=True)
    sim_dir = trial_dir / "sim"

    result: dict[str, Any] = {
        "trial_id": tid,
        "status": "running",
        "started_utc": _utc(),
        "parent_idf": str(parent_idf.resolve()),
        "parent_idf_sha256": sha256_file(parent_idf),
        "epw": str(epw.resolve()),
        "epw_sha256": sha256_file(epw),
        "knobs": trial.get("knobs") or {},
        "param_manifest": {
            "param_id": trial.get("param_id"),
            "stage": trial.get("stage"),
            "bound_label": trial.get("bound_label"),
            "value": trial.get("value"),
        },
    }
    _write_trial_result(trial_dir, result)

    try:
        idf_text = parent_idf.read_text(encoding="utf-8", errors="replace")
        knobs = trial.get("knobs") or {}
        if not knobs:
            raise AlignmentError("empty knobs")
        unknown = set(knobs) - EXECUTABLE_KNOBS
        if unknown:
            result["status"] = "rejected"
            result["reject_reason"] = f"unsupported knobs: {sorted(unknown)}"
            result["ended_utc"] = _utc()
            _write_trial_result(trial_dir, result)
            return result

        mutated = apply_knobs(idf_text, knobs)
        trial_idf = trial_dir / "trial.idf"
        trial_idf.write_text(mutated, encoding="utf-8")
        result["trial_idf"] = str(trial_idf.resolve())
        result["trial_idf_sha256"] = sha256_file(trial_idf)

        manifest = run_energyplus(
            run_id=f"{camp.name}_{tid}",
            scenario_id=tid,
            idf_path=trial_idf,
            epw_path=epw,
            output_dir=sim_dir,
            heat_cop=heat_cop,
            cool_cop=cool_cop,
            require_zero_severe=False,
            allow_staged_idf=False,
        )
        result["energyplus"] = {
            "version": energyplus_version(),
            "exit_code": manifest.exit_code,
            "accepted": manifest.accepted,
            "severe_count": manifest.severe_count,
            "fatal_count": manifest.fatal_count,
            "reject_reasons": list(manifest.reject_reasons or []),
            "command": list(manifest.command),
            "runtime_sec": manifest.runtime_sec,
            "output_dir": str(sim_dir.resolve()),
        }
        # Hash key outputs if present
        out_hashes = {}
        for name in ("eplusout.err", "eplusmtr.csv", "eplusout.csv", "eplusout.end"):
            p = sim_dir / name
            if p.is_file():
                out_hashes[name] = sha256_file(p)
        result["output_sha256"] = out_hashes

        if manifest.exit_code != 0 or not (sim_dir / "eplusmtr.csv").is_file():
            result["status"] = "failed"
            result["reject_reason"] = (
                f"energyplus exit={manifest.exit_code} or missing eplusmtr.csv; "
                f"reasons={manifest.reject_reasons}"
            )
            result["ended_utc"] = _utc()
            _write_trial_result(trial_dir, result)
            return result

        metrics = _score_sim(root, sim_dir)
        result["post_run_metrics"] = {
            "monthly_utility": metrics["monthly_utility"],
            "monthly_interval": metrics["monthly_interval"],
            "hourly": metrics["hourly"],
            "q15": metrics["q15"],
            "holdout_hourly": metrics["holdout_hourly"],
            "aligned_hourly_n": metrics["aligned_hourly_n"],
            "aligned_15_n": metrics["aligned_15_n"],
        }
        result["chronological_periods"] = metrics["chronological_periods"]
        result["ranking"] = _rank_candidate(
            metrics["monthly_utility"], metrics["hourly"]
        )
        # Promotion: never promote when hourly fails
        hourly_ok = (metrics["hourly"] or {}).get("status") == "pass"
        result["promote_allowed"] = False
        result["promote_block_reason"] = (
            None
            if hourly_ok
            else "hourly validation failed — refuse promotion"
        )
        result["status"] = "succeeded"
        result["ended_utc"] = _utc()
        _write_trial_result(trial_dir, result)
        return result
    except Exception as e:
        result["status"] = "failed"
        result["reject_reason"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()[-4000:]
        result["ended_utc"] = _utc()
        _write_trial_result(trial_dir, result)
        return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["A", "B", "C", "all"], default="B")
    ap.add_argument("--run-id", default=None)
    ap.add_argument(
        "--plan-only",
        action="store_true",
        help="Write planned trial records only (no EnergyPlus). Does not count as execution.",
    )
    ap.add_argument(
        "--run-eplus",
        action="store_true",
        help="Execute EnergyPlus for each planned executable trial (required for real campaign).",
    )
    ap.add_argument(
        "--max-trials",
        type=int,
        default=8,
        help="Max executable trials when --run-eplus (bounded campaign).",
    )
    ap.add_argument(
        "--smoke",
        action="store_true",
        help="Execute at most 2 trials to prove the full loop.",
    )
    args = ap.parse_args(argv)

    if not args.plan_only and not args.run_eplus:
        print(
            "ERROR: specify --run-eplus to execute trials, or --plan-only to plan. "
            "The previous no-op --run-eplus behavior has been removed.",
            file=sys.stderr,
        )
        return 2

    os.environ.setdefault(
        "LAKESIDE_SITE_ROOT",
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
    )
    root = site_root()
    registry = _load_registry()
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    run_id = args.run_id or _run_id()
    camp = root / "eplus" / "campaigns" / run_id
    camp.mkdir(parents=True, exist_ok=True)
    ledger_path = camp / "ledger.jsonl"

    ptr = root / "eplus" / "models" / "staged" / "DSM_ELIGIBLE.json"
    elig = json.loads(ptr.read_text(encoding="utf-8")) if ptr.is_file() else {}
    idf = Path(elig.get("staged_idf") or "")
    if not idf.is_file():
        idf = root / "eplus" / "models" / "staged" / "lakeside_6zone_gshp_best_utility_dsm_v1.idf"
    epw = root / "eplus" / "weather" / "madison_amy_202508_202607.epw"
    if not idf.is_file() or not epw.is_file():
        print(f"missing idf/epw: {idf} / {epw}", file=sys.stderr)
        return 2

    # Baseline metrics from existing repaired sim (no re-run)
    baseline_sim = root / "eplus" / "dsm_native" / "runs" / "dsm_repair_v1_full" / "sim"
    before = _score_sim(root, baseline_sim) if baseline_sim.is_dir() else {}
    if before:
        from eplus_calib_diagnostics import write_diagnostic_suite
        import pandas as pd

        products = build_hourly_and_15min(root, baseline_sim)
        ah = products["hourly"].rename(
            columns={"observed_kw": "kw_meas", "simulated_kw": "kw_mod", "interval_end_utc": "timestamp_utc"}
        )
        a15 = products["q15"].rename(
            columns={"observed_kw": "kw_meas", "simulated_kw": "kw_mod", "interval_end_utc": "timestamp_utc"}
        )
        ah.to_csv(camp / "aligned_hourly.csv", index=False)
        a15.to_csv(camp / "aligned_15min.csv", index=False)
        write_diagnostic_suite(ah, camp / "diagnostics", aligned_15=a15)

    validation = build_validation_document(
        monthly_utility=before.get("monthly_utility"),
        monthly_interval=before.get("monthly_interval"),
        hourly=before.get("hourly"),
        q15=before.get("q15"),
        physics_label=registry.get("physics"),
        idf_sha256=sha256_file(idf).upper(),
        epw_sha256=sha256_file(epw).upper(),
        chronological_periods=before.get("chronological_periods"),
        extra={"baseline_sim": str(baseline_sim)},
    )
    # Force DSM blocked while hourly fails
    if not validation["overall"]["hourly_pass"]:
        validation["overall"]["operational_dsm_readiness"] = "BLOCKED"
        validation["overall"]["recommendation_allowed"] = False
    (camp / "validation_before.json").write_text(
        json.dumps(validation, indent=2, default=str) + "\n", encoding="utf-8"
    )

    max_n = 2 if args.smoke else int(args.max_trials)
    if args.stage == "all":
        plan = _bounded_executable_plan(registry, max_trials=max_n)
        # Also persist rejected non-executable for audit
        rejected_audit = []
        for st in ("A", "B", "C"):
            rejected_audit.extend(
                [t for t in _sensitivity_screen(registry, st) if t["status"] == "rejected"]
            )
    else:
        full = _sensitivity_screen(registry, args.stage)
        plan = [t for t in full if t["status"] == "planned"][:max_n]
        rejected_audit = [t for t in full if t["status"] == "rejected"]

    (camp / "planned_trials.json").write_text(
        json.dumps(plan + rejected_audit, indent=2) + "\n", encoding="utf-8"
    )

    executed: list[dict[str, Any]] = []
    if args.run_eplus:
        for trial in plan:
            print(f"EXEC {trial['trial_id']} knobs={trial['knobs']}", flush=True)
            res = execute_trial(
                root=root, camp=camp, parent_idf=idf, epw=epw, trial=trial
            )
            executed.append(res)
            with ledger_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"event": "trial", **res}, default=str) + "\n")
    else:
        with ledger_path.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "event": "plan_only",
                        "n_planned": len(plan),
                        "n_rejected_nonexecutable": len(rejected_audit),
                        "note": "No EnergyPlus execution — do not count as campaign success",
                    }
                )
                + "\n"
            )

    n_succ = sum(1 for r in executed if r.get("status") == "succeeded")
    n_fail = sum(1 for r in executed if r.get("status") == "failed")
    n_rej = sum(1 for r in executed if r.get("status") == "rejected") + len(rejected_audit)

    # Leaderboard from succeeded only
    board = []
    for r in executed:
        if r.get("status") != "succeeded":
            continue
        h = (r.get("post_run_metrics") or {}).get("hourly") or {}
        board.append(
            {
                "trial_id": r["trial_id"],
                "knobs": r.get("knobs"),
                "hourly_cvrmse_pct": h.get("cvrmse_pct"),
                "hourly_rmse_kw": h.get("rmse_kw"),
                "hourly_status": h.get("status"),
                "rank_key": (r.get("ranking") or {}).get("rank_key"),
                "promote_allowed": r.get("promote_allowed"),
            }
        )
    board.sort(key=lambda x: x.get("rank_key") or (1, 1e9))

    # Structural verdict: if all succeeded trials still fail hourly, IdealLoads inadequate for hourly DSM
    structural = {
        "physics": registry.get("physics"),
        "n_executed_succeeded": n_succ,
        "all_succeeded_fail_hourly": bool(board)
        and all(b.get("hourly_status") != "pass" for b in board),
        "verdict": None,
        "recommendation": None,
    }
    if args.run_eplus and n_succ >= 1:
        if structural["all_succeeded_fail_hourly"]:
            structural["verdict"] = (
                "BOUNDED_SEARCH_FAILED_HOURLY — IdealLoads+fixed-COP did not meet "
                "hourly screen under executed knobs; do not claim GSHP plant fidelity"
            )
            structural["recommendation"] = (
                "A) Build physically meaningful plant/heat-pump model, or "
                "B) Restrict E+ to monthly/engineering benchmark; use measured-data ML "
                "for absolute facility kW and zone temperatures"
            )
        else:
            structural["verdict"] = "at_least_one_trial_passed_hourly_screen"
            structural["recommendation"] = "re-evaluate promote gates and locked holdout"

    before_h = (before.get("hourly") or {}) if before else {}
    after_best = board[0] if board else None
    summary = {
        "run_id": run_id,
        "campaign_dir": str(camp),
        "plan_only": bool(args.plan_only),
        "run_eplus": bool(args.run_eplus),
        "smoke": bool(args.smoke),
        "parent_idf_sha256": sha256_file(idf),
        "epw_sha256": sha256_file(epw),
        "n_planned_executable": len(plan),
        "n_executed_attempted": len(executed),
        "n_succeeded": n_succ,
        "n_failed": n_fail,
        "n_rejected": n_rej,
        "n_planned_not_counted_as_success": len(plan) if args.plan_only else 0,
        "leaderboard": board,
        "before_hourly": {
            "nmbe_pct": before_h.get("nmbe_pct"),
            "cvrmse_pct": before_h.get("cvrmse_pct"),
            "rmse_kw": before_h.get("rmse_kw"),
            "mae_kw": before_h.get("mae_kw"),
            "status": before_h.get("status"),
            "n": before_h.get("n"),
        },
        "best_after": after_best,
        "structural": structural,
        "validation_before_overall": validation["overall"],
        "champion_protected": True,
        "policy_id": policy.get("policy_id"),
        "holdout": (before.get("chronological_periods") or {}).get("locked_final_holdout"),
        "operational_dsm_readiness": "NO-GO",
    }
    (camp / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (camp / "structural_verdict.json").write_text(
        json.dumps(structural, indent=2) + "\n", encoding="utf-8"
    )

    mirror = _APP / "ml" / "artifacts" / "eplus_campaigns"
    mirror.mkdir(parents=True, exist_ok=True)
    (mirror / "latest_summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )

    print(json.dumps(summary, indent=2, default=str))
    if args.plan_only:
        return 0
    if n_succ == 0 and args.run_eplus:
        return 3
    if not validation["overall"]["hourly_pass"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
