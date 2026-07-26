"""Programmatic WattLab Studio smoke — 4-page dumb-down walk.

Usage (from vibe_code_apps_20):
  python scripts/smoke_studio.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PAGES = [
    "Uploads",
    "Fuel dashboard",
    "Twin / calibrate",
    "ECMs",
]

MINIMAL_DUMP = ROOT / "tests" / "fixtures" / "minimal_wattlab_dump"
FIXTURE_CAMPUS = ROOT / "tests" / "fixtures" / "shared_meter_campus"


def _fail(at, page: str) -> int:
    print(f"FAIL on page {page!r}:")
    for exc in at.exception:
        print(f"  - {exc.value}")
    return 1


def main() -> int:
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "studio.py"), default_timeout=120)
    at.run()
    if at.exception:
        return _fail(at, "boot")

    for page in PAGES:
        at.radio(key="studio_page").set_value(page).run()
        if at.exception:
            return _fail(at, page)
    print(f"OK: bare walk of {len(PAGES)} pages, 0 exceptions")

    if MINIMAL_DUMP.is_dir():
        at.radio(key="studio_page").set_value("Uploads").run()
        at.text_input(key="uploads_dump_path").set_value(str(MINIMAL_DUMP)).run()
        at.button(key="uploads_load_dump").click().run()
        if at.exception:
            return _fail(at, "Uploads(dump)")
        print("OK: minimal dump loaded")

    if FIXTURE_CAMPUS.is_dir():
        at.radio(key="studio_page").set_value("Uploads").run()
        at.text_input(key="uploads_energy_path").set_value(str(FIXTURE_CAMPUS)).run()
        at.button(key="uploads_load_energy").click().run()
        if at.exception:
            return _fail(at, "Uploads(energy)")
        at.radio(key="studio_page").set_value("Fuel dashboard").run()
        if at.exception:
            return _fail(at, "Fuel dashboard(loaded)")
        at.button(key="fuel_dash_synth").click().run()
        if at.exception:
            return _fail(at, "Fuel dashboard(synth)")
        print("OK: energy fixture + Fuel dashboard synth")

    at.radio(key="studio_page").set_value("Twin / calibrate").run()
    at.text_input(key="twin_btype").set_value("office")
    at.text_input(key="twin_city").set_value("detroit")
    at.number_input(key="twin_area").set_value(75000.0)
    at.button(key="FormSubmitter:twin_profile_form-Resolve profile").click().run()
    if at.exception:
        return _fail(at, "Twin(resolve)")
    at.button(key="twin_dry_run").click().run()
    if at.exception:
        return _fail(at, "Twin(dry-run)")
    # Client deliverable package (no live E+ required)
    at.button(key="twin_build_deliverable").click().run()
    if at.exception:
        return _fail(at, "Twin(deliverable)")
    print("OK: Twin deliverable build (no Streamlit exceptions)")

    at.radio(key="studio_page").set_value("ECMs").run()
    if at.exception:
        return _fail(at, "ECMs")
    page = " ".join(str(x) for x in at.markdown) + " ".join(str(x) for x in at.caption)
    if "Advanced — Easy Buttons" in page or "Include client DOCX" in page:
        print("FAIL: Advanced / DOCX still present on ECMs (BUG-043)")
        return 1
    # Mirror UI — Reload / Rebuild from scenario (no invent Build)
    keys = [str(getattr(b, "key", "") or "") for b in at.button]
    if not any("ecm_notebook_reload" in k or "ecm_notebook_rebuild_scenario" in k for k in keys):
        print("FAIL: ECMs mirror buttons missing (BUG-050)")
        return 1
    print("OK: ECMs disk-mirror page (no Streamlit exceptions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
