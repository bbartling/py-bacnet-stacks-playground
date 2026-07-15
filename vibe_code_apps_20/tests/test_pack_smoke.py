"""Unit tests for OpenFDD WattLab schemas / examples / scrub (no Docker required)."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN = re.compile(r"sket" + r"chbox", re.IGNORECASE)



def _tracked_text_files() -> list[Path]:
    skip_parts = {
        "third_party",
        ".artifacts",
        "__pycache__",
        ".pytest_cache",
        ".venv",
        "pytest-cache-files",
    }
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".py", ".json", ".txt", ".example"}:
            continue
        if any(p in skip_parts for p in path.parts):
            continue
        out.append(path)
    return out


def test_no_forbidden_legacy_brand_strings() -> None:
    hits: list[str] = []
    for path in _tracked_text_files():
        text = path.read_text(encoding="utf-8", errors="replace")
        if FORBIDDEN.search(text):
            hits.append(str(path.relative_to(ROOT)))
    assert hits == [], f"forbidden legacy brand strings in: {hits}"


def test_building_examples_have_required_keys() -> None:
    bdir = ROOT / "examples" / "buildings"
    files = list(bdir.glob("*.json"))
    assert files, "expected building examples"
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data.get("project_id")
        assert data.get("display_name")
        assert data.get("energyplus", {}).get("prototype_idf")
        assert data.get("energyplus", {}).get("epw")
        assert isinstance(data.get("measures"), list)
        for m in data["measures"]:
            assert m.get("measure_id")
            assert m.get("review_status") in {"draft", "approved", "rejected", "needs_input"}
            if m.get("review_status") == "approved":
                assert (m.get("idf_patch") or {}).get("name")


def test_measure_brief_example_matches_schema_required() -> None:
    schema = json.loads((ROOT / "schemas" / "measure_brief.schema.json").read_text(encoding="utf-8"))
    example = json.loads(
        (ROOT / "examples" / "measure_brief.schedule.example.json").read_text(encoding="utf-8")
    )
    for key in schema["required"]:
        assert key in example


def test_agents_routing_and_skills_exist() -> None:
    assert (ROOT / "AGENTS.md").is_file()
    assert (ROOT / "README.md").is_file()
    assert (ROOT / ".agents" / "routing.md").is_file()
    assert (ROOT / ".agents" / "skills" / "openfdd-bridge" / "SKILL.md").is_file()
    assert (ROOT / ".agents" / "skills" / "energyplus-mcp" / "SKILL.md").is_file()
    assert (ROOT / ".agents" / "skills" / "easy-button-calibrate" / "SKILL.md").is_file()
    assert (ROOT / ".agents" / "skills" / "idf-patching" / "SKILL.md").is_file()
    assert (ROOT / ".agents" / "skills" / "epw-climate" / "SKILL.md").is_file()
    assert (ROOT / ".agents" / "skills" / "gl36-airside" / "SKILL.md").is_file()
    assert (ROOT / ".cursor" / "skills" / "openfdd-wattlab" / "SKILL.md").is_file()
    assert (ROOT / "easy_button.py").is_file()
    assert (ROOT / "madison_office.py").is_file()
    assert not (ROOT / ".agents" / "skills" / "browser-operator").exists()
    legacy_ui = "sketch" + "box_ui.py"
    assert not (ROOT / legacy_ui).exists()


def test_agents_handbook_wattlab_identity() -> None:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "OpenFDD WattLab" in text
    assert "OpenFDD WattLab" in readme
    assert "EnergyPlus" in text
    assert "conceptual, uncalibrated screening model" in text
    assert "Guideline 36" in text or "GL36" in text
    assert "SCHED-247" in text
    assert "easy_button" in text


def test_madison_office_profile() -> None:
    path = ROOT / "examples" / "buildings" / "madison_office.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["project_id"] == "MAD-OFFICE-CONCEPT-001"
    assert data["anonymized"] is True
    assert data.get("product") == "OpenFDD WattLab"
    assert "conceptual, uncalibrated" in data["disclaimer"].lower()
    ids = {m["measure_id"] for m in data["measures"]}
    assert "ECM-AHU-SCHED-ALIGN" in ids
    assert "ECM-GL36-AIRSIDE" in ids
    assert (ROOT / "examples" / "evidence" / "madison_office_evidence.json").is_file()
    assert (ROOT / "examples" / "prototypes" / "5ZoneAirCooled.idf").is_file()


def test_madison_dry_run_and_literature() -> None:
    from easy_button import GL36_LIT, plan_dry_run, validate_against_literature

    plan = plan_dry_run(ROOT / "examples" / "buildings" / "madison_office.json")
    assert plan["dry_run"] is True
    assert plan["product"] == "OpenFDD WattLab"
    assert "ECM-GL36-AIRSIDE" in plan["approved_measure_ids"]
    assert any(s.get("step") == "select_prototype" for s in plan["steps"])
    assert GL36_LIT["hvac_savings_pct_avg"] == 31.0
    v = validate_against_literature(
        baseline={"electricity_kwh_year": 1000, "site_eui_kbtu_ft2_year": 40, "utility_cost_usd_year": 100},
        after_ecm1={"electricity_kwh_year": 600, "site_eui_kbtu_ft2_year": 30, "utility_cost_usd_year": 60},
        after_ecm2={"electricity_kwh_year": 500, "site_eui_kbtu_ft2_year": 26, "utility_cost_usd_year": 52},
    )
    assert v["verdict"] in {"PASS", "WARN"}
    assert v["pct_savings"]["ecm2_incremental_kwh_vs_ecm1"] == 16.67


def test_idf_schedule_and_gl36_patches() -> None:
    from idf_patches import (
        apply_fan_avail_continuous,
        apply_fan_avail_occupied_office,
        apply_gl36_airside_proxy,
    )

    proto = ROOT / "examples" / "prototypes" / "5ZoneAirCooled.idf"
    tmp = ROOT / ".artifacts" / "_patch_unit"
    tmp.mkdir(parents=True, exist_ok=True)
    cont = tmp / "cont.idf"
    occ = tmp / "occ.idf"
    gl = tmp / "gl.idf"
    assert apply_fan_avail_continuous(proto, cont)["ok"]
    assert apply_fan_avail_occupied_office(cont, occ)["ok"]
    meta = apply_gl36_airside_proxy(occ, gl)
    assert meta["ok"]
    assert meta["vav_terminals_patched"] >= 1
    text = gl.read_text(encoding="utf-8")
    assert "0.15," in text
    assert "conceptual_gl36_proxy" in text
