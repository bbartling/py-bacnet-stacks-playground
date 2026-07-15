"""Madison Liberty-style conceptual Sketchbox screening drive.

Uses examples/buildings/madison_liberty_concept.json.

Honesty rules:
- Emits required conceptual disclaimer on every export.
- Prefer Sketchbox built-in VAV assumptions; do not invent capacity.
- Two shells: AHU-1 occupied (Normal) vs AHU-2 Always Occupied (24/7) for schedule ECM.
- Air-cooled chiller is NOT available in this UI path — document VAV with HW Reheat + DX.
- Duct-static reset is NOT in Add Measure catalog — keep NEEDS_INPUT (no invented savings).
- vibe19 bridge: SCHED-247 → schedule ECM; AHU-DUCTHI → static reset (when mappable).

Usage:
  python run_madison_concept.py
  python run_madison_concept.py --dry-run
  python run_madison_concept.py --probe-only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import ROOT, sketchbox_creds
from explore_sketchbox import STORAGE, login_fresh
from sketchbox_driver import ART, _save_snapshot
from sketchbox_ui import (
    AIR_SIDE_VAV,
    AREA_CSS,
    ASPECT_CSS,
    FLOOR_HEIGHT_CSS,
    FLOORS_CSS,
    HEATING_FUEL_ASSUMPTION,
    WWR_EAST_CSS,
    WWR_NORTH_CSS,
    WWR_SOUTH_CSS,
    WWR_WEST_CSS,
    goto_view,
    select_by_label,
    write_and_read_back,
)
from testdrive import (
    sanitize_project_name,
    set_project_name,
    wait_and_scrape_results,
    zero_offsets,
)

DISCLAIMER = (
    "This is a conceptual, uncalibrated screening model for an anonymized office building. "
    "It is not a design load calculation, code-compliance model, calibrated energy model, "
    "or representation of a specific Madison property."
)

PROFILE_PATH = ROOT / "examples" / "buildings" / "madison_liberty_concept.json"
EVIDENCE_PATH = ROOT / "examples" / "evidence" / "madison_liberty_concept_evidence.json"


def _run_dir() -> Path:
    rid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = ART / f"madison_{rid}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def configure_madison(page, profile: dict) -> dict:
    notes: dict = {"rename": set_project_name(page, profile["display_name"])}
    goto_view(page, "project")
    notes["State"] = select_by_label(page, "State", profile["climate_state"])
    page.wait_for_timeout(600)
    notes["Nearest City"] = select_by_label(page, "Nearest City", profile["climate_city"])
    notes["Energy Code"] = select_by_label(
        page, "Energy Code", profile.get("energy_code") or "IECC 2018"
    )
    notes["Rate Category"] = select_by_label(
        page, "Rate Category", profile.get("rate_category") or "Commercial"
    )
    try:
        notes["observed_energy_code"] = page.locator(
            "label:text-is('Energy Code')"
        ).locator(
            "xpath=ancestor::div[contains(@class,'ripple-input')][1]//select"
        ).first.input_value()
    except Exception:
        notes["observed_energy_code"] = None
    return notes


def ensure_two_shells(page) -> dict:
    goto_view(page, "design")
    page.wait_for_timeout(800)
    body = page.locator("body").inner_text()
    has_second = "Office (2)" in body or body.count("Office") >= 2
    out: dict = {"already_had_second": has_second, "ok": has_second}
    if not has_second:
        for label in ("Add Shell", "Add shell"):
            loc = page.get_by_text(label, exact=False)
            if loc.count():
                try:
                    loc.first.click(timeout=4000)
                    page.wait_for_timeout(1000)
                    out["ok"] = True
                    out["clicked"] = label
                    break
                except Exception as exc:
                    out["error"] = str(exc)[:200]
    out["snap"] = _save_snapshot(page, "design_shells")
    out["body_nav"] = page.locator("body").inner_text()[:1200]
    return out


def select_shell(page, name: str) -> bool:
    """Click shell nav label (e.g. Office / Office (2))."""
    loc = page.get_by_text(name, exact=True)
    if loc.count() == 0:
        loc = page.get_by_text(name, exact=False)
    if loc.count() == 0:
        return False
    try:
        loc.first.click(timeout=4000)
        page.wait_for_timeout(800)
        return True
    except Exception:
        return False


def configure_shell_design(page, *, area_ft2: float, aspect: float = 2.0) -> dict:
    goto_view(page, "design")
    page.wait_for_timeout(600)
    notes: dict = {}
    notes["area"] = write_and_read_back(page, AREA_CSS, str(int(area_ft2)))
    notes["aspect"] = write_and_read_back(page, ASPECT_CSS, str(aspect))
    notes["floors"] = write_and_read_back(page, FLOORS_CSS, "6")
    notes["floor_height"] = write_and_read_back(page, FLOOR_HEIGHT_CSS, "13")
    for key, css in (
        ("wwr_n", WWR_NORTH_CSS),
        ("wwr_s", WWR_SOUTH_CSS),
        ("wwr_e", WWR_EAST_CSS),
        ("wwr_w", WWR_WEST_CSS),
    ):
        notes[key] = write_and_read_back(page, css, "0.65")
    notes["air_side"] = select_by_label(page, "Air-Side System", AIR_SIDE_VAV)
    notes["heating_fuel"] = select_by_label(page, "Heating Fuel Type", HEATING_FUEL_ASSUMPTION)
    notes["heating_system"] = select_by_label(page, "Heating System", "Boiler")
    # Cooling often collapses to Direct Expansion under VAV+HW path — record honestly
    notes["cooling_system"] = select_by_label(page, "Cooling System", "Direct Expansion")
    return notes


def set_schedule_occupancy(page, *, schedule_type: str, occupancy: str) -> dict:
    """Per-shell SCHEDULES: Simplified + Occupancy mode (Always Occupied / Normal / …)."""
    goto_view(page, "schedules")
    page.wait_for_timeout(700)
    out: dict = {"schedule_type": [], "occupancy": None}
    selects = page.locator("select")
    for i in range(selects.count()):
        sel = selects.nth(i)
        try:
            text = sel.inner_text(timeout=2000)
            if "ASHRAE" in text and "Simplified" in text:
                sel.select_option(label=schedule_type, timeout=4000)
                out["schedule_type"].append(i)
        except Exception:
            continue
    page.wait_for_timeout(500)
    # Occupancy select under Weekday
    out["occupancy"] = select_by_label(page, "Occupancy", occupancy)
    if not out["occupancy"].get("ok"):
        # Fallback: any select containing Always Occupied
        for i in range(selects.count()):
            sel = selects.nth(i)
            try:
                text = sel.inner_text()
                if occupancy in text:
                    sel.select_option(label=occupancy, timeout=4000)
                    out["occupancy"] = {"ok": True, "option": occupancy, "idx": i}
                    break
            except Exception:
                continue
    out["snap"] = _save_snapshot(page, f"sched_{occupancy.replace(' ', '_')}")
    return out


def inventory_add_measure(page) -> dict:
    goto_view(page, "measures")
    page.wait_for_timeout(800)
    try:
        page.get_by_text("Add Measure", exact=True).first.click(timeout=5000)
        page.wait_for_timeout(1200)
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200]}
    body = page.locator("body").inner_text()
    wanted = [
        "Fan Power",
        "VAV Box Minimum",
        "Hot Water Temperature Reset",
        "Static",
        "Duct",
        "Schedule",
        "Occupancy",
        "Thermostat",
        "Empty Measure",
    ]
    hits = {k: (k.lower() in body.lower()) for k in wanted}
    snap = _save_snapshot(page, "add_measure_catalog")
    # close dialog if possible
    for label in ("Cancel", "Close", "×"):
        b = page.get_by_text(label, exact=False)
        if b.count():
            try:
                b.first.click(timeout=1500)
                break
            except Exception:
                pass
    page.keyboard.press("Escape")
    return {"ok": True, "hits": hits, "body_excerpt": body[:6000], "snap": snap}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--probe-only", action="store_true")
    ap.add_argument("--skip-ecm1", action="store_true", help="Baseline only")
    args = ap.parse_args()

    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    evidence = (
        json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
        if EVIDENCE_PATH.is_file()
        else {}
    )

    plan = {
        "disclaimer": DISCLAIMER,
        "project_id": profile["project_id"],
        "display_name": sanitize_project_name(profile["display_name"]),
        "weather_location": profile["weather_location"],
        "sketchbox_hvac_approximation": {
            "requested_cooling": "air-cooled chiller",
            "available_closest": AIR_SIDE_VAV,
            "cooling_path": "Direct Expansion (UI-constrained under VAV+HW)",
            "heating_fuel_assumption": HEATING_FUEL_ASSUMPTION,
            "flag": "heating_fuel_assumption_unconfirmed",
        },
        "shells": [
            {"nav": "Office", "area": 75000, "occupancy_baseline": "Normal"},
            {"nav": "Office (2)", "area": 75000, "occupancy_baseline": "Always Occupied"},
        ],
        "ecm1": "Office (2) Occupancy Always Occupied → Normal (SCHED-247 class)",
        "ecm2": "duct static reset — NOT in Add Measure catalog → NEEDS_INPUT",
        "vibe19_bridge": ["SCHED-247", "AHU-DUCTHI", "FC1"],
    }
    if args.dry_run:
        print(json.dumps(plan, indent=2))
        return 0

    creds = sketchbox_creds()
    if not creds["email"] or not creds["password"]:
        print("Missing SKETCHBOX_EMAIL/PASSWORD in .env", file=sys.stderr)
        return 2

    out_dir = _run_dir()
    report: dict = {
        "disclaimer": DISCLAIMER,
        "project_id": profile["project_id"],
        "model_purpose": profile["model_purpose"],
        "calibration_status": "uncalibrated",
        "anonymized": True,
        "weather_location": profile["weather_location"],
        "conceptual_existing_building_vintage": "unknown",
        "out_dir": str(out_dir),
        "evidence": evidence,
        "limitations": [],
        "quality_flags": [
            "conceptual_uncalibrated",
            "anonymized_madison_weather_only",
            "heating_fuel_assumption_unconfirmed",
            "hvac_approx_vav_hw_reheat_dx_not_air_cooled_chiller",
        ],
        "status": "READY",
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=creds["slow_mo_ms"])
        context = browser.new_context(
            viewport={"width": 1440, "height": 960},
            storage_state=str(STORAGE) if STORAGE.is_file() else None,
        )
        page = context.new_page()
        page.set_default_timeout(8000)
        login_fresh(page, creds)

        report["project_config"] = configure_madison(page, profile)
        report["sketchbox_baseline_code"] = report["project_config"].get(
            "observed_energy_code"
        )

        shells = ensure_two_shells(page)
        report["shells_setup"] = shells
        if not shells.get("ok"):
            report["limitations"].append("Second shell not confirmed; schedule contrast degraded.")
            report["shell_representation"] = "one_shell_or_unknown"
        else:
            report["shell_representation"] = "two_shells"

        # Configure shell 1 — occupied Normal
        select_shell(page, "Office")
        report["shell1_design"] = configure_shell_design(page, area_ft2=75000, aspect=2.0)
        report["shell1_schedule"] = set_schedule_occupancy(
            page, schedule_type="Simplified", occupancy="Normal"
        )

        # Configure shell 2 — Always Occupied (24/7)
        if shells.get("ok"):
            select_shell(page, "Office (2)")
            report["shell2_design"] = configure_shell_design(page, area_ft2=75000, aspect=2.0)
            report["shell2_schedule"] = set_schedule_occupancy(
                page, schedule_type="Simplified", occupancy="Always Occupied"
            )

        zero_offsets(page)
        report["measure_catalog"] = inventory_add_measure(page)

        print("Scraping true baseline RESULTS ...", flush=True)
        baseline = wait_and_scrape_results(page, timeout_s=120)
        report["baseline_results"] = baseline.get("parsed")
        report["baseline_flags"] = baseline.get("quality_flags")

        ecm_notes = []
        # ECM-1: put AHU-2 / Office (2) onto Normal schedule
        ecm1 = {
            "measure_id": "ECM-AHU2-SCHED-ALIGN",
            "title": "Put AHU-2 on occupied schedule (end continuous runtime)",
            "vibe19_bridge": {"rule_ids": ["SCHED-247"], "equipment_ids": ["AHU-2"]},
        }
        if args.skip_ecm1 or not shells.get("ok"):
            ecm1["automation_status"] = "SKIPPED"
        else:
            select_shell(page, "Office (2)")
            applied = set_schedule_occupancy(
                page, schedule_type="Simplified", occupancy="Normal"
            )
            ecm1["applied"] = applied
            ecm1["automation_status"] = (
                "COMPLETE" if (applied.get("occupancy") or {}).get("ok") else "BLOCKED_UI_CHANGE"
            )
            print("Scraping post-ECM1 RESULTS ...", flush=True)
            m1 = wait_and_scrape_results(page, timeout_s=120)
            ecm1["results"] = m1.get("parsed")
            ecm1["quality_flags"] = m1.get("quality_flags")
        ecm_notes.append(ecm1)

        # ECM-2: duct static — no mapped measure
        catalog_hits = (report.get("measure_catalog") or {}).get("hits") or {}
        ecm2 = {
            "measure_id": "ECM-AHU-DUCT-STATIC-RESET",
            "title": "AHU duct-static-pressure reset for both AHUs",
            "vibe19_bridge": {
                "rule_ids": ["AHU-DUCTHI", "FC1"],
                "equipment_ids": ["AHU-1", "AHU-2"],
            },
            "automation_status": "NEEDS_INPUT",
            "reason": (
                "Add Measure catalog has Fan Power / VAV Box Minimum / HW reset but no "
                "duct-static-pressure reset control. Refusing to invent savings. "
                f"catalog_hits={catalog_hits}"
            ),
        }
        report["limitations"].append(ecm2["reason"])
        ecm_notes.append(ecm2)
        report["ecm_automation"] = ecm_notes

        report["limitations"].append(
            "Requested air-cooled chiller plant is not available in this Sketchbox UI path; "
            f"modeled closest system {AIR_SIDE_VAV} with DX cooling and {HEATING_FUEL_ASSUMPTION} HW."
        )
        report["limitations"].append(
            "AHU-1 target hours 07:00–17:00 / Sat 07:00–14:00 approximated as Occupancy=Normal "
            "under Simplified schedules (UI shows Weekday Schedule ~9am–5pm). Exact hour matrix "
            "not automated in this pass."
        )

        if report.get("baseline_results"):
            report["status"] = "COMPLETE"
        else:
            report["status"] = "RESULTS_SUSPECT"

        (out_dir / "madison_report.json").write_text(
            json.dumps(report, indent=2, default=str), encoding="utf-8"
        )
        (out_dir / "DISCLAIMER.txt").write_text(DISCLAIMER + "\n", encoding="utf-8")
        (out_dir / "result_record.json").write_text(
            json.dumps(
                {
                    "run_id": out_dir.name,
                    "measure_id": ecm1.get("measure_id"),
                    "input_hash": profile["project_id"],
                    "status": report["status"],
                    "quality_flags": report["quality_flags"],
                    "disclaimer": DISCLAIMER,
                    "sketchbox_baseline_code": report.get("sketchbox_baseline_code"),
                    "weather_location": report["weather_location"],
                    "conceptual_existing_building_vintage": "unknown",
                    "annual": {
                        "baseline": report.get("baseline_results") or {},
                        "after_ecm_ahu2_schedule": ecm1.get("results") or {},
                    },
                    "ecm_statuses": [
                        {"id": e["measure_id"], "status": e.get("automation_status")}
                        for e in ecm_notes
                    ],
                    "artifacts": [str(p) for p in out_dir.glob("*")],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

        context.storage_state(path=str(STORAGE))
        browser.close()

    print(
        json.dumps(
            {
                "disclaimer": DISCLAIMER,
                "out_dir": str(out_dir),
                "status": report["status"],
                "sketchbox_baseline_code": report.get("sketchbox_baseline_code"),
                "shell_representation": report.get("shell_representation"),
                "baseline": report.get("baseline_results"),
                "after_ecm1": (report.get("ecm_automation") or [{}])[0].get("results"),
                "ecm_statuses": [
                    {
                        "id": e["measure_id"],
                        "status": e.get("automation_status"),
                    }
                    for e in (report.get("ecm_automation") or [])
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
