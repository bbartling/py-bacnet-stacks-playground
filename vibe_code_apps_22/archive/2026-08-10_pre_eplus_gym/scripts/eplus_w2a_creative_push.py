#!/usr/bin/env python3
"""Creative W2A dial-in push: setback SP + fan SCH_HVAC + deeper capacity cuts.

Reuses expanded base from integrity closure. ≤6 unique live-knob E+ trials.
Does not weaken gates; hybrid-v2 farm still not run.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.runner import energyplus_version, run_energyplus  # noqa: E402
from eplus_native.w2a_plant_knobs import (  # noqa: E402
    W2APlantKnobs,
    apply_w2a_plant_knobs,
    detect_duplicate_models,
)
from eplus_w2a_plant_calib import _score_integrity  # noqa: E402

CREATIVE_TRIALS: list[tuple[str, W2APlantKnobs]] = [
    # Deeper setback (60°F) + capacity cut
    (
        "C01_setback60_cap55",
        W2APlantKnobs(htg_coil_capacity_mult=0.55, setback_heat_sp_c=15.56),
    ),
    # Aggressive setback 58°F + very low capacity
    (
        "C02_setback58_cap45",
        W2APlantKnobs(htg_coil_capacity_mult=0.45, setback_heat_sp_c=14.44),
    ),
    # Fan avail → SCH_HVAC (weekend fans off) + modest capacity
    (
        "C03_fanHVAC_cap60",
        W2APlantKnobs(htg_coil_capacity_mult=0.60, fan_avail_use_sch_hvac=True),
    ),
    # Combine: setback 62°F + fan SCH_HVAC + cap 0.55 + cold loop
    (
        "C04_combo_struct",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.55,
            setback_heat_sp_c=16.67,
            fan_avail_use_sch_hvac=True,
            loop_setpoint_c=28.0,
            fan_delta_p_mult=0.7,
        ),
    ),
    # Soft OA shoulders + setback 60 + cap 0.50
    (
        "C05_oa_shoulder_setback",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.50,
            setback_heat_sp_c=15.56,
            oa_shoulder_scale=0.35,
            oa_frac_scale=0.85,
        ),
    ),
    # Prior best direction + setback (I07-ish + 60°F setback)
    (
        "C06_blend_setback60",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.70,
            htg_coil_cop_mult=1.1,
            setback_heat_sp_c=15.56,
            fan_eff_mult=0.95,
            pump_power_mult=0.9,
        ),
    ),
]


def main() -> int:
    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    camp = (
        site
        / "eplus"
        / "campaigns"
        / f"w2a_creative_push_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
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

    results: list[dict] = []
    for tid, knobs in CREATIVE_TRIALS:
        tdir = camp / "trials" / tid
        tdir.mkdir(parents=True)
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
        }
        if applied["n_fields_changed"] <= 0:
            rec["status"] = "failed_empty_fields_changed"
            results.append(rec)
            continue
        probe = detect_duplicate_models(results + [rec])
        if any(tid in c.get("trial_ids", []) for c in probe["duplicate_collisions"]):
            rec["status"] = "skipped_duplicate_model"
            results.append(rec)
            continue
        print(f"RUN {tid} sha={applied['expanded_idf_sha256'][:12]} nchg={applied['n_fields_changed']}", flush=True)
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
            metrics = _score_integrity(site, tdir / "sim", expanded_text=applied["text"])
            st = metrics.get("structural") or {}
            util = metrics.get("utility_monthly") or {}
            res = metrics.get("reserved_final_winter_audit") or {}
            h = res.get("hourly_score") or {}
            rec["metrics"] = {
                "selection_score": metrics.get("selection_score"),
                "weekend_ratio": st.get("weekend_collapse_ratio_mod_over_meas"),
                "weekend_kw_mod": st.get("winter_weekend_kw_mod_mean"),
                "weekend_kw_meas": st.get("winter_weekend_kw_meas_mean"),
                "overnight_kw_mod": st.get("winter_overnight_kw_mod_mean"),
                "util_cvrmse_pct": util.get("cvrmse_pct"),
                "util_nmbe_pct": util.get("nmbe_pct"),
                "feb_cvrmse_pct": h.get("cvrmse_pct"),
                "unmet_sum": (metrics.get("unmet_heating") or {}).get(
                    "sum_zone_unmet_heating_hours"
                ),
            }
            rec["gates"] = metrics.get("gates")
            rec["composite_selection_score"] = metrics.get("selection_score")
            rec["status"] = "succeeded"
            (tdir / "trial_result.json").write_text(
                json.dumps(rec, indent=2) + "\n", encoding="utf-8"
            )
            print(
                f"  OK wk_ratio={rec['metrics']['weekend_ratio']:.3f} "
                f"wk_mod={rec['metrics']['weekend_kw_mod']:.1f} "
                f"util_cv={rec['metrics']['util_cvrmse_pct']:.1f} "
                f"sel={rec['metrics']['selection_score']:.1f} "
                f"raw={rec['gates'].get('raw_eplus_gates_pass')}",
                flush=True,
            )
        else:
            rec["status"] = "failed_energyplus"
            (tdir / "trial_result.json").write_text(
                json.dumps(rec, indent=2) + "\n", encoding="utf-8"
            )
            print(f"  FAILED exit={man.exit_code}", flush=True)
        results.append(rec)

    uniq = detect_duplicate_models(results)
    ok = [r for r in results if r.get("status") == "succeeded"]
    ok.sort(
        key=lambda r: (
            r.get("composite_selection_score")
            if r.get("composite_selection_score") is not None
            else 1e9
        )
    )
    any_raw = any((r.get("gates") or {}).get("raw_eplus_gates_pass") for r in ok)
    prior_best = {
        "trial_id": "I07_blend",
        "weekend_ratio": 1.598,
        "weekend_kw_mod": 102.0,
        "util_cvrmse_pct": 26.94,
        "selection_score": 47.13,
    }
    best = None if not ok else {
        "trial_id": ok[0]["trial_id"],
        **(ok[0].get("metrics") or {}),
        "raw_pass": (ok[0].get("gates") or {}).get("raw_eplus_gates_pass"),
    }
    summary = {
        "campaign_id": camp.name,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "hypothesis": (
            "Weekend overshoot persists at 65°F setback with always-on fans; "
            "try deeper setback, SCH_HVAC fan avail, OA shoulder cut, lower capacity."
        ),
        "parent_expanded_from": str(base),
        "attempted_runs": len(results),
        "unique_models": uniq["unique_models"],
        "uniqueness_ok": uniq["uniqueness_ok"],
        "succeeded": len(ok),
        "failed": len(results) - len(ok),
        "raw_eplus_gates_any_pass": any_raw,
        "hybrid_dsm_96_v2_farm_run": False,
        "dsm_status": "NO-GO",
        "prior_integrity_best": prior_best,
        "creative_best": best,
        "energyplus_version": energyplus_version(),
        "trial_status": {r["trial_id"]: r["status"] for r in results},
        "trials_slim": [
            {
                "trial_id": r["trial_id"],
                "status": r["status"],
                "knobs": r.get("knobs"),
                "metrics": r.get("metrics"),
                "raw_pass": (r.get("gates") or {}).get("raw_eplus_gates_pass"),
                "sha": r.get("expanded_idf_sha256"),
            }
            for r in results
        ],
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    mirror = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-w2a-creative-push-summary.json"
    mirror.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "campaign_id", "succeeded", "failed", "raw_eplus_gates_any_pass",
        "prior_integrity_best", "creative_best",
    )}, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
