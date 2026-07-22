"""OpenFDD WattLab easy button — prototype IDF + EPW → baseline → progressive ECMs.

Usage:
  python easy_button.py --building examples/buildings/madison_office.json --dry-run
  python easy_button.py --building examples/buildings/madison_office.json
  python easy_button.py --minimal "{\"building_type\":\"office\",\"city\":\"madison\",\"measure_set\":\"best\"}"
  python easy_button.py --building examples/buildings/madison_office.json --measure-set better
"""

from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wattlab.config import (
    ARTIFACTS,
    DEFAULT_ELEC_RATE_USD_PER_KWH,
    DEFAULT_EPW_NOTE,
    DEFAULT_GAS_RATE_USD_PER_THERM,
    DEFAULT_MADISON_EPW,
    DEFAULT_PROTOTYPE_IDF,
    PROTOTYPE_AREA_FT2_NOMINAL,
    ROOT,
    artifacts_root,
    weather_suitability,
)
from wattlab.measures.measure_sets import expand_measure_set, list_measure_sets
from wattlab.energyplus.mcp import simulate
from wattlab.energyplus.patches import apply_monthly_energy_tables
from wattlab.energyplus.patches.registry import apply_patch as registry_apply_patch
from wattlab.energyplus.results import (
    annual_from_output_dir,
    build_result_record,
    file_sha256,
    savings_by_measure,
)
from wattlab.energyplus.manifest import build_run_manifest, write_run_manifest


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


def approved_measures(profile: dict, measure_set: str | None = None) -> list[dict]:
    """Return ordered measures: explicit measure_set expands, else approved profile measures."""
    set_id = measure_set or profile.get("measure_set")
    if set_id:
        return expand_measure_set(str(set_id))
    return [
        m
        for m in profile.get("measures") or []
        if (m.get("review_status") or "").lower() == "approved"
    ]


def plan_dry_run(profile_path: Path, measure_set: str | None = None) -> dict[str, Any]:
    profile = load_profile(profile_path)
    ep = profile.get("energyplus") or {}
    prototype = resolve_path(ep.get("prototype_idf"), DEFAULT_PROTOTYPE_IDF)
    epw = resolve_path(ep.get("epw"), DEFAULT_MADISON_EPW)
    epw_note = ep.get("epw_note") or DEFAULT_EPW_NOTE
    city_id = str((profile.get("location") or {}).get("city_id") or profile.get("city") or "")
    wx = weather_suitability(epw_path=epw, epw_note=epw_note, city_id=city_id)
    measures = approved_measures(profile, measure_set)
    steps: list[dict[str, Any]] = [
        {
            "step": "select_prototype",
            "prototype_idf": str(prototype),
            "epw": str(epw),
            "epw_note": epw_note,
            "weather_suitability": wx,
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
        "measure_set": measure_set or profile.get("measure_set"),
        "weather_suitability": wx,
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
    """Compatibility facade over the patch registry (dispatch moved there)."""
    patch = (measure or {}).get("idf_patch") or {}
    params = patch.get("params") or {}
    return registry_apply_patch(name, src, dest, params)


def run_easy_button(
    profile_path: Path | None = None,
    *,
    profile: dict[str, Any] | None = None,
    skip_ecm2: bool = False,
    dry_run: bool = False,
    measure_set: str | None = None,
    progress_dir: Path | str | None = None,
) -> dict[str, Any]:
    if profile is None:
        if profile_path is None:
            raise ValueError("profile_path or profile required")
        if dry_run:
            return plan_dry_run(profile_path, measure_set)
        profile = load_profile(profile_path)
    elif dry_run and profile_path is not None:
        return plan_dry_run(profile_path, measure_set)
    elif dry_run:
        # dry-run from in-memory profile
        tmp = ARTIFACTS / "_dry_profile.json"
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(profile), encoding="utf-8")
        return plan_dry_run(tmp, measure_set)

    ep = profile.get("energyplus") or {}
    prototype = resolve_path(ep.get("prototype_idf"), DEFAULT_PROTOTYPE_IDF)
    epw = resolve_path(ep.get("epw"), DEFAULT_MADISON_EPW)
    epw_note = ep.get("epw_note") or DEFAULT_EPW_NOTE
    city_id = str((profile.get("location") or {}).get("city_id") or profile.get("city") or "")
    wx = weather_suitability(epw_path=epw, epw_note=epw_note, city_id=city_id)
    elec_rate, gas_rate = _rates(profile)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    art_root = artifacts_root()

    # Claim Studio runs/<id> early so Twin can poll progress.json mid-DinD.
    studio_progress: Path | None = Path(progress_dir) if progress_dir else None
    if studio_progress is not None:
        run_id = studio_progress.name
        studio_progress.mkdir(parents=True, exist_ok=True)
        try:
            from wattlab.energyplus.docker import write_progress

            write_progress(studio_progress, percent=0, status="running", note="easy-button")
        except Exception:  # noqa: BLE001
            pass
    else:
        try:
            from wattlab.energyplus.docker import write_progress
            from wattlab.studio.workspace import runs_dir

            studio_progress = runs_dir() / run_id
            studio_progress.mkdir(parents=True, exist_ok=True)
            write_progress(studio_progress, percent=0, status="running", note="easy-button claimed")
        except Exception:  # noqa: BLE001
            studio_progress = None

    run_dir = art_root / f"wattlab_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    measures = approved_measures(profile, measure_set)

    if skip_ecm2:
        measures = [
            m
            for m in measures
            if "GL36" not in (m.get("measure_id") or "")
            and "SAT" not in (m.get("measure_id") or "")
        ]

    # --- baseline: continuous fan avail (SCHED-247 inefficient archetype) ---
    # First ensure monthly facility meters so eplustbl carries the monthly
    # BUILDING ENERGY PERFORMANCE tables (G14 bill gate needs them).
    prepped_idf = run_dir / "prototype_prepped.idf"
    monthly_meta = apply_monthly_energy_tables(prototype, prepped_idf)
    # Partial-year AMY / short EPW: align RunPeriod or EnergyPlus fatals on EOF.
    run_period_meta: dict[str, Any] | None = None
    try:
        from wattlab.weather.epw import epw_data_period
        from wattlab.energyplus.patches import apply_run_period

        span = epw_data_period(epw)
        if span and not span.get("full_calendar_year"):
            aligned = run_dir / "prototype_runperiod.idf"
            run_period_meta = apply_run_period(
                prepped_idf,
                aligned,
                begin=span["begin"],
                end=span["end"],
            )
            run_period_meta["reason"] = (
                f"EPW span {span['begin']}→{span['end']} is not a full calendar year; "
                "RunPeriod auto-aligned (partial-year AMY)."
            )
            prepped_idf = aligned
    except Exception as exc:  # noqa: BLE001 — never block baseline on span probe
        run_period_meta = {"patch": "run_period", "error": str(exc)}
    baseline_idf = run_dir / "baseline.idf"
    baseline_patch_name = ep.get("baseline_idf_patch") or "fan_avail_continuous"
    patch_meta = _apply_patch(baseline_patch_name, prepped_idf, baseline_idf)
    patch_log: list[dict[str, Any]] = [monthly_meta, patch_meta]
    if run_period_meta:
        patch_log.insert(1, run_period_meta)
    base_out = run_dir / "sim_baseline"
    sim_meta = simulate(baseline_idf, epw, base_out, progress_dir=studio_progress)
    sizing_scenario = "autosize"
    hard_size = (ep.get("hard_size") or profile.get("hard_size") or {})
    if isinstance(hard_size, dict) and (
        hard_size.get("cooling_tons") is not None or hard_size.get("fan_hp") is not None
    ):
        from wattlab.energyplus.sizing import (
            freeze_autosized_values,
            nameplate_to_capacity_factors,
            parse_sizing_inventory,
        )

        inv = parse_sizing_inventory(base_out)
        area_ft2 = float(
            profile.get("conditioned_floor_area_ft2") or profile.get("floor_area_ft2") or 0
        )
        area_scale = (
            area_ft2 / PROTOTYPE_AREA_FT2_NOMINAL if area_ft2 > 0 else None
        )
        factors, factor_meta = nameplate_to_capacity_factors(
            inv,
            cooling_tons=(
                float(hard_size["cooling_tons"])
                if hard_size.get("cooling_tons") is not None
                else None
            ),
            fan_hp=(
                float(hard_size["fan_hp"]) if hard_size.get("fan_hp") is not None else None
            ),
            prototype_area_scale=area_scale,
        )
        patch_log.append({"patch": "hard_size_factors", **factor_meta, "factors": factors})
        if factor_meta.get("hard_size_refused"):
            sizing_scenario = "hard_size_refused"
            patch_log.append(
                {
                    "patch": "hard_size",
                    "ok": False,
                    "needs_input": True,
                    "note": factor_meta.get("refuse_reason")
                    or "Hard-size factors out of band; kept autosize (NEEDS_INPUT).",
                    "refused_factors": factor_meta.get("refused_factors"),
                }
            )
        elif factors:
            hard_idf = run_dir / "baseline_hard_size.idf"
            freeze_meta = freeze_autosized_values(
                baseline_idf, hard_idf, inv, capacity_factors=factors
            )
            patch_log.append(freeze_meta)
            baseline_idf = hard_idf
            base_out = run_dir / "sim_baseline_hard"
            sim_meta = simulate(baseline_idf, epw, base_out, progress_dir=studio_progress)
            sizing_scenario = "hard_size"
        else:
            sizing_scenario = "autosize_observe_hard_size_unavailable"
            patch_log.append(
                {
                    "patch": "hard_size",
                    "ok": False,
                    "note": "Nameplate provided but autosized inventory lacked comparable fields; kept autosize.",
                }
            )
    annual = annual_from_output_dir(
        base_out, elec_rate_usd_per_kwh=elec_rate, gas_rate_usd_per_therm=gas_rate
    )
    records: list[dict] = []
    baseline_flags = ["uncalibrated", "conceptual_screening", "openfdd_wattlab"]
    if sizing_scenario == "hard_size":
        baseline_flags.append("hard_size_nameplate")
    elif sizing_scenario == "hard_size_refused":
        baseline_flags.append("hard_size_refused_needs_input")
    baseline_record = build_result_record(
        run_id=f"{run_id}_baseline",
        measure_id=None,
        idf_path=baseline_idf,
        annual=annual,
        artifacts=[str(base_out / "eplustbl.htm"), str(baseline_idf)],
        extra_flags=baseline_flags,
    )
    records.append(baseline_record)
    (run_dir / "result_record_baseline.json").write_text(
        json.dumps(baseline_record, indent=2), encoding="utf-8"
    )

    current_idf = baseline_idf
    after_ecm1_annual: dict | None = None
    after_ecm2_annual: dict | None = None

    for m in measures:
        mid = m["measure_id"]
        pname = ((m.get("idf_patch") or {}).get("name")) or ""
        if not pname:
            continue
        next_idf = run_dir / f"{mid}.idf"
        meta = _apply_patch(pname, current_idf, next_idf, m)
        patch_log.append(meta)
        out = run_dir / f"sim_{mid}"
        simulate(next_idf, epw, out, progress_dir=studio_progress)
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
    savings = savings_by_measure(records)

    # ESCO proxy crosscheck: profile may carry proxy_savings
    # (measure_id -> {savings_kwh, savings_therms?}) from wattlab.bench.
    crosscheck_block: dict[str, Any] | None = None
    proxy_savings = profile.get("proxy_savings") or {}
    if proxy_savings:
        from wattlab.crosscheck import crosscheck_report, prototype_area_scale

        bills = (profile.get("utility") or {}).get("bills_monthly_kwh")
        baseline_monthly = [
            float(m["electricity_kwh"])
            for m in baseline_record.get("monthly") or []
            if m.get("electricity_kwh") is not None
        ] or None
        area_scale = prototype_area_scale(
            target_ft2=profile.get("conditioned_floor_area_ft2")
            or profile.get("floor_area_ft2"),
            model_area_m2=(baseline_record.get("annual") or {}).get("building_area_m2"),
        )
        crosscheck_block = crosscheck_report(
            savings,
            proxy_savings,
            bills_monthly_kwh=bills,
            baseline_monthly_kwh=baseline_monthly,
            area_scale=area_scale,
        )

    finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    final_idf = current_idf
    manifest = build_run_manifest(
        run_id=run_id,
        run_dir=run_dir,
        idf_path=final_idf,
        epw_path=epw,
        patches=patch_log,
        weather_suitability=wx,
        status="SUCCESS",
        started_at=started_at,
        finished_at=finished_at,
        extra={
            "baseline_idf_sha256": file_sha256(baseline_idf) if baseline_idf.is_file() else None,
            "prototype_sha256": file_sha256(prototype) if prototype.is_file() else None,
            "product": PRODUCT,
        },
    )
    write_run_manifest(run_dir, manifest)

    report = {
        "product": PRODUCT,
        "run_id": run_id,
        "project_id": profile.get("project_id"),
        "display_name": profile.get("display_name"),
        "disclaimer": profile.get("disclaimer") or DISCLAIMER,
        "measure_set": measure_set or profile.get("measure_set"),
        "prototype_idf": str(prototype),
        "prototype_sha256": file_sha256(prototype),
        "prototype_area_ft2_nominal": PROTOTYPE_AREA_FT2_NOMINAL,
        "target_floor_area_ft2": float(
            profile.get("conditioned_floor_area_ft2") or profile.get("floor_area_ft2") or 0
        )
        or None,
        "prototype_area_scale": (
            float(profile.get("conditioned_floor_area_ft2") or profile.get("floor_area_ft2") or 0)
            / PROTOTYPE_AREA_FT2_NOMINAL
            if float(profile.get("conditioned_floor_area_ft2") or profile.get("floor_area_ft2") or 0)
            > 0
            else None
        ),
        "area_honesty": (
            "Results are for the unscaled 5ZoneAirCooled prototype footprint "
            f"(~{PROTOTYPE_AREA_FT2_NOMINAL:.0f} ft2). Target floor_area_ft2 does not resize "
            "the IDF — compare EUI / use prototype_area_scale for screening only; "
            "do not claim calibrated building savings without a scaled or site-specific model."
        ),
        "sizing_scenario": sizing_scenario,
        "hard_size": hard_size if isinstance(hard_size, dict) and hard_size else None,
        "epw": str(epw),
        "epw_note": epw_note,
        "weather_suitability": wx,
        "run_manifest": manifest,
        "baseline_sim": sim_meta,
        "patches": patch_log,
        "result_records": records,
        "savings_by_measure": savings,
        "crosscheck": crosscheck_block,
        "literature_validation": lit,
        "field_sources": profile.get("field_sources"),
        "artifacts_dir": str(run_dir),
    }
    (run_dir / "wattlab_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )

    (run_dir / "resolved_profile.json").write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )
    if profile_path is not None and profile_path.is_file():
        shutil.copy2(profile_path, run_dir / "building_profile.json")

    # Publish into Studio workspace so any external AI agent / human browser
    # Twin page can show APIHelper-08 panes without copying by hand.
    try:
        from wattlab.studio.ep_viz import publish_run_for_studio
        from wattlab.studio.workspace import workspace_root

        _ = workspace_root()  # ensure env-aware root
        published = publish_run_for_studio(run_dir, run_id=run_id, report=report)
        report["studio_run_dir"] = str(published)
    except Exception as exc:
        report["studio_publish_error"] = str(exc)

    return report


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=f"{PRODUCT} easy button (EnergyPlus)")
    p.add_argument(
        "--building",
        type=Path,
        default=None,
        help="Building profile JSON",
    )
    p.add_argument(
        "--minimal",
        type=str,
        default=None,
        help="JSON string of responsive-defaults minimal inputs (uses wattlab_defaults)",
    )
    p.add_argument(
        "--minimal-file",
        type=Path,
        default=None,
        help="Path to JSON file of minimal inputs (preferred on PowerShell)",
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-ecm2", action="store_true")
    p.add_argument(
        "--measure-set",
        choices=[s["id"] for s in list_measure_sets()],
        default=None,
        help="Expand a measure set from measure_sets.json (overrides profile measures)",
    )
    args = p.parse_args(argv)

    profile: dict[str, Any] | None = None
    building: Path | None = None

    if args.minimal or args.minimal_file:
        from wattlab.defaults import resolve_profile

        if args.minimal_file:
            mf = args.minimal_file
            if not mf.is_absolute():
                mf = (ROOT / mf).resolve()
            minimal = json.loads(mf.read_text(encoding="utf-8-sig"))
        else:
            minimal = json.loads(args.minimal)
        if args.measure_set:
            minimal["measure_set"] = args.measure_set
        profile = resolve_profile(minimal)
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        building = ARTIFACTS / "_minimal_profile.json"
        building.write_text(json.dumps(profile, indent=2), encoding="utf-8")
    else:
        building = args.building or (
            ROOT / "examples" / "buildings" / "madison_office.json"
        )
        if not building.is_absolute():
            building = (ROOT / building).resolve()

    report = run_easy_button(
        building,
        profile=profile,
        skip_ecm2=args.skip_ecm2,
        dry_run=args.dry_run,
        measure_set=args.measure_set,
    )
    print(json.dumps(report, indent=2))
    if args.dry_run:
        return 0
    ok = all(r.get("status") == "COMPLETE" for r in report.get("result_records") or [])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
