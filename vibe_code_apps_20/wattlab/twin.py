"""Turnkey dump → gaps → profile → bridge → (optional) calibrate / ECM plan.

Generalized for any vibe19 WattLab dump zip. No building-ID hardcoding.
Codex / agents: start here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wattlab.bridge import merge_into_profile, suggest_from_bundle
from wattlab.config import ARTIFACTS
from wattlab.defaults import resolve_profile
from wattlab.seed import gap_report, load_bundle

REQUIRED_FIELDS = ("building_type", "city", "floor_area_ft2")


def _dump_root(bundle) -> Path | None:
    """Best-effort path to the extracted dump root (for bridge/calibrate file IO)."""
    for name in ("model_seed.json", "run_report.json", "MANIFEST.json", "fdd_summary.csv"):
        p = bundle.files.get(name)
        if p is not None:
            return Path(p).parent
    if bundle.fdd_timeseries_dir is not None:
        return Path(bundle.fdd_timeseries_dir).parent
    return None


def _merge_inputs(seed: dict[str, Any], inputs: dict[str, Any] | None) -> dict[str, Any]:
    """Overlay human/agent answers onto the data-derived model seed."""
    out = dict(seed or {})
    if not inputs:
        return out
    for key, val in inputs.items():
        if val is None or val == "":
            continue
        if key == "utility" and isinstance(val, dict) and isinstance(out.get("utility"), dict):
            merged = dict(out["utility"])
            merged.update(val)
            out["utility"] = merged
        else:
            out[key] = val
    fs = dict(out.get("field_sources") or {})
    for key in inputs:
        if inputs[key] in (None, ""):
            continue
        fs[key] = {"source": "user", "value": inputs[key]}
    out["field_sources"] = fs
    return out


def _required_missing(seed: dict[str, Any], gaps: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    for field in REQUIRED_FIELDS:
        val = seed.get(field)
        if val in (None, "", {}, []):
            missing.append(field)
    # Also honor gap_report required rows still missing after merge
    for g in gaps:
        if g.get("severity") == "required" and g.get("status") == "missing":
            if g["field"] not in missing and seed.get(g["field"]) in (None, "", {}, []):
                missing.append(g["field"])
    return missing


def _manifest_summary(bundle) -> dict[str, Any]:
    man = bundle.manifest or {}
    files = man.get("files") or []
    return {
        "schema_version": man.get("schema_version"),
        "file_count": man.get("file_count") or len(files),
        "paths": [f.get("path") for f in files if isinstance(f, dict)][:40],
        "has_manifest": bool(man),
        "how_to_use_hint": (
            "Read MANIFEST.json first; each file has purpose + how_to_use. "
            "Artifacts are conditional — missing CSV means that slice was empty."
        ),
    }


def prepare_twin(
    dump_path: str | Path,
    *,
    inputs: dict[str, Any] | None = None,
    out_dir: str | Path | None = None,
    dry_run: bool = True,
    calibrate: bool = False,
    measure_set: str | None = None,
    extract_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Prepare a digital-twin intake from any vibe19 WattLab dump.

    Returns an ``intake_report`` dict with status:
    - ``NEEDS_INPUT`` when required fields (building_type, city, floor_area_ft2) missing
    - ``READY`` when profile + bridge are written (dry-run plan for ECM)
    - ``COMPLETE`` when optional calibrate / easy-button plan steps finish

    Never invents building characteristics. Never hardcodes a building ID.
    """
    dump_path = Path(dump_path)
    bundle = load_bundle(dump_path, extract_dir=extract_dir)
    root = _dump_root(bundle)
    seed = _merge_inputs(bundle.model_seed or {}, inputs)
    # Temporary seed for gap evaluation after merge
    bundle.model_seed = seed
    gaps = gap_report(bundle)
    missing = _required_missing(seed, gaps)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    started = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out = Path(out_dir) if out_dir else ARTIFACTS / f"twin_intake_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "product": "OpenFDD WattLab Twin Intake",
        "status": "NEEDS_INPUT" if missing else "READY",
        "run_id": run_id,
        "started_at": started,
        "dump_path": str(dump_path),
        "dump_root": str(root) if root else None,
        "building_id": bundle.building_id,
        "manifest": _manifest_summary(bundle),
        "summary": bundle.summary(),
        "gaps": gaps,
        "required_missing": missing,
        "ask_human": [
            {
                "field": f,
                "why": next((g["why"] for g in gaps if g["field"] == f), "Required for prototype selection"),
            }
            for f in missing
        ],
        "evidence_available": {
            "has_weather": bundle.has_observed_weather,
            "has_bills": bundle.has_bills,
            "has_operating_signatures": not bundle.operating_signatures.empty,
            "has_fdd_findings": not bundle.fdd_findings.empty,
            "has_fdd_summary": not bundle.fdd_summary.empty,
            "has_diurnal": not bundle.sensor_diurnal_24h.empty,
            "has_fdd_timeseries": bool(bundle.fdd_timeseries_dir and bundle.fdd_timeseries_dir.is_dir()),
            "schedule_hints": bool((seed.get("schedule_hints") or {})),
        },
        "next_steps": [],
        "artifacts_dir": str(out),
        "dry_run": dry_run,
    }

    # Persist merged seed for downstream calibrate / human review
    seed_path = out / "model_seed_resolved.json"
    seed_path.write_text(json.dumps(seed, indent=2, default=str), encoding="utf-8")
    report["model_seed_resolved"] = str(seed_path)

    if missing:
        report["next_steps"] = [
            "Ask the human for required_missing fields (building_type, city, floor_area_ft2).",
            "Re-run: wattlab twin <dump.zip> --inputs answers.json --out <dir>",
            "Do NOT invent office/Madison/Chicago defaults for a real building.",
            "Optional recommended: floors, utility rates, utility_bills, lat/lon.",
        ]
        (out / "intake_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        report["intake_report"] = str(out / "intake_report.json")
        return report

    # Resolve profile + bridge FDD → measures
    minimal = {
        k: seed[k]
        for k in (
            "building_type",
            "city",
            "code_year",
            "floor_area_ft2",
            "floors",
            "floor_to_floor_ft",
            "wwr",
            "hvac",
            "utility",
            "project_id",
            "display_name",
            "anonymized",
            "lat",
            "lon",
        )
        if seed.get(k) is not None
    }
    # conditioned_floor_area_ft2 alias for resolve_profile
    if "floor_area_ft2" in minimal and "conditioned_floor_area_ft2" not in minimal:
        minimal["conditioned_floor_area_ft2"] = minimal["floor_area_ft2"]

    profile = resolve_profile(minimal)
    bridge_src = root if root is not None else dump_path
    bridge = suggest_from_bundle(bridge_src)
    profile = merge_into_profile(profile, bridge)

    profile_path = out / "resolved_profile.json"
    profile_path.write_text(json.dumps(profile, indent=2, default=str), encoding="utf-8")
    bridge_path = out / "bridge.json"
    bridge_path.write_text(json.dumps(bridge, indent=2, default=str), encoding="utf-8")
    report["resolved_profile"] = str(profile_path)
    report["bridge"] = {
        "path": str(bridge_path),
        "measure_ids": bridge.get("measure_ids") or [],
        "evidence_count": len(bridge.get("evidence") or []),
        "stats": bridge.get("stats") or {},
    }

    report["next_steps"] = [
        "Review resolved_profile.json provenance (field_sources).",
        "Review bridge.json suggested measures (from fdd_findings / fdd_summary).",
        "If weather_observed present: wattlab calibrate --bundle <dump_root> "
        "(or re-run twin with --calibrate).",
        "Screen ECMs: wattlab easy-button --profile resolved_profile.json "
        f"--measure-set {measure_set or 'better'} --dry-run",
        "Live sims need Docker image energyplus-mcp-dev — never invent savings.",
    ]

    # Optional calibrate dry-run / live
    if calibrate:
        if not bundle.has_observed_weather:
            report["calibration"] = {
                "status": "NEEDS_INPUT",
                "reason": "weather_observed.csv missing — cannot build AMY EPW",
            }
            report["status"] = "NEEDS_INPUT"
        else:
            from wattlab.calibrate import run_calibration

            cal_bundle = root if root is not None else dump_path
            # Write resolved seed next to calibrate inputs if we have a root
            if root is not None:
                # Prefer resolved seed for calibration identity fields
                cal = run_calibration(
                    Path(cal_bundle),
                    seed_path=seed_path,
                    dry_run=dry_run,
                    lat=float(seed["lat"]) if seed.get("lat") is not None else None,
                    lon=float(seed["lon"]) if seed.get("lon") is not None else None,
                )
            else:
                cal = run_calibration(
                    Path(cal_bundle),
                    seed_path=seed_path,
                    dry_run=dry_run,
                )
            report["calibration"] = cal
            if not dry_run and cal.get("status"):
                report["status"] = "COMPLETE"

    # Optional easy-button dry-run plan
    if measure_set:
        from wattlab.easy_button import run_easy_button

        plan = run_easy_button(
            profile=profile,
            measure_set=measure_set,
            dry_run=True,
        )
        plan_path = out / "ecm_plan_dry_run.json"
        plan_path.write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
        report["ecm_plan"] = str(plan_path)
        report["ecm_measure_ids"] = plan.get("approved_measure_ids") or []

    if report["status"] == "READY" and not dry_run and not calibrate:
        # Profile written; screening still conceptual until calibrate/bills
        report["status"] = "READY"

    (out / "intake_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    report["intake_report"] = str(out / "intake_report.json")
    return report


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(
        prog="wattlab twin",
        description=(
            "Turnkey vibe19 dump -> gap checklist -> resolved profile -> FDD bridge. "
            "Generalized for any building; never invents type/city/area."
        ),
    )
    p.add_argument("dump", type=Path, help="WattLab dump zip or extracted folder")
    p.add_argument(
        "--inputs",
        type=Path,
        default=None,
        help="JSON with human answers: building_type, city, floor_area_ft2, floors, utility, …",
    )
    p.add_argument("--out", type=Path, default=None, help="Output directory for intake artifacts")
    p.add_argument(
        "--calibrate",
        action="store_true",
        help="Also run calibration (requires weather_observed + required inputs)",
    )
    p.add_argument(
        "--measure-set",
        default=None,
        help="If set, write an easy-button dry-run ECM plan for this set (good|better|best)",
    )
    p.add_argument(
        "--live",
        action="store_true",
        help="Allow live EnergyPlus calibrate (default is dry-run for calibrate)",
    )
    args = p.parse_args(argv)

    inputs: dict[str, Any] | None = None
    if args.inputs:
        inputs = json.loads(args.inputs.read_text(encoding="utf-8"))
        if not isinstance(inputs, dict):
            print("--inputs must be a JSON object", file=sys.stderr)
            return 2

    report = prepare_twin(
        args.dump,
        inputs=inputs,
        out_dir=args.out,
        dry_run=not args.live,
        calibrate=args.calibrate,
        measure_set=args.measure_set,
    )
    print(json.dumps(report, indent=2, default=str))
    if report.get("status") == "NEEDS_INPUT":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
