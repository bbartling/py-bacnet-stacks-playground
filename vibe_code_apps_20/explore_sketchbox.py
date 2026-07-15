"""Explore post-login Sketchbox tabs (SCHEDULES / MEASURES) using saved session or fresh login."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from config import ROOT, sketchbox_creds
from sketchbox_driver import ART, _inventory_inputs, _save_snapshot, _ts

STORAGE = ART / "sketchbox_storage.json"


def login_fresh(page, creds: dict) -> None:
    page.goto(creds["base_url"] + "/", wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(1500)
    # Already in the app?
    if page.locator('div.view-link[view="project"]').count() > 0:
        return
    if "sign-in-email" not in page.content() and "My Project" in (page.title() or ""):
        return
    email = page.locator("#sign-in-email")
    email.wait_for(state="visible", timeout=30000)
    email.fill(creds["email"])
    page.locator("#sign-in-password").fill(creds["password"])
    page.get_by_role("button", name=re.compile(r"sign\s*in", re.I)).click()
    page.wait_for_timeout(3000)
    page.locator('div.view-link[view="project"]').wait_for(state="visible", timeout=30000)


def click_tab(page, name: str) -> None:
    """Tabs are ``div.view-link[view=...]`` with lowercase labels (CSS may uppercase)."""
    key = name.strip().lower()
    loc = page.locator(f'div.view-link[view="{key}"]')
    if loc.count() == 0:
        loc = page.get_by_text(key, exact=False).first
    else:
        loc = loc.first
    loc.click(timeout=15000)
    page.wait_for_timeout(1500)


def try_tweak_schedule(page, *, mutate: bool = False) -> dict:
    """Open SCHEDULES and inventory controls. Mutations require ``mutate=True``."""
    notes: dict = {"actions": [], "mutate": mutate}
    click_tab(page, "SCHEDULES")
    page.wait_for_timeout(1000)
    notes["snap"] = _save_snapshot(page, "schedules_tab")
    notes["controls"] = _inventory_inputs(page)
    body = page.locator("body").inner_text()[:3000]
    notes["body_excerpt"] = body

    nums = page.locator('input[type="number"], input[type="text"]')
    n = nums.count()
    notes["n_inputs"] = n
    if mutate and n:
        for i in range(min(n, 12)):
            el = nums.nth(i)
            try:
                if not el.is_visible():
                    continue
                val = el.input_value()
                notes["actions"].append({"idx": i, "before": val})
                if val.replace(".", "", 1).isdigit():
                    new_v = "6" if val in {"0", "0.0", ""} else val
                    el.fill(new_v)
                    notes["actions"].append({"idx": i, "after": new_v, "status": "filled"})
                    break
            except Exception as exc:
                notes["actions"].append({"idx": i, "error": str(exc)})
        notes["snap_after"] = _save_snapshot(page, "schedules_after_tweak")
    else:
        notes["actions"].append({"status": "read_only", "note": "pass mutate=True to write"})
    return notes


def explore_measures(page) -> dict:
    click_tab(page, "MEASURES")
    page.wait_for_timeout(1200)
    return {
        "snap": _save_snapshot(page, "measures_tab"),
        "controls": _inventory_inputs(page),
        "body_excerpt": page.locator("body").inner_text()[:3500],
    }


def main() -> int:
    creds = sketchbox_creds()
    if not creds["email"] or not creds["password"]:
        print("Missing creds in .env", file=sys.stderr)
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, slow_mo=creds["slow_mo_ms"])
        context = browser.new_context(
            viewport={"width": 1400, "height": 900},
            storage_state=str(STORAGE) if STORAGE.is_file() else None,
        )
        page = context.new_page()
        login_fresh(page, creds)
        home = _save_snapshot(page, "explore_home")
        print(json.dumps({"home": home, "title": page.title()}, indent=2))

        sched = try_tweak_schedule(page)
        measures = explore_measures(page)

        # Also peek DESIGN + RESULTS labels
        for tab in ("DESIGN", "BASELINE", "RESULTS"):
            try:
                click_tab(page, tab)
                _save_snapshot(page, f"tab_{tab.lower()}")
            except Exception as exc:
                print(f"tab {tab} failed: {exc}")

        out = ART / f"{_ts()}_explore_report.json"
        out.write_text(
            json.dumps(
                {
                    "home": home,
                    "schedules": {
                        "n_inputs": sched.get("n_inputs"),
                        "actions": sched.get("actions"),
                        "snap": sched.get("snap"),
                        "snap_after": sched.get("snap_after"),
                        "body_excerpt": sched.get("body_excerpt"),
                    },
                    "measures": {
                        "snap": measures.get("snap"),
                        "body_excerpt": measures.get("body_excerpt"),
                        "n_controls": len(measures.get("controls") or []),
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        context.storage_state(path=str(STORAGE))
        print(f"Wrote report -> {out}")
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
