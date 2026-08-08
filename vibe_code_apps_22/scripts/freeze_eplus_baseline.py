#!/usr/bin/env python
"""P0: Freeze immutable multi-resolution baseline before any model changes.

Writes machine-readable report under site reports/eplus/baseline/ and a repo
mirror under ml/artifacts/eplus_baseline/ (JSON only).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
for p in (_APP, _ML, _APP / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lakeside.paths import site_root  # noqa: E402
from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_multires_metrics import cross_correlation_lags  # noqa: E402
from eplus_validation_contract import (  # noqa: E402
    build_hourly_and_15min,
    chronological_splits,
    interval_monthly_from_aligned_hourly,
    score_aligned,
    utility_monthly_from_trial_sim,
)


def _git_sha() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=_APP.parent,
                text=True,
            ).strip()
        )
    except Exception as e:
        return f"unknown:{e}"


def main() -> int:
    os.environ.setdefault(
        "LAKESIDE_SITE_ROOT",
        r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside",
    )
    root = site_root()
    sim = root / "eplus" / "dsm_native" / "runs" / "dsm_repair_v1_full" / "sim"
    ptr = root / "eplus" / "models" / "staged" / "DSM_ELIGIBLE.json"
    elig = json.loads(ptr.read_text(encoding="utf-8")) if ptr.is_file() else {}
    idf_path = Path(elig.get("staged_idf") or "")
    if not idf_path.is_file():
        idf_path = root / "eplus" / "models" / "staged" / "lakeside_6zone_gshp_best_utility_dsm_v1.idf"
    epw = root / "eplus" / "weather" / "madison_amy_202508_202607.epw"

    products = build_hourly_and_15min(root, sim)
    aligned_h = products["hourly"]
    aligned_15 = products["q15"]
    hourly = score_aligned(aligned_h, resolution="hourly")
    q15 = score_aligned(aligned_15, resolution="15min")
    util = utility_monthly_from_trial_sim(root, sim)
    interv = interval_monthly_from_aligned_hourly(aligned_h)
    periods = chronological_splits(aligned_h)
    xcorr = cross_correlation_lags(
        aligned_h["observed_kw"], aligned_h["simulated_kw"], max_lag=24
    )

    known_truth = {
        "note": "Immutable pre-change baseline — do not silently reinterpret",
        "interval_derived_monthly_screen_approx": {
            "nmbe_pct": 2.73,
            "cvrmse_pct": 11.60,
            "n": 11,
            "warning": "NOT utility bills",
        },
        "utility_bill_approx": {
            "nmbe_pct": -0.06,
            "cvrmse_pct": 11.44,
            "n": 10,
        },
        "hourly_approx": {
            "nmbe_pct": 3.11,
            "cvrmse_pct": 96.79,
            "rmse_kw": 63.8,
            "n": 8064,
        },
        "q15_approx": {"cvrmse_pct": 114.37, "rmse_kw": 75.4},
        "physics": "ZoneHVAC:IdealLoadsAirSystem + fixed-COP proxy; filename gshp is naming only",
    }

    report = {
        "schema": "eplus_immutable_baseline_v1",
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "git_sha": _git_sha(),
        "commands": [
            "python scripts/freeze_eplus_baseline.py",
            "python scripts/validate_eplus_multires.py --plots",
        ],
        "paths": {
            "site_root": str(root.resolve()),
            "sim_dir": str(sim.resolve()),
            "idf": str(idf_path.resolve()) if idf_path.is_file() else None,
            "epw": str(epw.resolve()) if epw.is_file() else None,
            "measured_interval": str(
                (root / "utilities" / "demand_interval_kw.csv").resolve()
            ),
        },
        "hashes": {
            "idf_sha256": sha256_file(idf_path).upper() if idf_path.is_file() else None,
            "epw_sha256": sha256_file(epw).upper() if epw.is_file() else None,
            "measured_interval_sha256": sha256_file(
                root / "utilities" / "demand_interval_kw.csv"
            ).upper(),
            "elig_staged_sha256": elig.get("staged_sha256"),
        },
        "timestamp_convention": {
            "measured": "interval_end UTC",
            "energyplus": "interval_end LST fixed CST-6 → UTC (no civil DST on E+ stamps)",
            "design_day_filter": "keep_last_per_eplus_stamp",
        },
        "coverage": {
            "hourly_n": int(len(aligned_h)),
            "hourly_start": str(aligned_h["interval_end_utc"].min()),
            "hourly_end": str(aligned_h["interval_end_utc"].max()),
            "q15_n": int(len(aligned_15)),
        },
        "products": {
            "A_utility_bill_monthly": util,
            "B_interval_meter_monthly": interv,
            "C_interval_hourly": hourly,
            "D_interval_15min_dsm": q15,
        },
        "chronological_periods": periods,
        "cross_correlation": {
            "best_lag_h": xcorr.get("best_lag"),
            "best_corr": xcorr.get("best_corr"),
        },
        "known_truth_prior": known_truth,
        "operational_dsm_readiness": "NO-GO",
        "reasons": [
            "hourly CV(RMSE) far above calibrated-sim hourly screen (~30%)",
            "15-min DSM diagnostic likewise fails response fidelity",
            "IdealLoads + fixed-COP is not a GSHP plant model",
        ],
    }
    # Integrity fingerprint of product metrics
    blob = json.dumps(report["products"], sort_keys=True, default=str).encode()
    report["baseline_fingerprint_sha256"] = hashlib.sha256(blob).hexdigest()

    out_site = root / "reports" / "eplus" / "baseline"
    out_site.mkdir(parents=True, exist_ok=True)
    fp = report["baseline_fingerprint_sha256"][:16]
    stamped = out_site / f"immutable_baseline_v1_{fp}.json"
    path = out_site / "immutable_baseline_v1.json"
    # Never silently overwrite a different frozen baseline — write stamped + pointer
    if path.is_file():
        try:
            prev = json.loads(path.read_text(encoding="utf-8"))
            prev_fp = prev.get("baseline_fingerprint_sha256")
            if prev_fp and prev_fp != report["baseline_fingerprint_sha256"]:
                archive = out_site / f"immutable_baseline_superseded_{prev_fp[:16]}.json"
                if not archive.is_file():
                    archive.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
                report["supersedes_fingerprint"] = prev_fp
                report["immutability_note"] = (
                    "Prior baseline archived; this file is a new freeze pointer, "
                    "not an in-place silent rewrite of the same scientific record."
                )
        except Exception:
            pass
    stamped.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    path.write_text(stamped.read_text(encoding="utf-8"), encoding="utf-8")

    mirror = _ML / "artifacts" / "eplus_baseline"
    mirror.mkdir(parents=True, exist_ok=True)
    (mirror / "immutable_baseline_v1.json").write_text(
        path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (mirror / stamped.name).write_text(stamped.read_text(encoding="utf-8"), encoding="utf-8")

    print(json.dumps({
        "wrote": str(path),
        "git_sha": report["git_sha"],
        "fingerprint": report["baseline_fingerprint_sha256"],
        "hourly_cvrmse": hourly.get("cvrmse_pct"),
        "hourly_rmse_kw": hourly.get("rmse_kw"),
        "utility_n": (util or {}).get("n"),
        "interval_monthly_n": (interv or {}).get("n"),
        "operational": "NO-GO",
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
