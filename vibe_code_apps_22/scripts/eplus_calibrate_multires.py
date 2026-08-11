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
_ML = _APP / "archive" / "ml"
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
    score_period,
    utility_monthly_from_trial_sim,
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


def _multi_param_smoke_plan() -> list[dict[str, Any]]:
    """Small multi-parameter combinations (not OFAT-only) for corrected scoring proof."""
    combos = [
        {"equip_mult": 1.0, "lights_mult": 1.0, "infil_mult": 1.0},
        {"equip_mult": 0.85, "lights_mult": 0.9, "infil_mult": 1.0},
        {"equip_mult": 1.0, "lights_mult": 0.9, "infil_mult": 0.9},
    ]
    out = []
    for i, knobs in enumerate(combos):
        out.append(
            {
                "trial_id": f"MP_smoke_{i}_{'_'.join(f'{k}{v}' for k,v in knobs.items())}",
                "param_id": "multi_param",
                "category": "B_C_interaction",
                "stage": "B",
                "knobs": knobs,
                "value": None,
                "bound_label": f"combo_{i}",
                "approval_required": False,
                "status": "planned",
                "reject_reason": None,
            }
        )
    return out


def _bounded_executable_plan(registry: dict[str, Any], *, max_trials: int) -> list[dict[str, Any]]:
    """Prefer stage B/C executable knobs for a bounded real campaign."""
    planned: list[dict[str, Any]] = []
    for stage in ("B", "C", "A"):
        for t in _sensitivity_screen(registry, stage):
            if t["status"] != "planned":
                continue
            planned.append(t)
            if len(planned) >= max_trials:
                return planned
    return planned


def _rank_candidate(
    monthly_utility: dict | None,
    monthly_interval: dict | None,
    chrono_val_hourly: dict | None,
) -> dict[str, Any]:
    """Rank on chrono-validation hourly + trial monthly gates. Never all-period or holdout."""
    util_ok = (monthly_utility or {}).get("status") == "pass"
    interv_ok = (monthly_interval or {}).get("status") == "pass"
    hourly_dist = (
        gl14_distance(chrono_val_hourly or {}, nmbe_abs_max=10.0, cvrmse_max=30.0)
        if chrono_val_hourly
        else float("nan")
    )
    monthly_ok = bool(util_ok and interv_ok)
    return {
        "monthly_utility_pass": util_ok,
        "monthly_interval_pass": interv_ok,
        "monthly_hard_gate": monthly_ok,
        "chrono_val_hourly_distance": hourly_dist,
        "chrono_val_hourly_status": (chrono_val_hourly or {}).get("status"),
        "rank_key": (
            0 if monthly_ok else 1,
            0 if util_ok else 1,
            float(hourly_dist) if hourly_dist == hourly_dist else 1e9,
        ),
        "ranking_uses_holdout": False,
        "ranking_period": "chronological_validation",
    }


def _promotion_gate(metrics: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed conjunction. Scorecard status never unblocks."""
    util = metrics.get("monthly_utility") or {}
    interv = metrics.get("monthly_interval") or {}
    chrono = metrics.get("hourly_chronological_validation") or {}
    winter = metrics.get("hourly_locked_winter_holdout")
    q15 = metrics.get("q15") or {}
    reasons: list[str] = []
    if util.get("status") != "pass":
        reasons.append(f"monthly_utility={util.get('status')}")
    if util.get("scorecard_gl14_status_imported"):
        reasons.append("scorecard_status_imported_forbidden")
    if interv.get("status") != "pass":
        reasons.append(f"monthly_interval={interv.get('status')}")
    if chrono.get("status") != "pass":
        reasons.append(f"chrono_val_hourly={chrono.get('status')}")
    # Locked winter is only required when present (champion holdout report).
    if winter is not None and winter.get("status") != "pass":
        reasons.append(f"locked_winter_hourly={winter.get('status')}")
    q15_n = int(q15.get("n") or 0)
    q15_status = q15.get("status")
    if q15_status not in {"diagnostic_only", "pass"} or q15_n < 96:
        reasons.append(
            f"q15_peak_response_insufficient(status={q15_status},n={q15_n})"
        )
    # Zone/comfort: IdealLoads campaign does not yet publish zone MAE — fail closed
    zone = metrics.get("zone_temperature")
    if not zone or zone.get("status") not in {"pass"}:
        reasons.append("zone_temperature_comfort=insufficient_or_fail")
    prov = metrics.get("provenance") or {}
    if not prov.get("measured") or not prov.get("modeled"):
        reasons.append("provenance_incomplete")
    # Operational DSM always blocked in this PR
    reasons.append("operational_dsm_blocked_no_treatment_effect_evidence")
    return {
        "promote_allowed": False,  # hard NO-GO this task
        "gates_clear_technical": len([r for r in reasons if not r.startswith("operational")]) == 0,
        "promote_block_reasons": reasons,
        "operational_dsm_readiness": "NO-GO",
    }


def _post_run_metrics_from_score(
    metrics: dict[str, Any],
    *,
    include_locked_holdout: bool = False,
) -> dict[str, Any]:
    """Shared schema for execute_trial and rescore trial metric documents."""
    out: dict[str, Any] = {
        "family_label": metrics.get("family_label"),
        "monthly_utility": metrics["monthly_utility"],
        "monthly_interval": metrics["monthly_interval"],
        "hourly": metrics["hourly"],
        "hourly_chronological_validation": metrics.get("hourly_chronological_validation"),
        "hourly_calibration_development": metrics.get("hourly_calibration_development"),
        "hourly_winter_peak_validation": metrics.get("hourly_winter_peak_validation"),
        "hourly_annual_summer_generalization": metrics.get(
            "hourly_annual_summer_generalization"
        ),
        "hourly_post_holdout_generalization": metrics.get(
            "hourly_post_holdout_generalization"
        ),
        "q15": metrics["q15"],
        "q15_chronological_validation": metrics.get("q15_chronological_validation"),
        "day_level_peaks_chrono_val": metrics.get("day_level_peaks_chrono_val"),
        "aligned_hourly_n": metrics["aligned_hourly_n"],
        "aligned_15_n": metrics["aligned_15_n"],
        "provenance": metrics.get("provenance"),
        "include_locked_holdout": bool(include_locked_holdout),
    }
    if include_locked_holdout:
        out["hourly_locked_winter_holdout"] = metrics.get("hourly_locked_winter_holdout")
    return out


def _score_sim(
    root: Path,
    sim_dir: Path,
    *,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
    include_locked_holdout: bool = False,
) -> dict[str, Any]:
    from eplus_validation_contract import day_level_peak_metrics, period_mask

    products = build_hourly_and_15min(root, sim_dir, heat_cop=heat_cop, cool_cop=cool_cop)
    aligned_h = products["hourly"]
    aligned_15 = products["q15"]
    hourly_all = score_aligned(aligned_h, resolution="hourly")
    q15 = score_aligned(aligned_15, resolution="15min")
    util = utility_monthly_from_trial_sim(root, sim_dir, heat_cop=heat_cop, cool_cop=cool_cop)
    interv = interval_monthly_from_aligned_hourly(aligned_h)
    periods = chronological_splits(aligned_h)

    period_scores = {
        "hourly_calibration_development": score_period(aligned_h, "calibration_development"),
        "hourly_chronological_validation": score_period(aligned_h, "chronological_validation"),
        "hourly_winter_peak_validation": score_period(aligned_h, "winter_peak_validation"),
        "hourly_post_holdout_generalization": score_period(
            aligned_h, "post_holdout_generalization"
        ),
        "hourly_annual_summer_generalization": score_period(
            aligned_h, "annual_summer_generalization"
        ),
    }
    # Candidate scoring never computes locked holdout metrics.
    if include_locked_holdout:
        period_scores["hourly_locked_winter_holdout"] = score_period(
            aligned_h, "locked_winter_holdout"
        )

    try:
        m15 = period_mask(aligned_15, "chronological_validation")
        q15_val = score_aligned(aligned_15.loc[m15], resolution="15min") if m15.any() else None
    except Exception:
        q15_val = None

    try:
        m_val = period_mask(aligned_h, "chronological_validation")
        day_peaks = (
            day_level_peak_metrics(aligned_h.loc[m_val]) if m_val.any() else None
        )
    except Exception:
        day_peaks = None

    ranking = _rank_candidate(
        util, interv, period_scores["hourly_chronological_validation"]
    )
    out = {
        "hourly": hourly_all,
        "q15": q15,
        "q15_chronological_validation": q15_val,
        "monthly_utility": util,
        "monthly_interval": interv,
        "chronological_periods": periods,
        **period_scores,
        "day_level_peaks_chrono_val": day_peaks,
        "aligned_hourly_n": int(len(aligned_h)),
        "aligned_15_n": int(len(aligned_15)),
        "provenance": {
            "measured": products.get("measured_provenance"),
            "modeled": products.get("modeled_provenance"),
        },
        "family_label": "RAW_EPLUS_IDEALLOADS_FIXED_COP",
        "ranking": ranking,
        "include_locked_holdout": bool(include_locked_holdout),
    }
    out["promotion"] = _promotion_gate(out)
    return out


def evaluate_selected_champion_holdout(
    root: Path,
    sim_dir: Path,
    *,
    champion_id: str,
    selection_artifact_hash: str,
    heat_cop: float = 3.5,
    cool_cop: float = 4.5,
) -> dict[str, Any]:
    """Immutable locked-winter report for the selected champion only — never reranks."""
    from eplus_validation_contract import day_level_peak_metrics, period_mask

    scored = _score_sim(
        root,
        sim_dir,
        heat_cop=heat_cop,
        cool_cop=cool_cop,
        include_locked_holdout=True,
    )
    winter = scored.get("hourly_locked_winter_holdout")
    day_peaks = None
    try:
        products = build_hourly_and_15min(
            root, sim_dir, heat_cop=heat_cop, cool_cop=cool_cop
        )
        aligned_h = products["hourly"]
        m_w = period_mask(aligned_h, "locked_winter_holdout")
        if m_w.any():
            day_peaks = day_level_peak_metrics(aligned_h.loc[m_w])
    except Exception as e:
        day_peaks = {"status": "error", "error": str(e)}
    return {
        "schema": "champion_locked_holdout_report_v1",
        "champion_id": champion_id,
        "selection_artifact_hash": selection_artifact_hash,
        "evaluated_utc": _utc(),
        "hourly_locked_winter_holdout": winter,
        "day_level_peaks_locked_winter": day_peaks,
        "chronological_periods": scored.get("chronological_periods"),
        "reranked_after_holdout": False,
        "operational_dsm_readiness": "NO-GO",
        "holdout_pass": (winter or {}).get("status") == "pass",
        "note": (
            "Holdout failure retains the selected champion; report failure only. "
            "Never rerank after seeing holdout."
        ),
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

        metrics = _score_sim(
            root, sim_dir, heat_cop=heat_cop, cool_cop=cool_cop, include_locked_holdout=False
        )
        # Persist trial-specific monthly pairs beside result
        pairs = (metrics.get("monthly_utility") or {}).get("monthly_pairs") or []
        if pairs:
            import csv

            with (trial_dir / "utility_monthly_pairs.csv").open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["month", "kwh_obs", "kwh_sim"])
                w.writeheader()
                w.writerows(pairs)
        result["post_run_metrics"] = _post_run_metrics_from_score(
            metrics, include_locked_holdout=False
        )
        result["chronological_periods"] = metrics["chronological_periods"]
        result["ranking"] = metrics["ranking"]
        promo = metrics["promotion"]
        result["promote_allowed"] = promo["promote_allowed"]
        result["promote_block_reasons"] = promo["promote_block_reasons"]
        result["operational_dsm_readiness"] = promo["operational_dsm_readiness"]
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


def _rescore_existing_campaign(camp: Path) -> int:
    """Recompute trial metrics without mutating the original execution summary.

    Writes ``summary_rescored_<timestamp>.json`` and a pointer file. Never
    overwrites ``summary.json``. Preserves failed/rejected trial statuses.
    """
    root = site_root()
    camp = Path(camp)
    trials_dir = camp / "trials"
    if not trials_dir.is_dir():
        print(f"missing trials dir {trials_dir}", file=sys.stderr)
        return 2

    original_summary_path = camp / "summary.json"
    original_summary = None
    original_summary_sha = None
    if original_summary_path.is_file():
        raw = original_summary_path.read_bytes()
        original_summary_sha = hashlib.sha256(raw).hexdigest()
        try:
            original_summary = json.loads(raw.decode("utf-8"))
        except Exception as e:
            print(f"WARNING: could not parse original summary.json: {e}", file=sys.stderr)

    executed: list[dict[str, Any]] = []
    for td in sorted(trials_dir.iterdir()):
        if not td.is_dir():
            continue
        trp = td / "trial_result.json"
        prev: dict[str, Any] = {}
        if trp.is_file():
            prev = json.loads(trp.read_text(encoding="utf-8"))
        original_status = prev.get("status")
        sim = td / "sim"
        # Only rescore trials that previously succeeded with meters present.
        if original_status in {"failed", "rejected", "planned", "running"}:
            executed.append(prev)
            continue
        if not (sim / "eplusmtr.csv").is_file():
            executed.append(prev)
            continue
        print(f"RESCORE {td.name} (preserving status={original_status})", flush=True)
        try:
            metrics = _score_sim(root, sim, include_locked_holdout=False)
            pairs = (metrics.get("monthly_utility") or {}).get("monthly_pairs") or []
            if pairs:
                import csv

                with (td / "utility_monthly_pairs.csv").open(
                    "w", encoding="utf-8", newline=""
                ) as f:
                    w = csv.DictWriter(f, fieldnames=["month", "kwh_obs", "kwh_sim"])
                    w.writeheader()
                    w.writerows(pairs)
            prev["post_run_metrics"] = _post_run_metrics_from_score(
                metrics, include_locked_holdout=False
            )
            prev["ranking"] = metrics["ranking"]
            prev["promote_allowed"] = metrics["promotion"]["promote_allowed"]
            prev["promote_block_reasons"] = metrics["promotion"]["promote_block_reasons"]
            prev["operational_dsm_readiness"] = "NO-GO"
            # Never promote failed/rejected → succeeded
            if original_status:
                prev["status"] = original_status
            elif prev.get("status") not in {"succeeded", "failed", "rejected"}:
                prev["status"] = "succeeded"
            prev["rescored_utc"] = _utc()
            prev["trial_id"] = td.name
            prev["knobs"] = prev.get("knobs") or {}
            _write_trial_result(td, prev)
            executed.append(prev)
        except Exception as e:
            print(f"  FAIL {td.name}: {e}", file=sys.stderr)
            prev["rescore_error"] = str(e)
            executed.append(prev)

    board = []
    for r in executed:
        if r.get("status") != "succeeded":
            continue
        prm = r.get("post_run_metrics") or {}
        if "hourly_locked_winter_holdout" in prm:
            raise RuntimeError(
                "candidate post_run_metrics must not contain locked holdout after rescore"
            )
        util = prm.get("monthly_utility") or {}
        interv = prm.get("monthly_interval") or {}
        chrono = prm.get("hourly_chronological_validation") or {}
        board.append(
            {
                "trial_id": r["trial_id"],
                "knobs": r.get("knobs"),
                "family_label": prm.get("family_label"),
                "utility_nmbe_pct": util.get("nmbe_pct"),
                "utility_cvrmse_pct": util.get("cvrmse_pct"),
                "utility_status": util.get("status"),
                "interval_monthly_status": interv.get("status"),
                "chrono_val_hourly_cvrmse_pct": chrono.get("cvrmse_pct"),
                "chrono_val_hourly_rmse_kw": chrono.get("rmse_kw"),
                "chrono_val_hourly_status": chrono.get("status"),
                "all_period_hourly_cvrmse_pct": (prm.get("hourly") or {}).get("cvrmse_pct"),
                "rank_key": (r.get("ranking") or {}).get("rank_key"),
                "ranking_uses_holdout": False,
                "promote_allowed": r.get("promote_allowed"),
                "promote_block_reasons": r.get("promote_block_reasons"),
            }
        )
    board.sort(key=lambda x: x.get("rank_key") or (1, 1, 1e9))

    selection_blob = json.dumps(board, sort_keys=True, default=str).encode()
    selection_hash = hashlib.sha256(selection_blob).hexdigest()
    holdout_report = None
    if board:
        champ = board[0]["trial_id"]
        champ_sim = camp / "trials" / champ / "sim"
        if (champ_sim / "eplusmtr.csv").is_file():
            holdout_report = evaluate_selected_champion_holdout(
                root,
                champ_sim,
                champion_id=champ,
                selection_artifact_hash=selection_hash,
            )
            (camp / "champion_locked_holdout_report.json").write_text(
                json.dumps(holdout_report, indent=2, default=str) + "\n",
                encoding="utf-8",
            )

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    summary = {
        "run_id": camp.name,
        "campaign_dir": str(camp.resolve()),
        "rescored": True,
        "rescored_utc": _utc(),
        "original_summary_path": str(original_summary_path) if original_summary_path.is_file() else None,
        "original_summary_sha256": original_summary_sha,
        "original_execution_provenance": {
            "parent_idf_sha256": (original_summary or {}).get("parent_idf_sha256"),
            "epw_sha256": (original_summary or {}).get("epw_sha256"),
            "n_executed_attempted": (original_summary or {}).get("n_executed_attempted"),
            "n_succeeded": (original_summary or {}).get("n_succeeded"),
            "n_failed": (original_summary or {}).get("n_failed"),
            "n_rejected": (original_summary or {}).get("n_rejected"),
            "energyplus_version": (original_summary or {}).get("energyplus_version"),
            "note": (
                "Original summary.json is immutable. If these fields are null, "
                "provenance was previously overwritten and must be reconstructed "
                "from trial manifests / ledger."
            ),
        },
        "n_succeeded": sum(1 for r in executed if r.get("status") == "succeeded"),
        "n_failed": sum(1 for r in executed if r.get("status") == "failed"),
        "n_rejected": sum(1 for r in executed if r.get("status") == "rejected"),
        "leaderboard": board,
        "utility_monthly_table": [
            {
                "trial_id": b["trial_id"],
                "nmbe_pct": b["utility_nmbe_pct"],
                "cvrmse_pct": b["utility_cvrmse_pct"],
                "status": b["utility_status"],
            }
            for b in board
        ],
        "best_after": board[0] if board else None,
        "selection_artifact_hash": selection_hash,
        "champion_locked_holdout_report": holdout_report,
        "operational_dsm_readiness": "NO-GO",
        "family_label": "RAW_EPLUS_IDEALLOADS_FIXED_COP",
        "baseline_parent_note": (
            "If best trial knobs are identity (equip_mult=1.0 etc.), that is the "
            "unchanged parent/baseline — not a materially improved model."
        ),
    }
    out_name = f"summary_rescored_{ts}.json"
    out_path = camp / out_name
    out_path.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    (camp / "summary_rescored_latest.json").write_text(
        json.dumps(
            {
                "pointer": out_name,
                "sha256": hashlib.sha256(out_path.read_bytes()).hexdigest(),
                "original_summary_sha256": original_summary_sha,
                "written_utc": _utc(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # CRITICAL: never overwrite original summary.json
    if original_summary_path.is_file():
        after = hashlib.sha256(original_summary_path.read_bytes()).hexdigest()
        if original_summary_sha and after != original_summary_sha:
            raise RuntimeError("rescore mutated summary.json — abort")
    mirror = _APP / "archive" / "ml" / "artifacts" / "eplus_campaigns"
    mirror.mkdir(parents=True, exist_ok=True)
    (mirror / "latest_summary_rescored.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, default=str))
    return 0


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
    ap.add_argument(
        "--rescore-existing",
        type=Path,
        default=None,
        help="Rescore trials under an existing campaign dir (no EnergyPlus).",
    )
    ap.add_argument(
        "--multi-param-smoke",
        action="store_true",
        help="Run 3 multi-parameter combinations instead of OFAT screen.",
    )
    args = ap.parse_args(argv)

    if args.rescore_existing is not None:
        return _rescore_existing_campaign(Path(args.rescore_existing))

    if not args.plan_only and not args.run_eplus:
        print(
            "ERROR: specify --run-eplus to execute trials, or --plan-only to plan. "
            "The previous no-op --run-eplus behavior has been removed.",
            file=sys.stderr,
        )
        return 2

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
    if args.multi_param_smoke:
        plan = _multi_param_smoke_plan()[:max_n]
        rejected_audit = []
    elif args.stage == "all":
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

    # Leaderboard from succeeded only — rank on chrono-val + trial utility (NOT holdout)
    board = []
    for r in executed:
        if r.get("status") != "succeeded":
            continue
        prm = r.get("post_run_metrics") or {}
        if "hourly_locked_winter_holdout" in prm:
            raise RuntimeError("candidate metrics must not include locked holdout")
        util = prm.get("monthly_utility") or {}
        interv = prm.get("monthly_interval") or {}
        chrono = prm.get("hourly_chronological_validation") or {}
        board.append(
            {
                "trial_id": r["trial_id"],
                "knobs": r.get("knobs"),
                "family_label": prm.get("family_label") or "RAW_EPLUS_IDEALLOADS_FIXED_COP",
                "utility_nmbe_pct": util.get("nmbe_pct"),
                "utility_cvrmse_pct": util.get("cvrmse_pct"),
                "utility_status": util.get("status"),
                "interval_monthly_status": interv.get("status"),
                "chrono_val_hourly_cvrmse_pct": chrono.get("cvrmse_pct"),
                "chrono_val_hourly_rmse_kw": chrono.get("rmse_kw"),
                "chrono_val_hourly_status": chrono.get("status"),
                "all_period_hourly_cvrmse_pct": (prm.get("hourly") or {}).get("cvrmse_pct"),
                "rank_key": (r.get("ranking") or {}).get("rank_key"),
                "ranking_uses_holdout": False,
                "promote_allowed": r.get("promote_allowed"),
                "promote_block_reasons": r.get("promote_block_reasons"),
            }
        )
    board.sort(key=lambda x: x.get("rank_key") or (1, 1, 1e9))

    selection_blob = json.dumps(board, sort_keys=True, default=str).encode()
    selection_hash = hashlib.sha256(selection_blob).hexdigest()
    holdout_report = None
    if board and args.run_eplus:
        champ_id = board[0]["trial_id"]
        champ_sim = camp / "trials" / champ_id / "sim"
        if (champ_sim / "eplusmtr.csv").is_file():
            holdout_report = evaluate_selected_champion_holdout(
                root,
                champ_sim,
                champion_id=champ_id,
                selection_artifact_hash=selection_hash,
            )
            (camp / "champion_locked_holdout_report.json").write_text(
                json.dumps(holdout_report, indent=2, default=str) + "\n",
                encoding="utf-8",
            )

    # Structural verdict: distinguish FAIL vs INSUFFICIENT_DATA
    statuses = [b.get("chrono_val_hourly_status") for b in board]
    all_fail = bool(board) and all(s == "fail" for s in statuses)
    all_insufficient = bool(board) and all(s == "insufficient_data" for s in statuses)
    mixed_or_partial = bool(board) and not all_fail and not all_insufficient and all(
        s != "pass" for s in statuses
    )
    structural = {
        "physics": registry.get("physics"),
        "n_executed_succeeded": n_succ,
        "all_succeeded_fail_chrono_val_hourly": all_fail,
        "all_succeeded_insufficient_chrono_val_hourly": all_insufficient,
        "verdict": None,
        "recommendation": None,
        "champion_locked_holdout_report": holdout_report,
        "family_label": "RAW_EPLUS_IDEALLOADS_FIXED_COP",
    }
    if args.run_eplus and n_succ >= 1:
        if all_insufficient:
            structural["verdict"] = "INSUFFICIENT_DATA"
            structural["recommendation"] = (
                "Chrono-validation windows empty or too short — expand AMY overlap "
                "before interpreting IdealLoads+fixed-COP screen failure"
            )
        elif all_fail or mixed_or_partial:
            structural["verdict"] = "FAIL"
            structural["recommendation"] = (
                "A) Build physically meaningful plant/heat-pump model, or "
                "B) Restrict E+ to monthly/engineering benchmark; use measured-data ML "
                "for absolute facility kW. Proxy corrector remains DIAGNOSTIC_ONLY."
            )
        else:
            structural["verdict"] = "at_least_one_trial_passed_chrono_val_hourly_screen"
            structural["recommendation"] = "re-evaluate promote gates and locked winter holdout"

    before_h = (before.get("hourly") or {}) if before else {}
    before_util = (before.get("monthly_utility") or {}) if before else {}
    after_best = board[0] if board else None
    summary = {
        "run_id": run_id,
        "campaign_dir": str(camp),
        "plan_only": bool(args.plan_only),
        "run_eplus": bool(args.run_eplus),
        "smoke": bool(args.smoke),
        "energyplus_version": energyplus_version(),
        "parent_idf_sha256": sha256_file(idf),
        "epw_sha256": sha256_file(epw),
        "n_planned_executable": len(plan),
        "n_executed_attempted": len(executed),
        "n_succeeded": n_succ,
        "n_failed": n_fail,
        "n_rejected": n_rej,
        "n_planned_not_counted_as_success": len(plan) if args.plan_only else 0,
        "leaderboard": board,
        "selection_artifact_hash": selection_hash,
        "utility_monthly_table": [
            {
                "trial_id": b["trial_id"],
                "nmbe_pct": b["utility_nmbe_pct"],
                "cvrmse_pct": b["utility_cvrmse_pct"],
                "status": b["utility_status"],
            }
            for b in board
        ],
        "before_hourly": {
            "nmbe_pct": before_h.get("nmbe_pct"),
            "cvrmse_pct": before_h.get("cvrmse_pct"),
            "rmse_kw": before_h.get("rmse_kw"),
            "mae_kw": before_h.get("mae_kw"),
            "status": before_h.get("status"),
            "n": before_h.get("n"),
        },
        "before_utility_trial_specific": {
            "nmbe_pct": before_util.get("nmbe_pct"),
            "cvrmse_pct": before_util.get("cvrmse_pct"),
            "status": before_util.get("status"),
            "n": before_util.get("n"),
        },
        "best_after": after_best,
        "baseline_parent_note": (
            "If best trial knobs are identity multipliers, that is the unchanged "
            "parent/baseline — not a materially improved model."
        ),
        "champion_locked_holdout_report": holdout_report,
        "structural": structural,
        "validation_before_overall": validation["overall"],
        "champion_protected": True,
        "policy_id": policy.get("policy_id"),
        "locked_winter_holdout": (before.get("chronological_periods") or {}).get(
            "locked_winter_holdout"
        ),
        "annual_summer_generalization": (before.get("chronological_periods") or {}).get(
            "annual_summer_generalization"
        ),
        "operational_dsm_readiness": "NO-GO",
        "written_utc": _utc(),
    }
    (camp / "summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (camp / "structural_verdict.json").write_text(
        json.dumps(structural, indent=2) + "\n", encoding="utf-8"
    )

    mirror = _APP / "archive" / "ml" / "artifacts" / "eplus_campaigns"
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
