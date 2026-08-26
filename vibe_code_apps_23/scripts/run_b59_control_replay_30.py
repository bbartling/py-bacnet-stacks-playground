#!/usr/bin/env python3
"""Run the Building 59 30-candidate CONTROL_REPLAY screening campaign.

Dial SAT setpoint, zone setpoints, OA minimum, and DX capacity/airflow toward
measured/published discrepancy evidence. Does not fix topology. Claim status is
always CONTROL_REPLAY_SCREENING_NOT_CALIBRATED.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from vibe23.b59_campaign_runner import run_b59_screening_campaign
from vibe23.b59_control_replay import (
    CLAIM_STATUS,
    CONTROL_REPLAY_BASE,
    MAX_CONTROL_REPLAY_RUNS,
    control_replay_candidates,
)
from vibe23.b59_model import build_b59_screening_seed_idf, screening_seed_summary


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _publish(
    *,
    results: list[dict[str, Any]],
    energyplus: Path,
    epw: Path,
    measured: Path,
    publish_dir: Path,
    champion_idf: Path,
) -> dict[str, Any]:
    results = sorted(results, key=lambda row: row["candidate"]["ordinal"])
    if len(results) != MAX_CONTROL_REPLAY_RUNS:
        raise RuntimeError(f"expected {MAX_CONTROL_REPLAY_RUNS} results; got {len(results)}")
    publish_dir.mkdir(parents=True, exist_ok=True)

    admitted = [row for row in results if row.get("admitted") and row.get("score")]
    if not admitted:
        raise RuntimeError("no admitted scored runs; cannot publish a champion")
    best = min(
        admitted,
        key=lambda row: (float(row["score"]["objective"]), int(row["candidate"]["ordinal"])),
    )
    best_params = next(
        c.parameters
        for c in control_replay_candidates()
        if c.run_id == best["candidate"]["run_id"]
    )

    champion_idf.parent.mkdir(parents=True, exist_ok=True)
    champion_idf.write_text(
        build_b59_screening_seed_idf(best_params, output_profile="lean"),
        encoding="utf-8",
    )
    champion_parameters = publish_dir / "champion_parameters.json"
    champion_parameters.write_text(
        json.dumps(asdict(best_params), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    monthly_rows = best["score"]["monthly_kwh"]
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
                "nmbe_pct": row["score"]["full_year_gl14"]["nmbe_pct"] if row.get("score") else None,
                "cvrmse_pct": row["score"]["full_year_gl14"]["cvrmse_pct"] if row.get("score") else None,
                "tuning_nmbe_pct": row["score"]["tuning_gl14"]["nmbe_pct"] if row.get("score") else None,
                "tuning_cvrmse_pct": row["score"]["tuning_gl14"]["cvrmse_pct"] if row.get("score") else None,
                "objective": row["score"]["objective"] if row.get("score") else None,
                "admitted": row["admitted"],
                "sat_setpoint_c": row["candidate"]["parameters"].get("supply_air_temperature_setpoint_c"),
                "idf_sha256": row["input_hashes"]["idf_sha256"],
                "epw_sha256": row["input_hashes"]["epw_sha256"],
            }
            for row in results
        ]
    ).to_csv(campaign_log, index=False)

    results_path = publish_dir / "campaign_results.jsonl"
    results_path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":"), default=str) + "\n" for row in results),
        encoding="utf-8",
    )

    version = subprocess.run(
        [str(energyplus), "--version"], capture_output=True, text=True, check=False
    )
    version_text = (version.stdout or version.stderr).strip()
    full = best["score"]["full_year_gl14"]
    baseline = next(row for row in results if row["candidate"]["run_id"] == "R01")
    summary = {
        "schema": "vibe23.b59_control_replay_30.v1",
        "claim_status": CLAIM_STATUS,
        "reason_not_claimable": [
            "topology still lacks UFT fans, hydronic reheat, and water-cooled plant",
            "TwoSpeedDX coil airflow cannot reach published 20,000 cfm without leaving the rated domain",
            "derived office subtotal is not a utility bill",
            "source-clock months vs EnergyPlus local-standard months remain unresolved",
            "this is a discrepancy-driven control/rating dial-in, not as-operated calibration",
        ],
        "published_run_count": len(results),
        "all_runs_admitted": all(row.get("admitted") for row in results),
        "selection_rule": "minimum January-September preregistered objective among admitted runs",
        "numeric_full_year_gl14_style_gate_met": bool(full["passes"]),
        "baseline_r01_full_year_gl14": baseline.get("score", {}).get("full_year_gl14"),
        "champion_run_id": best["candidate"]["run_id"],
        "champion_scores": best["score"],
        "base_parameters": asdict(CONTROL_REPLAY_BASE),
        "energyplus": {"version": version_text, "executable_name": energyplus.name},
        "inputs": {
            "epw": {"name": epw.name, "sha256": _sha256(epw)},
            "measured_monthly": {"name": measured.name, "sha256": _sha256(measured)},
        },
        "champion": {
            "idf": {"path": champion_idf.as_posix(), "sha256": _sha256(champion_idf)},
            "parameters": {"path": champion_parameters.name, "sha256": _sha256(champion_parameters)},
            "seed_summary": screening_seed_summary(best_params),
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--energyplus", type=Path, required=True)
    parser.add_argument("--epw", type=Path, required=True)
    parser.add_argument(
        "--measured-monthly",
        type=Path,
        default=Path("scorecards/b59_2020_screening/source_targets/b59_2020_monthly_records.csv"),
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("campaigns/runs/b59_2020_control_replay_30"),
    )
    parser.add_argument(
        "--publish-dir",
        type=Path,
        default=Path("scorecards/b59_2020_control_replay_30"),
    )
    parser.add_argument(
        "--champion-idf",
        type=Path,
        default=Path("model/b59_control_replay_champion.generated.idf"),
    )
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    candidates = control_replay_candidates()
    print(f"CONTROL_REPLAY: {len(candidates)} candidates | claim={CLAIM_STATUS}")
    results = run_b59_screening_campaign(
        energyplus_executable=args.energyplus,
        epw=args.epw,
        measured_monthly_csv=args.measured_monthly,
        output_root=args.run_root,
        max_workers=args.workers,
        candidates=candidates,
    )
    failed = [row for row in results if not row.get("admitted")]
    if failed:
        reasons = {row["candidate"]["run_id"]: row.get("reasons") for row in failed}
        raise SystemExit(f"fail-closed admission gate: {reasons}")

    summary = _publish(
        results=results,
        energyplus=args.energyplus,
        epw=args.epw,
        measured=args.measured_monthly,
        publish_dir=args.publish_dir,
        champion_idf=args.champion_idf,
    )
    print(json.dumps(
        {
            "claim_status": summary["claim_status"],
            "champion_run_id": summary["champion_run_id"],
            "full_year_gl14": summary["champion_scores"]["full_year_gl14"],
            "gate_met": summary["numeric_full_year_gl14_style_gate_met"],
            "publish_dir": str(args.publish_dir),
        },
        indent=2,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
