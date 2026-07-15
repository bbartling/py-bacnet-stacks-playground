"""Lightweight unit tests for vibe20 schemas / examples (no live Sketchbox)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_building_examples_have_required_keys() -> None:
    bdir = ROOT / "examples" / "buildings"
    files = list(bdir.glob("*.json"))
    assert files, "expected building examples"
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("project_id")
        assert data.get("display_name")
        assert "—" not in data["display_name"], "Sketchbox rejects em dash in project names"
        assert isinstance(data.get("measures"), list)
        for m in data["measures"]:
            assert m.get("measure_id")
            assert m.get("review_status") in {"draft", "approved", "rejected", "needs_input"}


def test_measure_brief_example_matches_schema_required() -> None:
    schema = json.loads((ROOT / "schemas" / "measure_brief.schema.json").read_text(encoding="utf-8"))
    example = json.loads((ROOT / "examples" / "measure_brief.schedule.example.json").read_text(encoding="utf-8"))
    for key in schema["required"]:
        assert key in example


def test_agents_routing_exists() -> None:
    assert (ROOT / "AGENTS.md").is_file()
    assert (ROOT / ".agents" / "routing.md").is_file()
    assert (ROOT / ".agents" / "skills" / "browser-operator" / "SKILL.md").is_file()
    assert (ROOT / ".agents" / "skills" / "openfdd-bridge" / "SKILL.md").is_file()
    assert (ROOT / ".agents" / "skills" / "gl36-airside" / "SKILL.md").is_file()
    assert (ROOT / ".cursor" / "skills" / "vibe20-sketchbox" / "SKILL.md").is_file()
    assert (ROOT / "sketchbox_ui.py").is_file()


def test_agents_handbook_has_gl36_and_disclaimer() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "conceptual, uncalibrated screening model" in text
    assert "GL36" in text or "Guideline 36" in text
    assert "ECM-GL36-AIRSIDE-BOTH-AHUS" in text
    assert "SCHED-247" in text
    assert "no public api" in text.lower()
    # scrubbed provenance docs should not be required
    assert not (ROOT / "docs" / "SOURCES.md").exists()
    assert not (ROOT / "docs" / "FABLE5_CRITIQUE.md").exists()
    assert not (ROOT / "docs" / "FDD_TO_SKETCHBOX_WORKFLOW.md").exists()


def test_madison_concept_profile() -> None:
    path = ROOT / "examples" / "buildings" / "madison_liberty_concept.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["project_id"] == "MAD-LIBERTY-CONCEPT-001"
    assert data["anonymized"] is True
    assert "conceptual, uncalibrated" in data["disclaimer"].lower()
    assert data["shell_strategy"]["one_shell_adequate"] is False
    assert len(data["shell_strategy"]["shells"]) == 2
    ids = {m["measure_id"] for m in data["measures"]}
    assert "ECM-AHU2-SCHED-ALIGN" in ids
    assert "ECM-GL36-AIRSIDE-BOTH-AHUS" in ids
    assert "ECM-AHU-DUCT-STATIC-RESET" not in ids
    assert (ROOT / "run_madison_concept.py").is_file()


def test_madison_dry_run_includes_gl36() -> None:
    import run_madison_concept as m

    # dry-run path via plan construction
    profile = json.loads((ROOT / "examples" / "buildings" / "madison_liberty_concept.json").read_text(encoding="utf-8"))
    assert any(x["measure_id"] == "ECM-GL36-AIRSIDE-BOTH-AHUS" for x in profile["measures"])
    assert m.GL36_LIT["hvac_savings_pct_avg"] == 31.0
    v = m.validate_against_literature(
        baseline={"electricity_kwh_year": 1000, "site_eui_kbtu_ft2_year": 40, "utility_cost_usd_year": 100},
        after_ecm1={"electricity_kwh_year": 600, "site_eui_kbtu_ft2_year": 30, "utility_cost_usd_year": 60},
        after_ecm2={"electricity_kwh_year": 500, "site_eui_kbtu_ft2_year": 26, "utility_cost_usd_year": 52},
    )
    assert v["verdict"] in {"PASS", "WARN"}
    assert v["pct_savings"]["ecm2_incremental_kwh_vs_ecm1"] == 16.67


def test_dry_run_plan_shape() -> None:
    from testdrive import plan_dry_run

    paths = sorted((ROOT / "examples" / "buildings").glob("*.json"))
    plan = plan_dry_run(paths)
    assert plan["dry_run"] is True
    assert len(plan["buildings"]) >= 3
    for b in plan["buildings"]:
        assert "zero_offsets" in b["writes"]["sequence"]
