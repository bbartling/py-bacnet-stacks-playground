#!/usr/bin/env python3
"""W2A peak (~275 kW) + monthly GL14 dial — plant first, then people/plugs.

No optimal start. No fan→SCH_HVAC. Design day = 2026-01-26 (utility bill ~285 kW).
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
sys.path.insert(0, str(ROOT / "archive" / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.runner import energyplus_version, run_energyplus  # noqa: E402
from eplus_native.w2a_monthly_hold import (  # noqa: E402
    PEAK_DESIGN_DAY,
    PEAK_TARGET_KW,
    monthly_gl14_style_pass,
    peak_band_pass,
    rank_key_monthly_hold_peak,
)
from eplus_native.w2a_plant_knobs import (  # noqa: E402
    W2APlantKnobs,
    apply_w2a_plant_knobs,
    detect_duplicate_models,
)
from eplus_validation_contract import build_hourly_and_15min  # noqa: E402
from eplus_w2a_plant_calib import _score_integrity  # noqa: E402

# Stage A: plant toward ~275 kW. Stage B: add research-anchored gains.
# All optimum_start_h=0; fan_avail_use_sch_hvac=False.
DIAL_TRIALS: list[tuple[str, W2APlantKnobs]] = [
    # --- Stage A: plant ---
    ("P00_c02_ref", W2APlantKnobs(htg_coil_capacity_mult=0.45, setback_heat_sp_c=14.44)),
    ("P01_cap70_sb58", W2APlantKnobs(htg_coil_capacity_mult=0.70, setback_heat_sp_c=14.44)),
    ("P02_cap85_sb58", W2APlantKnobs(htg_coil_capacity_mult=0.85, setback_heat_sp_c=14.44)),
    ("P03_cap100_sb58", W2APlantKnobs(htg_coil_capacity_mult=1.00, setback_heat_sp_c=14.44)),
    (
        "P04_cap70_cop85",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.70,
            setback_heat_sp_c=14.44,
            htg_coil_cop_mult=0.85,
        ),
    ),
    (
        "P05_cap85_cop80",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.85,
            setback_heat_sp_c=14.44,
            htg_coil_cop_mult=0.80,
        ),
    ),
    (
        "P06_cap75_sb55",
        W2APlantKnobs(htg_coil_capacity_mult=0.75, setback_heat_sp_c=12.78),
    ),
    (
        "P07_cap90_oa12",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.90,
            setback_heat_sp_c=14.44,
            oa_frac_scale=1.2,
        ),
    ),
    # --- Stage B: plant + people/plugs/lights ---
    (
        "G00_cap80_eq15",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.80,
            setback_heat_sp_c=14.44,
            equip_w_area_mult=1.5,
        ),
    ),
    (
        "G01_cap85_eq15_pe12",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.85,
            setback_heat_sp_c=14.44,
            equip_w_area_mult=1.5,
            people_density_mult=1.2,
        ),
    ),
    (
        "G02_cap70_cop85_eq16",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.70,
            setback_heat_sp_c=14.44,
            htg_coil_cop_mult=0.85,
            equip_w_area_mult=1.6,
            people_density_mult=1.15,
        ),
    ),
    (
        "G03_cap95_eq13_li11",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.95,
            setback_heat_sp_c=14.44,
            equip_w_area_mult=1.3,
            lights_w_area_mult=1.1,
        ),
    ),
    (
        "G04_cap80_cop75_eq15",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.80,
            setback_heat_sp_c=14.44,
            htg_coil_cop_mult=0.75,
            equip_w_area_mult=1.5,
        ),
    ),
    (
        "G05_cap100_eq14_pe11",
        W2APlantKnobs(
            htg_coil_capacity_mult=1.00,
            setback_heat_sp_c=14.44,
            equip_w_area_mult=1.4,
            people_density_mult=1.1,
        ),
    ),
    (
        "G06_cap85_cop80_eq18",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.85,
            setback_heat_sp_c=14.44,
            htg_coil_cop_mult=0.80,
            equip_w_area_mult=1.8,
        ),
    ),
    (
        "G07_cap75_sb55_eq15_pe12",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.75,
            setback_heat_sp_c=12.78,
            equip_w_area_mult=1.5,
            people_density_mult=1.2,
            lights_w_area_mult=1.1,
        ),
    ),
    (
        "G08_cap90_cop85_eq15_li12",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.90,
            setback_heat_sp_c=15.0,
            htg_coil_cop_mult=0.85,
            equip_w_area_mult=1.5,
            lights_w_area_mult=1.2,
        ),
    ),
    (
        "G09_cap88_cop78_eq16_pe12",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.88,
            setback_heat_sp_c=14.44,
            htg_coil_cop_mult=0.78,
            equip_w_area_mult=1.6,
            people_density_mult=1.2,
        ),
    ),
    # --- Bridge: between C02 monthly-pass (~190 kW) and first monthly-fail ---
    ("B01_cap50_sb58", W2APlantKnobs(htg_coil_capacity_mult=0.50, setback_heat_sp_c=14.44)),
    ("B02_cap55_sb58", W2APlantKnobs(htg_coil_capacity_mult=0.55, setback_heat_sp_c=14.44)),
    ("B03_cap60_sb58", W2APlantKnobs(htg_coil_capacity_mult=0.60, setback_heat_sp_c=14.44)),
    ("B04_cap55_eq12", W2APlantKnobs(htg_coil_capacity_mult=0.55, setback_heat_sp_c=14.44, equip_w_area_mult=1.2)),
    (
        "B05_cap52_cop95",
        W2APlantKnobs(
            htg_coil_capacity_mult=0.52,
            setback_heat_sp_c=14.44,
            htg_coil_cop_mult=0.95,
        ),
    ),
]


def jan26_peak_kw(site: Path, sim_dir: Path) -> dict[str, Any]:
    packed = build_hourly_and_15min(site, sim_dir, heat_cop=3.5, cool_cop=4.5)
    f = packed["q15"].copy()
    f["interval_end_utc"] = pd.to_datetime(f["interval_end_utc"], utc=True)
    local = f["interval_end_utc"].dt.tz_convert("America/Chicago")
    f = f.assign(local=local, d=local.dt.strftime("%Y-%m-%d"))
    d = f[f["d"] == PEAK_DESIGN_DAY]
    if d.empty:
        return {"peak_kw": None, "peak_local": None, "n": 0}
    i = d["simulated_kw"].idxmax()
    return {
        "peak_kw": float(d.loc[i, "simulated_kw"]),
        "peak_local": str(d.loc[i, "local"]),
        "meas_peak_kw": float(d["observed_kw"].max()),
        "n": int(len(d)),
    }


def _slim_metrics(metrics: dict[str, Any], peak_info: dict[str, Any]) -> dict[str, Any]:
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
        "jan26_sim_peak_kw": peak_info.get("peak_kw"),
        "jan26_meas_peak_kw": peak_info.get("meas_peak_kw"),
        "jan26_peak_local": peak_info.get("peak_local"),
        "unmet_sum": (metrics.get("unmet_heating") or {}).get("sum_zone_unmet_heating_hours"),
    }


def _write_summary(camp: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    uniq = detect_duplicate_models(results)
    ranked = [r for r in results if r.get("ranked")]
    ranked.sort(key=rank_key_monthly_hold_peak)
    dual = [
        r
        for r in ranked
        if (r.get("peak_hold") or {}).get("pass") and (r.get("monthly_hold") or {}).get("pass")
    ]
    best = None
    if ranked:
        b = ranked[0]
        best = {
            "trial_id": b["trial_id"],
            **(b.get("metrics") or {}),
            "monthly_hold": b.get("monthly_hold"),
            "peak_hold": b.get("peak_hold"),
            "dual_pass": b["trial_id"] in {x["trial_id"] for x in dual},
        }
    summary = {
        "campaign_id": camp.name,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "family": "W2A_peak275_monthly_gl14_dial",
        "peak_target_kw": PEAK_TARGET_KW,
        "peak_design_day": PEAK_DESIGN_DAY,
        "monthly_constraint": monthly_gl14_style_pass({"nmbe_pct": 0, "cvrmse_pct": 0})["label"],
        "attempted_runs": len(results),
        "unique_models": uniq["unique_models"],
        "uniqueness_ok": uniq["uniqueness_ok"],
        "monthly_passers": sum(1 for r in results if (r.get("monthly_hold") or {}).get("pass")),
        "peak_band_passers": sum(1 for r in results if (r.get("peak_hold") or {}).get("pass")),
        "dual_passers": len(dual),
        "monthly_rejects": sum(1 for r in results if r.get("status") == "rejected_monthly_hold_fail"),
        "failed_energyplus": sum(1 for r in results if r.get("status") == "failed_energyplus"),
        "dsm_status": "NO-GO",
        "best_monthly_then_peak": best,
        "dual_passer_ids": [r["trial_id"] for r in dual],
        "energyplus_version": energyplus_version(),
        "trial_status": {r["trial_id"]: r["status"] for r in results},
        "trials_slim": [
            {
                "trial_id": r["trial_id"],
                "status": r["status"],
                "ranked": r.get("ranked"),
                "monthly_hold": r.get("monthly_hold"),
                "peak_hold": r.get("peak_hold"),
                "metrics": r.get("metrics"),
                "sha": r.get("expanded_idf_sha256"),
            }
            for r in results
        ],
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    mirror = ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-w2a-peak-monthly-dial-summary.json"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--resume", default=None)
    ap.add_argument("--finalize-only", action="store_true")
    args = ap.parse_args(argv)

    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    if args.resume or args.finalize_only:
        name = args.resume
        if not name:
            camps = sorted(
                (site / "eplus" / "campaigns").glob("w2a_peak_monthly_dial_*"),
                key=lambda p: p.name,
            )
            if not camps:
                raise SystemExit("no peak-monthly campaign to finalize")
            name = camps[-1].name
        camp = site / "eplus" / "campaigns" / name
        if not camp.is_dir():
            raise SystemExit(f"campaign not found: {camp}")
    else:
        camp = (
            site
            / "eplus"
            / "campaigns"
            / f"w2a_peak_monthly_dial_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
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

    def _ingest(rec: dict[str, Any]) -> None:
        results.append(rec)

    if args.finalize_only:
        for tid, _k in DIAL_TRIALS:
            p = camp / "trials" / tid / "trial_result.json"
            if p.is_file():
                _ingest(json.loads(p.read_text(encoding="utf-8")))
        print(f"FINALIZE {camp.name} n={len(results)}", flush=True)
    else:
        for tid, knobs in DIAL_TRIALS:
            if knobs.fan_avail_use_sch_hvac:
                raise SystemExit(f"banned knob fan_avail_use_sch_hvac on {tid}")
            if knobs.optimum_start_h:
                raise SystemExit(f"banned optimum_start on {tid} (building has none)")
            tdir = camp / "trials" / tid
            tdir.mkdir(parents=True, exist_ok=True)
            existing = tdir / "trial_result.json"
            if existing.is_file():
                rec = json.loads(existing.read_text(encoding="utf-8"))
                print(f"SKIP {tid} ({rec.get('status')})", flush=True)
                _ingest(rec)
                continue

            applied = apply_w2a_plant_knobs(base_text, knobs)
            trial_idf = tdir / "trial.idf"
            trial_idf.write_text(applied["text"], encoding="utf-8", newline="\n")
            rec: dict[str, Any] = {
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

            print(
                f"RUN {tid} sha={applied['expanded_idf_sha256'][:12]} "
                f"fields={applied['n_fields_changed']}",
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
            rec["energyplus_run"] = True
            rec["exit_code"] = man.exit_code
            rec["runtime_sec"] = man.runtime_sec
            rec["idf_sha256"] = sha256_file(trial_idf)
            if man.exit_code == 0 and (tdir / "sim" / "eplusmtr.csv").is_file():
                print(f"  E+ done ({man.runtime_sec:.1f}s); scoring…", flush=True)
                full = _score_integrity(site, tdir / "sim", expanded_text=applied["text"])
                peak_info = jan26_peak_kw(site, tdir / "sim")
                util = full.get("utility_monthly") or {}
                hold = monthly_gl14_style_pass(util if isinstance(util, dict) else {})
                peak = peak_band_pass(peak_info.get("peak_kw"))
                rec["monthly_hold"] = hold
                rec["peak_hold"] = peak
                rec["metrics"] = _slim_metrics(full, peak_info)
                rec["gates"] = full.get("gates")
                if hold["pass"]:
                    rec["status"] = (
                        "succeeded_dual"
                        if peak["pass"]
                        else "succeeded_monthly_hold"
                    )
                    rec["ranked"] = True
                else:
                    rec["status"] = "rejected_monthly_hold_fail"
                    rec["ranked"] = False
                print(
                    f"  monthly={hold['pass']} nmbe={hold.get('nmbe_pct')} cv={hold.get('cvrmse_pct')} "
                    f"jan26_peak={peak.get('peak_kw')} band={peak['pass']} "
                    f"feb_cv={rec['metrics'].get('feb_cvrmse_pct')}",
                    flush=True,
                )
            else:
                rec["status"] = "failed_energyplus"
                print(f"  FAILED exit={man.exit_code}", flush=True)

            existing.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
            _ingest(rec)

    summary = _write_summary(camp, results)
    print(
        json.dumps(
            {
                k: summary[k]
                for k in (
                    "campaign_id",
                    "attempted_runs",
                    "monthly_passers",
                    "peak_band_passers",
                    "dual_passers",
                    "dual_passer_ids",
                    "best_monthly_then_peak",
                )
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
