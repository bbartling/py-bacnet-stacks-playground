#!/usr/bin/env python3
"""Multiobjective provisional plant-proxy calibration (20–40 real E+ trials).

Calibrates plant/schedule knobs only on the repaired IdealLoads family.
DSM remains NO-GO. January prior IdealLoads results are historical audit only.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.provisional_plant import (  # noqa: E402
    HONESTY,
    PROVENANCE,
    PlantProxyKnobs,
    apply_plant_proxy,
    write_design_card,
)
from eplus_native.runner import energyplus_version, run_energyplus  # noqa: E402
from eplus_schedule_sanity_campaign import (  # noqa: E402
    _champion_idf,
    _epw,
    _score_trial,
    _site_root,
    structural_metrics,
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def space_filling_grid(n_target: int = 24) -> list[PlantProxyKnobs]:
    caps = [2.3, 2.5, 2.7, 2.9, 3.2]
    unocc = [62.0, 65.0, 68.0]
    oa = [0.75, 1.0]
    opt = [0.0, 1.0]
    fan = [0.8, 1.0, 1.2]
    combos = list(itertools.product(caps, unocc, oa, opt, fan))
    # space-fill: stride through product
    step = max(1, len(combos) // n_target)
    picked = [combos[i] for i in range(0, len(combos), step)][:n_target]
    return [
        PlantProxyKnobs(
            heating_capacity_mmbtu_h=c,
            unocc_heat_sp_f=u,
            oa_occupied_frac=o,
            optimum_start_hours=s,
            fan_proxy_mult=f,
        )
        for c, u, o, s, f in picked
    ]


def composite_score(metrics: dict[str, Any]) -> float:
    """Lower is better. Predeclared blend — not called GL14."""
    util = metrics.get("utility_monthly") or {}
    nmbe = util.get("nmbe_pct") if isinstance(util, dict) else None
    cv = util.get("cvrmse_pct") if isinstance(util, dict) else None
    hourly = metrics.get("hourly_score") or {}
    h_cv = hourly.get("cvrmse_pct")
    st = metrics.get("structural") or {}
    ratio = st.get("weekend_collapse_ratio_mod_over_meas")
    weekend_pen = abs(float(ratio) - 1.0) * 50.0 if ratio is not None else 100.0
    parts = [weekend_pen]
    if cv is not None:
        parts.append(abs(float(cv)))
    if nmbe is not None:
        parts.append(abs(float(nmbe)) * 2.0)
    if h_cv is not None:
        parts.append(min(float(h_cv), 200.0) * 0.25)
    return float(sum(parts))


def promotion_gates(metrics: dict[str, Any]) -> dict[str, Any]:
    util = metrics.get("utility_monthly") or {}
    nmbe = util.get("nmbe_pct") if isinstance(util, dict) else None
    cv = util.get("cvrmse_pct") if isinstance(util, dict) else None
    hourly = metrics.get("hourly_score") or {}
    h_cv = hourly.get("cvrmse_pct")
    st = metrics.get("structural") or {}
    ratio = st.get("weekend_collapse_ratio_mod_over_meas")
    util_ok = nmbe is not None and cv is not None and abs(float(nmbe)) < 5 and float(cv) < 15
    struct_ok = ratio is not None and 0.5 <= float(ratio) <= 1.8
    hourly_ok = h_cv is not None and float(h_cv) < 30  # aspirational; not GL14 claim
    return {
        "utility_partial_period_screen": bool(util_ok),
        "utility_screen_label": "partial-period utility screen (not pristine holdout)",
        "hourly_structure_ratio_ok": bool(struct_ok),
        "hourly_cvrmse_aspirational_ok": bool(hourly_ok),
        "hourly_not_called_gl14": True,
        "dsm_eligible": False,
        "raw_eplus_gates_pass": bool(util_ok and struct_ok and hourly_ok),
        "nmbe_pct": nmbe,
        "cvrmse_pct": cv,
        "hourly_cvrmse_pct": h_cv,
        "weekend_ratio": ratio,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-trials", type=int, default=24)
    ap.add_argument("--campaign-id", default=None)
    ap.add_argument("--smoke-only", action="store_true")
    args = ap.parse_args(argv)

    site = _site_root()
    write_design_card()
    cid = args.campaign_id or f"plant_proxy_calib_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    camp = site / "eplus" / "campaigns" / cid
    camp.mkdir(parents=True, exist_ok=True)
    parent = _champion_idf(site)
    epw = _epw(site)
    parent_text = parent.read_text(encoding="utf-8", errors="replace")

    knobs_list = space_filling_grid(3 if args.smoke_only else args.n_trials)
    results = []
    for i, knobs in enumerate(knobs_list):
        tid = f"P{i:02d}_cap{knobs.heating_capacity_mmbtu_h}_u{knobs.unocc_heat_sp_f}_oa{knobs.oa_occupied_frac}_os{knobs.optimum_start_hours}_f{knobs.fan_proxy_mult}"
        tid = tid.replace(".", "p")
        trial_dir = camp / "trials" / tid
        sim_dir = trial_dir / "sim"
        trial_dir.mkdir(parents=True, exist_ok=True)
        trial_idf = trial_dir / "trial.idf"
        trial_idf.write_text(apply_plant_proxy(parent_text, knobs), encoding="utf-8", newline="\n")
        print(f"RUN {tid}", flush=True)
        man = run_energyplus(
            run_id=f"{cid}_{tid}",
            scenario_id=tid,
            idf_path=trial_idf,
            epw_path=epw,
            output_dir=sim_dir,
            require_zero_severe=False,
            allow_staged_idf=True,
        )
        rec: dict[str, Any] = {
            "trial_id": tid,
            "knobs": knobs.to_dict(),
            "provenance": PROVENANCE,
            "idf_sha256": sha256_file(trial_idf),
            "energyplus": {
                "exit_code": man.exit_code,
                "accepted": man.accepted,
                "runtime_sec": man.runtime_sec,
                "severe_count": man.severe_count,
            },
            "status": "running",
        }
        if man.exit_code != 0 or not (sim_dir / "eplusmtr.csv").is_file():
            rec["status"] = "failed"
        else:
            try:
                metrics = _score_trial(site, sim_dir, heat_cop=3.5, cool_cop=4.5)
                rec["metrics"] = metrics
                rec["composite_score"] = composite_score(metrics)
                rec["gates"] = promotion_gates(metrics)
                rec["status"] = "succeeded"
            except Exception as e:
                rec["status"] = "failed"
                rec["score_error"] = f"{type(e).__name__}: {e}"
        (trial_dir / "trial_result.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        results.append(rec)

    succeeded = [r for r in results if r.get("status") == "succeeded"]
    succeeded.sort(key=lambda r: r.get("composite_score", 1e9))
    best = succeeded[0] if succeeded else None
    any_raw = any((r.get("gates") or {}).get("raw_eplus_gates_pass") for r in succeeded)
    summary = {
        "campaign_id": cid,
        "created_utc": _utc(),
        "provenance": PROVENANCE,
        "honesty": HONESTY,
        "energyplus_version": energyplus_version(),
        "planned": len(knobs_list),
        "succeeded": len(succeeded),
        "failed": len(results) - len(succeeded),
        "best_trial_id": None if not best else best["trial_id"],
        "best_composite_score": None if not best else best.get("composite_score"),
        "best_gates": None if not best else best.get("gates"),
        "raw_eplus_gates_any_pass": any_raw,
        "dsm_status": "NO-GO",
        "audit": "READY" if any_raw else "NO-GO",
        "note": "January prior IdealLoads = historical audit only for this family",
        "trials": [
            {
                "trial_id": r["trial_id"],
                "status": r["status"],
                "composite_score": r.get("composite_score"),
                "gates": r.get("gates"),
                "knobs": r.get("knobs"),
            }
            for r in results
        ],
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    slim = {k: v for k, v in summary.items() if k != "trials"}
    slim["trial_status"] = {r["trial_id"]: r["status"] for r in results}
    slim["leaderboard_top5"] = [
        {"trial_id": r["trial_id"], "composite_score": r.get("composite_score"), "gates": r.get("gates")}
        for r in succeeded[:5]
    ]
    repo = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-plant-proxy-calib-summary.json"
    repo.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(slim, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
