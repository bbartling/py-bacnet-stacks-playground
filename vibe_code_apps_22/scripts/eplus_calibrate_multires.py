#!/usr/bin/env python
"""Versioned multi-resolution EnergyPlus calibration campaign runner (stages A–C).

Writes only under ``eplus/campaigns/<run_id>/`` — never overwrites staged champion.
Heavy EnergyPlus sims are optional (``--run-eplus``); default path scores the
current repaired sim + runs residual diagnostics + bounded sensitivity ledger.

Chronological blocked validation: do not peek final holdout during tuning.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
for p in (_APP, _ML, _APP / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from lakeside.paths import site_root  # noqa: E402
from eplus_multires_metrics import (  # noqa: E402
    build_validation_document,
    gl14_distance,
    resolution_block,
)
# Diagnostics (matplotlib) imported lazily in main() so unit tests can import
# ranking helpers without CI matplotlib.
from eplus_native.align import (  # noqa: E402
    aggregate_5min_to_15min_mean,
    aggregate_5min_to_hourly_mean,
    parse_eplus_csv_timestamp,
)
from eplus_native.extract import load_timestep_proxy_kw  # noqa: E402
from eplus_native.hashes import sha256_file  # noqa: E402

REGISTRY = _APP / "contracts" / "eplus_calib_param_registry_v1.json"
POLICY = _APP / "contracts" / "eplus_dsm_acceptance_policy_v1.json"


def _run_id() -> str:
    return datetime.now(timezone.utc).strftime("multires_%Y%m%dT%H%M%SZ")


def _load_registry() -> dict[str, Any]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _load_aligned(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    meas = pd.read_csv(root / "utilities" / "demand_interval_kw.csv")
    hourly_m = aggregate_5min_to_hourly_mean(meas, ts_col="timestamp_utc", kw_col="kw_demand")
    q15_m = aggregate_5min_to_15min_mean(meas, ts_col="timestamp_utc", kw_col="kw_demand")
    sim = root / "eplus" / "dsm_native" / "runs" / "dsm_repair_v1_full" / "sim"
    ts = load_timestep_proxy_kw(sim, interval_hours=0.25)
    rows = []
    for _, r in ts.iterrows():
        stamp = str(r["eplus_stamp"])
        month = int(stamp.split("/")[0]) if "/" in stamp else 1
        year = 2025 if month >= 8 else 2026
        dt = parse_eplus_csv_timestamp(stamp, year_hint=year)
        if dt is None:
            continue
        rows.append(
            {
                "timestamp_utc": dt.astimezone(__import__("datetime").timezone.utc),
                "kw_mod": float(r["site_electric_proxy_kw"]),
            }
        )
    mod = pd.DataFrame(rows)
    mod["timestamp_utc"] = pd.to_datetime(mod["timestamp_utc"], utc=True)
    mod_h = (
        mod.set_index("timestamp_utc")["kw_mod"]
        .resample("1h", label="right", closed="right")
        .mean()
        .rename("kw_mod")
        .to_frame()
        .reset_index()
    )
    aligned = hourly_m.merge(mod_h, on="timestamp_utc", how="inner").rename(
        columns={"kw_mean": "kw_meas"}
    ).dropna()
    mod_15 = (
        mod.set_index("timestamp_utc")["kw_mod"]
        .resample("15min", label="right", closed="right")
        .mean()
        .rename("kw_mod")
        .to_frame()
        .reset_index()
    )
    aligned_15 = q15_m.merge(mod_15, on="timestamp_utc", how="inner").rename(
        columns={"kw_mean": "kw_meas"}
    ).dropna()
    return aligned, aligned_15


def _monthly_block(root: Path) -> dict[str, Any] | None:
    elig = root / "eplus" / "models" / "staged" / "DSM_ELIGIBLE.json"
    sc = root / "eplus" / "dsm_native" / "phase1" / "scorecard_after_dsm_v1.json"
    if sc.is_file():
        g = json.loads(sc.read_text(encoding="utf-8")).get("gl14") or {}
        block = {
            "resolution": "monthly",
            "status": "pass",
            "n": int(g.get("n") or 0),
            "p": 1,
            "nmbe_pct": g.get("nmbe_pct"),
            "cvrmse_pct": g.get("cvrmse_pct"),
            "mean_obs": g.get("mean_obs"),
            "gates": {"nmbe_abs_max_pct": 5.0, "cvrmse_max_pct": 15.0},
            "labeled_as_gl14": True,
            "partial_year_monthly": int(g.get("n") or 0) < 12,
            "formula": "scorecard",
            "distance_to_gate": None,
        }
        from eplus_multires_metrics import gate_monthly

        block["status"] = gate_monthly(block)
        block["distance_to_gate"] = gl14_distance(block)
        return block
    if elig.is_file():
        e = json.loads(elig.read_text(encoding="utf-8"))
        return {
            "resolution": "monthly",
            "status": e.get("gl14_status") or "fail",
            "n": 11,
            "p": 1,
            "nmbe_pct": e.get("nmbe_pct"),
            "cvrmse_pct": e.get("cvrmse_pct"),
            "labeled_as_gl14": True,
            "partial_year_monthly": True,
            "gates": {"nmbe_abs_max_pct": 5.0, "cvrmse_max_pct": 15.0},
        }
    return None


def _sensitivity_screen(registry: dict[str, Any], stage: str) -> list[dict[str, Any]]:
    """Bounded one-at-a-time screen (no E+): records planned trials + bounds only."""
    trials = []
    for p in registry.get("parameters", []):
        if p.get("stage") != stage:
            continue
        lo, hi = p["bounds"]
        mid = (float(lo) + float(hi)) / 2.0
        for label, val in (("lo", lo), ("mid", mid), ("hi", hi)):
            trials.append(
                {
                    "param_id": p["id"],
                    "category": p["category"],
                    "stage": stage,
                    "value": val,
                    "bound_label": label,
                    "approval_required": p.get("approval_required", False),
                    "status": "planned",
                    "note": "Sensitivity screen — run with --run-eplus to execute",
                }
            )
    return trials


def _rank_candidate(monthly: dict | None, hourly: dict | None) -> dict[str, Any]:
    monthly_ok = (monthly or {}).get("status") == "pass"
    hourly_dist = (
        gl14_distance(
            hourly or {},
            nmbe_abs_max=10.0,
            cvrmse_max=30.0,
        )
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["A", "B", "C", "all"], default="all")
    ap.add_argument("--run-id", default=None)
    ap.add_argument(
        "--run-eplus",
        action="store_true",
        help="Execute EnergyPlus trials (default: diagnostics + planned sensitivity only)",
    )
    args = ap.parse_args(argv)

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
    diag_dir = camp / "diagnostics"
    ledger_path = camp / "ledger.jsonl"

    # Input hashes for cache key
    idf = Path(
        json.loads((root / "eplus" / "models" / "staged" / "DSM_ELIGIBLE.json").read_text()).get(
            "staged_idf", ""
        )
    )
    epw = root / "eplus" / "weather" / "madison_amy_202508_202607.epw"
    input_hash = hashlib.sha256()
    if idf.is_file():
        input_hash.update(sha256_file(idf).encode())
    if epw.is_file():
        input_hash.update(sha256_file(epw).encode())
    cache_key = input_hash.hexdigest()[:16]

    aligned, aligned_15 = _load_aligned(root)
    aligned.to_csv(camp / "aligned_hourly.csv", index=False)
    aligned_15.to_csv(camp / "aligned_15min.csv", index=False)

    from eplus_calib_diagnostics import write_diagnostic_suite

    diag_manifest = write_diagnostic_suite(aligned, diag_dir, aligned_15=aligned_15)

    monthly = _monthly_block(root)
    hourly = resolution_block(aligned["kw_meas"], aligned["kw_mod"], resolution="hourly")
    q15 = resolution_block(aligned_15["kw_meas"], aligned_15["kw_mod"], resolution="15min")
    validation = build_validation_document(
        monthly=monthly,
        hourly=hourly,
        q15=q15,
        physics_label=registry.get("physics"),
        idf_sha256=sha256_file(idf).upper() if idf.is_file() else None,
        epw_sha256=sha256_file(epw).upper() if epw.is_file() else None,
    )
    (camp / "validation.json").write_text(
        json.dumps(validation, indent=2, default=str) + "\n", encoding="utf-8"
    )

    stages = ["A", "B", "C"] if args.stage == "all" else [args.stage]
    all_trials: list[dict[str, Any]] = []
    for st in stages:
        trials = _sensitivity_screen(registry, st)
        all_trials.extend(trials)
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
            "stage": st,
            "cache_key": cache_key,
            "event": "sensitivity_screen_planned",
            "n_trials": len(trials),
            "run_eplus": bool(args.run_eplus),
            "ranking": _rank_candidate(monthly, hourly),
            "before_metrics": {
                "monthly": monthly,
                "hourly": {
                    "nmbe_pct": hourly.get("nmbe_pct"),
                    "cvrmse_pct": hourly.get("cvrmse_pct"),
                    "status": hourly.get("status"),
                },
            },
        }
        with ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
        (camp / f"stage_{st}_trials.json").write_text(
            json.dumps(trials, indent=2) + "\n", encoding="utf-8"
        )
        if args.run_eplus:
            # Explicit: do not silently overwrite champion; trials go under camp/trials/
            (camp / "trials").mkdir(exist_ok=True)
            (camp / "trials" / f"stage_{st}_NOTE.txt").write_text(
                "E+ execution hook reserved. Apply knobs via eplus_campaign.apply_knobs "
                "into camp/trials/<trial_id>/ only. Staged DSM_ELIGIBLE is immutable here.\n",
                encoding="utf-8",
            )

    summary = {
        "run_id": run_id,
        "cache_key": cache_key,
        "stages": stages,
        "n_planned_trials": len(all_trials),
        "diagnostics": diag_manifest.get("questions"),
        "validation_overall": validation["overall"],
        "ranking": _rank_candidate(monthly, hourly),
        "champion_protected": True,
        "policy_id": policy.get("policy_id"),
        "holdout_policy": "do_not_peek_final_holdout_during_tuning",
        "campaign_dir": str(camp),
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8")
    # Repo-side mirror for notebooks (small JSON only)
    mirror = _APP / "ml" / "artifacts" / "eplus_campaigns"
    mirror.mkdir(parents=True, exist_ok=True)
    (mirror / "latest_summary.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
    )

    print(json.dumps(summary, indent=2, default=str))
    if not validation["overall"]["hourly_pass"]:
        print(
            "NOTE: hourly gate failed — Wave 3 IdealLoads structural checkpoint required "
            "before further IDF search or farm promote.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
