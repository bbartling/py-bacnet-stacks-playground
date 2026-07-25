"""Quality gate tests."""

from app.reporting.models import Classification, EngineeringFinding, ReportArtifacts
from app.reporting.quality_gate import run_quality_gate


def test_quality_gate_rejects_fp_in_body():
    f = EngineeringFinding(
        finding_id="F01",
        title="x",
        classification=Classification.LIKELY_FALSE_POSITIVE,
        priority=1,
        why_it_matters="",
        observed_behavior="",
        evidence_bullets=["e"],
        contradicting_evidence=[],
        likely_causes=[],
        field_verification=[],
        possible_corrective=[],
        rule_ids=["R"],
        equipment_ids=["E"],
        systems=["VAV"],
        automated_assessment={},
    )
    art = ReportArtifacts(
        building="B",
        analysis_period="p",
        generated_at="t",
        findings=[f],
        suppressed=[],
        candidates=[],
        assessments=[],
        data_quality=[],
        comfort_summary={},
        metrics={},
        field_checklist=[],
        assumptions={},
        quality_gate={},
    )
    gate = run_quality_gate(art)
    assert gate["ok"] is False
    assert any("false positive" in e.lower() for e in gate["errors"])


def test_quality_gate_ok_for_supported_with_evidence():
    f = EngineeringFinding(
        finding_id="F01",
        title="AHU static",
        classification=Classification.STRONGLY_SUPPORTED,
        priority=1,
        why_it_matters="m",
        observed_behavior="o",
        evidence_bullets=["fan off high"],
        contradicting_evidence=["none"],
        likely_causes=["sensor"],
        field_verification=["check"],
        possible_corrective=["verify then replace if needed"],
        rule_ids=["FAN-OFF-STATIC"],
        equipment_ids=["AHU_2"],
        systems=["AHU"],
        chart_spec={"kind": "fan_off_static"},
        automated_assessment={"score": 90},
    )
    art = ReportArtifacts(
        building="B",
        analysis_period="p",
        generated_at="t",
        findings=[f],
        suppressed=[],
        candidates=[],
        assessments=[],
        data_quality=[],
        comfort_summary={},
        metrics={},
        field_checklist=[],
        assumptions={},
        quality_gate={},
    )
    gate = run_quality_gate(art)
    assert gate["ok"] is True


def _base_finding(**kwargs):
    defaults = dict(
        finding_id="F01",
        title="Telemetry review",
        classification=Classification.INCONCLUSIVE,
        priority=1,
        why_it_matters="m",
        observed_behavior="o",
        evidence_bullets=["pattern present"],
        contradicting_evidence=[],
        likely_causes=["unknown"],
        field_verification=["verify in field"],
        possible_corrective=[],
        rule_ids=["R1"],
        equipment_ids=["AHU_1"],
        systems=["AHU"],
        automated_assessment={"score": 40},
    )
    defaults.update(kwargs)
    return EngineeringFinding(**defaults)


def _artifacts(finding: EngineeringFinding) -> ReportArtifacts:
    return ReportArtifacts(
        building="B",
        analysis_period="p",
        generated_at="t",
        findings=[finding],
        suppressed=[],
        candidates=[],
        assessments=[],
        data_quality=[],
        comfort_summary={},
        metrics={},
        field_checklist=[],
        assumptions={},
        quality_gate={},
    )


def test_quality_gate_allows_do_not_replace_on_inconclusive():
    f = _base_finding(
        possible_corrective=[
            "Do not replace equipment solely from this telemetry review — complete field verification first"
        ],
    )
    gate = run_quality_gate(_artifacts(f))
    assert gate["ok"] is True
    assert not any("replace" in e.lower() for e in gate["errors"])


def test_quality_gate_rejects_proactive_replace_on_inconclusive():
    f = _base_finding(
        possible_corrective=["Replace the outdoor-air damper actuator"],
    )
    gate = run_quality_gate(_artifacts(f))
    assert gate["ok"] is False
    assert any("replace" in e.lower() for e in gate["errors"])


def test_quality_gate_allows_soft_negation_and_flags_replacement_noun():
    ok_f = _base_finding(
        possible_corrective=["No need to replace the actuator until field verification"],
    )
    assert run_quality_gate(_artifacts(ok_f))["ok"] is True

    bad_f = _base_finding(
        possible_corrective=["Replacement of the actuator is recommended"],
    )
    gate = run_quality_gate(_artifacts(bad_f))
    assert gate["ok"] is False
    assert any("replace" in e.lower() for e in gate["errors"])
