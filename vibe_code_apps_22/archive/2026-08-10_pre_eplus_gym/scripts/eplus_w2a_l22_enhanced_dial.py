#!/usr/bin/env python3
"""Enhanced L22 dial: plugs/lights + plant bump, keep cold setback + opt-start.

Phase A: ≥10 unique trials around L22 with equip/lights/capacity/COP.
Phase B: if any dual improves peak ≥5 kW over L22 (or enters 275–290 with GL14),
         continue up to 20 total. If peak≈285 but monthly GL14 fails, try
         reduced equip_w_area_mult (runtime/gain lever) while holding opt-start.

Overnight gate uses winter observed summary stats (aligned 15-min): prefer
overnight 0–4 mean ≤ OVERNIGHT_MAX_KW (~p90 winter observed + buffer).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_native.runner import run_energyplus  # noqa: E402
from eplus_native.w2a_monthly_hold import monthly_gl14_style_pass  # noqa: E402
from eplus_native.w2a_plant_knobs import W2APlantKnobs, apply_w2a_plant_knobs  # noqa: E402
from eplus_validation_contract import (  # noqa: E402
    build_hourly_and_15min,
    utility_monthly_from_trial_sim,
)

PEAK_DESIGN_DAY = "2026-01-26"
PEAK_TARGET_KW = 285.0
L22_PEAK_KW = 260.98
L22_OVERNIGHT_KW = 126.4
# Winter overnight observed mean ~68, p90 ~106; L22 sits ~126. Cap worse baseload.
OVERNIGHT_MAX_KW = 140.0

# L22 anchor
_L22 = dict(
    htg_coil_capacity_mult=1.45,
    htg_coil_cop_mult=1.24,
    setback_heat_sp_c=7.78,
    optimum_start_h=3.5,
)


def _k(**overrides: Any) -> W2APlantKnobs:
    d = dict(_L22)
    d.update(overrides)
    return W2APlantKnobs(**d)


# Phase A: 10 enhanced trials (plugs/lights + plant). Always keep opt-start > 0.
PHASE_A: list[tuple[str, W2APlantKnobs]] = [
    ("E01_eq125_li110", _k(equip_w_area_mult=1.25, lights_w_area_mult=1.10)),
    ("E02_eq140_li115", _k(equip_w_area_mult=1.40, lights_w_area_mult=1.15)),
    (
        "E03_cap155_eq150_li120",
        _k(
            htg_coil_capacity_mult=1.55,
            equip_w_area_mult=1.50,
            lights_w_area_mult=1.20,
        ),
    ),
    (
        "E04_cap155_cop118_eq135_li115",
        _k(
            htg_coil_capacity_mult=1.55,
            htg_coil_cop_mult=1.18,
            equip_w_area_mult=1.35,
            lights_w_area_mult=1.15,
        ),
    ),
    (
        "E05_cap160_cop120_eq140_opt40",
        _k(
            htg_coil_capacity_mult=1.60,
            htg_coil_cop_mult=1.20,
            equip_w_area_mult=1.40,
            lights_w_area_mult=1.10,
            optimum_start_h=4.0,
        ),
    ),
    (
        "E06_cap150_cop115_eq130_li120_opt40",
        _k(
            htg_coil_capacity_mult=1.50,
            htg_coil_cop_mult=1.15,
            equip_w_area_mult=1.30,
            lights_w_area_mult=1.20,
            optimum_start_h=4.0,
        ),
    ),
    (
        "E07_cap165_cop122_eq145_li115",
        _k(
            htg_coil_capacity_mult=1.65,
            htg_coil_cop_mult=1.22,
            equip_w_area_mult=1.45,
            lights_w_area_mult=1.15,
        ),
    ),
    (
        "E08_cap155_cop128_eq120_li125",
        _k(
            htg_coil_capacity_mult=1.55,
            htg_coil_cop_mult=1.28,
            equip_w_area_mult=1.20,
            lights_w_area_mult=1.25,
        ),
    ),
    (
        "E09_cap150_cop130_eq155_opt40",
        _k(
            htg_coil_capacity_mult=1.50,
            htg_coil_cop_mult=1.30,
            equip_w_area_mult=1.55,
            lights_w_area_mult=1.10,
            optimum_start_h=4.0,
        ),
    ),
    (
        "E10_cap170_cop120_eq135_li115",
        _k(
            htg_coil_capacity_mult=1.70,
            htg_coil_cop_mult=1.20,
            equip_w_area_mult=1.35,
            lights_w_area_mult=1.15,
        ),
    ),
]

# Phase B dual-hunt (only used if Phase A shows progress)
PHASE_B_DUAL: list[tuple[str, W2APlantKnobs]] = [
    (
        "E11_cap175_cop118_eq140_li110_opt40",
        _k(
            htg_coil_capacity_mult=1.75,
            htg_coil_cop_mult=1.18,
            equip_w_area_mult=1.40,
            lights_w_area_mult=1.10,
            optimum_start_h=4.0,
        ),
    ),
    (
        "E12_cap165_cop125_eq130_li120_opt45",
        _k(
            htg_coil_capacity_mult=1.65,
            htg_coil_cop_mult=1.25,
            equip_w_area_mult=1.30,
            lights_w_area_mult=1.20,
            optimum_start_h=4.5,
        ),
    ),
    (
        "E13_cap180_cop122_eq125_li115",
        _k(
            htg_coil_capacity_mult=1.80,
            htg_coil_cop_mult=1.22,
            equip_w_area_mult=1.25,
            lights_w_area_mult=1.15,
        ),
    ),
    (
        "E14_cap160_cop112_eq145_li120_opt40",
        _k(
            htg_coil_capacity_mult=1.60,
            htg_coil_cop_mult=1.12,
            equip_w_area_mult=1.45,
            lights_w_area_mult=1.20,
            optimum_start_h=4.0,
        ),
    ),
    (
        "E15_cap170_cop128_eq110_li130",
        _k(
            htg_coil_capacity_mult=1.70,
            htg_coil_cop_mult=1.28,
            equip_w_area_mult=1.10,
            lights_w_area_mult=1.30,
        ),
    ),
]

# Phase B recovery: peak near 285 but GL14 fail → cut plug gains (equip "runtime")
# Phase C: neighborhood of E20 (GL14 + ~271 kW) — push peak toward 285.
PHASE_C_E20: list[tuple[str, W2APlantKnobs]] = [
    (
        "E21_cap175_cop115_eq075_li110",
        _k(
            htg_coil_capacity_mult=1.75,
            htg_coil_cop_mult=1.15,
            equip_w_area_mult=0.75,
            lights_w_area_mult=1.10,
            optimum_start_h=3.5,
        ),
    ),
    (
        "E22_cap180_cop118_eq070_li115_opt40",
        _k(
            htg_coil_capacity_mult=1.80,
            htg_coil_cop_mult=1.18,
            equip_w_area_mult=0.70,
            lights_w_area_mult=1.15,
            optimum_start_h=4.0,
        ),
    ),
    (
        "E23_cap170_cop110_eq070_li110",
        _k(
            htg_coil_capacity_mult=1.70,
            htg_coil_cop_mult=1.10,
            equip_w_area_mult=0.70,
            lights_w_area_mult=1.10,
            optimum_start_h=3.5,
        ),
    ),
    (
        "E24_cap185_cop120_eq080_li105",
        _k(
            htg_coil_capacity_mult=1.85,
            htg_coil_cop_mult=1.20,
            equip_w_area_mult=0.80,
            lights_w_area_mult=1.05,
            optimum_start_h=3.5,
        ),
    ),
    (
        "E25_cap175_cop122_eq065_li115_opt40",
        _k(
            htg_coil_capacity_mult=1.75,
            htg_coil_cop_mult=1.22,
            equip_w_area_mult=0.65,
            lights_w_area_mult=1.15,
            optimum_start_h=4.0,
        ),
    ),
]

PHASE_B_EQUIP_CUT: list[tuple[str, W2APlantKnobs]] = [
    (
        "E16_peakplant_eq090_li110",
        _k(
            htg_coil_capacity_mult=1.70,
            htg_coil_cop_mult=1.10,
            equip_w_area_mult=0.90,
            lights_w_area_mult=1.10,
            optimum_start_h=4.0,
        ),
    ),
    (
        "E17_peakplant_eq080_li105",
        _k(
            htg_coil_capacity_mult=1.75,
            htg_coil_cop_mult=1.08,
            equip_w_area_mult=0.80,
            lights_w_area_mult=1.05,
            optimum_start_h=4.0,
        ),
    ),
    (
        "E18_peakplant_eq070_li100",
        _k(
            htg_coil_capacity_mult=1.80,
            htg_coil_cop_mult=1.05,
            equip_w_area_mult=0.70,
            lights_w_area_mult=1.00,
            optimum_start_h=4.5,
        ),
    ),
    (
        "E19_peakplant_eq085_li120_cop115",
        _k(
            htg_coil_capacity_mult=1.65,
            htg_coil_cop_mult=1.15,
            equip_w_area_mult=0.85,
            lights_w_area_mult=1.20,
            optimum_start_h=4.0,
        ),
    ),
    (
        "E20_peakplant_eq075_li110_cop120",
        _k(
            htg_coil_capacity_mult=1.70,
            htg_coil_cop_mult=1.20,
            equip_w_area_mult=0.75,
            lights_w_area_mult=1.10,
            optimum_start_h=3.5,
        ),
    ),
]


def _score_day(site: Path, sim_dir: Path) -> dict[str, Any]:
    packed = build_hourly_and_15min(site, sim_dir, heat_cop=3.5, cool_cop=4.5)
    f = packed["q15"].copy()
    f["interval_end_utc"] = pd.to_datetime(f["interval_end_utc"], utc=True)
    local = f["interval_end_utc"].dt.tz_convert("America/Chicago")
    f = f.assign(local=local, d=local.dt.strftime("%Y-%m-%d"), hod=local.dt.hour)
    d = f[f["d"] == PEAK_DESIGN_DAY]
    if d.empty:
        return {"jan26_peak_kw": None, "overnight_0_4_sim_kw": None, "overnight_0_4_obs_kw": None}
    peak = float(d["simulated_kw"].max())
    ov = d[d["hod"].between(0, 3)]
    return {
        "jan26_peak_kw": peak,
        "overnight_0_4_sim_kw": float(ov["simulated_kw"].mean()) if len(ov) else None,
        "overnight_0_4_obs_kw": float(ov["observed_kw"].mean()) if len(ov) else None,
        "jan26_obs_peak_kw": float(d["observed_kw"].max()),
    }


def _run_one(
    *,
    site: Path,
    camp: Path,
    base_text: str,
    epw: Path,
    tid: str,
    knobs: W2APlantKnobs,
) -> dict[str, Any]:
    if knobs.fan_avail_use_sch_hvac:
        raise SystemExit(f"banned knob fan_avail_use_sch_hvac on {tid}")
    if not knobs.optimum_start_h or knobs.optimum_start_h <= 0:
        raise SystemExit(f"{tid}: optimum_start_h required (>0)")

    tdir = camp / "trials" / tid
    tdir.mkdir(parents=True, exist_ok=True)
    existing = tdir / "trial_result.json"
    if existing.is_file():
        rec = json.loads(existing.read_text(encoding="utf-8"))
        print(f"SKIP {tid} ({rec.get('status')})", flush=True)
        return rec

    applied = apply_w2a_plant_knobs(base_text, knobs)
    trial_idf = tdir / "trial.idf"
    trial_idf.write_text(applied["text"], encoding="utf-8", newline="\n")
    rec: dict[str, Any] = {
        "trial_id": tid,
        "knobs": applied["knobs"],
        "expanded_idf_sha256": applied["expanded_idf_sha256"],
        "n_fields_changed": applied["n_fields_changed"],
        "status": "pending",
    }
    print(
        f"RUN {tid} sha={applied['expanded_idf_sha256'][:12]} fields={applied['n_fields_changed']}",
        flush=True,
    )
    man = run_energyplus(
        run_id=f"{camp.name}_{tid}",
        scenario_id=tid,
        idf_path=trial_idf,
        epw_path=epw,
        output_dir=tdir / "sim",
        require_zero_severe=False,
        allow_staged_idf=True,
    )
    rec["exit_code"] = man.exit_code
    rec["runtime_sec"] = man.runtime_sec
    if man.exit_code != 0 or not (tdir / "sim" / "eplusmtr.csv").is_file():
        rec["status"] = "failed_energyplus"
        existing.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        print(f"  FAILED exit={man.exit_code}", flush=True)
        return rec

    day = _score_day(site, tdir / "sim")
    util = utility_monthly_from_trial_sim(site, tdir / "sim")
    hold = monthly_gl14_style_pass(util if isinstance(util, dict) else {})
    rec.update(day)
    rec["nmbe_pct"] = hold.get("nmbe_pct")
    rec["cvrmse_pct"] = hold.get("cvrmse_pct")
    rec["gl14_pass"] = bool(hold.get("pass"))
    ov = rec.get("overnight_0_4_sim_kw")
    rec["overnight_ok"] = ov is not None and float(ov) <= OVERNIGHT_MAX_KW
    peak = rec.get("jan26_peak_kw")
    rec["peak_near_285"] = peak is not None and 275.0 <= float(peak) <= 295.0
    if rec["gl14_pass"] and rec["overnight_ok"]:
        rec["status"] = "ok_dual_candidate"
    elif rec["gl14_pass"]:
        rec["status"] = "ok_gl14_high_overnight"
    else:
        rec["status"] = "ok_gl14_fail"
    existing.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(
        f"  peak={peak} ov={ov} gl14={rec['gl14_pass']} "
        f"nmbe={rec['nmbe_pct']} cv={rec['cvrmse_pct']} overnight_ok={rec['overnight_ok']}",
        flush=True,
    )
    return rec


def _write_summary(camp: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    dual = [
        r
        for r in results
        if r.get("gl14_pass") and r.get("overnight_ok") and r.get("jan26_peak_kw") is not None
    ]
    dual.sort(key=lambda r: -float(r["jan26_peak_kw"]))
    best = dual[0] if dual else None
    improved = (
        best is not None
        and float(best["jan26_peak_kw"]) >= (L22_PEAK_KW + 5.0)
    )
    summary = {
        "campaign_id": camp.name,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "family": "W2A_l22_enhanced_plugs_lights",
        "l22_anchor_peak_kw": L22_PEAK_KW,
        "l22_anchor_overnight_kw": L22_OVERNIGHT_KW,
        "overnight_max_kw": OVERNIGHT_MAX_KW,
        "peak_target_kw": PEAK_TARGET_KW,
        "peak_design_day": PEAK_DESIGN_DAY,
        "n_trials": len(results),
        "gl14_passers": sum(1 for r in results if r.get("gl14_pass")),
        "dual_candidates": [r["trial_id"] for r in dual],
        "best_dual": (
            {
                "trial_id": best["trial_id"],
                "jan26_peak_kw": best["jan26_peak_kw"],
                "overnight_0_4_sim_kw": best["overnight_0_4_sim_kw"],
                "nmbe_pct": best["nmbe_pct"],
                "cvrmse_pct": best["cvrmse_pct"],
                "knobs": best.get("knobs"),
            }
            if best
            else None
        ),
        "improved_vs_l22": improved,
        "champion_recommendation": (
            best["trial_id"] if improved and best else "L22_cap145_cop124_sb46_opt35"
        ),
        "trials": [
            {
                "trial_id": r["trial_id"],
                "status": r.get("status"),
                "jan26_peak_kw": r.get("jan26_peak_kw"),
                "overnight_0_4_sim_kw": r.get("overnight_0_4_sim_kw"),
                "gl14_pass": r.get("gl14_pass"),
                "nmbe_pct": r.get("nmbe_pct"),
                "cvrmse_pct": r.get("cvrmse_pct"),
                "overnight_ok": r.get("overnight_ok"),
                "peak_near_285": r.get("peak_near_285"),
            }
            for r in results
        ],
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    mirror = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-l22-enhanced-dial-summary.json"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", default=None, help="Existing campaign folder name")
    ap.add_argument("--max-trials", type=int, default=20)
    ap.add_argument("--phase-a-only", action="store_true")
    ap.add_argument(
        "--phase-c-only",
        action="store_true",
        help="Only run E20-neighborhood Phase C (resume after E20 dual found)",
    )
    args = ap.parse_args(argv)

    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    if args.resume:
        camp = site / "eplus" / "campaigns" / args.resume
        if not camp.is_dir():
            raise SystemExit(f"campaign not found: {camp}")
    else:
        camp = (
            site
            / "eplus"
            / "campaigns"
            / f"w2a_l22_enhanced_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        )
        camp.mkdir(parents=True)

    base = (
        site
        / "eplus"
        / "campaigns"
        / "w2a_integrity_closure_20260808T161626Z"
        / "shared"
        / "expand"
        / "expanded.idf"
    )
    if not base.is_file():
        raise SystemExit(f"missing expanded base: {base}")
    base_text = base.read_text(encoding="utf-8", errors="replace")
    epw = site / "eplus" / "weather" / "madison_amy_202508_202607.epw"

    results: list[dict[str, Any]] = []
    print(f"CAMPAIGN {camp.name}", flush=True)

    def _ingest_existing() -> None:
        for p in sorted((camp / "trials").glob("*/trial_result.json")):
            results.append(json.loads(p.read_text(encoding="utf-8")))

    if args.phase_c_only or args.resume:
        _ingest_existing()
        # de-dupe by trial_id keeping last
        by_id = {r["trial_id"]: r for r in results}
        results = list(by_id.values())
        print(f"RESUME loaded {len(results)} trials", flush=True)

    if not args.phase_c_only:
        seen = {r["trial_id"] for r in results}
        for tid, knobs in PHASE_A:
            if tid in seen:
                continue
            if len(results) >= args.max_trials:
                break
            results.append(
                _run_one(site=site, camp=camp, base_text=base_text, epw=epw, tid=tid, knobs=knobs)
            )

        # Decide Phase B
        dual = [
            r
            for r in results
            if r.get("gl14_pass") and r.get("overnight_ok") and r.get("jan26_peak_kw") is not None
        ]
        dual.sort(key=lambda r: -float(r["jan26_peak_kw"]))
        best_peak = float(dual[0]["jan26_peak_kw"]) if dual else 0.0
        near_fail = [
            r
            for r in results
            if r.get("peak_near_285") and not r.get("gl14_pass")
        ]
        progress = best_peak >= (L22_PEAK_KW + 5.0) or any(
            r.get("gl14_pass") and r.get("peak_near_285") for r in results
        )

        if not args.phase_a_only and len(results) < args.max_trials:
            if progress:
                print(f"PHASE B dual-hunt (best_peak={best_peak:.1f})", flush=True)
                for tid, knobs in PHASE_B_DUAL:
                    if len(results) >= args.max_trials:
                        break
                    results.append(
                        _run_one(
                            site=site, camp=camp, base_text=base_text, epw=epw, tid=tid, knobs=knobs
                        )
                    )
            elif near_fail:
                print(
                    f"PHASE B equip-cut recovery (n_near285_fail={len(near_fail)})",
                    flush=True,
                )
                for tid, knobs in PHASE_B_EQUIP_CUT:
                    if len(results) >= args.max_trials:
                        break
                    results.append(
                        _run_one(
                            site=site, camp=camp, base_text=base_text, epw=epw, tid=tid, knobs=knobs
                        )
                    )
            else:
                print(
                    "No dual progress ≥5 kW over L22 and no ~285/GL14-fail — "
                    "stopping after Phase A; champion stays L22.",
                    flush=True,
                )

        # Re-check after B: if still have near-285 fails and room, run equip-cut
        results_by_id = {r["trial_id"]: r for r in results}
        if not args.phase_a_only and len(results) < args.max_trials:
            near_fail2 = [
                r
                for r in results
                if r.get("peak_near_285") and not r.get("gl14_pass")
            ]
            dual2 = [
                r
                for r in results
                if r.get("gl14_pass") and r.get("overnight_ok") and r.get("jan26_peak_kw") is not None
            ]
            dual_peak = max((float(r["jan26_peak_kw"]) for r in dual2), default=0.0)
            if near_fail2 and dual_peak < 275.0:
                print("PHASE B2 equip-cut after dual-hunt miss", flush=True)
                for tid, knobs in PHASE_B_EQUIP_CUT:
                    if tid in results_by_id:
                        continue
                    if len(results) >= args.max_trials:
                        break
                    rec = _run_one(
                        site=site, camp=camp, base_text=base_text, epw=epw, tid=tid, knobs=knobs
                    )
                    results.append(rec)
                    results_by_id[tid] = rec

    # Phase C: if we have a dual better than L22 but still short of 285, dial further
    dual_now = [
        r
        for r in results
        if r.get("gl14_pass") and r.get("overnight_ok") and r.get("jan26_peak_kw") is not None
    ]
    dual_peak_now = max((float(r["jan26_peak_kw"]) for r in dual_now), default=0.0)
    if (args.phase_c_only or dual_peak_now >= (L22_PEAK_KW + 5.0)) and dual_peak_now < 275.0:
        print(f"PHASE C E20-neighborhood (dual_peak={dual_peak_now:.1f})", flush=True)
        seen = {r["trial_id"] for r in results}
        # allow up to max_trials + len(PHASE_C) when explicitly phase-c
        cap = max(args.max_trials, len(results) + len(PHASE_C_E20))
        for tid, knobs in PHASE_C_E20:
            if tid in seen:
                continue
            if len(results) >= cap:
                break
            results.append(
                _run_one(site=site, camp=camp, base_text=base_text, epw=epw, tid=tid, knobs=knobs)
            )

    summary = _write_summary(camp, results)
    print(json.dumps({k: summary[k] for k in (
        "campaign_id",
        "n_trials",
        "gl14_passers",
        "dual_candidates",
        "best_dual",
        "improved_vs_l22",
        "champion_recommendation",
    )}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
