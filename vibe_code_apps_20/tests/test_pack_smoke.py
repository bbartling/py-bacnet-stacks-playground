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
    assert (ROOT / ".cursor" / "skills" / "vibe20-sketchbox" / "SKILL.md").is_file()
    assert (ROOT / "sketchbox_ui.py").is_file()


def test_dry_run_plan_shape() -> None:
    from testdrive import plan_dry_run

    paths = sorted((ROOT / "examples" / "buildings").glob("*.json"))
    plan = plan_dry_run(paths)
    assert plan["dry_run"] is True
    assert len(plan["buildings"]) == 3
    for b in plan["buildings"]:
        assert b["approved_measures"]
        assert "zero_offsets" in b["writes"]["sequence"]
