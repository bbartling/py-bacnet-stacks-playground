"""Programmatic WattLab Studio smoke check — walk every page, fail on any exception.

Usage (from vibe_code_apps_20):
  python scripts/smoke_studio.py

Mirrors vibe19's scripts/smoke_streamlit_app.py: AppTest catches script
errors that a plain HTTP 200 on the SPA shell would miss.

Pre-ship gate (with tests):
  python scripts/smoke_studio.py
  python -m pytest tests/test_studio_app.py -q
  python scripts/browser_smoke_vibe20.py --url http://localhost:8520 \\
      --screenshots .artifacts/browser/native
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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

MINIMAL_DUMP = ROOT / "tests" / "fixtures" / "minimal_wattlab_dump"


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

    # Bare walk: every page must render without state.
    for page in PAGES:
        at.radio(key="studio_page").set_value(page).run()
        if at.exception:
            return _fail(at, page)
    print(f"OK: bare walk of {len(PAGES)} pages, 0 exceptions")

    # Dump path: load minimal fixture → Data Explorer + Assumption Ledger.
    if MINIMAL_DUMP.is_dir():
        at.radio(key="studio_page").set_value("Ingest").run()
        at.text_input(key="studio_dump_folder").set_value(str(MINIMAL_DUMP)).run()
        at.button(key="studio_load_dump").click().run()
        if at.exception:
            return _fail(at, "Ingest(load dump)")
        if "studio_bundle" not in at.session_state:
            print("FAIL: studio_bundle missing after Load dump")
            return 1
        at.radio(key="studio_page").set_value("Data Explorer").run()
        if at.exception:
            return _fail(at, "Data Explorer(loaded)")
        at.radio(key="studio_page").set_value("Assumption Ledger").run()
        if at.exception:
            return _fail(at, "Assumption Ledger(loaded)")
        print("OK: minimal dump → Data Explorer + Assumption Ledger")
    else:
        print(f"WARN: missing fixture {MINIMAL_DUMP}; skipped dump walk")

    # Loaded walk: Liberty bills -> profile -> measures -> dry-run -> gated plan.
    at.radio(key="studio_page").set_value("Benchmark").run()
    at.button(key="studio_load_campus").click().run()
    if at.exception:
        return _fail(at, "Benchmark(load)")
    summary = at.session_state["studio_benchmark_summary"]
    print(
        f"OK: Liberty loaded - campus EUI {summary['campus']['site_eui_kbtu_ft2']} kBtu/ft2, "
        f"window {summary['window']['start']}..{summary['window']['end']}"
    )
    at.selectbox(key="studio_allocation").set_value("gas_share").run()
    if at.exception:
        return _fail(at, "Benchmark(gas_share)")

    at.radio(key="studio_page").set_value("Fuel Weather").run()
    at.button(key="fuel_weather_load_campus").click().run()
    if at.exception:
        return _fail(at, "Fuel Weather(load)")
    at.button(key="fuel_weather_synth").click().run()
    if at.exception:
        return _fail(at, "Fuel Weather(synth)")
    print("OK: Fuel Weather loaded + synthetic OAT")

    at.radio(key="studio_page").set_value("Model").run()
    at.text_input(key="studio_btype").set_value("office")
    at.text_input(key="studio_city").set_value("madison")
    at.number_input(key="studio_area").set_value(75000.0)
    at.button[0].set_value(True).run()
    if at.exception:
        return _fail(at, "Model(resolve)")
    try:
        at.session_state["studio_profile"]
    except KeyError:
        print("FAIL on page 'Model(resolve)': profile was not resolved")
        return 1

    at.radio(key="studio_page").set_value("Assumption Ledger").run()
    if at.exception:
        return _fail(at, "Assumption Ledger(profile)")

    at.radio(key="studio_page").set_value("Measures").run()
    at.button(key="studio_build_measures").click().run()
    if at.exception:
        return _fail(at, "Measures(build)")

    at.radio(key="studio_page").set_value("Twin loop").run()
    at.button(key="studio_dry_run").click().run()
    if at.exception:
        return _fail(at, "Twin loop(dry-run)")

    at.radio(key="studio_page").set_value("Capital plan").run()
    if at.exception:
        return _fail(at, "Capital plan")
    gate = at.session_state["studio_guardrail_gate"]
    print(
        f"OK: loaded walk complete - guardrail verdict {gate['verdict']} "
        f"({gate['investigate_count']} investigate)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
