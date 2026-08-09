#!/usr/bin/env python3
"""W2A integrity-first closure: ≤8 unique live-knob EnergyPlus trials.

Pipeline: stage_w2a → ExpandObjects → post-expand mutator → uniqueness gate → run.
Selection: Nov–Dec rolling origins only. Reserved final: Feb 2026 local month.
DSM remains NO-GO unless every expanded raw gate passes (hybrid-v2 farm not run).
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_campaign_enrichment import (  # noqa: E402
    load_nine_zone_temps,
    unmet_heating_hours,
)
from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.runner import energyplus_version, run_energyplus  # noqa: E402
from eplus_native.schedule_calendar_repair import repair_idf_file  # noqa: E402
from eplus_native.w2a_integrity_gates import integrity_promotion_gates  # noqa: E402
from eplus_native.w2a_plant_knobs import (  # noqa: E402
    W2APlantKnobs,
    apply_w2a_plant_knobs,
    detect_duplicate_models,
    plant_plausibility_check,
)
from eplus_native.zone_agg import aggregate_zone_temp_frame, load_agg_contract  # noqa: E402
from eplus_schedule_sanity_campaign import structural_metrics  # noqa: E402
from eplus_stage_provisional_w2a import expand_objects, stage_w2a  # noqa: E402
from eplus_validation_contract import (  # noqa: E402
    JANUARY_HOLDOUT_NOTE,
    build_hourly_and_15min,
    score_aligned,
    score_reserved_final_winter_audit,
    score_rolling_origin_selection,
    utility_monthly_from_trial_sim,
)


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Declared integrity-closure grid only (max 8). No W15–W19 ad-hoc trials.
INTEGRITY_TRIALS: list[tuple[str, W2APlantKnobs]] = [
    ("I00_cap1p0", W2APlantKnobs(htg_coil_capacity_mult=1.0)),
    ("I01_cap0p75", W2APlantKnobs(htg_coil_capacity_mult=0.75)),
    ("I02_cap1p25", W2APlantKnobs(htg_coil_capacity_mult=1.25)),
    ("I03_cop0p85", W2APlantKnobs(htg_coil_capacity_mult=1.0, htg_coil_cop_mult=0.85)),
    (
        "I04_fan_pump",
        W2APlantKnobs(
            htg_coil_capacity_mult=1.0,
            fan_delta_p_mult=1.4,
            pump_power_mult=1.3,
        ),
    ),
    (
        "I05_loop_oa",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.9,
            loop_setpoint_c=30.0,
            oa_frac_scale=0.7,
        ),
    ),
    (
        "I06_optstart",
        W2APlantKnobs(htg_coil_capacity_mult=1.05, optimum_start_h=1.0),
    ),
    (
        "I07_blend",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.85,
            htg_coil_cop_mult=1.1,
            fan_eff_mult=0.95,
            pump_power_mult=0.9,
        ),
    ),
]


def _score_integrity(site: Path, sim_dir: Path, *, expanded_text: str) -> dict[str, Any]:
    print(f"  score: align hourly…", flush=True)
    packed = build_hourly_and_15min(site, sim_dir, heat_cop=3.5, cool_cop=4.5)
    hourly = packed["hourly"].copy()
    # structural expects kw_mod / kw_meas / timestamp_utc
    struct_df = hourly.rename(
        columns={
            "observed_kw": "kw_meas",
            "simulated_kw": "kw_mod",
            "interval_end_utc": "timestamp_utc",
        }
    )
    print(f"  score: selection/reserved/utility…", flush=True)
    selection = score_rolling_origin_selection(hourly)
    reserved = score_reserved_final_winter_audit(hourly)
    util = utility_monthly_from_trial_sim(site, sim_dir, heat_cop=3.5, cool_cop=4.5)
    print(f"  score: zone MAT extract…", flush=True)
    nine = load_nine_zone_temps(sim_dir)
    unmet = unmet_heating_hours(nine) if not nine.empty else {"status": "empty"}
    print(f"  score: six-zone metrics (n_zone={len(nine)})…", flush=True)
    zones = _six_zone_metrics_from_nine(site, nine)
    plant = plant_plausibility_check(expanded_text)
    metrics: dict[str, Any] = {
        "hourly_score": score_aligned(hourly, resolution="hourly"),
        "utility_monthly": util,
        "structural": structural_metrics(struct_df),
        "rolling_origin_selection": selection,
        "reserved_final_winter_audit": reserved,
        "six_zone_metrics": zones,
        "unmet_heating": unmet,
        "plant_plausibility": plant,
        "selection_score": selection.get("selection_score"),
    }
    metrics["gates"] = integrity_promotion_gates(metrics, expanded_idf_text=expanded_text)
    print(f"  score: done", flush=True)
    return metrics


def _six_zone_metrics_from_nine(site: Path, nine: pd.DataFrame) -> dict[str, Any]:
    """Six-zone MAE vs BAS; accepts preloaded nine-zone frame (no second CSV pass)."""
    if nine.empty:
        return {}
    cal = load_agg_contract()
    agg = aggregate_zone_temp_frame(nine, contract=cal, mode="hp_count")
    candidates = [
        site / "clean_data" / "LAKESIDE_ES" / "zone_temp_15min.parquet",
        site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet",
    ]
    meas_path = next((p for p in candidates if p.is_file()), None)
    if meas_path is None:
        return {"status": "no_measured_zone_parquet"}
    meas = pd.read_parquet(meas_path)
    if "interval_end_utc" not in meas.columns and "timestamp_utc" in meas.columns:
        meas = meas.rename(columns={"timestamp_utc": "interval_end_utc"})
    if "interval_end_utc" not in meas.columns:
        return {"status": "measured_missing_timestamp", "path": str(meas_path)}
    meas["interval_end_utc"] = pd.to_datetime(meas["interval_end_utc"], utc=True)
    agg = agg.copy()
    if "interval_end_utc" not in agg.columns:
        agg["interval_end_utc"] = pd.to_datetime(nine["interval_end_utc"], utc=True).to_numpy()
    else:
        agg["interval_end_utc"] = pd.to_datetime(agg["interval_end_utc"], utc=True)
    out: dict[str, Any] = {}
    try:
        out["measured_source"] = str(meas_path.relative_to(site))
    except ValueError:
        out["measured_source"] = str(meas_path)
    for col in [c for c in agg.columns if c.startswith("zone_temp_")]:
        if col not in meas.columns:
            continue
        m = meas[["interval_end_utc", col]].merge(
            agg[["interval_end_utc", col]],
            on="interval_end_utc",
            how="inner",
            suffixes=("_m", "_s"),
        )
        if m.empty:
            continue
        yt = m[f"{col}_m"].to_numpy(dtype=float)
        yp = m[f"{col}_s"].to_numpy(dtype=float)
        err = yp - yt
        out[col] = {
            "n": int(len(m)),
            "mae": float(abs(err).mean()),
            "bias": float(err.mean()),
        }
    if len([k for k in out if k.startswith("zone_temp_")]) == 0:
        out["status"] = "no_zone_overlap"
    return out


def _six_zone_metrics(site: Path, sim_dir: Path) -> dict[str, Any]:
    return _six_zone_metrics_from_nine(site, load_nine_zone_temps(sim_dir))


def main() -> int:
    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    camp = (
        site
        / "eplus"
        / "campaigns"
        / f"w2a_integrity_closure_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    camp.mkdir(parents=True)
    champ = sorted(
        (site / "eplus" / "campaigns").glob("freeze_pre_schedule_plant_*/champion_B_equip_mult_mid_model.idf")
    )[-1]
    # Prefer schedule-repaired mid parent when present
    parent = (
        site
        / "eplus"
        / "campaigns"
        / "schedule_sanity_20260808T150000Z"
        / "staged_idfs"
        / "S3_cap_mid_2p7.idf"
    )
    if not parent.is_file():
        parent = camp / "repaired_parent.idf"
        repair_idf_file(champ, parent, heating_capacity_mmbtu_h=2.7)
    epw = site / "eplus" / "weather" / "madison_amy_202508_202607.epw"

    # Stage + expand once (shared templates); mutate per trial on expanded text
    shared = camp / "shared"
    shared.mkdir(parents=True)
    staged = shared / "trial_template.idf"
    stage_w2a(parent, staged)
    expanded_base = expand_objects(staged, shared / "expand")
    base_text = expanded_base.read_text(encoding="utf-8", errors="replace")

    results: list[dict[str, Any]] = []
    uniqueness_failed = False

    for tid, knobs in INTEGRITY_TRIALS:
        tdir = camp / "trials" / tid
        tdir.mkdir(parents=True)
        applied = apply_w2a_plant_knobs(base_text, knobs)
        trial_idf = tdir / "trial.idf"
        trial_idf.write_text(applied["text"], encoding="utf-8", newline="\n")
        shutil.copy2(trial_idf, tdir / "expanded_mutated.idf")

        rec: dict[str, Any] = {
            "trial_id": tid,
            "knobs": applied["knobs"],
            "expanded_idf_sha256": applied["expanded_idf_sha256"],
            "fields_changed": applied["fields_changed"],
            "n_fields_changed": applied["n_fields_changed"],
            "status": "pending",
            "energyplus_run": False,
        }
        if applied["n_fields_changed"] <= 0:
            rec["status"] = "failed_empty_fields_changed"
            uniqueness_failed = True
            (tdir / "trial_result.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
            results.append(rec)
            continue

        # Pre-check uniqueness vs prior attempted trials with different knobs
        probe = detect_duplicate_models(results + [rec])
        if not probe["uniqueness_ok"] and any(
            tid in c.get("trial_ids", []) for c in probe["duplicate_collisions"]
        ):
            rec["status"] = "skipped_duplicate_model"
            uniqueness_failed = True
            (tdir / "trial_result.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
            results.append(rec)
            continue

        print(f"RUN {tid} sha={applied['expanded_idf_sha256'][:12]} …", flush=True)
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
            try:
                metrics = _score_integrity(site, tdir / "sim", expanded_text=applied["text"])
                rec["metrics"] = {
                    "utility_monthly": {
                        k: (metrics["utility_monthly"] or {}).get(k)
                        for k in ("nmbe_pct", "cvrmse_pct", "status")
                    },
                    "structural": metrics.get("structural"),
                    "rolling_origin_selection": metrics.get("rolling_origin_selection"),
                    "reserved_final_winter_audit": {
                        k: (metrics.get("reserved_final_winter_audit") or {}).get(k)
                        for k in (
                            "period_id",
                            "status",
                            "n",
                            "used_for_selection",
                            "hourly_score",
                            "day_level_peaks",
                        )
                    },
                    "selection_score": metrics.get("selection_score"),
                    "unmet_heating_sum": (metrics.get("unmet_heating") or {}).get(
                        "sum_zone_unmet_heating_hours"
                    ),
                    "six_zone_metrics": metrics.get("six_zone_metrics"),
                }
                rec["gates"] = metrics.get("gates")
                rec["composite_selection_score"] = metrics.get("selection_score")
                rec["status"] = "succeeded"
            except Exception as e:
                rec["status"] = "failed_score"
                rec["score_error"] = f"{type(e).__name__}: {e}"
        else:
            rec["status"] = "failed_energyplus"
        (tdir / "trial_result.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        results.append(rec)

    uniq = detect_duplicate_models(results)
    if not uniq["uniqueness_ok"]:
        uniqueness_failed = True

    ok = [r for r in results if r["status"] == "succeeded"]
    ok.sort(
        key=lambda r: (
            r.get("composite_selection_score")
            if r.get("composite_selection_score") is not None
            else 1e9
        )
    )
    any_raw = any((r.get("gates") or {}).get("raw_eplus_gates_pass") for r in ok)
    unique_ran = len({r["expanded_idf_sha256"] for r in results if r.get("energyplus_run")})
    attempted = len(results)

    summary = {
        "campaign_id": camp.name,
        "created_utc": _utc(),
        "provenance": "PROVISIONAL_W2A_HVACTEMPLATE_INTEGRITY_CLOSURE",
        "honesty": (
            "Post-expand live knobs only; rolling-origin Nov–Dec selection; "
            "Feb reserved final audit; January IdealLoads holdout consumed. "
            + JANUARY_HOLDOUT_NOTE
        ),
        "planned_trials": len(INTEGRITY_TRIALS),
        "attempted_runs": attempted,
        "unique_models": uniq["unique_models"],
        "unique_energyplus_runs": unique_ran,
        "duplicate_collisions": uniq["duplicate_collisions"],
        "empty_fields_changed": uniq["empty_fields_changed"],
        "uniqueness_ok": uniq["uniqueness_ok"],
        "uniqueness_fail_closed": uniqueness_failed,
        "succeeded": len(ok),
        "failed": attempted - len(ok),
        "raw_eplus_gates_any_pass": any_raw,
        "hybrid_dsm_96_v2_farm_run": False,
        "hybrid_dsm_96_v2_farm_reason": (
            "not run — raw gates did not all pass"
            if not any_raw
            else "eligible but farm deferred to explicit operator request"
        ),
        "dsm_status": "NO-GO" if not any_raw else "SCREENING_ONLY_RAW_GATES",
        "audit": "NO-GO" if (not any_raw or uniqueness_failed) else "SCREENING ONLY",
        "best_trial_id": None if not ok else ok[0]["trial_id"],
        "energyplus_version": energyplus_version(),
        "declared_trial_ids": [t[0] for t in INTEGRITY_TRIALS],
        "supersedes_nonreproducible_w2a_calib": {
            "prior_campaign_id": "w2a_plant_calib_20260808T152458Z",
            "retracted": ["W15", "W16", "W17", "W18", "W19", "claimed_20_of_20"],
            "reason": "ad-hoc runner / dead IdealLoads capacity knobs; not in declared script grid",
        },
        "trials": results,
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    slim = {k: v for k, v in summary.items() if k != "trials"}
    slim["trial_status"] = {r["trial_id"]: r["status"] for r in results}
    slim["trial_sha256"] = {
        r["trial_id"]: r.get("expanded_idf_sha256") for r in results if r.get("expanded_idf_sha256")
    }
    mirror = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-w2a-integrity-closure-summary.json"
    mirror.write_text(json.dumps(slim, indent=2) + "\n", encoding="utf-8")
    # Retract unreproducible prior summary counts
    prior = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-w2a-plant-calib-summary.json"
    prior.write_text(
        json.dumps(
            {
                "status": "RETRACTED_NONREPRODUCIBLE",
                "prior_campaign_id": "w2a_plant_calib_20260808T152458Z",
                "reason": (
                    "Committed runner was a 15-trial cap×unocc IdealLoads grid; "
                    "W15–W19 came from an ad-hoc runner; heating_capacity_mmbtu_h was "
                    "stripped before ExpandObjects (dead knob). Superseded by integrity closure."
                ),
                "superseded_by": camp.name,
                "superseded_by_mirror": "2026-08-08-w2a-integrity-closure-summary.json",
                "retracted_trial_ids": [
                    "W15_cap2p4_u64p0_os0p0",
                    "W16_cap2p6_u66p0_os1p0",
                    "W17_cap2p8_u63p0_os0p0",
                    "W18_cap3p0_u67p0_os1p0",
                    "W19_cap3p1_u65p0_os0p5",
                ],
                "do_not_cite_as_20_of_20": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(slim, indent=2))
    if uniqueness_failed:
        return 2
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
