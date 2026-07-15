"""OpenFDD WattLab easy button — prototype IDF + EPW → baseline → progressive ECMs.

Usage:
  python easy_button.py --building examples/buildings/madison_office.json --dry-run
  python easy_button.py --building examples/buildings/madison_office.json
  python easy_button.py --building examples/buildings/madison_office.json --skip-ecm2
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import (
    ARTIFACTS,
    DEFAULT_ELEC_RATE_USD_PER_KWH,
    DEFAULT_EPW_NOTE,
    DEFAULT_GAS_RATE_USD_PER_THERM,
    DEFAULT_MADISON_EPW,
    DEFAULT_PROTOTYPE_IDF,
    ROOT,
)
from ep_mcp_client import simulate
from idf_patches import (
    apply_fan_avail_continuous,
    apply_fan_avail_occupied_office,
    apply_gl36_airside_proxy,
)
from results_parse import annual_from_output_dir, build_result_record, file_sha256

PRODUCT = "OpenFDD WattLab"
DISCLAIMER = (
    "This is a conceptual, uncalibrated screening model for an anonymized office building. "
    "It is not a design load calculation, code-compliance model, calibrated energy model, "
    "or representation of a specific Madison property."
)

GL36_LIT = {
    "hvac_savings_pct_avg": 31.0,
    "hvac_savings_pct_band": (20.0, 40.0),
    "component_site_pct_approx": {
        "vav_minimum": 16.0,
        "sat_reset": 7.0,
        "duct_static_reset": 4.0,
    },
    "incremental_whole_building_kwh_pct_band": (5.0, 35.0),
}


def pct_delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None or before == 0:
        return None
    return round(100.0 * (before - after) / before, 2)


def validate_against_literature(
    *,
    baseline: dict,
    after_ecm1: dict | None,
    after_ecm2: dict | None,
) -> dict:
    b_kwh = (baseline or {}).get("electricity_kwh_year")
    b_eui = (baseline or {}).get("site_eui_kbtu_ft2_year")
    b_cost = (baseline or {}).get("utility_cost_usd_year")
    e1_kwh = (after_ecm1 or {}).get("electricity_kwh_year")
    e2_kwh = (after_ecm2 or {}).get("electricity_kwh_year")
    e2_eui = (after_ecm2 or {}).get("site_eui_kbtu_ft2_year")
    e2_cost = (after_ecm2 or {}).get("utility_cost_usd_year")

    inc_kwh = pct_delta(e1_kwh, e2_kwh)
    cum_kwh = pct_delta(b_kwh, e2_kwh)
    cum_eui = pct_delta(b_eui, e2_eui)
    cum_cost = pct_delta(b_cost, e2_cost)
    ecm1_kwh = pct_delta(b_kwh, e1_kwh)

    lo, hi = GL36_LIT["incremental_whole_building_kwh_pct_band"]
    flags: list[str] = [
        "whole_building_not_hvac_only",
        "conceptual_gl36_proxy",
        "gl36_proxy_not_full_sequences",
    ]
    verdict = "SKIPPED"
    notes: list[str] = []

    if after_ecm2 and e1_kwh and e2_kwh:
        if inc_kwh is None:
            verdict = "WARN"
            notes.append("Could not compute incremental kWh %.")
        elif inc_kwh < 0:
            verdict = "WARN"
            flags.append("gl36_incremental_negative")
            notes.append("GL36-proxy increased energy vs post-schedule case.")
        elif lo <= inc_kwh <= hi:
            verdict = "PASS"
            notes.append(
                f"Incremental GL36-proxy whole-building kWh savings {inc_kwh}% within "
                f"screening band {lo}–{hi}%."
            )
        else:
            verdict = "WARN"
            flags.append("gl36_incremental_outside_band")
            notes.append(
                f"Incremental {inc_kwh}% outside {lo}–{hi}% whole-building screening band "
                "(not HVAC-only literature %)."
            )
    elif after_ecm1 and b_kwh and e1_kwh:
        verdict = "PASS" if (ecm1_kwh or 0) > 0 else "WARN"
        notes.append(f"Schedule ECM whole-building kWh delta {ecm1_kwh}%.")

    return {
        "verdict": verdict,
        "pct_savings": {
            "ecm1_kwh_vs_baseline": ecm1_kwh,
            "ecm2_incremental_kwh_vs_ecm1": inc_kwh,
            "cumulative_kwh_vs_baseline": cum_kwh,
            "cumulative_eui_vs_baseline": cum_eui,
            "cumulative_cost_vs_baseline": cum_cost,
        },
        "literature": GL36_LIT,
        "quality_flags": flags,
        "notes": notes,
    }


def resolve_path(p: str | Path | None, default: Path) -> Path:
    if not p:
        return default
    path = Path(p)
    if not path.is_absolute():
        path = (ROOT / path).resolve()
    return path


def load_profile(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def approved_measures(profile: dict) -> list[dict]:
    return [
        m
        for m in profile.get("measures") or []
        if (m.get("review_status") or "").lower() == "approved"
    ]


def plan_dry_run(profile_path: Path) -> dict[str, Any]:
    profile = load_profile(profile_path)
    ep = profile.get("energyplus") or {}
    prototype = resolve_path(ep.get("prototype_idf"), DEFAULT_PROTOTYPE_IDF)
    epw = resolve_path(ep.get("epw"), DEFAULT_MADISON_EPW)
    measures = approved_measures(profile)
    steps: list[dict[str, Any]] = [
        {
            "step": "select_prototype",
            "prototype_idf": str(prototype),
            "epw": str(epw),
            "epw_note": ep.get("epw_note") or DEFAULT_EPW_NOTE,
        },
        {
            "step": "baseline_patch",
            "idf_patch": (ep.get("baseline_idf_patch") or "fan_avail_continuous"),
            "calibration": ep.get("calibration") or {"status": "NEEDS_INPUT"},
        },
        {"step": "simulate", "label": "baseline"},
    ]
    for m in measures:
        steps.append(
            {
                "step": "apply_measure",
                "measure_id": m.get("measure_id"),
                "idf_patch": (m.get("idf_patch") or {}).get("name"),
                "title": m.get("title"),
            }
        )
        steps.append({"step": "simulate", "label": m.get("measure_id")})
    return {
        "product": PRODUCT,
        "dry_run": True,
        "project_id": profile.get("project_id"),
        "display_name": profile.get("display_name"),
        "disclaimer": profile.get("disclaimer") or DISCLAIMER,
        "steps": steps,
        "approved_measure_ids": [m["measure_id"] for m in measures],
    }


def _rates(profile: dict) -> tuple[float, float]:
    util = profile.get("utility") or {}
    return (
        float(util.get("elec_usd_per_kwh") or DEFAULT_ELEC_RATE_USD_PER_KWH),
        float(util.get("gas_usd_per_therm") or DEFAULT_GAS_RATE_USD_PER_THERM),
    )


def _apply_patch(name: str, src: Path, dest: Path, measure: dict | None = None) -> dict:
    patch = (measure or {}).get("idf_patch") or {}
    params = patch.get("params") or {}
    if name in {"fan_avail_continuous", "baseline_continuous"}:
        return apply_fan_avail_continuous(src, dest)
    if name in {"fan_avail_occupied_office", "schedule_occupied"}:
        return apply_fan_avail_occupied_office(src, dest)
    if name in {"gl36_airside_proxy", "gl36_proxy"}:
        return apply_gl36_airside_proxy(
            src,
            dest,
            vav_min_fraction=float(params.get("vav_min_fraction") or 0.15),
            fan_pressure_pa=float(params.get("fan_pressure_pa") or 400.0),
            fan_power_min_fraction=float(params.get("fan_power_min_fraction") or 0.15),
        )
    raise ValueError(f"Unknown idf_patch name: {name}")


def run_easy_button(
    profile_path: Path,
    *,
    skip_ecm2: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    if dry_run:
        return plan_dry_run(profile_path)

    profile = load_profile(profile_path)
    ep = profile.get("energyplus") or {}
    prototype = resolve_path(ep.get("prototype_idf"), DEFAULT_PROTOTYPE_IDF)
    epw = resolve_path(ep.get("epw"), DEFAULT_MADISON_EPW)
    elec_rate, gas_rate = _rates(profile)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = ARTIFACTS / f"wattlab_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    measures = approved_measures(profile)
    if skip_ecm2:
        measures = [m for m in measures if "GL36" not in (m.get("measure_id") or "")]

    # --- baseline: continuous fan avail (SCHED-247 inefficient archetype) ---
    baseline_idf = run_dir / "baseline.idf"
    baseline_patch_name = ep.get("baseline_idf_patch") or "fan_avail_continuous"
    patch_meta = _apply_patch(baseline_patch_name, prototype, baseline_idf)
    base_out = run_dir / "sim_baseline"
    sim_meta = simulate(baseline_idf, epw, base_out)
    annual = annual_from_output_dir(
        base_out, elec_rate_usd_per_kwh=elec_rate, gas_rate_usd_per_therm=gas_rate
    )
    records: list[dict] = []
    baseline_record = build_result_record(
        run_id=f"{run_id}_baseline",
        measure_id=None,
        idf_path=baseline_idf,
        annual=annual,
        artifacts=[str(base_out / "eplustbl.htm"), str(baseline_idf)],
        extra_flags=["uncalibrated", "conceptual_screening", "openfdd_wattlab"],
    )
    records.append(baseline_record)
    (run_dir / "result_record_baseline.json").write_text(
        json.dumps(baseline_record, indent=2), encoding="utf-8"
    )

    current_idf = baseline_idf
    after_ecm1_annual: dict | None = None
    after_ecm2_annual: dict | None = None
    patch_log = [patch_meta]

    for m in measures:
        mid = m["measure_id"]
        pname = ((m.get("idf_patch") or {}).get("name")) or ""
        if not pname:
            continue
        next_idf = run_dir / f"{mid}.idf"
        meta = _apply_patch(pname, current_idf, next_idf, m)
        patch_log.append(meta)
        out = run_dir / f"sim_{mid}"
        simulate(next_idf, epw, out)
        ann = annual_from_output_dir(
            out, elec_rate_usd_per_kwh=elec_rate, gas_rate_usd_per_therm=gas_rate
        )
        rr = build_result_record(
            run_id=f"{run_id}_{mid}",
            measure_id=mid,
            idf_path=next_idf,
            annual=ann,
            artifacts=[str(out / "eplustbl.htm"), str(next_idf)],
            extra_flags=list(meta.get("flags") or []) + ["openfdd_wattlab"],
        )
        records.append(rr)
        (run_dir / f"result_record_{mid}.json").write_text(
            json.dumps(rr, indent=2), encoding="utf-8"
        )
        if "SCHED" in mid or "SCHED" in pname.upper() or "occupied" in pname:
            after_ecm1_annual = ann
        if "GL36" in mid:
            after_ecm2_annual = ann
        current_idf = next_idf

    lit = validate_against_literature(
        baseline=baseline_record.get("annual") or {},
        after_ecm1=(after_ecm1_annual or {}),
        after_ecm2=(after_ecm2_annual or None),
    )

    report = {
        "product": PRODUCT,
        "run_id": run_id,
        "project_id": profile.get("project_id"),
        "display_name": profile.get("display_name"),
        "disclaimer": profile.get("disclaimer") or DISCLAIMER,
        "prototype_idf": str(prototype),
        "prototype_sha256": file_sha256(prototype),
        "epw": str(epw),
        "epw_note": ep.get("epw_note") or DEFAULT_EPW_NOTE,
        "baseline_sim": sim_meta,
        "patches": patch_log,
        "result_records": records,
        "literature_validation": lit,
        "artifacts_dir": str(run_dir),
    }
    (run_dir / "wattlab_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    shutil.copy2(profile_path, run_dir / "building_profile.json")
    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=f"{PRODUCT} easy button (EnergyPlus)")
    p.add_argument(
        "--building",
        type=Path,
        default=ROOT / "examples" / "buildings" / "madison_office.json",
        help="Building profile JSON",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-ecm2", action="store_true")
    args = p.parse_args(argv)
    building = args.building
    if not building.is_absolute():
        building = (ROOT / building).resolve()
    report = run_easy_button(building, skip_ecm2=args.skip_ecm2, dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    if args.dry_run:
        return 0
    ok = all(r.get("status") == "COMPLETE" for r in report.get("result_records") or [])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
