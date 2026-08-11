#!/usr/bin/env python3
"""W2A monthly-held hourly dial-in around creative best C02.

Hard-rejects trials that fail GL14-style partial-period utility (|NMBE|<5, CVRMSE<15).
Ranks monthly-passers by reserved Feb hourly CVRMSE. Bans fan→SCH_HVAC.

Supports --resume / --finalize-only so a stuck scoring pass can continue without
re-running finished EnergyPlus trials.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.runner import energyplus_version, run_energyplus  # noqa: E402
from eplus_native.w2a_monthly_hold import (  # noqa: E402
    C02_BASELINE_FEB_CVRMSE,
    early_stop_no_feb_gain,
    monthly_gl14_style_pass,
    rank_key_monthly_hold_hourly,
)
from eplus_native.w2a_plant_knobs import (  # noqa: E402
    W2APlantKnobs,
    apply_w2a_plant_knobs,
    detect_duplicate_models,
)
from eplus_w2a_plant_calib import _score_integrity  # noqa: E402

# C02 neighborhood — fan_avail_use_sch_hvac never True
DIAL_TRIALS: list[tuple[str, W2APlantKnobs]] = [
    ("H00_c02_ref", W2APlantKnobs(htg_coil_capacity_mult=0.45, setback_heat_sp_c=14.44)),
    ("H01_sb60_cap45", W2APlantKnobs(htg_coil_capacity_mult=0.45, setback_heat_sp_c=15.56)),
    ("H02_sb59_cap45", W2APlantKnobs(htg_coil_capacity_mult=0.45, setback_heat_sp_c=15.0)),
    ("H03_sb58_cap40", W2APlantKnobs(htg_coil_capacity_mult=0.40, setback_heat_sp_c=14.44)),
    ("H04_sb58_cap50", W2APlantKnobs(htg_coil_capacity_mult=0.50, setback_heat_sp_c=14.44)),
    ("H05_sb61_cap42", W2APlantKnobs(htg_coil_capacity_mult=0.42, setback_heat_sp_c=16.11)),
    (
        "H06_opt_sb58",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.45,
            setback_heat_sp_c=14.44,
            optimum_start_h=0.75,
        ),
    ),
    (
        "H07_oa_loop",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.45,
            setback_heat_sp_c=14.44,
            oa_shoulder_scale=0.6,
            loop_setpoint_c=30.0,
        ),
    ),
    (
        "H08_cop11_sb60",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.48,
            setback_heat_sp_c=15.56,
            htg_coil_cop_mult=1.1,
        ),
    ),
    (
        "H09_blend_peak",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.43,
            setback_heat_sp_c=15.0,
            optimum_start_h=0.5,
            oa_shoulder_scale=0.7,
            fan_delta_p_mult=0.85,
        ),
    ),
]


def _slim_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    st = metrics.get("structural") or {}
    util = metrics.get("utility_monthly") or {}
    res = metrics.get("reserved_final_winter_audit") or {}
    h = res.get("hourly_score") or {}
    peaks = res.get("day_level_peaks") or {}
    wk_mod = st.get("winter_weekend_kw_mod_mean")
    wk_meas = st.get("winter_weekend_kw_meas_mean")
    return {
        "selection_score": metrics.get("selection_score"),
        "weekend_ratio": st.get("weekend_collapse_ratio_mod_over_meas"),
        "weekend_kw_mod": wk_mod,
        "weekend_kw_meas": wk_meas,
        "weekend_abs_err": (
            abs(float(wk_mod) - float(wk_meas))
            if wk_mod is not None and wk_meas is not None
            else None
        ),
        "util_cvrmse_pct": util.get("cvrmse_pct") if isinstance(util, dict) else None,
        "util_nmbe_pct": util.get("nmbe_pct") if isinstance(util, dict) else None,
        "feb_cvrmse_pct": h.get("cvrmse_pct"),
        "feb_nmbe_pct": h.get("nmbe_pct"),
        "he05_09_mae_median": (peaks.get("morning_he05_09_mae_kw") or {}).get("median"),
        "peak_mag_mae_median": (peaks.get("abs_peak_magnitude_error_kw") or {}).get("median"),
        "unmet_sum": (metrics.get("unmet_heating") or {}).get("sum_zone_unmet_heating_hours"),
        "six_zone_status": (
            "ok"
            if any(str(k).startswith("zone_temp_") for k in (metrics.get("six_zone_metrics") or {}))
            else (metrics.get("six_zone_metrics") or {}).get("status")
        ),
    }


def _write_summary(camp: Path, results: list[dict[str, Any]], *, stopped_early: bool, stop_reason: str | None) -> dict[str, Any]:
    uniq = detect_duplicate_models(results)
    ranked = [r for r in results if r.get("ranked")]
    ranked.sort(key=rank_key_monthly_hold_hourly)
    any_raw = any((r.get("gates") or {}).get("raw_eplus_gates_pass") for r in ranked)
    best = None
    if ranked:
        b = ranked[0]
        best = {
            "trial_id": b["trial_id"],
            **(b.get("metrics") or {}),
            "monthly_hold": b.get("monthly_hold"),
            "raw_pass": (b.get("gates") or {}).get("raw_eplus_gates_pass"),
            "beats_c02_feb": (
                b.get("metrics", {}).get("feb_cvrmse_pct") is not None
                and float(b["metrics"]["feb_cvrmse_pct"]) <= C02_BASELINE_FEB_CVRMSE - 1.0
            ),
        }
    summary = {
        "campaign_id": camp.name,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "family": "W2A_C02_neighborhood_monthly_hold_hourly_dial",
        "c02_baseline_feb_cvrmse": C02_BASELINE_FEB_CVRMSE,
        "monthly_constraint": monthly_gl14_style_pass({"nmbe_pct": 0, "cvrmse_pct": 0})["label"],
        "attempted_runs": len(results),
        "unique_models": uniq["unique_models"],
        "uniqueness_ok": uniq["uniqueness_ok"],
        "monthly_passers": len(ranked),
        "monthly_rejects": sum(1 for r in results if r.get("status") == "rejected_monthly_hold_fail"),
        "failed_energyplus": sum(1 for r in results if r.get("status") == "failed_energyplus"),
        "stopped_early": stopped_early,
        "stop_reason": stop_reason,
        "raw_eplus_gates_any_pass": any_raw,
        "hybrid_dsm_96_v2_farm_run": False,
        "dsm_status": "NO-GO",
        "best_monthly_hold_by_feb_hourly": best,
        "energyplus_version": energyplus_version(),
        "trial_status": {r["trial_id"]: r["status"] for r in results},
        "trials_slim": [
            {
                "trial_id": r["trial_id"],
                "status": r["status"],
                "ranked": r.get("ranked"),
                "monthly_hold": r.get("monthly_hold"),
                "metrics": r.get("metrics"),
                "raw_pass": (r.get("gates") or {}).get("raw_eplus_gates_pass"),
                "sha": r.get("expanded_idf_sha256"),
            }
            for r in results
        ],
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    mirror = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-w2a-monthly-hold-hourly-dial-summary.json"
    mirror.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", default=None, help="Existing campaign folder name under eplus/campaigns")
    ap.add_argument(
        "--finalize-only",
        action="store_true",
        help="Rebuild summary from existing trial_result.json; no EnergyPlus",
    )
    args = ap.parse_args(argv)

    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    if args.resume or args.finalize_only:
        name = args.resume
        if not name:
            camps = sorted(
                (site / "eplus" / "campaigns").glob("w2a_monthly_hold_hourly_dial_*"),
                key=lambda p: p.name,
            )
            if not camps:
                raise SystemExit("no monthly-hold campaign to finalize")
            name = camps[-1].name
        camp = site / "eplus" / "campaigns" / name
        if not camp.is_dir():
            raise SystemExit(f"campaign not found: {camp}")
    else:
        camp = (
            site
            / "eplus"
            / "campaigns"
            / f"w2a_monthly_hold_hourly_dial_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
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
    monthly_passer_feb: list[float] = []
    stopped_early = False
    stop_reason: str | None = None

    def _ingest(rec: dict[str, Any]) -> None:
        results.append(rec)
        if rec.get("ranked") and (rec.get("metrics") or {}).get("feb_cvrmse_pct") is not None:
            monthly_passer_feb.append(float(rec["metrics"]["feb_cvrmse_pct"]))

    if args.finalize_only:
        for tid, _k in DIAL_TRIALS:
            p = camp / "trials" / tid / "trial_result.json"
            if p.is_file():
                _ingest(json.loads(p.read_text(encoding="utf-8")))
        stopped_early = early_stop_no_feb_gain(monthly_passer_feb) and len(results) >= 6
        stop_reason = (
            f"finalize: 3 monthly-passers failed to beat C02 Feb CVRMSE "
            f"({C02_BASELINE_FEB_CVRMSE:.2f}) by >=1 pt"
            if stopped_early
            else "finalize_only"
        )
        print(f"FINALIZE {camp.name} n={len(results)} passers={len(monthly_passer_feb)}", flush=True)
    else:
        for tid, knobs in DIAL_TRIALS:
            if knobs.fan_avail_use_sch_hvac:
                raise SystemExit(f"banned knob fan_avail_use_sch_hvac on {tid}")
            tdir = camp / "trials" / tid
            tdir.mkdir(parents=True)
            existing = tdir / "trial_result.json"
            if existing.is_file():
                rec = json.loads(existing.read_text(encoding="utf-8"))
                print(f"SKIP {tid} ({rec.get('status')})", flush=True)
                _ingest(rec)
                if len(results) >= 6 and early_stop_no_feb_gain(monthly_passer_feb):
                    stopped_early = True
                    stop_reason = (
                        f"after >=6 attempts, 3 consecutive monthly-passers failed to beat C02 Feb CVRMSE "
                        f"({C02_BASELINE_FEB_CVRMSE:.2f}) by >=1 pt"
                    )
                    print(f"EARLY STOP: {stop_reason}", flush=True)
                    break
                continue

            applied = apply_w2a_plant_knobs(base_text, knobs)
            trial_idf = tdir / "trial.idf"
            trial_idf.write_text(applied["text"], encoding="utf-8", newline="\n")
            rec = {
                "trial_id": tid,
                "knobs": applied["knobs"],
                "expanded_idf_sha256": applied["expanded_idf_sha256"],
                "fields_changed": applied["fields_changed"],
                "n_fields_changed": applied["n_fields_changed"],
                "energyplus_run": False,
                "status": "pending",
                "ranked": False,
            }
            if applied["n_fields_changed"] <= 0:
                rec["status"] = "failed_empty_fields_changed"
                _ingest(rec)
                existing.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
                continue
            probe = detect_duplicate_models(results + [rec])
            if any(tid in c.get("trial_ids", []) for c in probe["duplicate_collisions"]):
                rec["status"] = "skipped_duplicate_model"
                _ingest(rec)
                existing.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
                continue

            print(f"RUN {tid} sha={applied['expanded_idf_sha256'][:12]}", flush=True)
            man = run_energyplus(
                run_id=f"{camp.name}_{tid}",
                scenario_id=tid,
                idf_path=trial_idf,
                epw_path=epw,
                output_dir=tdir / "sim",
                require_zero_severe=False,
                allow_staged_idf=True,
            )
            rec["energyplus_run"] = True
            rec["exit_code"] = man.exit_code
            rec["runtime_sec"] = man.runtime_sec
            rec["idf_sha256"] = sha256_file(trial_idf)
            if man.exit_code == 0 and (tdir / "sim" / "eplusmtr.csv").is_file():
                print(f"  E+ done ({man.runtime_sec:.1f}s); scoring…", flush=True)
                full = _score_integrity(site, tdir / "sim", expanded_text=applied["text"])
                util = full.get("utility_monthly") or {}
                hold = monthly_gl14_style_pass(util if isinstance(util, dict) else {})
                rec["monthly_hold"] = hold
                rec["metrics"] = _slim_metrics(full)
                rec["gates"] = full.get("gates")
                rec["composite_selection_score"] = full.get("selection_score")
                if hold["pass"]:
                    rec["status"] = "succeeded_monthly_hold"
                    rec["ranked"] = True
                else:
                    rec["status"] = "rejected_monthly_hold_fail"
                    rec["ranked"] = False
                print(
                    f"  monthly={hold['pass']} nmbe={hold.get('nmbe_pct')} cv={hold.get('cvrmse_pct')} "
                    f"feb_cv={rec['metrics'].get('feb_cvrmse_pct')} wk_ratio={rec['metrics'].get('weekend_ratio')}",
                    flush=True,
                )
            else:
                rec["status"] = "failed_energyplus"
                print(f"  FAILED exit={man.exit_code}", flush=True)

            existing.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
            _ingest(rec)

            if len(results) >= 6 and early_stop_no_feb_gain(monthly_passer_feb):
                stopped_early = True
                stop_reason = (
                    f"after >=6 attempts, 3 consecutive monthly-passers failed to beat C02 Feb CVRMSE "
                    f"({C02_BASELINE_FEB_CVRMSE:.2f}) by >=1 pt"
                )
                print(f"EARLY STOP: {stop_reason}", flush=True)
                break

    summary = _write_summary(camp, results, stopped_early=stopped_early, stop_reason=stop_reason)
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "campaign_id",
                    "attempted_runs",
                    "monthly_passers",
                    "monthly_rejects",
                    "stopped_early",
                    "raw_eplus_gates_any_pass",
                    "best_monthly_hold_by_feb_hourly",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
