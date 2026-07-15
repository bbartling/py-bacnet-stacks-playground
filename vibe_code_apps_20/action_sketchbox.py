"""Targeted Sketchbox actions: fix/set cooling offset, open MEASURES, dump RESULTS if possible."""

from __future__ import annotations

import json
import re
import sys

from playwright.sync_api import sync_playwright

from config import sketchbox_creds
from explore_sketchbox import STORAGE, click_tab, login_fresh
from sketchbox_driver import ART, _save_snapshot, _ts


def set_cooling_offset(page, value: str = "2") -> dict:
    click_tab(page, "schedules")
    page.wait_for_timeout(800)
    result = {"target": value, "ok": False}
    el = page.locator('input[type="text"][title*="cooling setpoint by this offset"]').first
    try:
        if el.count():
            result["before"] = el.input_value()
            el.fill(value)
            el.press("Tab")
            result["ok"] = True
            result["after"] = value
            result["selector"] = 'title*=cooling setpoint by this offset'
    except Exception as exc:
        result["error"] = str(exc)
    page.wait_for_timeout(500)
    result["snap"] = _save_snapshot(page, "schedules_offset_set")
    return result


def open_measures(page) -> dict:
    # Force click via JS on view attribute
    page.evaluate("""() => {
      const el = document.querySelector('div.view-link[view="measures"]');
      if (el) el.click();
    }""")
    page.wait_for_timeout(2000)
    return {
        "snap": _save_snapshot(page, "measures_forced"),
        "active_view": page.evaluate("""() => {
          const a = document.querySelector('div.view-link.-active, div.view-link.active');
          return a ? a.getAttribute('view') : null;
        }"""),
        "body_head": page.locator("body").inner_text()[:2500],
    }


def main() -> int:
    creds = sketchbox_creds()
    if not creds["email"]:
        print("missing creds", file=sys.stderr)
        return 2
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=80)
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            storage_state=str(STORAGE) if STORAGE.is_file() else None,
        )
        page = context.new_page()
        login_fresh(page, creds)
        offset = set_cooling_offset(page, "2")
        measures = open_measures(page)
        # Try RESULTS similarly
        page.evaluate("""() => {
          const el = document.querySelector('div.view-link[view="results"]');
          if (el) el.click();
        }""")
        page.wait_for_timeout(2000)
        results = {
            "snap": _save_snapshot(page, "results_forced"),
            "body_head": page.locator("body").inner_text()[:2500],
        }
        out = ART / f"{_ts()}_action_report.json"
        out.write_text(json.dumps({"offset": offset, "measures": measures, "results": results}, indent=2), encoding="utf-8")
        context.storage_state(path=str(STORAGE))
        print(json.dumps({"report": str(out), "offset_ok": offset.get("ok"), "measures_active": measures.get("active_view")}, indent=2))
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
