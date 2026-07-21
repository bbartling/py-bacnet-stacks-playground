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
    at.button(key="ecm_build_measures").click().run()
    if at.exception:
        return _fail(at, "ECMs(build)")
    try:
        gate = at.session_state["studio_guardrail_gate"]
    except KeyError:
        print("FAIL: studio_guardrail_gate missing after ECMs build")
        return 1
    print(
        f"OK: loaded walk complete - guardrail verdict {gate.get('verdict')} "
        f"({gate.get('investigate_count')} investigate)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
