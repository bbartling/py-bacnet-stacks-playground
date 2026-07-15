"""Multi-building Sketchbox test drive driven by examples/buildings/*.json.

Per building (integrity order):
  1. PROJECT — ASCII-safe name + State/City/Energy Code when enabled
  2. SCHEDULES — ASHRAE; zero thermostat offsets
  3. RESULTS — scrape true baseline
  4. SCHEDULES — apply *approved* measure offsets only
  5. RESULTS — scrape measure case
  6. Write schema-shaped result_record under .artifacts/<run_id>/

Usage:
  python testdrive.py --buildings examples/buildings
  python testdrive.py --buildings examples/buildings --limit 1
  python testdrive.py --dry-run --buildings examples/buildings
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import ROOT, sketchbox_creds
from explore_sketchbox import STORAGE, login_fresh
from sketchbox_driver import ART, _save_snapshot
from sketchbox_ui import (
    COOLING_OFFSET_CSS,
    HEATING_OFFSET_CSS,
    SELECTOR_MAP_VERSION,
    goto_view,
    select_by_label,
    write_and_read_back,
)

ART.mkdir(exist_ok=True)

EM_DASH = "\u2014"
APPROVED = "approved"


def _run_dir() -> Path:
    rid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = ART / f"testdrive_{rid}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def sanitize_project_name(name: str) -> str:
    cleaned = name.replace(EM_DASH, "-").replace("–", "-").replace("—", "-")
    cleaned = re.sub(r"[^\w\s.\-()+]", "-", cleaned)
    return cleaned.strip() or "Vibe20 Test Project"


def move_snap(snap: dict, bdir: Path) -> dict:
    out = dict(snap)
    for key in ("png", "html"):
        if key not in snap:
            continue
        src = Path(snap[key])
        dest = bdir / src.name
        try:
            src.replace(dest)
            out[key] = str(dest)
        except Exception:
            pass
    return out


def input_hash(profile: dict, measures: list) -> str:
    payload = json.dumps(
        {"profile": profile, "measures": measures, "selector_map": SELECTOR_MAP_VERSION},
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def approved_measures(profile: dict) -> list:
    return [
        m
        for m in (profile.get("measures") or [])
        if m.get("review_status") == APPROVED
    ]


def set_project_name(page, name: str) -> dict:
    goto_view(page, "project")
    safe = sanitize_project_name(name)
    out = {"requested": name, "sanitized": safe, "ok": False}
    try:
        inp = page.locator("label:text-is('Project Name')").locator(
            "xpath=ancestor::div[contains(@class,'ripple-input')][1]//input"
        ).first
        if inp.count() == 0:
            inp = page.locator("input[type='text']").first
        inp.fill(safe, timeout=5000)
        inp.press("Tab")
        page.wait_for_timeout(500)
        err = page.locator(".ripple-input.has-error .error-message").first
        if err.count() and err.is_visible():
            out["error"] = err.inner_text()[:200]
        else:
            out["ok"] = True
        return out
    except Exception as exc:
        out["error"] = str(exc)[:240]
        return out


def configure_location(page, profile: dict) -> dict:
    notes: dict = {}
    mapping = [
        ("State", profile.get("climate_state")),
        ("Nearest City", profile.get("climate_city")),
        ("Energy Code", profile.get("energy_code")),
        ("Rate Category", profile.get("rate_category")),
    ]
    for label, value in mapping:
        if not value:
            continue
        notes[label] = select_by_label(page, label, str(value))
        page.wait_for_timeout(300)
    return notes


def set_schedule_type_ashrae(page) -> dict:
    goto_view(page, "schedules")
    page.wait_for_timeout(800)
    applied = []
    selects = page.locator("select")
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            if sel.get_attribute("disabled") is not None:
                continue
            opts = sel.inner_text(timeout=2000)
            if "ASHRAE" in opts:
                sel.select_option(label="ASHRAE", timeout=4000)
                applied.append(i)
        except Exception:
            continue
    page.wait_for_timeout(400)
    return {"ashrae_select_indexes": applied}


def apply_thermostat_offset(
    page, *, cooling: float | None = None, heating: float | None = None
) -> dict:
    goto_view(page, "schedules")
    page.wait_for_timeout(600)
    out: dict = {"cooling": None, "heating": None, "quality_flags": []}

    cool_val = cooling
    if cool_val is not None and cool_val > 5:
        cool_val = 5.0
        out["quality_flags"].append("cooling_clamped")

    def _fmt(v: float) -> str:
        return str(int(v)) if float(v) == int(v) else str(v)

    if cool_val is not None:
        out["cooling"] = write_and_read_back(page, COOLING_OFFSET_CSS, _fmt(float(cool_val)))
    if heating is not None:
        out["heating"] = write_and_read_back(page, HEATING_OFFSET_CSS, _fmt(float(heating)))
    return out


def zero_offsets(page) -> dict:
    return apply_thermostat_offset(page, cooling=0.0, heating=0.0)


def offsets_from_measures(measures: list) -> tuple[float | None, float | None]:
    cool = heat = None
    for m in measures:
        for ch in m.get("proposed_changes") or []:
            p = str(ch.get("parameter") or "")
            if "cooling_offset" in p:
                cool = float(ch["value"])
            if "heating_offset" in p:
                heat = float(ch["value"])
    return cool, heat


def wait_and_scrape_results(page, timeout_s: float = 90) -> dict:
    goto_view(page, "results")
    t0 = time.time()
    body = ""
    while time.time() - t0 < timeout_s:
        body = page.locator("body").inner_text()
        if "Running models" not in body and (
            "Baseline" in body or "kWh" in body or "Utility Cost" in body
        ):
            break
        page.wait_for_timeout(2500)
        goto_view(page, "results")
    parsed: dict = {}
    flat = re.sub(r"\s+", " ", body)
    m = re.search(
        r"Baseline\s+([\d,]+)\s+([\d.]+)\s+([\d.]+)\s+([\d,]+)\s+([\d,]+)",
        flat,
    )
    flags = ["parse_positional_regex"]
    if m:
        parsed = {
            "utility_cost_usd_year": float(m.group(1).replace(",", "")),
            "site_eui_kbtu_ft2_year": float(m.group(2)),
            "source_eui_kbtu_ft2_year": float(m.group(3)),
            "electricity_kwh_year": float(m.group(4).replace(",", "")),
            "natural_gas_therm_year": float(m.group(5).replace(",", "")),
        }
    else:
        flags.append("parse_failed")
    return {
        "waited_s": round(time.time() - t0, 1),
        "parsed": parsed,
        "body_excerpt": body[:3500],
        "snap": _save_snapshot(page, "results"),
        "quality_flags": flags,
    }


def drive_building(page, profile: dict, out_dir: Path, run_id: str) -> dict:
    pid = profile.get("project_id") or "UNKNOWN"
    bdir = out_dir / pid
    bdir.mkdir(parents=True, exist_ok=True)
    measures = approved_measures(profile)
    report: dict = {
        "project_id": pid,
        "display_name": profile.get("display_name"),
        "steps": {},
        "approved_measure_count": len(measures),
    }
    qflags: list[str] = []

    report["steps"]["rename"] = set_project_name(page, profile.get("display_name") or pid)
    report["snap_project"] = move_snap(_save_snapshot(page, f"{pid}_project"), bdir)

    loc = configure_location(page, profile)
    report["steps"]["location"] = loc
    for label, info in loc.items():
        if isinstance(info, dict) and info.get("error") == "select_disabled":
            qflags.append(f"select_disabled:{label}")

    report["steps"]["ashrae"] = set_schedule_type_ashrae(page)

    # True baseline: zero offsets first
    report["steps"]["zero_offsets"] = zero_offsets(page)
    baseline = wait_and_scrape_results(page)
    baseline["snap"] = move_snap(baseline["snap"], bdir)
    report["baseline"] = baseline
    qflags.extend(baseline.get("quality_flags") or [])

    cool, heat = offsets_from_measures(measures)
    measure_case = None
    if measures and (cool is not None or heat is not None):
        # When only one side is specified, leave the other at 0 (already zeroed)
        report["steps"]["offsets"] = apply_thermostat_offset(
            page, cooling=cool if cool is not None else 0.0, heating=heat if heat is not None else 0.0
        )
        for side in ("cooling", "heating"):
            side_info = (report["steps"]["offsets"] or {}).get(side) or {}
            if side_info.get("ok") is False:
                qflags.append(f"offset_write_failed:{side}")
            qflags.extend(report["steps"]["offsets"].get("quality_flags") or [])
        report["snap_schedules"] = move_snap(_save_snapshot(page, f"{pid}_schedules"), bdir)
        measure_case = wait_and_scrape_results(page)
        measure_case["snap"] = move_snap(measure_case["snap"], bdir)
        report["measure_case"] = measure_case
        qflags.extend(measure_case.get("quality_flags") or [])
    else:
        qflags.append("no_approved_measure_params")

    status = "COMPLETE"
    if not baseline.get("parsed"):
        status = "RESULTS_SUSPECT"
    if measure_case is not None and not measure_case.get("parsed"):
        status = "RESULTS_SUSPECT"

    mid = measures[0]["measure_id"] if measures else None
    record = {
        "run_id": run_id,
        "measure_id": mid,
        "input_hash": input_hash(profile, measures),
        "status": status,
        "quality_flags": sorted(set(qflags)),
        "project_id": pid,
        "display_name": profile.get("display_name"),
        "climate_city": profile.get("climate_city"),
        "climate_state": profile.get("climate_state"),
        "measures_applied": measures,
        "annual": {
            "baseline": baseline.get("parsed") or {},
            "measure_case": (measure_case or {}).get("parsed") or {},
        },
        "artifacts": [
            str(p)
            for p in bdir.glob("*")
            if p.suffix in {".png", ".html", ".json"}
        ],
    }
    (bdir / "result_record.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    (bdir / "drive_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    report["result_record"] = record
    return report


def plan_dry_run(paths: list[Path]) -> dict:
    planned = []
    for path in paths:
        profile = json.loads(path.read_text(encoding="utf-8"))
        measures = approved_measures(profile)
        cool, heat = offsets_from_measures(measures)
        planned.append(
            {
                "file": str(path),
                "project_id": profile.get("project_id"),
                "display_name": sanitize_project_name(profile.get("display_name") or ""),
                "climate": f"{profile.get('climate_city')}, {profile.get('climate_state')}",
                "approved_measures": [m.get("measure_id") for m in measures],
                "skipped_unapproved": [
                    m.get("measure_id")
                    for m in (profile.get("measures") or [])
                    if m.get("review_status") != APPROVED
                ],
                "writes": {
                    "cooling_offset_f": cool,
                    "heating_offset_f": heat,
                    "sequence": [
                        "rename_project",
                        "set_location",
                        "ashrae_schedule",
                        "zero_offsets",
                        "scrape_baseline",
                        "apply_approved_offsets",
                        "scrape_measure_case",
                    ],
                },
            }
        )
    return {"dry_run": True, "buildings": planned}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--buildings", type=Path, default=ROOT / "examples" / "buildings")
    ap.add_argument("--limit", type=int, default=0, help="Max buildings (0=all)")
    ap.add_argument("--dry-run", action="store_true", help="Print planned writes; no browser")
    ap.add_argument("--artifact-dir", type=Path, default=None)
    args = ap.parse_args()

    paths = sorted(args.buildings.glob("*.json"))
    if args.limit:
        paths = paths[: args.limit]
    if not paths:
        print(f"No building JSON under {args.buildings}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(json.dumps(plan_dry_run(paths), indent=2))
        return 0

    creds = sketchbox_creds()
    if not creds["email"] or not creds["password"]:
        print("Missing SKETCHBOX_EMAIL/PASSWORD in .env", file=sys.stderr)
        return 2

    out_dir = args.artifact_dir or _run_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = out_dir.name
    summary = {"out_dir": str(out_dir), "run_id": run_id, "buildings": []}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=creds["slow_mo_ms"])
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            storage_state=str(STORAGE) if STORAGE.is_file() else None,
        )
        page = context.new_page()
        page.set_default_timeout(8000)
        login_fresh(page, creds)

        for path in paths:
            profile = json.loads(path.read_text(encoding="utf-8"))
            print(f"Driving {profile.get('project_id')} ...", flush=True)
            try:
                rep = drive_building(page, profile, out_dir, run_id)
                rec = rep["result_record"]
                summary["buildings"].append(
                    {
                        "project_id": rep["project_id"],
                        "status": rec["status"],
                        "baseline": rec["annual"]["baseline"],
                        "measure_case": rec["annual"]["measure_case"],
                        "quality_flags": rec["quality_flags"],
                        "measure_id": rec.get("measure_id"),
                    }
                )
            except Exception as exc:
                summary["buildings"].append(
                    {
                        "project_id": profile.get("project_id"),
                        "status": "MODEL_RUN_FAILED",
                        "error": str(exc),
                    }
                )
                _save_snapshot(page, f"error_{profile.get('project_id')}")

        context.storage_state(path=str(STORAGE))
        browser.close()

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
