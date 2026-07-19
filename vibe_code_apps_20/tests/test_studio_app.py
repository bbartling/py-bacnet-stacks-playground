"""Streamlit AppTest coverage for WattLab Studio (dry-run path, no Docker)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "studio.py"
TIMEOUT = 60


def _boot(page: str | None = None) -> AppTest:
    at = AppTest.from_file(str(STUDIO), default_timeout=TIMEOUT)
    at.run()
    assert not at.exception
    if page is not None:
        at.radio(key="studio_page").set_value(page).run()
        assert not at.exception
    return at


def test_studio_boots_on_ingest():
    at = _boot()
    assert at.radio(key="studio_page").value == "Ingest"
    # No dump loaded yet — the page should hint instead of crashing.
    assert any("No dump loaded" in str(block.value) for block in at.info)


def test_studio_ep_results_page_loads_without_dump():
    at = _boot("EP Results")
    assert at.radio(key="studio_page").value == "EP Results"
    assert not at.exception
    # Empty state should hint, not crash
    info_text = " ".join(str(b.value) for b in at.info)
    assert "eplusout" in info_text.lower() or "dump" in info_text.lower() or "scorecard" in info_text.lower()


def test_studio_model_resolves_profile_with_defaults():
    at = _boot("Model")
    at.text_input(key="studio_btype").set_value("office")
    at.text_input(key="studio_city").set_value("madison")
    at.number_input(key="studio_area").set_value(75000.0)
    at.button[0].set_value(True).run()  # form submit
    assert not at.exception
    profile = at.session_state["studio_profile"]
    assert profile["building_type"] == "office"
    assert profile["conditioned_floor_area_ft2"] == 75000.0
    assert profile.get("field_sources")


def test_studio_measures_builds_list_with_proxy_savings():
    at = _boot("Model")
    at.text_input(key="studio_btype").set_value("office")
    at.text_input(key="studio_city").set_value("madison")
    at.number_input(key="studio_area").set_value(75000.0)
    at.button[0].set_value(True).run()
    at.radio(key="studio_page").set_value("Measures").run()
    assert not at.exception
    at.button(key="studio_build_measures").click().run()
    assert not at.exception
    measures = at.session_state["studio_measures"]
    assert measures, "expected measures from the selected set"
    proxies = at.session_state["studio_proxies"]
    assert set(proxies) == {m["measure_id"] for m in measures}
    # Scheduling measures should get a nonzero ESCO proxy estimate.
    sched = [mid for mid in proxies if "SCHED" in mid]
    assert sched and proxies[sched[0]]["savings_kwh"] > 0


def test_studio_twin_loop_dry_run_plan():
    at = _boot("Model")
    at.text_input(key="studio_btype").set_value("office")
    at.text_input(key="studio_city").set_value("madison")
    at.number_input(key="studio_area").set_value(75000.0)
    at.button[0].set_value(True).run()
    at.radio(key="studio_page").set_value("Measures").run()
    at.button(key="studio_build_measures").click().run()
    at.radio(key="studio_page").set_value("Twin loop").run()
    assert not at.exception
    at.button(key="studio_dry_run").click().run()
    assert not at.exception
    plan = at.session_state["studio_plan"]
    assert plan["dry_run"] is True
    steps = [s["step"] for s in plan["steps"]]
    assert "select_prototype" in steps and "simulate" in steps
    assert plan["approved_measure_ids"]


def test_studio_benchmark_page_loads_liberty_campus():
    at = _boot("Benchmark")
    # Liberty example path is pre-filled; load and annualize.
    at.button(key="studio_load_campus").click().run()
    assert not at.exception
    campus = at.session_state["studio_campus"]
    assert campus.campus_id == "liberty"
    summary = at.session_state["studio_benchmark_summary"]
    assert summary["campus"]["site_eui_kbtu_ft2"] == 71.6
    assert summary["window"]["start"] == "2024-12"
    # Switching allocation reruns the summary with the new split.
    at.selectbox(key="studio_allocation").set_value("gas_share").run()
    assert not at.exception
    euis = {b["building_id"]: b["site_eui_kbtu_ft2"]
            for b in at.session_state["studio_benchmark_summary"]["buildings"]}
    assert euis["liberty_50"] == 62.2 and euis["liberty_100"] == 81.0


def test_studio_capital_plan_gated_by_benchmarks():
    at = _boot("Benchmark")
    at.button(key="studio_load_campus").click().run()
    at.radio(key="studio_page").set_value("Model").run()
    at.text_input(key="studio_btype").set_value("office")
    at.text_input(key="studio_city").set_value("madison")
    at.number_input(key="studio_area").set_value(75000.0)
    at.button[0].set_value(True).run()
    at.radio(key="studio_page").set_value("Measures").run()
    at.button(key="studio_build_measures").click().run()
    at.radio(key="studio_page").set_value("Capital plan").run()
    assert not at.exception
    gate = at.session_state["studio_guardrail_gate"]
    assert gate["verdict"] in {"PUBLISH", "INVESTIGATE"}
    names = {c["check"] for c in gate["checks"]}
    # With Liberty bills loaded, the EUI and savings checks must actually run.
    assert {"baseline_eui_band", "savings_fraction"} <= names
    statuses = {c["check"]: c["status"] for c in gate["checks"]}
    assert statuses["baseline_eui_band"] != "skipped"
    assert statuses["savings_fraction"] != "skipped"


def test_studio_capital_plan_rollup_and_downloads():
    at = _boot("Model")
    at.button[0].set_value(True).run()
    at.radio(key="studio_page").set_value("Measures").run()
    at.button(key="studio_build_measures").click().run()
    at.radio(key="studio_page").set_value("Capital plan").run()
    assert not at.exception
    plan = at.session_state["studio_capital_plan"]
    assert plan["measures"], "capital plan should include measures"
    totals = plan["totals"]
    assert totals["implementation_cost_usd"] > 0
    assert totals["annual_cost_saved_usd"] > 0
    # Measures sorted by payback ascending (None last).
    paybacks = [m["simple_payback_years"] for m in plan["measures"] if m["simple_payback_years"] is not None]
    assert paybacks == sorted(paybacks)
