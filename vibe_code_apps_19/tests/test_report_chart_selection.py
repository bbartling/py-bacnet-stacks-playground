"""Chart selection smoke tests."""

from app.reporting.charts import build_report_charts
from app.reporting.models import Classification, EngineeringFinding, ReportArtifacts


def test_chart_selection_attaches_confidence_and_finding_charts(tmp_path):
    f = EngineeringFinding(
        finding_id="F01",
        title="AHU_2 static",
        classification=Classification.STRONGLY_SUPPORTED,
        priority=1,
        why_it_matters="x",
        observed_behavior="y",
        evidence_bullets=["e"],
        contradicting_evidence=[],
        likely_causes=[],
        field_verification=[],
        possible_corrective=[],
        rule_ids=["FAN-OFF-STATIC"],
        equipment_ids=["AHU_2"],
        systems=["AHU"],
        chart_spec={
            "kind": "fan_off_static",
            "equipment_id": "AHU_2",
            "fan_off_p50": 7.19,
            "fan_on_p50": 1.61,
            "units": "in. w.c.",
        },
        automated_assessment={"score": 90},
    )
    art = ReportArtifacts(
        building="B",
        analysis_period="test",
        generated_at="now",
        findings=[f],
        suppressed=[],
        candidates=[],
        assessments=[],
        data_quality=[],
        comfort_summary={"rows": []},
        metrics={},
        field_checklist=[],
        assumptions={},
        quality_gate={},
    )
    charts = build_report_charts(art, out_dir=tmp_path)
    names = {c["name"] for c in charts}
    assert "confidence_summary" in names
    assert any(c.get("finding_id") == "F01" for c in charts)
