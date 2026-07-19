"""Turnkey dump → gaps → profile → bridge → (optional) calibrate / ECM plan.

Generalized for any vibe19 WattLab dump zip. No building-ID hardcoding.
Codex / agents: start here.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

from wattlab.bridge import merge_into_profile, suggest_from_bundle
from wattlab.config import ACTUAL_YEAR_CALIBRATION, ARTIFACTS, weather_suitability
from wattlab.defaults import resolve_profile
from wattlab.seed import gap_report, load_bundle

REQUIRED_FIELDS = ("building_type", "city", "floor_area_ft2")
Opener = Callable[[str], bytes]


def _parse_window_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    text = str(raw).strip().replace("Z", "+00:00")
    try:
        if "T" in text or " " in text:
            return datetime.fromisoformat(text).date()
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def maybe_build_amy_from_open_meteo(
    seed: dict[str, Any],
    out_dir: Path,
    *,
    has_observed_weather: bool,
    opener: Opener | None = None,
) -> dict[str, Any] | None:
    """When dump lacks weather_observed but has lat/lon + data_window, fetch AMY.

    Writes ``amy.epw`` + vibe19-shaped ``weather_observed.csv`` into ``out_dir``.
    Returns weather artifact metadata, or None when prerequisites are missing.
    """
    if has_observed_weather:
        return None
    lat = seed.get("lat")
    lon = seed.get("lon")
    if lat is None or lon is None:
        return None
    window = seed.get("data_window") or {}
    start = _parse_window_date(
        window.get("start_utc") or window.get("start") or window.get("start_date")
    )
    end = _parse_window_date(
        window.get("end_utc") or window.get("end") or window.get("end_date")
    )
    if start is None or end is None:
        return None

    from wattlab.contracts import WeatherRequest
    from wattlab.weather.epw import build_amy_epw, utc_frame_to_local_standard
    from wattlab.weather.open_meteo import download_archive_weather

    request = WeatherRequest(
        latitude=float(lat),
        longitude=float(lon),
        start_date=start,
        end_date=end,
        allow_partial=True,
    )
    cache_dir = out_dir / "open_meteo_cache"
    df, meta = download_archive_weather(request, cache_dir, opener=opener)

    # Persist vibe19-compatible observed weather for calibrate.py
    wx_csv = out_dir / "weather_observed.csv"
    export = df.reset_index()
    # index name may be timestamp_utc
    ts_col = export.columns[0]
    export = export.rename(
        columns={
            ts_col: "timestamp_utc",
            "dry_bulb_f": "web-outside-air-temp",
            "dew_point_f": "web-outside-air-dewpoint",
            "relative_humidity_pct": "web-outside-air-humidity",
        }
    )
    keep = [
        c
        for c in (
            "timestamp_utc",
            "web-outside-air-temp",
            "web-outside-air-dewpoint",
            "web-outside-air-humidity",
            "surface_pressure_hpa",
            "shortwave_radiation_wm2",
            "direct_normal_irradiance_wm2",
            "diffuse_radiation_wm2",
            "wind_speed_mph",
            "wind_direction_deg",
        )
        if c in export.columns
    ]
    export[keep].to_csv(wx_csv, index=False)

    epw_path = out_dir / "amy.epw"
    tz_hours = int(round(float(lon) / 15.0))
    full_year = start.month == 1 and start.day == 1 and end.month == 12 and end.day == 31
    if full_year:
        local = utc_frame_to_local_standard(df, tz_hours=tz_hours)
        epw_meta = build_amy_epw(
            local,
            epw_path,
            lat=float(lat),
            lon=float(lon),
            location_name=str(seed.get("project_id") or "OpenFDD_AMY"),
            coverage_mode="annual",
            tz_hours=tz_hours,
        )
    else:
        epw_meta = build_amy_epw(
            df,
            epw_path,
            lat=float(lat),
            lon=float(lon),
            location_name=str(seed.get("project_id") or "OpenFDD_AMY"),
            coverage_mode="partial",
        )

    wx = weather_suitability(
        source="amy",
        epw_note=(
            f"AMY EPW from Open-Meteo archive ({meta.source}, "
            f"{start.isoformat()}..{end.isoformat()}, sha256={meta.sha256[:12]}…)"
        ),
        city_id=str(seed.get("city") or ""),
    )
    return {
        "status": "READY",
        "mode": ACTUAL_YEAR_CALIBRATION,
        "weather_observed_csv": str(wx_csv),
        "amy_epw": str(epw_path),
        "open_meteo": {
            "source": meta.source,
            "sha256": meta.sha256,
            "rows": meta.rows,
            "cached_path": meta.cached_path,
            "start_date": str(meta.start_date),
            "end_date": str(meta.end_date),
        },
        "epw_meta": epw_meta,
        "weather_suitability": wx,
    }


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
    opener: Opener | None = None,
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
            "Optional recommended: floors, utility rates, utility_bills, lat/lon, "
            "data_window, custom_idf / prototype_idf.",
        ]
        (out / "intake_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        report["intake_report"] = str(out / "intake_report.json")
        return report

    # Open-Meteo AMY when dump has no weather_observed but lat/lon + window exist
    amy_info: dict[str, Any] | None = None
    try:
        amy_info = maybe_build_amy_from_open_meteo(
            seed,
            out,
            has_observed_weather=bool(bundle.has_observed_weather),
            opener=opener,
        )
    except Exception as exc:  # noqa: BLE001 — network/validation must not kill intake
        report["amy_weather"] = {
            "status": "FAILED",
            "reason": str(exc),
            "note": "Open-Meteo AMY fetch failed; continuing with TMY/proxy epw from defaults.",
        }
        amy_info = None
    if amy_info:
        report["amy_weather"] = {
            k: amy_info[k]
            for k in (
                "status",
                "mode",
                "weather_observed_csv",
                "amy_epw",
                "open_meteo",
                "weather_suitability",
            )
            if k in amy_info
        }
        seed["epw"] = amy_info["amy_epw"]
        seed["amy_epw"] = amy_info["amy_epw"]
        seed["epw_note"] = (amy_info.get("weather_suitability") or {}).get("epw_note")
        seed_path.write_text(json.dumps(seed, indent=2, default=str), encoding="utf-8")
        report["evidence_available"]["has_weather"] = True
        report["evidence_available"]["weather_source"] = "open_meteo_amy"

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
            "prototype_idf",
            "custom_idf",
            "epw",
            "amy_epw",
            "epw_note",
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

    # Stamp AMY EPW onto energyplus block for easy-button / ECM screens
    if amy_info:
        ep = dict(profile.get("energyplus") or {})
        ep["epw"] = amy_info["amy_epw"]
        ep["epw_note"] = (amy_info.get("weather_suitability") or {}).get("epw_note")
        ep["weather_suitability"] = amy_info.get("weather_suitability")
        profile["energyplus"] = ep
        fs = dict(profile.get("field_sources") or {})
        fs["epw"] = {
            "value": amy_info["amy_epw"],
            "source": "open_meteo",
            "note": ep.get("epw_note"),
        }
        profile["field_sources"] = fs

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
        "If weather_observed or Open-Meteo AMY present: wattlab calibrate --bundle … "
        "(or re-run twin with --calibrate).",
        "Screen ECMs: wattlab easy-button --profile resolved_profile.json "
        f"--measure-set {measure_set or 'better'} --dry-run",
        "Live sims need Docker image energyplus-mcp-dev — never invent savings.",
        "Optional: pass custom_idf / prototype_idf in --inputs for a human IDF.",
    ]

    # Optional calibrate dry-run / live
    has_wx = bool(bundle.has_observed_weather) or bool(amy_info)
    if calibrate:
        if not has_wx:
            report["calibration"] = {
                "status": "NEEDS_INPUT",
                "reason": (
                    "weather_observed.csv missing and no lat/lon+data_window for Open-Meteo AMY"
                ),
            }
            report["status"] = "NEEDS_INPUT"
        else:
            from wattlab.calibrate import run_calibration

            # Prefer dump root; if AMY was fetched into out/, stage a cal bundle there
            if amy_info and root is not None:
                cal_bundle = out / "cal_bundle"
                cal_bundle.mkdir(parents=True, exist_ok=True)
                import shutil

                for name in (
                    "operating_signatures.csv",
                    "utility_bills.csv",
                    "fdd_findings.csv",
                    "fdd_summary.csv",
                ):
                    src = Path(root) / name
                    if src.is_file():
                        shutil.copy2(src, cal_bundle / name)
                shutil.copy2(amy_info["weather_observed_csv"], cal_bundle / "weather_observed.csv")
                shutil.copy2(seed_path, cal_bundle / "model_seed.json")
                cal = run_calibration(
                    cal_bundle,
                    seed_path=cal_bundle / "model_seed.json",
                    dry_run=dry_run,
                    lat=float(seed["lat"]) if seed.get("lat") is not None else None,
                    lon=float(seed["lon"]) if seed.get("lon") is not None else None,
                )
            else:
                cal_bundle = root if root is not None else dump_path
                cal = run_calibration(
                    Path(cal_bundle),
                    seed_path=seed_path,
                    dry_run=dry_run,
                    lat=float(seed["lat"]) if seed.get("lat") is not None else None,
                    lon=float(seed["lon"]) if seed.get("lon") is not None else None,
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
