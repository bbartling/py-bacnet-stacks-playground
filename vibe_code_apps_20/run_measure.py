"""Add a Sketchbox measure, wait for RESULTS run to finish, capture savings table."""

from __future__ import annotations

import json
import sys
import time

from playwright.sync_api import sync_playwright

from config import sketchbox_creds
from explore_sketchbox import STORAGE, login_fresh
from sketchbox_driver import ART, _save_snapshot, _ts


def goto_view(page, view: str) -> None:
    page.evaluate(
        """(view) => {
      const el = document.querySelector(`div.view-link[view="${view}"]`);
      if (el) el.click();
    }""",
        view,
    )
    page.wait_for_timeout(1500)


def add_first_measure(page) -> dict:
    goto_view(page, "measures")
    page.wait_for_timeout(800)
    before = _save_snapshot(page, "measures_before_add")
    # Click Add Measure
    btn = page.get_by_text("Add Measure", exact=True).first
    btn.click()
    page.wait_for_timeout(1500)
    after_click = _save_snapshot(page, "measures_add_dialog")
    # Try pick first selectable option / checkbox / list item in any dialog
    notes = {"picked": None}
    # Look for common measure names
    for label in (
        "Occupancy Sensors",
        "Lighting",
        "Schedule",
        "Economizer",
        "Setpoint",
        "VFD",
        "Efficiency",
    ):
        loc = page.get_by_text(label, exact=False)
        if loc.count():
            try:
                loc.first.click(timeout=3000)
                notes["picked"] = label
                page.wait_for_timeout(800)
                break
            except Exception:
                continue
    # Confirm buttons
    for conf in ("Add", "OK", "Apply", "Save", "Confirm"):
        b = page.get_by_role("button", name=conf)
        if b.count():
            try:
                b.first.click(timeout=2000)
                notes["confirm"] = conf
                page.wait_for_timeout(1000)
                break
            except Exception:
                continue
    notes["snap"] = _save_snapshot(page, "measures_after_add")
    notes["body"] = page.locator("body").inner_text()[:3000]
    notes["before"] = before
    notes["dialog"] = after_click
    return notes


def wait_results(page, timeout_s: float = 90) -> dict:
    goto_view(page, "results")
    t0 = time.time()
    last = ""
    while time.time() - t0 < timeout_s:
        text = page.locator("body").inner_text()
        last = text[:4000]
        if "Running models" not in text and ("kWh" in text or "Energy" in text or "Cost" in text or "Baseline" in text):
            break
        page.wait_for_timeout(2000)
        # refresh results view
        goto_view(page, "results")
    return {"snap": _save_snapshot(page, "results_final"), "body": last, "waited_s": round(time.time() - t0, 1)}


def main() -> int:
    creds = sketchbox_creds()
    if not creds["email"]:
        print("missing creds", file=sys.stderr)
        return 2
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=60)
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            storage_state=str(STORAGE) if STORAGE.is_file() else None,
        )
        page = context.new_page()
        login_fresh(page, creds)
        added = add_first_measure(page)
        results = wait_results(page, timeout_s=120)
        out = ART / f"{_ts()}_measure_run.json"
        out.write_text(json.dumps({"added": added, "results": results}, indent=2), encoding="utf-8")
        context.storage_state(path=str(STORAGE))
        print(json.dumps({"report": str(out), "picked": added.get("picked"), "waited_s": results.get("waited_s")}, indent=2))
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
