#!/usr/bin/env python3
"""Playwright browser smoke for WattLab Studio (Vibe 20).

Walks every sidebar page; optionally uploads a WattLab dump and opens
Data Explorer + Assumption Ledger. Fails on Traceback / StreamlitAPIException /
PlotlyError / page errors.

Usage:
  python scripts/browser_smoke_vibe20.py --url http://localhost:8520 \\
      --screenshots .artifacts/browser/native

  python scripts/browser_smoke_vibe20.py --url http://localhost:8520 \\
      --package path/to/wattlab_dump.zip --screenshots .artifacts/browser/ghcr
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FATAL_PAGE_PATTERNS = (
    "Traceback",
    "StreamlitAPIException",
    "PlotlyError",
    "Exception:",
    "ModuleNotFoundError",
    "AttributeError:",
    "TypeError:",
    "ValueError:",
)

PAGES = [
    "Ingest",
    "Data Explorer",
    "Assumption Ledger",
    "Model",
    "Benchmark",
    "Fuel Weather",
    "Measures",
    "Twin loop",
    "EP Results",
    "Hypothesis Lab",
    "ECM Easy Buttons",
    "Capital plan",
]


def _minimal_dump_zip() -> bytes:
    """Tiny wattlab_dump_v3 zip for upload smoke when --package omitted."""
    files = {
        "MANIFEST.json": json.dumps(
            {
                "schema_version": "wattlab_dump_v3",
                "export_profile": "summary",
                "file_count": 4,
                "files": [
                    {
                        "path": "fdd_findings.csv",
                        "kind": "fdd",
                        "purpose": "findings",
                        "how_to_use": "read",
                    }
                ],
            },
            indent=2,
        ),
        "model_seed.json": json.dumps(
            {
                "project_id": "BROWSER_SMOKE",
                "building_type": None,
                "city": None,
                "floor_area_ft2": None,
            },
            indent=2,
        ),
        "fdd_findings.csv": (
            "rule_id,equipment_id,status,confirmed_fault,fault_hours\n"
            "FC1,AHU_1,FAULT,True,1.0\n"
        ),
        "fdd_summary.csv": "rule_id,equipment_id,status\nFC1,AHU_1,fault\n",
        "operating_signatures.csv": "equipment_id,bin_start,on_fraction\nAHU_1,50,0.4\n",
        "telemetry/AHU_1.csv": (
            "timestamp_utc,sat,fan_status\n"
            "2024-06-01T00:00:00Z,55,1\n"
        ),
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return buf.getvalue()


def _assert_no_fatal(page) -> None:
    body = page.content()
    for pat in FATAL_PAGE_PATTERNS:
        if pat in body:
            raise AssertionError(f"Fatal page pattern {pat!r} found in DOM")


def _click_workflow(page, label: str) -> None:
    # Streamlit sidebar radio: click the label text.
    page.get_by_text(label, exact=True).first.click()
    page.wait_for_timeout(800)


def run_smoke(*, url: str, screenshots: Path, package: Path | None, headed: bool) -> None:
    from playwright.sync_api import sync_playwright

    screenshots.mkdir(parents=True, exist_ok=True)
    console_errors: list[str] = []
    page_errors: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        context = browser.new_context(viewport={"width": 1400, "height": 900})
        page = context.new_page()
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: page_errors.append(str(exc)))

        page.goto(url, wait_until="domcontentloaded", timeout=120_000)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(screenshots / "00_startup.png"), full_page=True)
        _assert_no_fatal(page)

        for label in PAGES:
            _click_workflow(page, label)
            _assert_no_fatal(page)
            safe = label.lower().replace(" ", "_")
            page.screenshot(path=str(screenshots / f"page_{safe}.png"), full_page=True)

        # Dump path: upload → Load dump → Data Explorer + Assumption Ledger
        _click_workflow(page, "Ingest")
        zip_path = package
        if zip_path is None:
            zip_path = screenshots / "_packages" / "browser_smoke_minimal.zip"
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            zip_path.write_bytes(_minimal_dump_zip())
        else:
            zip_path = Path(zip_path)

        file_input = page.locator('input[type="file"]').first
        file_input.set_input_files(str(zip_path))
        page.wait_for_timeout(1000)
        load_btn = page.get_by_role("button", name="Load dump")
        # Streamlit may keep the button disabled briefly after upload.
        for _ in range(30):
            if load_btn.is_enabled():
                break
            page.wait_for_timeout(500)
        if not load_btn.is_enabled():
            raise AssertionError("Load dump remained disabled after file upload")
        load_btn.click()
        page.wait_for_timeout(2500)
        _assert_no_fatal(page)
        page.screenshot(path=str(screenshots / "ingest_loaded.png"), full_page=True)

        _click_workflow(page, "Data Explorer")
        _assert_no_fatal(page)
        page.screenshot(path=str(screenshots / "data_explorer.png"), full_page=True)

        _click_workflow(page, "Assumption Ledger")
        _assert_no_fatal(page)
        page.screenshot(path=str(screenshots / "assumption_ledger.png"), full_page=True)

        browser.close()

    fatal_console = [e for e in console_errors if any(p in e for p in FATAL_PAGE_PATTERNS)]
    if page_errors:
        raise AssertionError("Page errors: " + "; ".join(page_errors[:5]))
    if fatal_console:
        raise AssertionError("Console errors: " + "; ".join(fatal_console[:5]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", default="http://localhost:8520")
    ap.add_argument("--screenshots", type=Path, default=ROOT / ".artifacts" / "browser" / "native")
    ap.add_argument("--package", type=Path, default=None, help="Optional WattLab dump zip")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args(argv)

    t0 = time.time()
    try:
        run_smoke(
            url=args.url,
            screenshots=args.screenshots,
            package=args.package,
            headed=args.headed,
        )
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK browser smoke: {len(PAGES)} pages + dump explorer/ledger "
        f"in {time.time() - t0:.1f}s -> {args.screenshots}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
