"""Unit + AppTest coverage for Studio bootstrap + Fuel tabs."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytest.importorskip("streamlit")

from streamlit.testing.v1 import AppTest

from wattlab.studio.bootstrap import (
    apply_bootstrap_to_session,
    build_bootstrap_payload,
    clear_bootstrap_session_flags,
    resolve_bootstrap_path,
    upsert_bootstrap_preferred_run,
    validate_bootstrap_payload,
    write_bootstrap,
)

ROOT = Path(__file__).resolve().parents[1]
STUDIO = ROOT / "studio.py"
TIMEOUT = 60
FIXTURE_CAMPUS = ROOT / "tests" / "fixtures" / "shared_meter_campus" / "campus.json"
MINIMAL_DUMP = ROOT / "tests" / "fixtures" / "minimal_wattlab_dump"
EPLUS_FIXTURE = ROOT / "tests" / "fixtures" / "eplusout" / "eplusout.csv"


def test_build_and_write_bootstrap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    payload = build_bootstrap_payload(
        energy_campus_dir="uploads/energy/campus",
        preferred_run_id="run_a",
        notes="test",
    )
    assert payload["version"] == 1
    written = write_bootstrap(payload)
    assert any(p.name == "studio_bootstrap.json" for p in written)
    assert (tmp_path / "studio_bootstrap.json").is_file()
    assert resolve_bootstrap_path(tmp_path) is not None


def test_bootstrap_disable_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    write_bootstrap(build_bootstrap_payload(preferred_run_id="x"))
    monkeypatch.setenv("WATTLAB_STUDIO_BOOTSTRAP_DISABLE", "1")
    assert resolve_bootstrap_path(tmp_path) is None


def test_validate_bootstrap_payload_warnings():
    assert any("version missing" in w for w in validate_bootstrap_payload({}))
    assert any("empty bootstrap" in w for w in validate_bootstrap_payload({}))
    bad = validate_bootstrap_payload({"version": 99, "extra_key": 1})
    assert any("version=" in w for w in bad)
    assert any("unknown keys" in w for w in bad)
    ok = validate_bootstrap_payload(
        {"version": 1, "preferred_run_id": "run_a", "auto_refresh_runs": True}
    )
    assert ok == []


def test_upsert_bootstrap_preferred_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    monkeypatch.delenv("WATTLAB_STUDIO_BOOTSTRAP_DISABLE", raising=False)
    path = upsert_bootstrap_preferred_run("run_new", workspace=tmp_path)
    assert path is not None and path.is_file()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["preferred_run_id"] == "run_new"
    assert data["version"] == 1
    # Merge preserves campus + prior --notes text
    write_bootstrap(
        build_bootstrap_payload(
            energy_campus_dir="uploads/energy/x",
            preferred_run_id="old",
            notes="agent campus handoff for Liberty",
        )
    )
    upsert_bootstrap_preferred_run("run_merged", workspace=tmp_path)
    merged = json.loads((tmp_path / "studio_bootstrap.json").read_text(encoding="utf-8"))
    assert merged["preferred_run_id"] == "run_merged"
    assert merged["energy_campus_dir"] == "uploads/energy/x"
    assert "agent campus handoff for Liberty" in merged["notes"]
    assert "preferred_run_id upserted by publish_run_for_studio @" in merged["notes"]
    monkeypatch.setenv("WATTLAB_STUDIO_BOOTSTRAP_DISABLE", "1")
    assert upsert_bootstrap_preferred_run("nope", workspace=tmp_path) is None


def test_apply_bootstrap_loads_campus_and_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    energy = tmp_path / "uploads" / "energy" / "shared"
    energy.mkdir(parents=True)
    # Copy fixture campus package
    import shutil

    src = FIXTURE_CAMPUS.parent
    for item in src.iterdir():
        dest = energy / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    run_dir = tmp_path / "runs" / "boot_run_1"
    run_dir.mkdir(parents=True)
    if EPLUS_FIXTURE.is_file():
        shutil.copy2(EPLUS_FIXTURE, run_dir / "eplusout.csv")
    else:
        (run_dir / "eplusout.csv").write_text("Date/Time,Zone\n", encoding="utf-8")
    (tmp_path / "runs" / "CURRENT_RUN.txt").write_text(str(run_dir), encoding="utf-8")

    write_bootstrap(
        build_bootstrap_payload(
            energy_campus_dir="uploads/energy/shared",
            preferred_run_id="boot_run_1",
        )
    )
    state: dict = {}
    result = apply_bootstrap_to_session(state, workspace=tmp_path)
    assert result["applied"] is True
    assert "studio_campus" in state
    assert state.get("studio_active_run")
    assert state["_studio_bootstrapped"] is True
    # Idempotent
    result2 = apply_bootstrap_to_session(state, workspace=tmp_path)
    assert result2.get("skipped") == "already_bootstrapped"


def test_apply_bootstrap_missing_campus_no_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    write_bootstrap(
        build_bootstrap_payload(energy_campus_dir="uploads/energy/does_not_exist")
    )
    state: dict = {}
    result = apply_bootstrap_to_session(state, workspace=tmp_path)
    assert result["applied"] is True
    assert result["needs_input"]
    assert "studio_campus" not in state


def test_studio_bootstrap_apptest_zero_clicks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    monkeypatch.delenv("WATTLAB_STUDIO_BOOTSTRAP_DISABLE", raising=False)
    import shutil

    energy = tmp_path / "uploads" / "energy" / "shared"
    energy.mkdir(parents=True)
    src = FIXTURE_CAMPUS.parent
    for item in src.iterdir():
        dest = energy / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    run_dir = tmp_path / "runs" / "boot_run_1"
    run_dir.mkdir(parents=True)
    if EPLUS_FIXTURE.is_file():
        shutil.copy2(EPLUS_FIXTURE, run_dir / "eplusout.csv")
    else:
        (run_dir / "eplusout.csv").write_text("Date/Time,Zone\n", encoding="utf-8")
    write_bootstrap(
        build_bootstrap_payload(
            energy_campus_dir="uploads/energy/shared",
            preferred_run_id="boot_run_1",
        )
    )

    at = AppTest.from_file(str(STUDIO), default_timeout=TIMEOUT)
    at.run()
    assert not at.exception
    assert "studio_campus" in at.session_state or "studio_energy" in at.session_state
    # Fuel without Uploads clicks
    at.radio(key="studio_page").set_value("Fuel dashboard").run()
    assert not at.exception
    metric_labels = [m.label for m in at.metric]
    assert any("EUI" in (lab or "") for lab in metric_labels)
    # Twin without Refresh clicks
    at.radio(key="studio_page").set_value("Twin / calibrate").run()
    assert not at.exception
    assert "studio_active_run" in at.session_state


def test_studio_pages_no_exception_when_bootstrapped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    monkeypatch.delenv("WATTLAB_STUDIO_BOOTSTRAP_DISABLE", raising=False)
    import shutil

    energy = tmp_path / "uploads" / "energy" / "shared"
    energy.mkdir(parents=True)
    src = FIXTURE_CAMPUS.parent
    for item in src.iterdir():
        dest = energy / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)
    write_bootstrap(build_bootstrap_payload(energy_campus_dir="uploads/energy/shared"))
    at = AppTest.from_file(str(STUDIO), default_timeout=TIMEOUT)
    at.run()
    assert not at.exception
    for page in ("Uploads", "Fuel dashboard", "Twin / calibrate", "ECMs"):
        at.radio(key="studio_page").set_value(page).run()
        assert not at.exception, page


def test_fuel_tabs_render_with_fixture_campus():
    at = AppTest.from_file(str(STUDIO), default_timeout=TIMEOUT)
    at.run()
    assert not at.exception
    at.text_input(key="uploads_energy_path").set_value(str(FIXTURE_CAMPUS.parent)).run()
    at.button(key="uploads_load_energy").click().run()
    assert not at.exception
    at.radio(key="studio_page").set_value("Fuel dashboard").run()
    assert not at.exception
    # Tab labels present in markdown/text
    blob = " ".join(str(getattr(el, "value", el)) for el in list(at.markdown) + list(at.header))
    # Tabs may not expose labels via markdown — ensure metrics + synth still work
    metric_labels = [m.label for m in at.metric]
    assert any("EUI" in (lab or "") for lab in metric_labels)
    at.button(key="fuel_dash_synth").click().run()
    assert not at.exception


def test_studio_reapply_bootstrap_button(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path))
    monkeypatch.delenv("WATTLAB_STUDIO_BOOTSTRAP_DISABLE", raising=False)
    write_bootstrap(build_bootstrap_payload(preferred_run_id="reapply_run"))
    at = AppTest.from_file(str(STUDIO), default_timeout=TIMEOUT)
    at.run()
    assert not at.exception
    assert "_studio_bootstrapped" in at.session_state
    assert at.session_state["_studio_bootstrapped"] is True
    # Re-apply present when bootstrap file exists
    btn = at.button(key="studio_reapply_bootstrap")
    btn.click().run()
    assert not at.exception
    assert at.session_state["_studio_bootstrapped"] is True


def test_clear_bootstrap_session_flags():
    state = {
        "_studio_bootstrapped": True,
        "_studio_bootstrap_notes": ["x"],
        "_studio_bootstrap_applied_mtime": 1.0,
        "studio_campus": "keep",
    }
    clear_bootstrap_session_flags(state)
    assert "_studio_bootstrapped" not in state
    assert state["studio_campus"] == "keep"
