#!/usr/bin/env python
"""Phase 0–1: stage-repair utility champion, native run, GL14 re-score."""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from lakeside.paths import site_root  # noqa: E402
from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.idf_stage import stage_repair_idf  # noqa: E402
from eplus_native.runner import run_energyplus  # noqa: E402
from eplus_native import EXPECTED_EPW_SHA256, EXPECTED_IDF_SHA256  # noqa: E402

sys.path.insert(0, str(_APP / "scripts"))
from eplus_score_run import score_run  # noqa: E402


def main() -> int:
    os.environ.setdefault(
        "LAKESIDE_SITE_ROOT",
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
    )
    root = site_root()
    eplus = root / "eplus"
    champ = eplus / "models" / "lakeside_6zone_gshp_best_utility.idf"
    epw = eplus / "weather" / "madison_amy_202508_202607.epw"
    staged_dir = eplus / "models" / "staged"
    staged = staged_dir / "lakeside_6zone_gshp_best_utility_dsm_v1.idf"
    phase1 = eplus / "dsm_native" / "phase1"
    phase1.mkdir(parents=True, exist_ok=True)

    idf_h = sha256_file(champ)
    epw_h = sha256_file(epw)
    before = {
        "champion_idf": str(champ),
        "idf_sha256": idf_h,
        "idf_match": idf_h == EXPECTED_IDF_SHA256,
        "epw_sha256": epw_h,
        "epw_match": epw_h == EXPECTED_EPW_SHA256,
        "before_scorecard": str(eplus / "scorecards" / "best_scorecard_utility.json"),
    }
    (phase1 / "before_pins.json").write_text(json.dumps(before, indent=2) + "\n", encoding="utf-8")
    if not before["idf_match"] or not before["epw_match"]:
        print("HASH MISMATCH — abort", before, file=sys.stderr)
        return 2

    # Snapshot before scorecard
    sc_before = eplus / "scorecards" / "best_scorecard_utility.json"
    if sc_before.is_file():
        shutil.copy2(sc_before, phase1 / "scorecard_before_util_103.json")

    stage_repair_idf(champ, staged)
    print(f"staged repair → {staged} sha={sha256_file(staged)}", flush=True)

    run_dir = eplus / "dsm_native" / "runs" / "dsm_repair_v1_full"
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
    run_dir.mkdir(parents=True)
    shutil.copy2(staged, run_dir / "model.idf")

    os.environ.setdefault(
        "EPLUS_OBS_CSV",
        str(root / "reports" / "eplus" / "observed_monthly_utility.csv"),
    )

    manifest = run_energyplus(
        run_id="dsm_repair_v1_full",
        scenario_id="baseline_calibrated_schedule",
        idf_path=run_dir / "model.idf",
        epw_path=epw,
        output_dir=run_dir / "sim",
        require_zero_severe=True,
        allow_staged_idf=True,
    )
    print(
        json.dumps(
            {
                "accepted": manifest.accepted,
                "severe": manifest.severe_count,
                "fatal": manifest.fatal_count,
                "exit": manifest.exit_code,
                "reasons": manifest.reject_reasons,
                "runtime_sec": manifest.runtime_sec,
            },
            indent=2,
        ),
        flush=True,
    )
    if not manifest.accepted:
        # Still score for forensics but do not promote
        try:
            sc = score_run(run_dir / "sim")
            (phase1 / "scorecard_after_REJECTED.json").write_text(
                json.dumps(sc, indent=2) + "\n", encoding="utf-8"
            )
        except Exception as e:
            print(f"score_run failed: {e}", file=sys.stderr)
        (phase1 / "REPAIR_FAILED.txt").write_text(
            "\n".join(manifest.reject_reasons) + "\n", encoding="utf-8"
        )
        return 1

    sc = score_run(run_dir / "sim")
    sc["repair"] = {
        "staged_idf": str(staged),
        "staged_sha256": sha256_file(staged),
        "source_champion_sha256": idf_h,
        "changes": [
            "SCH_HtgSP/SCH_ClgSP: add SummerDesignDay/WinterDesignDay/AllOtherDays (fix 0C sizing)",
            "Building max warmup days 25→50",
            "Add Timestep meters/variables for DSM extraction",
            "Until:14:40→14:45 schedule alignment",
        ],
        "provenance_eligible": True,
        "run_manifest": str(run_dir / "run_manifest.json"),
    }
    (phase1 / "scorecard_after_dsm_v1.json").write_text(
        json.dumps(sc, indent=2) + "\n", encoding="utf-8"
    )
    # Do NOT overwrite best_utility.idf — write DSM-eligible pointer
    pointer = eplus / "models" / "staged" / "DSM_ELIGIBLE.json"
    pointer.write_text(
        json.dumps(
            {
                "staged_idf": str(staged),
                "staged_sha256": sha256_file(staged),
                "gl14_status": sc.get("gl14_status"),
                "nmbe_pct": sc.get("gl14", {}).get("nmbe_pct") if isinstance(sc.get("gl14"), dict) else sc.get("nmbe_pct"),
                "cvrmse_pct": sc.get("gl14", {}).get("cvrmse_pct") if isinstance(sc.get("gl14"), dict) else sc.get("cvrmse_pct"),
                "honesty": "Ideal Loads + fixed-COP proxy; zero severe native run",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("PHASE1 OK", pointer, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
