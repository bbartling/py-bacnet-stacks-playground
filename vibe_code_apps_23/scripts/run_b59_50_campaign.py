#!/usr/bin/env python3
"""Execute the preregistered adaptive 50-run Building 59 screening campaign.

The script selects incumbents using January--September only and publishes
October--December as a reserved diagnostic slice. The v1 implementation
computes that reserved slice for every candidate, so it is not blind and is not
a holdout. A numerical threshold pass remains a screening result because the
public telemetry and seed model have documented scope/time/topology gaps.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from vibe23.b59_campaign_runner import (
    MAX_B59_SCREENING_RUNS,
    B59CampaignCandidate,
    preregistered_candidates,
    run_b59_screening_campaign,
)
from vibe23.b59_model import build_b59_screening_seed_idf, screening_seed_summary


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _candidate_slice(
    start: int,
    stop: int,
    *,
    incumbent=None,
) -> tuple[B59CampaignCandidate, ...]:
    return tuple(
        candidate
        for candidate in preregistered_candidates(incumbent=incumbent)
        if start <= candidate.ordinal <= stop
    )


def _require_admitted(results: Iterable[dict[str, Any]], stage: str) -> None:
    failed = [row for row in results if not row.get("admitted")]
    if failed:
        reasons = {row["candidate"]["run_id"]: row.get("reasons", []) for row in failed}
        raise RuntimeError(f"{stage} stopped at the fail-closed admission gate: {reasons}")


def _best_tuning_result(results: Iterable[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        row
        for row in results
        if row.get("admitted") and not row["candidate"].get("holdout") and row.get("score")
    ]
    if not eligible:
        raise RuntimeError("no admitted tuning result is available for incumbent selection")
    return min(eligible, key=lambda row: (float(row["score"]["objective"]), row["candidate"]["ordinal"]))


def _run_stage(
    candidates: tuple[B59CampaignCandidate, ...],
    *,
    energyplus: Path,
    epw: Path,
    measured: Path,
    run_root: Path,
    workers: int,
) -> list[dict[str, Any]]:
    results = run_b59_screening_campaign(
        energyplus_executable=energyplus,
        epw=epw,
        measured_monthly_csv=measured,
        output_root=run_root,
        max_workers=workers,
        candidates=candidates,
    )
    _require_admitted(results, f"R{candidates[0].ordinal:02d}-R{candidates[-1].ordinal:02d}")
    return results


def _write_publication(
    *,
    results: list[dict[str, Any]],
    candidates: dict[str, B59CampaignCandidate],
    frozen_source: dict[str, Any],
    energyplus: Path,
    epw: Path,
    measured: Path,
    publish_dir: Path,
    champion_idf: Path,
) -> dict[str, Any]:
    results.sort(key=lambda row: row["candidate"]["ordinal"])
    if len(results) != MAX_B59_SCREENING_RUNS:
        raise RuntimeError(f"expected 50 completed results; got {len(results)}")
    publish_dir.mkdir(parents=True, exist_ok=True)
    champion = candidates[frozen_source["candidate"]["run_id"]]
    frozen_runs = [row for row in results if row["candidate"]["ordinal"] >= 47]
    frozen_best = min(frozen_runs, key=lambda row: row["candidate"]["ordinal"])
    champion_score = frozen_best["score"]

    champion_idf.parent.mkdir(parents=True, exist_ok=True)
    champion_idf.write_text(build_b59_screening_seed_idf(champion.parameters, output_profile="lean"), encoding="utf-8")
    champion_parameters = publish_dir / "champion_parameters.json"
    champion_parameters.write_text(
        json.dumps(asdict(champion.parameters), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    monthly_rows = champion_score["monthly_kwh"]
    monthly_csv = publish_dir / "champion_monthly_comparison.csv"
    pd.DataFrame(
        {
            "timestamp": [f"2020-{row['month']:02d}-01T00:00:00Z" for row in monthly_rows],
            "measured": [row["measured_kwh"] for row in monthly_rows],
            "simulated": [row["simulated_kwh"] for row in monthly_rows],
        }
    ).to_csv(monthly_csv, index=False)

    campaign_log = publish_dir / "campaign_log.csv"
    pd.DataFrame(
        [
            {
                "iteration": row["candidate"]["ordinal"],
                "run_id": row["candidate"]["run_id"],
                "stage": row["candidate"]["stage"],
                "parameter_family": "+".join(row["candidate"]["parameter_families"]),
                "nmbe_pct": row["score"]["full_year_gl14"]["nmbe_pct"],
                "cvrmse_pct": row["score"]["full_year_gl14"]["cvrmse_pct"],
                "tuning_nmbe_pct": row["score"]["tuning_gl14"]["nmbe_pct"],
                "tuning_cvrmse_pct": row["score"]["tuning_gl14"]["cvrmse_pct"],
                "holdout_nmbe_pct": row["score"]["holdout_gl14"]["nmbe_pct"],
                "holdout_cvrmse_pct": row["score"]["holdout_gl14"]["cvrmse_pct"],
                "complete_months": 12,
                "admitted": row["admitted"],
                "idf_sha256": row["input_hashes"]["idf_sha256"],
                "epw_sha256": row["input_hashes"]["epw_sha256"],
                "target_sha256": row["input_hashes"]["measured_monthly_sha256"],
            }
            for row in results
        ]
    ).to_csv(campaign_log, index=False)

    results_path = publish_dir / "campaign_results.jsonl"
    results_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in results),
        encoding="utf-8",
    )
    version = subprocess.run(
        [str(energyplus), "--version"], capture_output=True, text=True, check=False
    )
    version_text = (version.stdout or version.stderr).strip()
    full = champion_score["full_year_gl14"]
    summary = {
        "schema": "vibe23.b59_50_run_screening_campaign.v1",
        "claim_status": "SCREENING_ONLY_NOT_A_CALIBRATION_CLAIM",
        "reason_not_claimable": [
            "derived office subtotal is not a utility bill and includes unresolved panel loads",
            "source-clock monthly records are not yet reconciled to EnergyPlus local-standard time",
            "screening HVAC/geometry topology is not the reviewed as-built Building 59 model",
            "p=1 is a campaign diagnostic and is not a defensible count of all fitted degrees of freedom",
            "October-December metrics were stored for every run, so the reserved slice was not blind",
        ],
        "published_run_count": len(results),
        "all_runs_admitted_zero_warning": all(row["admitted"] and not row["reasons"] for row in results),
        "selection_rule": "minimum January-September preregistered objective; October-December not used by code",
        "validation_slice_blinding_status": (
            "NOT_BLIND_METRICS_WERE_COMPUTED_AND_STORED_FOR_EVERY_RUN; NO HOLDOUT CLAIM"
        ),
        "frozen_incumbent_source_run": frozen_source["candidate"]["run_id"],
        "frozen_evaluation_runs": [row["candidate"]["run_id"] for row in frozen_runs],
        "numeric_full_year_gl14_style_gate_met": bool(full["passes"]),
        "champion_scores": champion_score,
        "energyplus": {"version": version_text, "executable_name": energyplus.name},
        "inputs": {
            "epw": {"name": epw.name, "sha256": _sha256(epw)},
            "measured_monthly": {"name": measured.name, "sha256": _sha256(measured)},
        },
        "champion": {
            "idf": {"path": champion_idf.as_posix(), "sha256": _sha256(champion_idf)},
            "parameters": {"path": champion_parameters.name, "sha256": _sha256(champion_parameters)},
            "seed_summary": screening_seed_summary(champion.parameters),
        },
        "published_artifacts": {
            "monthly_comparison": {"path": monthly_csv.name, "sha256": _sha256(monthly_csv)},
            "campaign_log": {"path": campaign_log.name, "sha256": _sha256(campaign_log)},
            "campaign_results": {"path": results_path.name, "sha256": _sha256(results_path)},
        },
    }
    summary_path = publish_dir / "campaign_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--energyplus", type=Path, required=True)
    parser.add_argument("--epw", type=Path, required=True)
    parser.add_argument("--measured-monthly", type=Path, required=True)
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--publish-dir", type=Path, required=True)
    parser.add_argument("--champion-idf", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    all_results: list[dict[str, Any]] = []
    candidate_map: dict[str, B59CampaignCandidate] = {}

    first = _candidate_slice(1, 20)
    candidate_map.update({candidate.run_id: candidate for candidate in first})
    all_results.extend(
        _run_stage(
            first,
            energyplus=args.energyplus,
            epw=args.epw,
            measured=args.measured_monthly,
            run_root=args.run_root,
            workers=args.workers,
        )
    )
    incumbent = candidate_map[_best_tuning_result(all_results)["candidate"]["run_id"]].parameters

    second = _candidate_slice(21, 38, incumbent=incumbent)
    candidate_map.update({candidate.run_id: candidate for candidate in second})
    all_results.extend(
        _run_stage(
            second,
            energyplus=args.energyplus,
            epw=args.epw,
            measured=args.measured_monthly,
            run_root=args.run_root,
            workers=args.workers,
        )
    )
    incumbent = candidate_map[_best_tuning_result(all_results)["candidate"]["run_id"]].parameters

    third = _candidate_slice(39, 46, incumbent=incumbent)
    candidate_map.update({candidate.run_id: candidate for candidate in third})
    all_results.extend(
        _run_stage(
            third,
            energyplus=args.energyplus,
            epw=args.epw,
            measured=args.measured_monthly,
            run_root=args.run_root,
            workers=args.workers,
        )
    )
    frozen_source = _best_tuning_result(all_results)
    incumbent = candidate_map[frozen_source["candidate"]["run_id"]].parameters

    final = _candidate_slice(47, 50, incumbent=incumbent)
    candidate_map.update({candidate.run_id: candidate for candidate in final})
    all_results.extend(
        _run_stage(
            final,
            energyplus=args.energyplus,
            epw=args.epw,
            measured=args.measured_monthly,
            run_root=args.run_root,
            workers=args.workers,
        )
    )
    summary = _write_publication(
        results=all_results,
        candidates=candidate_map,
        frozen_source=frozen_source,
        energyplus=args.energyplus,
        epw=args.epw,
        measured=args.measured_monthly,
        publish_dir=args.publish_dir,
        champion_idf=args.champion_idf,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
