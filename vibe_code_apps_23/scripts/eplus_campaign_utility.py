#!/usr/bin/env python
"""GL14 calibration vs client utility bills (max 30 iters).

Uses native EnergyPlus 26.1 (same engine OpenStudio-MCP wraps). OpenStudio MCP
is not available inside Cursor (40-tool host cap); Docker Desktop was down at
authoring time — see vibe_code_apps_23 for the OS-MCP Docker bridge.

Observed series: reports/eplus/observed_monthly_utility.csv (2025-08..2026-05).
Seed: best IdealLoads IDF (or 9-zone seed). Caps at EPLUS_MAX_ITER (default 30).
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPLUS = ROOT / "eplus"
MODELS = EPLUS / "models"
RUNS = EPLUS / "runs"
LOG = EPLUS / "scorecards" / "campaign_log_utility.csv"
LEDGER = EPLUS / "assumptions" / "ledger.json"
SEED = MODELS / "creekside_6zone_gshp_best.idf"
if not SEED.is_file():
    SEED = MODELS / "creekside_6zone_gshp_v0.idf"
LATEST = MODELS / "creekside_6zone_gshp_latest.idf"
BEST = MODELS / "creekside_6zone_gshp_best_utility.idf"
BEST_SC = EPLUS / "scorecards" / "best_scorecard_utility.json"
AMY = EPLUS / "weather" / "madison_amy_202508_202607.epw"

os.environ.setdefault(
    "EPLUS_OBS_CSV",
    str(ROOT / "reports" / "eplus" / "observed_monthly_utility.csv"),
)

sys.path.insert(0, str(ROOT / "scripts"))
from eplus_campaign import apply_knobs, append_log as _unused, run_sim, update_ledger  # noqa: E402
from eplus_score_run import score_run  # noqa: E402


def iteration_plan() -> list[dict]:
    """≤30 utility-targeted steps from near-pass (interval G14) toward bill G14.

    Interval champion over-predicts bills (~NMBE −6%). Trim lights/equip/infil
    and/or raise heat COP proxy.
    """
    plan: list[dict] = []
    # 101 = rescore baseline knobs of iter 78 on utility obs (rebuild)
    steps = [
        (101, {"infil_mult": 1.2, "lights_mult": 0.9}, "util_I1.2_L0.9_rescore"),
        (102, {"infil_mult": 1.2, "lights_mult": 0.85}, "util_I1.2_L0.85"),
        (103, {"infil_mult": 1.2, "lights_mult": 0.8}, "util_I1.2_L0.8"),
        (104, {"infil_mult": 1.2, "lights_mult": 0.9, "equip_mult": 0.9}, "util_I1.2_L0.9_E0.9"),
        (105, {"infil_mult": 1.2, "lights_mult": 0.85, "equip_mult": 0.9}, "util_I1.2_L0.85_E0.9"),
        (106, {"infil_mult": 1.15, "lights_mult": 0.9}, "util_I1.15_L0.9"),
        (107, {"infil_mult": 1.1, "lights_mult": 0.9}, "util_I1.1_L0.9"),
        (108, {"infil_mult": 1.2, "lights_mult": 0.9, "heat_cop": 3.7}, "util_I1.2_L0.9_HC3.7"),
        (109, {"infil_mult": 1.2, "lights_mult": 0.85, "heat_cop": 3.7}, "util_I1.2_L0.85_HC3.7"),
        (110, {"infil_mult": 1.2, "lights_mult": 0.9, "heat_cop": 3.8}, "util_I1.2_L0.9_HC3.8"),
        (111, {"infil_mult": 1.2, "lights_mult": 0.85, "equip_mult": 0.85}, "util_I1.2_L0.85_E0.85"),
        (112, {"infil_mult": 1.1, "lights_mult": 0.85, "equip_mult": 0.9}, "util_I1.1_L0.85_E0.9"),
        (113, {"infil_mult": 1.2, "lights_mult": 0.88, "equip_mult": 0.92}, "util_I1.2_L0.88_E0.92"),
        (114, {"infil_mult": 1.05, "lights_mult": 0.9}, "util_I1.05_L0.9"),
        (115, {"infil_mult": 1.2, "lights_mult": 0.9, "cool_cop": 4.8, "heat_cop": 3.7}, "util_HC3.7_CC4.8"),
        (116, {"infil_mult": 1.15, "lights_mult": 0.85, "heat_cop": 3.6}, "util_I1.15_L0.85_HC3.6"),
        (117, {"infil_mult": 1.2, "lights_mult": 0.82, "equip_mult": 0.88}, "util_I1.2_L0.82_E0.88"),
        (118, {"infil_mult": 1.0, "lights_mult": 0.9}, "util_I1.0_L0.9"),
        (119, {"infil_mult": 1.2, "lights_mult": 0.9, "people_mult": 0.95}, "util_I1.2_L0.9_P0.95"),
        (120, {"infil_mult": 1.2, "lights_mult": 0.87, "equip_mult": 0.9, "heat_cop": 3.65}, "util_fine_trim"),
        (121, {"infil_mult": 1.18, "lights_mult": 0.86, "equip_mult": 0.9}, "util_I1.18_L0.86_E0.9"),
        (122, {"infil_mult": 1.2, "lights_mult": 0.84, "heat_cop": 3.75}, "util_I1.2_L0.84_HC3.75"),
        (123, {"infil_mult": 1.12, "lights_mult": 0.88, "equip_mult": 0.88, "heat_cop": 3.7}, "util_blend_a"),
        (124, {"infil_mult": 1.2, "lights_mult": 0.9, "window_shgc": 0.32}, "util_SHGC0.32"),
        (125, {"infil_mult": 1.25, "lights_mult": 0.85, "heat_cop": 3.8}, "util_I1.25_L0.85_HC3.8"),
        (126, {"infil_mult": 1.15, "lights_mult": 0.88, "equip_mult": 0.88, "heat_cop": 3.7}, "util_blend_b"),
        (127, {"infil_mult": 1.2, "lights_mult": 0.83, "equip_mult": 0.9}, "util_I1.2_L0.83_E0.9"),
        (128, {"infil_mult": 1.1, "lights_mult": 0.88, "heat_cop": 3.7}, "util_I1.1_L0.88_HC3.7"),
        (129, {"infil_mult": 1.2, "lights_mult": 0.9, "equip_mult": 0.85, "heat_cop": 3.7}, "util_confirm_a"),
        (130, {"infil_mult": 1.15, "lights_mult": 0.85, "equip_mult": 0.9, "heat_cop": 3.7}, "util_confirm_b"),
    ]
    for n, knobs, hyp in steps:
        plan.append({"iter": n, "weather": "amy", "knobs": knobs, "hypothesis": hyp})
    return plan


def append_log(row: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "iter", "hypothesis", "weather", "nmbe_pct", "cvrmse_pct",
        "gl14_status", "gl14_distance", "heat_cop", "cool_cop", "knobs_json", "obs_source",
    ]
    write_header = not LOG.is_file()
    with LOG.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if write_header:
            w.writeheader()
        w.writerow({k: row.get(k) for k in fields})


def main() -> int:
    max_iter = int(os.environ.get("EPLUS_MAX_ITER", "30"))
    start_iter = int(os.environ.get("EPLUS_START_ITER", "101"))
    # Cap plan to start_iter .. start_iter+max_iter-1 by count
    plan = [s for s in iteration_plan() if s["iter"] >= start_iter]
    plan = plan[:max_iter]

    if not SEED.is_file():
        print(f"missing seed {SEED}", file=sys.stderr)
        return 2
    if not AMY.is_file():
        print(f"missing AMY {AMY}", file=sys.stderr)
        return 2

    seed_text = SEED.read_text(encoding="utf-8")
    # Seed is already calibrated IDF — apply_knobs multiplies on top of baked values.
    # Prefer fresh seed geometry for multiplicative knobs:
    fresh = MODELS / "creekside_6zone_gshp_v0.idf"
    if fresh.is_file():
        seed_text = fresh.read_text(encoding="utf-8")
        print(f"using fresh seed {fresh.name} for multiplicative knobs", flush=True)

    passes = 0
    best_dist = float("inf")
    best_idf = None
    best_sc = None
    if BEST_SC.is_file():
        try:
            prev = json.loads(BEST_SC.read_text(encoding="utf-8"))
            d = prev.get("gl14_distance")
            if isinstance(d, (int, float)) and d == d:
                best_dist = float(d)
                print(f"holding prior utility best distance={best_dist}", flush=True)
        except Exception:
            pass

    print(
        f"utility GL14 campaign: {len(plan)} iters, obs={os.environ.get('EPLUS_OBS_CSV')}",
        flush=True,
    )

    for step in plan:
        n = step["iter"]
        print(f"\n=== UTIL ITER {n} {step['hypothesis']} ===", flush=True)
        knobs = dict(step["knobs"])
        led = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.is_file() else {
            "version": 1, "heat_cop_proxy": 3.5, "cool_cop_proxy": 4.5, "iterations": []
        }
        if "heat_cop" in knobs:
            led["heat_cop_proxy"] = knobs["heat_cop"]
        if "cool_cop" in knobs:
            led["cool_cop_proxy"] = knobs["cool_cop"]
        LEDGER.write_text(json.dumps(led, indent=2), encoding="utf-8")

        text = apply_knobs(seed_text, knobs)
        run_dir = RUNS / f"util_{n:03d}"
        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
        run_dir.mkdir(parents=True)
        idf_path = run_dir / "model.idf"
        idf_path.write_text(text, encoding="utf-8")
        LATEST.write_text(text, encoding="utf-8")

        sim_out = run_dir / "sim"
        ok = run_sim(idf_path, AMY, sim_out)
        if not ok:
            append_log({
                "iter": n, "hypothesis": step["hypothesis"], "weather": "amy",
                "nmbe_pct": "", "cvrmse_pct": "", "gl14_status": "sim_fail",
                "gl14_distance": "", "heat_cop": led.get("heat_cop_proxy"),
                "cool_cop": led.get("cool_cop_proxy"), "knobs_json": json.dumps(knobs),
                "obs_source": "utility_bill",
            })
            continue

        sc = score_run(sim_out, iter_id=f"util_{n:03d}")
        sc["obs_source"] = "utility_bill"
        (run_dir / "scorecard.json").write_text(json.dumps(sc, indent=2), encoding="utf-8")
        gl = sc.get("gl14") or {}
        append_log({
            "iter": n,
            "hypothesis": step["hypothesis"],
            "weather": "amy",
            "nmbe_pct": gl.get("nmbe_pct"),
            "cvrmse_pct": gl.get("cvrmse_pct"),
            "gl14_status": sc.get("gl14_status"),
            "gl14_distance": sc.get("gl14_distance"),
            "heat_cop": knobs.get("heat_cop", led.get("heat_cop_proxy", 3.5)),
            "cool_cop": knobs.get("cool_cop", led.get("cool_cop_proxy", 4.5)),
            "knobs_json": json.dumps(knobs),
            "obs_source": "utility_bill",
        })
        update_ledger({
            "iter": n,
            "hypothesis": step["hypothesis"],
            "knobs": knobs,
            "gl14_status": sc.get("gl14_status"),
            "gl14": gl,
            "obs_source": "utility_bill",
        })
        dist = sc.get("gl14_distance")
        print(
            f"util={n} status={sc.get('gl14_status')} "
            f"NMBE={gl.get('nmbe_pct')} CVRMSE={gl.get('cvrmse_pct')} dist={dist}",
            flush=True,
        )
        if isinstance(dist, (int, float)) and dist == dist:
            gl = sc.get("gl14") or {}
            nmbe_abs = abs(float(gl.get("nmbe_pct") or 999))
            better = dist < best_dist or (
                dist == best_dist and nmbe_abs < abs(float((best_sc or {}).get("gl14", {}).get("nmbe_pct") or 999))
            )
            if better:
                best_dist = float(dist)
                best_idf = text
                best_sc = sc
                BEST.write_text(text, encoding="utf-8")
                BEST_SC.write_text(json.dumps(sc, indent=2), encoding="utf-8")
        if sc.get("gl14_status") == "pass":
            passes += 1
            if passes >= 2:
                print("Early stop: 2 utility G14 confirmation passes", flush=True)
                break

    if best_idf:
        LATEST.write_text(best_idf, encoding="utf-8")
    if best_sc:
        BEST_SC.write_text(json.dumps(best_sc, indent=2), encoding="utf-8")
        print(json.dumps({"best": best_sc.get("iter"), "gl14": best_sc.get("gl14"),
                          "status": best_sc.get("gl14_status"), "log": str(LOG)}, indent=2))
    print(f"campaign log: {LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
