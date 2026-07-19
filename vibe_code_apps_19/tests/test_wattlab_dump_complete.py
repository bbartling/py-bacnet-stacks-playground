"""WattLab dump must always execute a complete cookbook run."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_build_wattlab_dump_always_reruns_complete_cookbook(monkeypatch: pytest.MonkeyPatch):
    pytest.importorskip("streamlit")
    import streamlit as st

    import streamlit_app as app
    from app.agent_api import AgentRun
    from app.rules.base import RuleResult

    frames = {
        "AHU_1": pd.DataFrame(
            {
                "fan-status": [1, 1, 0],
                "outside-air-temp": [70.0, 71.0, 72.0],
            },
            index=pd.date_range("2024-06-01", periods=3, freq="1h", tz="UTC"),
        )
    }
    frames["AHU_1"].attrs["equipment_type"] = "AHU"
    frames["AHU_1"].attrs["poll_seconds"] = 3600.0

    partial = [
        RuleResult(
            rule_id="PARTIAL-ONLY",
            equipment_id="AHU_1",
            status="PASS",
            applicable=True,
            fault_hours=0.0,
            missing_roles=[],
            notes="seeded partial session result",
        )
    ]
    complete = [
        RuleResult(
            rule_id="SCHED-247",
            equipment_id="AHU_1",
            status="FAULT",
            applicable=True,
            fault_hours=2.0,
            missing_roles=[],
            notes="complete cookbook result",
        ),
        RuleResult(
            rule_id="MECH-OAT-1",
            equipment_id="AHU_1",
            status="PASS",
            applicable=True,
            fault_hours=0.0,
            missing_roles=[],
            notes="complete cookbook result",
        ),
    ]

    calls = {"run_rules": 0}

    def fake_run_rules(dataset, **kwargs):
        calls["run_rules"] += 1
        return AgentRun(
            results=complete,
            summary=pd.DataFrame(
                [
                    {
                        "rule_id": "SCHED-247",
                        "equipment_id": "AHU_1",
                        "status": "FAULT",
                        "fault_hours": 2.0,
                    },
                    {
                        "rule_id": "MECH-OAT-1",
                        "equipment_id": "AHU_1",
                        "status": "PASS",
                        "fault_hours": 0.0,
                    },
                ]
            ),
            params=dataset.params,
        )

    def fake_export_agent_bundle(dataset, run, out_dir, include_bootstrap=False):
        out = Path(out_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "README_WATTLAB.md").write_text("ok\n", encoding="utf-8")
        (out / "MANIFEST.json").write_text("{}", encoding="utf-8")
        (out / "run_report.json").write_text("{}", encoding="utf-8")
        (out / "model_seed.json").write_text("{}", encoding="utf-8")
        pd.DataFrame(
            [
                {
                    "rule_id": r.rule_id,
                    "equipment_id": r.equipment_id,
                    "status": r.status,
                    "fault_hours": r.fault_hours,
                }
                for r in run.results
            ]
        ).to_csv(out / "fdd_findings.csv", index=False)
        return SimpleNamespace(path=out)

    # Seed a Streamlit session with a partial result set that must not be reused.
    st.session_state.clear()
    st.session_state.equipment_frames = frames
    st.session_state.weather = None
    st.session_state.role_map = {
        "AHU_1": {"fan-status": "fan-status", "outside-air-temp": "outside-air-temp"}
    }
    st.session_state.params = {}
    st.session_state.unit_system = "imperial"
    st.session_state.prefer_web_oat = True
    st.session_state.chw_leave_max_f = 48.0
    st.session_state.use_mech_cooling_status_proof = True
    st.session_state.column_map = {}
    st.session_state.package_report = {}
    st.session_state.data_source = "test"
    st.session_state.building_id = "PARTIAL_B1"
    st.session_state.batch_results = partial

    # Local imports inside `_build_wattlab_dump_zip` resolve these names.
    monkeypatch.setattr("app.agent_api.run_rules", fake_run_rules)
    monkeypatch.setattr("app.agent_api.export_agent_bundle", fake_export_agent_bundle)

    data, fname = app._build_wattlab_dump_zip()
    assert calls["run_rules"] == 1
    assert fname.endswith(".zip")
    assert len(st.session_state.batch_results) == 2
    assert {r.rule_id for r in st.session_state.batch_results} == {
        "SCHED-247",
        "MECH-OAT-1",
    }

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        findings = pd.read_csv(zf.open("fdd_findings.csv"))
    assert set(findings["rule_id"]) == {"SCHED-247", "MECH-OAT-1"}
    assert "PARTIAL-ONLY" not in set(findings["rule_id"])
