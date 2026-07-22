"""Live 08 progress helpers + t12 status/bootstrap fixes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wattlab.energyplus.docker import heuristic_ep_percent, write_progress
from wattlab.studio.bootstrap import (
    build_bootstrap_payload,
    merge_bootstrap_payload,
    write_bootstrap,
)
from wattlab.studio.ecm_scenario import load_ecm_scenario, save_ecm_scenario
from wattlab.studio.status import build_session_status, soften_required_gaps


def test_heuristic_ep_percent_increases():
    pct = 0
    pct = heuristic_ep_percent("Warmup Simulation", pct)
    assert pct >= 10
    pct = heuristic_ep_percent("Starting Simulation", pct)
    assert pct >= 25
    pct = heuristic_ep_percent("Simulating January", pct)
    assert pct >= 40
    pct = heuristic_ep_percent("EnergyPlus Completed Successfully", pct)
    assert pct >= 98


def test_write_progress_atomic(tmp_path: Path):
    write_progress(tmp_path, percent=42, status="running")
    data = json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))
    assert data["percent"] == 42
    assert data["status"] == "running"


def test_load_ecm_scenario_status_from_ids(tmp_path: Path):
    path = tmp_path / "ecm_scenario.json"
    path.write_text(
        json.dumps({"version": 1, "selected_ecm_ids": ["ECM-A", "ECM-B"]}),
        encoding="utf-8",
    )
    loaded = load_ecm_scenario(path)
    assert loaded["status"] == "2 ECMs selected"
    save_ecm_scenario({"selected_ecm_ids": []}, path=path)
    assert load_ecm_scenario(path)["status"].startswith("empty")


def test_session_status_g14_and_bills(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    (tmp_path / "reports").mkdir(parents=True)
    (tmp_path / "runs" / "cal_run").mkdir(parents=True)
    answers = {
        "building_type": "office",
        "city": "detroit",
        "floor_area_ft2": 140000,
        "utility_bills": [{"month": "2024-01", "kwh": 1}],
        "utility": {"elec_usd_per_kwh": 0.12},
    }
    (tmp_path / "reports" / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
    (tmp_path / "reports" / "utility_bills.csv").write_text("month,kwh\n2024-01,1\n", encoding="utf-8")
    scorecard = {
        "status": "screening",
        "utility_bills": {
            "pass_fail": "fail",
            "months_compared": 12,
            "stats_electricity": {"nmbe_pct": 52.1, "cvrmse_pct": 57.0},
        },
    }
    (tmp_path / "runs" / "cal_run" / "calibration_scorecard.json").write_text(
        json.dumps(scorecard), encoding="utf-8"
    )
    (tmp_path / "studio_bootstrap.json").write_text(
        json.dumps(
            {
                "version": 1,
                "answers_path": "reports/answers.json",
                "preferred_run_id": "cal_run",
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "reports" / "ecm_scenario.json").write_text(
        json.dumps({"selected_ecm_ids": ["ECM-AHU-SCHED-ALIGN"]}),
        encoding="utf-8",
    )
    status = build_session_status(workspace=tmp_path)
    assert status["fields"]["utility_bills"]["status"] == "answered"
    assert status["twin"]["g14"]["nmbe_elec_pct"] == 52.1
    assert "1 ECMs" in status["ecm_scenario"]["status"]
    soft = soften_required_gaps(
        [{"field": "utility", "severity": "recommended", "status": "missing"}],
        answers,
    )
    assert soft[0]["status"] == "answered"


def test_bootstrap_ecm_merge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    write_bootstrap(
        build_bootstrap_payload(
            energy_campus_dir="uploads/energy/x",
            ecm_scenario_path="reports/ecm_scenario.json",
            notes="keep me",
        )
    )
    merged = merge_bootstrap_payload(
        build_bootstrap_payload(preferred_run_id="new_run"),
        existing_path=tmp_path / "studio_bootstrap.json",
    )
    # preferred updated; campus + ecm preserved
    assert merged["preferred_run_id"] == "new_run"
    assert merged["energy_campus_dir"] == "uploads/energy/x"
    assert merged["ecm_scenario_path"] == "reports/ecm_scenario.json"


def test_detroit_latlon_epw_note():
    from wattlab.defaults import resolve_profile

    profile = resolve_profile(
        {
            "building_type": "office",
            "city": "detroit",
            "floor_area_ft2": 140000,
            "lat": 42.33,
            "lon": -83.04,
        }
    )
    note = str((profile.get("energyplus") or {}).get("epw_note") or "")
    assert "Open-Meteo" in note or "lat=" in note or "AMY" in note.upper() or "screening TMY" in note


def test_studio_apptest_no_exception_with_answers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    from wattlab.studio.bootstrap import build_bootstrap_payload, write_bootstrap

    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    monkeypatch.delenv("WATTLAB_STUDIO_BOOTSTRAP_DISABLE", raising=False)
    (tmp_path / "reports").mkdir(parents=True)
    answers = {
        "building_type": "office",
        "city": "detroit",
        "floor_area_ft2": 140000,
        "floors": 6,
        "lat": 42.33,
        "lon": -83.04,
    }
    (tmp_path / "reports" / "answers.json").write_text(json.dumps(answers), encoding="utf-8")
    write_bootstrap(
        build_bootstrap_payload(
            preferred_run_id="noop",
            answers_path="reports/answers.json",
        )
    )
    root = Path(__file__).resolve().parents[1]
    at = AppTest.from_file(str(root / "studio.py"), default_timeout=60)
    at.run()
    assert not at.exception
    assert "studio_profile" in at.session_state
    at.radio(key="studio_page").set_value("ECMs").run()
    assert not at.exception
    at.radio(key="studio_page").set_value("Twin / calibrate").run()
    assert not at.exception
    at.radio(key="studio_page").set_value("Fuel dashboard").run()
    assert not at.exception
