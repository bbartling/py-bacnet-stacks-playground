"""Streamlit AppTest coverage for dumbed-down WattLab Studio (4 pages)."""

from __future__ import annotations

import sys
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest

from wattlab.studio.state import invalidate_dependent_state, namespaced_key

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "studio.py"
TIMEOUT = 60
MINIMAL_DUMP = ROOT / "tests" / "fixtures" / "minimal_wattlab_dump"
FIXTURE_CAMPUS = ROOT / "tests" / "fixtures" / "shared_meter_campus" / "campus.json"

ALL_PAGES = [
    "Uploads",
    "Fuel dashboard",
    "Twin / calibrate",
    "ECMs",
]


def _boot(page: str | None = None) -> AppTest:
    at = AppTest.from_file(str(STUDIO), default_timeout=TIMEOUT)
    at.run()
    assert not at.exception
    if page is not None:
        at.radio(key="studio_page").set_value(page).run()
        assert not at.exception
    return at


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def test_studio_state_namespaces_and_invalidates_derived_results():
    state = {"unrelated": "keep"}
    assert namespaced_key("hypothesis_lab", "result") == "hypothesis_lab.result"
    assert not invalidate_dependent_state(state, profile={"city": "madison"})
    state["hypothesis_lab.result"] = {"badge": "CONCEPTUAL_HYPOTHESIS"}
    state["ecm_easy.scenario_ids"] = ["ECM-AHU-SCHED-ALIGN"]
    assert invalidate_dependent_state(state, profile={"city": "detroit"})
    assert "hypothesis_lab.result" not in state
    assert "ecm_easy.scenario_ids" not in state
    assert state["unrelated"] == "keep"


def test_studio_boots_on_uploads():
    at = _boot()
    assert at.radio(key="studio_page").value == "Uploads"
    assert not at.exception


@pytest.mark.parametrize("page", ALL_PAGES)
def test_studio_every_page_loads_without_exception(page: str):
    at = _boot(page)
    assert at.radio(key="studio_page").value == page
    assert not at.exception


def test_studio_uploads_load_minimal_dump():
    assert MINIMAL_DUMP.is_dir()
    at = _boot("Uploads")
    at.text_input(key="uploads_dump_path").set_value(str(MINIMAL_DUMP)).run()
    at.button(key="uploads_load_dump").click().run()
    assert not at.exception
    assert "studio_bundle" in at.session_state


def test_studio_fuel_dashboard_with_fixture_campus():
    assert FIXTURE_CAMPUS.is_file()
    at = _boot("Uploads")
    at.text_input(key="uploads_energy_path").set_value(str(FIXTURE_CAMPUS.parent)).run()
    at.button(key="uploads_load_energy").click().run()
    assert not at.exception
    assert "studio_campus" in at.session_state or "studio_energy" in at.session_state
    at.radio(key="studio_page").set_value("Fuel dashboard").run()
    assert not at.exception
    at.button(key="fuel_dash_synth").click().run()
    assert not at.exception


def test_studio_twin_and_ecms_dry_path():
    at = _boot("Twin / calibrate")
    # form submit is button[0]
    at.text_input(key="twin_btype").set_value("office")
    at.text_input(key="twin_city").set_value("detroit")
    at.number_input(key="twin_area").set_value(75000.0)
    at.button[0].set_value(True).run()
    assert not at.exception
    assert "studio_profile" in at.session_state

    at.button(key="twin_dry_run").click().run()
    assert not at.exception
    assert "studio_plan" in at.session_state

    at.radio(key="studio_page").set_value("ECMs").run()
    assert not at.exception
    at.button(key="ecm_build_measures").click().run()
    assert not at.exception
    assert "studio_guardrail_gate" in at.session_state


def test_turnkey_live_html_smoke():
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(STUDIO),
            "--server.headless",
            "true",
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
        ],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        url = f"http://127.0.0.1:{port}/_stcore/health"
        deadline = time.time() + 45
        body = ""
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=2) as resp:
                    body = resp.read().decode("utf-8", errors="replace")
                    if "ok" in body.lower():
                        break
            except (urllib.error.URLError, TimeoutError, ConnectionError):
                time.sleep(0.5)
        assert "ok" in body.lower()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
