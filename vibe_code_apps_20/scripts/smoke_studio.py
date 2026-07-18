"""Programmatic WattLab Studio smoke check — walk every page, fail on any exception.

Usage (from vibe_code_apps_20):
  python scripts/smoke_studio.py

Mirrors vibe19's scripts/smoke_streamlit_app.py: AppTest catches script
errors that a plain HTTP 200 on the SPA shell would miss.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PAGES = ["Ingest", "Model", "Benchmark", "Measures", "Twin loop", "Capital plan"]


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

    # Loaded walk: Liberty bills -> profile -> measures -> dry-run -> gated plan.
    at.radio(key="studio_page").set_value("Benchmark").run()
    at.button(key="studio_load_campus").click().run()
    if at.exception:
        return _fail(at, "Benchmark(load)")
    summary = at.session_state["studio_benchmark_summary"]
    print(f"OK: Liberty loaded - campus EUI {summary['campus']['site_eui_kbtu_ft2']} kBtu/ft2, "
          f"window {summary['window']['start']}..{summary['window']['end']}")
    at.selectbox(key="studio_allocation").set_value("gas_share").run()
    if at.exception:
        return _fail(at, "Benchmark(gas_share)")

    at.radio(key="studio_page").set_value("Model").run()
    at.button[0].set_value(True).run()
    if at.exception:
        return _fail(at, "Model(resolve)")

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
    print(f"OK: loaded walk complete - guardrail verdict {gate['verdict']} "
          f"({gate['investigate_count']} investigate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
