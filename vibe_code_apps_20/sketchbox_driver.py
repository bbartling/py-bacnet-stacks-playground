"""Playwright probe / driver for https://www.sketchbox.io/

Phase 1 (no creds): dump login DOM + screenshot.
Phase 2 (with SKETCHBOX_EMAIL/PASSWORD in .env): sign in and inventory UI.

Usage (from vibe_code_apps_20):
  python sketchbox_driver.py probe
  python sketchbox_driver.py login
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

ART = ROOT / ".artifacts"
ART.mkdir(exist_ok=True)


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _save_snapshot(page, label: str) -> dict[str, str]:
    stamp = _ts()
    png = ART / f"{stamp}_{label}.png"
    html = ART / f"{stamp}_{label}.html"
    page.screenshot(path=str(png), full_page=True)
    html.write_text(page.content(), encoding="utf-8")
    return {"png": str(png), "html": str(html), "url": page.url, "title": page.title()}


def _inventory_inputs(page) -> list[dict]:
    rows = []
    for loc in page.locator("input, button, select, a, textarea, [role=button]").all():
        try:
            tag = loc.evaluate("el => el.tagName.toLowerCase()")
            info = {
                "tag": tag,
                "type": loc.get_attribute("type") or "",
                "name": loc.get_attribute("name") or "",
                "id": loc.get_attribute("id") or "",
                "placeholder": loc.get_attribute("placeholder") or "",
                "text": (loc.inner_text() or "")[:80].strip(),
                "aria": loc.get_attribute("aria-label") or "",
                "href": loc.get_attribute("href") or "",
            }
            rows.append(info)
        except Exception:
            continue
    return rows


def cmd_probe(creds: dict) -> int:
    """Unauthenticated landing / login page dump."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not creds["headed"], slow_mo=creds["slow_mo_ms"])
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.goto(creds["base_url"] + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        snap = _save_snapshot(page, "probe_login")
        inv = _inventory_inputs(page)
        out = ART / f"{_ts()}_probe_inventory.json"
        out.write_text(json.dumps({"snap": snap, "controls": inv}, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "snap": snap, "n_controls": len(inv), "inventory": str(out)}, indent=2))
        browser.close()
    return 0


def cmd_login(creds: dict) -> int:
    if not creds["email"] or not creds["password"]:
        print(
            "Missing SKETCHBOX_EMAIL / SKETCHBOX_PASSWORD.\n"
            f"Copy {ROOT / '.env.example'} → {ROOT / '.env'} and fill them in.",
            file=sys.stderr,
        )
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not creds["headed"], slow_mo=creds["slow_mo_ms"])
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.goto(creds["base_url"] + "/", wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1000)
        _save_snapshot(page, "before_login")

        # Prefer known Sketchbox login ids from probe
        email_box = page.locator("#sign-in-email")
        if email_box.count() == 0:
            email_box = page.locator(
                'input[type="email"], input[name*="email" i], input[placeholder*="email" i]'
            ).first
        else:
            email_box = email_box.first
        pass_box = page.locator("#sign-in-password")
        if pass_box.count() == 0:
            pass_box = page.locator('input[type="password"]').first
        else:
            pass_box = pass_box.first
        email_box.wait_for(state="visible", timeout=20000)
        email_box.fill(creds["email"])
        pass_box.fill(creds["password"])

        # Sign In button
        btn = page.get_by_role("button", name=re.compile(r"sign\s*in", re.I))
        if btn.count() == 0:
            btn = page.locator('button[type="submit"], input[type="submit"]').first
        else:
            btn = btn.first
        btn.click()
        page.wait_for_timeout(4000)
        # Wait for navigation away from bare login, or error text
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        snap = _save_snapshot(page, "after_login")
        inv = _inventory_inputs(page)
        body_text = page.locator("body").inner_text()[:4000]
        out = ART / f"{_ts()}_login_inventory.json"
        payload = {
            "snap": snap,
            "controls": inv,
            "body_excerpt": body_text,
            "looks_logged_in": "sign in" not in body_text.lower()[:500]
            or "welcome" not in page.title().lower(),
        }
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(json.dumps({"ok": True, "url": page.url, "title": page.title(), "inventory": str(out), "snap": snap}, indent=2))
        # Keep session storage for next steps
        storage = ART / "sketchbox_storage.json"
        context.storage_state(path=str(storage))
        print(f"Wrote storage state -> {storage}")
        browser.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Sketchbox Playwright driver")
    ap.add_argument("cmd", choices=["probe", "login"], help="probe=login page; login=sign in with .env")
    args = ap.parse_args()
    creds = sketchbox_creds()
    if args.cmd == "probe":
        return cmd_probe(creds)
    return cmd_login(creds)


if __name__ == "__main__":
    raise SystemExit(main())
