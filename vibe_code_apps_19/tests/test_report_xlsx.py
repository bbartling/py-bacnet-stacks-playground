"""Engineering Findings punchlist-first Excel notebook."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.reporting.models import Classification, EngineeringFinding, ReportArtifacts


def _finding() -> EngineeringFinding:
    return EngineeringFinding(
        finding_id="F01",
        title="Economizer stuck closed",
        classification=Classification.STRONGLY_SUPPORTED,
        priority=1,
        why_it_matters="Missed free cooling",
        observed_behavior="OA damper stayed near minimum",
        evidence_bullets=["delta scatter near min OA"],
        contradicting_evidence=[],
        likely_causes=["actuator"],
        field_verification=["Verify OA damper travel"],
        possible_corrective=["Repair linkage"],
        rule_ids=["ECON-3"],
        equipment_ids=["AHU_1"],
        systems=["AHU"],
        automated_assessment={},
    )


def test_render_findings_xlsx_sheets(tmp_path: Path):
    openpyxl = pytest.importorskip("openpyxl")
    from app.reporting.xlsx import REQUIRED_SHEETS, render_findings_xlsx

    png = tmp_path / "overview_economizer_delta_scatter.png"
    # Minimal valid 1x1 PNG
    png.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082"
        )
    )
    art = ReportArtifacts(
        building="B100",
        analysis_period="2026-04-01 → 2026-04-30",
        generated_at="t",
        findings=[_finding()],
        suppressed=[],
        candidates=[],
        assessments=[],
        data_quality=[],
        comfort_summary={},
        metrics={"n_findings": 1},
        field_checklist=["Verify OA damper travel"],
        assumptions={},
        quality_gate={"ok": True, "errors": [], "warnings": []},
        overview_charts=[
            {
                "name": "overview_economizer_delta_scatter",
                "path": str(png),
                "title": "Economizer free-cooling delta scatter",
            }
        ],
        fault_inventory={"rows": [], "n_faults": 0, "n_in_priority": 0, "n_orphans": 0},
    )
    out = tmp_path / "findings.xlsx"
    render_findings_xlsx(art, out, embed_images=True)
    assert out.is_file()
    wb = openpyxl.load_workbook(out)
    assert tuple(wb.sheetnames) == REQUIRED_SHEETS
    punch = wb["Punchlist"]
    assert punch["B2"].value == "Verify OA damper travel"
    ov = wb["Overview_Charts"]
    assert ov["A3"].value == "overview_economizer_delta_scatter"
    assert ov["C3"].value is True
