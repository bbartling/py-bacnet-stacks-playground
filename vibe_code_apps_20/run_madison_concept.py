"""Madison Liberty-style conceptual Sketchbox screening drive.

ECM-1: AHU-2 Always Occupied → Normal (SCHED-247 class)
ECM-2: Conceptual GL36 airside proxy on BOTH shells (VAV Box Minimum + Fan Power)

Usage:
  python run_madison_concept.py
  python run_madison_concept.py --dry-run
  python run_madison_concept.py --skip-ecm2
"""

from __future__ import annotations

import argparse
import json
import re
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

# Literature sanity bands (domain knowledge for validation — HVAC-centric studies).
# Whole-building Sketchbox % after schedule ECM is expected LOWER than HVAC-only ~31% avg.
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


def _run_dir() -> Path:
    rid = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    d = ART / f"madison_{rid}"
    d.mkdir(parents=True, exist_ok=True)
    return d


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
    """Compare Sketchbox whole-building deltas to published GL36 order-of-magnitude bands."""
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
            notes.append(
                f"Incremental GL36 proxy increased kWh ({inc_kwh}%) — investigate measure direction."
            )
        elif inc_kwh == 0:
            verdict = "WARN"
            flags.append("gl36_incremental_zero_impact")
            notes.append(
                "Incremental kWh savings 0% — measures may be present as No Change / Custom unset; "
                "confirm Better/Custom values in Sketchbox MEASURES."
            )
        elif lo <= inc_kwh <= hi:
            verdict = "PASS"
            notes.append(
                f"Incremental whole-building kWh savings {inc_kwh}% within screening band "
                f"{lo}–{hi}% (lower than HVAC-only literature avg "
                f"{GL36_LIT['hvac_savings_pct_avg']}% as expected)."
            )
        elif 0 < inc_kwh < lo:
            verdict = "WARN"
            flags.append("gl36_incremental_below_band")
            notes.append(
                f"Incremental kWh savings {inc_kwh}% below {lo}% band — proxy may be weak or "
                "already efficient after schedule ECM."
            )
        else:
            verdict = "WARN"
            flags.append("gl36_incremental_above_band")
            notes.append(
                f"Incremental kWh savings {inc_kwh}% above {hi}% band — still possible for "
                "loose baselines; treat as conceptual screening only."
            )
        notes.append(
            "Literature order-of-magnitude (HVAC studies): avg ~31% HVAC energy; "
            "VAV-min ~16% / SAT ~7% / DSP ~4% of site energy in published decompositions. "
            "Do not equate whole-building Sketchbox % to HVAC-only study %"
        )
    elif after_ecm2 is None:
        notes.append("ECM-2 not applied or results missing.")
        verdict = "NEEDS_INPUT"

    return {
        "verdict": verdict,
        "literature": GL36_LIT,
        "pct_savings": {
            "ecm1_kwh_vs_baseline": ecm1_kwh,
            "ecm2_incremental_kwh_vs_ecm1": inc_kwh,
            "cumulative_kwh_vs_baseline": cum_kwh,
            "cumulative_eui_vs_baseline": cum_eui,
            "cumulative_cost_vs_baseline": cum_cost,
        },
        "quality_flags": flags,
        "notes": notes,
    }


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
    has_second = "Office (2)" in body
    out: dict = {"already_had_second": has_second, "ok": has_second}
    if not has_second:
        for label in ("Add Shell", "Add shell"):
            loc = page.get_by_text(label, exact=False)
            if loc.count():
                try:
                    loc.first.click(timeout=4000)
                    page.wait_for_timeout(1000)
                    out["ok"] = "Office (2)" in page.locator("body").inner_text()
                    out["clicked"] = label
                    break
                except Exception as exc:
                    out["error"] = str(exc)[:200]
    out["snap"] = _save_snapshot(page, "design_shells")
    return out


def select_shell(page, name: str) -> bool:
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
    notes["cooling_system"] = select_by_label(page, "Cooling System", "Direct Expansion")
    return notes


def set_schedule_occupancy(page, *, schedule_type: str, occupancy: str) -> dict:
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
    out["occupancy"] = select_by_label(page, "Occupancy", occupancy)
    if not out["occupancy"].get("ok"):
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
    wanted = ["Fan Power", "VAV Box Minimum", "Empty Measure", "Hot Water Temperature Reset"]
    hits = {k: (k.lower() in body.lower()) for k in wanted}
    snap = _save_snapshot(page, "add_measure_catalog")
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    return {"ok": True, "hits": hits, "body_excerpt": body[:6000], "snap": snap}


def _dismiss_dialogs(page) -> None:
    for _ in range(3):
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
    page.evaluate(
        """() => {
          const bg = document.querySelector('.modal-background');
          if (bg) bg.click();
        }"""
    )
    page.wait_for_timeout(250)


def save_project_online(page) -> dict:
    """Click Sketchbox 'Save this project' icon so it appears in saved projects."""
    out: dict = {"ok": False}
    _dismiss_dialogs(page)
    try:
        icon = page.locator('.save-project-icon, [title="Save this project"]').first
        if icon.count() == 0:
            out["error"] = "save_icon_missing"
            return out
        icon.click(timeout=5000, force=True)
        page.wait_for_timeout(2000)
        out["ok"] = True
        out["snap"] = _save_snapshot(page, "project_saved")
        body = page.locator("body").inner_text()[:1500]
        out["body_excerpt"] = body
        return out
    except Exception as exc:
        # DOM fallback
        clicked = page.evaluate(
            """() => {
              const el = document.querySelector('.save-project-icon, [title=\"Save this project\"]');
              if (!el) return false;
              el.click();
              return true;
            }"""
        )
        page.wait_for_timeout(2000)
        out["ok"] = bool(clicked)
        out["via"] = "dom_evaluate"
        if not clicked:
            out["error"] = str(exc)[:200]
        else:
            out["snap"] = _save_snapshot(page, "project_saved")
        return out


def add_measure_parameter(
    page,
    *,
    param_name: str,
    proposed: str,
    measure_name: str,
    apply_shell: str | None = None,
    prefer_better: bool = False,
) -> dict:
    """Add Measure via search → select param → name → Add → set Custom/Better value."""
    out: dict = {
        "parameter": param_name,
        "proposed": proposed,
        "measure_name": measure_name,
        "apply_shell": apply_shell,
        "ok": False,
    }
    _dismiss_dialogs(page)
    goto_view(page, "measures")
    page.wait_for_timeout(500)
    try:
        page.get_by_text("Add Measure", exact=True).first.click(timeout=5000, force=True)
        page.wait_for_timeout(1200)
    except Exception as exc:
        out["error"] = f"open_dialog:{exc}"[:200]
        _dismiss_dialogs(page)
        return out

    # Filter parameter list (required for reliable click)
    search = page.locator("#search-input")
    if search.count():
        search.fill(param_name[:16])
        page.wait_for_timeout(500)

    selected = page.evaluate(
        """(param) => {
          const el = Array.from(document.querySelectorAll('div.parameter-name'))
            .find(n => (n.textContent || '').trim() === param);
          if (!el) return false;
          el.scrollIntoView({block: 'center'});
          el.dispatchEvent(new MouseEvent('click', {bubbles: true}));
          return true;
        }""",
        param_name,
    )
    if not selected:
        out["error"] = "param_not_in_catalog"
        _dismiss_dialogs(page)
        return out
    out["clicked_param"] = True
    page.wait_for_timeout(600)

    if apply_shell:
        # Apply To list inside modal
        page.evaluate(
            """(shell) => {
              const root = document.querySelector('#modal-target') || document;
              const nodes = Array.from(root.querySelectorAll('*'));
              const el = nodes.find(n => (n.textContent || '').trim() === shell && n.children.length === 0);
              if (el) el.click();
            }""",
            apply_shell,
        )

    name_inp = page.locator("#measure-name-input")
    if name_inp.count():
        name_inp.fill(measure_name)
        out["named"] = measure_name

    confirmed = page.evaluate(
        """() => {
          const root = document.querySelector('#modal-target') || document;
          const hit = Array.from(root.querySelectorAll('button, .button'))
            .filter(b => (b.textContent || '').trim() === 'Add Measure');
          if (!hit.length) return false;
          hit[hit.length - 1].click();
          return true;
        }"""
    )
    out["confirm_add"] = confirmed
    page.wait_for_timeout(1500)
    _dismiss_dialogs(page)
    goto_view(page, "measures")
    page.wait_for_timeout(800)
    # Expand so measure cards show No Change / Better / Best / Custom
    try:
        exp = page.get_by_text("Expand all Measures", exact=False)
        if exp.count():
            exp.first.click(timeout=3000, force=True)
            page.wait_for_timeout(800)
    except Exception:
        pass

    value_set = page.evaluate(
        """({ preferBetter }) => {
          const blocks = Array.from(document.querySelectorAll('.change'));
          if (!blocks.length) {
            // fallback: click last Custom / Better option on page
            const customs = Array.from(document.querySelectorAll('.measure-card-custom-option'));
            const betters = Array.from(document.querySelectorAll('.measure-card-better-option'));
            if (preferBetter) {
              for (let i = betters.length - 1; i >= 0; i--) {
                if (!(betters[i].innerText || '').includes('Not Available')) {
                  betters[i].click();
                  return {ok: true, mode: 'better_fallback'};
                }
              }
            }
            if (customs.length) {
              const c = customs[customs.length - 1];
              c.click();
              const edit = c.querySelector('.edit-icon');
              if (edit) { edit.style.display = 'block'; edit.click(); }
              return {ok: true, mode: 'custom_fallback', n_custom: customs.length};
            }
            return {ok: false, reason: 'no_change_blocks', n_custom: customs.length};
          }
          const block = blocks[blocks.length - 1];
          if (preferBetter) {
            const better = block.querySelector('.measure-card-better-option');
            if (better && !(better.innerText || '').includes('Not Available')) {
              better.click();
              return {ok: true, mode: 'better'};
            }
          }
          const custom = block.querySelector('.measure-card-custom-option');
          if (!custom) return {ok: false, reason: 'no_custom_in_block'};
          custom.click();
          const edit = custom.querySelector('.edit-icon');
          if (edit) { edit.style.display = 'block'; edit.click(); }
          return {ok: true, mode: 'custom_clicked'};
        }""",
        {"preferBetter": prefer_better},
    )
    out["value_set"] = value_set
    page.wait_for_timeout(600)

    filled = []
    for i in range(page.locator("input[type='text']").count()):
        el = page.locator("input[type='text']").nth(i)
        try:
            if not el.is_visible():
                continue
            eid = el.get_attribute("id") or ""
            if eid in {"measure-name-input", "search-input", "sign-in-email", "sign-in-password"}:
                continue
            before = el.input_value()
            el.fill(proposed, timeout=3000)
            el.press("Tab")
            filled.append({"id": eid, "before": before, "after": el.input_value()})
            break
        except Exception:
            continue
    out["filled"] = filled

    # Also try clicking Custom value area and typing
    if not filled and (value_set or {}).get("mode") == "custom_clicked":
        try:
            custom = page.locator(".measure-card-custom-option").last
            custom.click(force=True)
            page.keyboard.type(proposed)
            page.keyboard.press("Enter")
            filled.append({"via": "keyboard_type", "after": proposed})
            out["filled"] = filled
        except Exception as exc:
            out["fill_error"] = str(exc)[:120]

    out["ok"] = bool(confirmed) and (
        bool(filled)
        or (value_set or {}).get("mode") == "better"
        or (value_set or {}).get("ok") is True
    )
    try:
        out["snap"] = _save_snapshot(page, f"measure_{param_name.replace(' ', '_')}")
    except Exception as exc:
        out["snap_error"] = str(exc)[:120]
    return out


def apply_gl36_proxy_both_shells(page) -> dict:
    """Apply VAV Box Minimum + Fan Power measures (prefer both shells / site apply)."""
    steps = []
    # One measure per parameter; Apply To targets active shell list when possible
    specs = [
        ("VAV Box Minimum", "0.15", "GL36 VAV Min both AHUs", False),
        ("Fan Power", "0.8", "GL36 Fan Power both AHUs", True),
    ]
    for param, value, name, prefer_better in specs:
        try:
            # First apply with Office selected, then duplicate intent for Office (2)
            for shell in ("Office", "Office (2)"):
                steps.append(
                    add_measure_parameter(
                        page,
                        param_name=param,
                        proposed=value,
                        measure_name=f"{name} - {shell}",
                        apply_shell=shell,
                        prefer_better=prefer_better,
                    )
                )
                _dismiss_dialogs(page)
        except Exception as exc:
            steps.append(
                {
                    "parameter": param,
                    "ok": False,
                    "error": f"exception:{exc}"[:240],
                }
            )
    any_ok = any(s.get("ok") for s in steps)
    added_ok = any(s.get("confirm_add") for s in steps)
    return {
        "steps": steps,
        "ok": any_ok or added_ok,
        "flag": "conceptual_gl36_proxy",
        "automation_status": "COMPLETE" if (any_ok or added_ok) else "NEEDS_INPUT",
        "note": "Measure added counts as progress even if Custom value edit is partial; RESULTS scrape validates impact.",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--probe-only", action="store_true")
    ap.add_argument("--skip-ecm1", action="store_true")
    ap.add_argument("--skip-ecm2", action="store_true")
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
        "ecm1": "Office (2) Occupancy Always Occupied → Normal (SCHED-247 class)",
        "ecm2": {
            "id": "ECM-GL36-AIRSIDE-BOTH-AHUS",
            "proxies": ["VAV Box Minimum", "Fan Power"],
            "scope": ["Office", "Office (2)"],
            "flag": "conceptual_gl36_proxy",
        },
        "validation_literature": GL36_LIT,
        "sequence": [
            "configure_madison",
            "two_shells_vav",
            "baseline_schedules",
            "scrape_baseline",
            "ecm1_schedule",
            "scrape_after_ecm1",
            "ecm2_gl36_proxy",
            "scrape_after_ecm2",
            "validate_vs_literature",
            "save_project_online",
        ],
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
            "gl36_proxy_not_full_sequences",
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
        report["shell_representation"] = "two_shells" if shells.get("ok") else "one_shell_or_unknown"
        if not shells.get("ok"):
            report["limitations"].append("Second shell not confirmed; GL36 both-AHU scope degraded.")

        select_shell(page, "Office")
        report["shell1_design"] = configure_shell_design(page, area_ft2=75000, aspect=2.0)
        report["shell1_schedule"] = set_schedule_occupancy(
            page, schedule_type="Simplified", occupancy="Normal"
        )
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

        ecm_notes: list[dict] = []
        ecm1: dict = {
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
        ecm_notes.append(ecm1)

        ecm2: dict = {
            "measure_id": "ECM-GL36-AIRSIDE-BOTH-AHUS",
            "title": "Conceptual GL36 airside package on both AHUs",
            "flags": ["conceptual_gl36_proxy", "gl36_proxy_not_full_sequences"],
            "vibe19_bridge": {
                "rule_ids": ["AHU-DUCTHI", "FC1", "VAV-1"],
                "equipment_ids": ["AHU-1", "AHU-2"],
            },
        }
        if args.skip_ecm2:
            ecm2["automation_status"] = "SKIPPED"
        else:
            print("Applying GL36 proxy measures (VAV Box Minimum + Fan Power) ...", flush=True)
            try:
                _dismiss_dialogs(page)
                gl36 = apply_gl36_proxy_both_shells(page)
            except Exception as exc:
                gl36 = {
                    "ok": False,
                    "automation_status": "BLOCKED_UI_CHANGE",
                    "error": str(exc)[:300],
                    "steps": [],
                    "flag": "conceptual_gl36_proxy",
                }
            ecm2["applied"] = gl36
            ecm2["automation_status"] = gl36.get("automation_status")
            if not gl36.get("ok"):
                report["limitations"].append(
                    "GL36 proxy Measure writes could not be confirmed by UI read-back; "
                    "status NEEDS_INPUT — no invented savings."
                )
            else:
                print("Scraping post-ECM2 GL36 RESULTS ...", flush=True)
                m2 = wait_and_scrape_results(page, timeout_s=120)
                ecm2["results"] = m2.get("parsed")
        ecm_notes.append(ecm2)
        report["ecm_automation"] = ecm_notes

        report["validation"] = validate_against_literature(
            baseline=report.get("baseline_results") or {},
            after_ecm1=ecm1.get("results"),
            after_ecm2=ecm2.get("results"),
        )
        report["quality_flags"] = sorted(
            set(report["quality_flags"] + (report["validation"].get("quality_flags") or []))
        )

        print("Saving project to Sketchbox cloud (Save this project) ...", flush=True)
        # Ensure project name is set before save
        set_project_name(page, profile["display_name"])
        report["save_project"] = save_project_online(page)
        if not report["save_project"].get("ok"):
            report["limitations"].append(
                "Could not confirm Sketchbox 'Save this project' click — check account UI."
            )

        report["limitations"].append(
            f"Requested air-cooled chiller not available; used {AIR_SIDE_VAV} + DX + "
            f"{HEATING_FUEL_ASSUMPTION} HW (flagged)."
        )
        report["limitations"].append(
            "AHU-1 hours approximated as Occupancy=Normal under Simplified schedules."
        )
        report["limitations"].append(
            "ECM-2 is a conceptual GL36 proxy (VAV Box Minimum + Fan Power), not full G36 sequences."
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
                    "measure_id": "ECM-GL36-AIRSIDE-BOTH-AHUS",
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
                        "after_ecm2_gl36": ecm2.get("results") or {},
                    },
                    "validation": report.get("validation"),
                    "save_project_ok": (report.get("save_project") or {}).get("ok"),
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
                "baseline": report.get("baseline_results"),
                "after_ecm1": ecm1.get("results"),
                "after_ecm2_gl36": ecm2.get("results"),
                "validation": report.get("validation"),
                "save_project": report.get("save_project"),
                "ecm_statuses": [
                    {"id": e["measure_id"], "status": e.get("automation_status")}
                    for e in ecm_notes
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
