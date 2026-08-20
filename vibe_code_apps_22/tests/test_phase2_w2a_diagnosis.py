"""Tests for Phase 2 W2A diagnosis (hypothesis + MCP evidence)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.phase2_mcp_evidence import assert_mcp_evidence_complete, build_mcp_evidence_block
from eplus_gym.phase2_w2a_diagnosis import CONCLUSION_STRENGTH, SCHEMA, build_w2a_diagnosis

APP = Path(__file__).resolve().parents[1]

MCP_LOAD = {
    "file_path": "lakeside_w2a_a04_dual_champion.idf",
    "loaded_successfully": True,
    "zone_count": 9,
}
MCP_SUMMARY = {
    "Building": {"Name": "Lakeside_ES"},
    "Site:Location": {"Name": "Sun_Prairie_WI"},
    "Version": {"Version Identifier": "26.1"},
}
MCP_HVAC = {
    "plant_loops": [{"name": "Only Water Loop Mixed Water Loop", "fluid_type": "Water"}],
    "summary": {"total_plant_loops": 1, "total_zones": 9},
}


@pytest.fixture
def mcp_block():
    return build_mcp_evidence_block(
        load_result=MCP_LOAD,
        model_summary=MCP_SUMMARY,
        hvac_loops=MCP_HVAC,
    )


def test_mcp_evidence_complete(mcp_block):
    assert_mcp_evidence_complete(mcp_block)
    assert len(mcp_block["mcp_tools_invoked"]) == 3
    assert all(mcp_block["payload_sha256"].values())


def test_phase2_diagnosis_hypothesis_and_mcp(mcp_block):
    idf = APP / "models" / "eplus" / A04_IDF_NAME
    freeze_path = APP / "docs" / "audits" / "figures" / "vibe22_mega_phase1" / "phase1_evidence_freeze.json"
    phase1 = json.loads(freeze_path.read_text(encoding="utf-8")) if freeze_path.is_file() else None
    diag = build_w2a_diagnosis(
        idf_path=idf,
        mcp_load_result=MCP_LOAD,
        mcp_model_summary=MCP_SUMMARY,
        mcp_hvac_loops=MCP_HVAC,
        phase1_freeze=phase1,
    )
    assert diag["schema"] == SCHEMA
    assert diag["conclusion_strength"] == CONCLUSION_STRENGTH
    assert len(diag["units"]) == 9
    assert diag["identical_hardcoded_heating_w"] is True
    assert diag["mcp_inspection"]["evidence_complete"] is True
    assert "leading_root_cause_hypotheses" in diag
    assert "root_causes" not in diag
    assert diag["historical_err_evidence"]["label"] == "HISTORICAL_PHASE1_FREEZE"
    assert diag["diagnosis_sha256"]


def test_phase2_unit_object_names(mcp_block):
    idf = APP / "models" / "eplus" / A04_IDF_NAME
    diag = build_w2a_diagnosis(
        idf_path=idf,
        mcp_load_result=MCP_LOAD,
        mcp_model_summary=MCP_SUMMARY,
        mcp_hvac_loops=MCP_HVAC,
        require_mcp=True,
    )
    lib = next(u for u in diag["units"] if u["zone"] == "1F_Library_IMC")
    assert lib["heating_coil_name"] == "1F_Library_IMC WAHP Heating Coil"
    assert lib["rated_heating_capacity_w"] == 149430.0


def test_mcp_required_fail_closed():
    idf = APP / "models" / "eplus" / A04_IDF_NAME
    with pytest.raises(ValueError, match="MCP evidence incomplete"):
        build_w2a_diagnosis(idf_path=idf, require_mcp=True)
