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
    # Metrics must include campus EUI + peer typical bands
    metric_labels = [m.label for m in at.metric]
    assert any("EUI" in (lab or "") for lab in metric_labels)
    assert any("p50" in (lab or "") or "typical" in (lab or "").lower() for lab in metric_labels)
    at.button(key="fuel_dash_synth").click().run()
    assert not at.exception


def test_studio_twin_eui_index_section():
    at = _boot("Twin / calibrate")
    assert not at.exception
    # EUI index subheader always renders
    assert any("EUI" in str(getattr(el, "value", el)) for el in at.subheader)


def test_studio_twin_and_ecms_dry_path(tmp_path, monkeypatch):
    # ECMs = spreadsheet vs EnergyPlus compare (no agent xlsx required)
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    (tmp_path / "reports").mkdir(parents=True, exist_ok=True)

    at = _boot("ECMs")
    assert not at.exception
    page = " ".join(str(x) for x in at.markdown) + " ".join(str(x) for x in at.caption)
    assert "Advanced — Easy Buttons" not in page
    assert "Include client DOCX" not in page

    btn_keys = [str(getattr(b, "key", "") or "") for b in at.button]
    assert any("ecm_compare_run" in k for k in btn_keys)
    assert not any("ecm_notebook_rebuild_scenario" in k for k in btn_keys)
    assert not any("ecm_notebook_build" in k for k in btn_keys)

    ui_blob = " ".join(
        str(getattr(el, "value", el))
        for group in (at.subheader, at.markdown, at.caption)
        for el in group
    )
    assert "Spreadsheet" in ui_blob or "spreadsheet" in page.lower()
    assert "EnergyPlus" in ui_blob or "EnergyPlus" in page
    assert "Formulas used" not in ui_blob
    assert "ESCO_Calcs" not in ui_blob
    assert not at.exception

    # Stub compare file written on first render
    from wattlab.ecm.compare import compare_path, load_compare

    cmp = load_compare(compare_path(tmp_path / "reports"))
    assert cmp is not None
    assert cmp["spreadsheet"]["status"] == "pending_external"
    assert len(cmp["measures"]) >= 3


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
