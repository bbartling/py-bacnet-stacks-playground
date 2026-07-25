"""BUG-019–023: Eng Findings VAV scope, raise, HITL, inventory."""

from __future__ import annotations

from app.reporting.fault_inventory import build_fault_inventory
from app.reporting.findings import cluster_and_prioritize
from app.reporting.hitl import apply_hitl_overrides, parse_note_arg
from app.reporting.models import (
    CandidateDetection,
    Classification,
    EngineeringFinding,
    EvidencePacket,
    FindingAssessment,
    ReportArtifacts,
)
from app.reporting.pipeline import build_engineering_findings
from app.reporting.quality_gate import run_quality_gate
from app.reporting.scope import FindingScope, TERMINAL_SCORE_BOOST


def _pkt(key: str) -> EvidencePacket:
    return EvidencePacket(
        candidate_key=key,
        identity={},
        rule_evidence={},
        mapping_evidence={},
        telemetry_evidence={},
        context={},
        sensor_quality={},
    )


def _cand(
    eid: str,
    rid: str,
    *,
    et: str,
    hours: float,
    score: float,
) -> tuple[CandidateDetection, FindingAssessment]:
    c = CandidateDetection(
        building="B100",
        equipment_id=eid,
        equipment_type=et,
        rule_id=rid,
        status="FAULT",
        fault_hours=hours,
        sample_count=int(hours * 12),
    )
    a = FindingAssessment(
        candidate_key=c.key,
        classification=Classification.PROBABLE,
        score=score,
        score_breakdown={},
        supporting=[f"{eid} {rid} evidence"],
    )
    return c, a


def _b100_like() -> tuple[list, dict, dict]:
    """Plant AHU/CHW high scores + high-volume VAV_22 VAV-5 (burial case)."""
    rows = [
        _cand("AHU_1", "AHU-DUCTHI", et="AHU", hours=200, score=92),
        _cand("AHU_2", "FAN-OFF-STATIC", et="AHU", hours=180, score=90),
        _cand("CH_1", "CHW-1", et="CHILLER", hours=150, score=88),
        _cand("CH_2", "CHW-2", et="CHILLER", hours=140, score=86),
        _cand("AHU_3", "SCHED-1", et="AHU", hours=120, score=84),
        _cand("AHU_4", "AHU-DUCTHI", et="AHU", hours=110, score=83),
        _cand("AHU_5", "FAN-OFF-STATIC", et="AHU", hours=100, score=82),
        # Buried terminal — high volume, slightly lower score
        _cand("VAV_22", "VAV-5", et="VAV", hours=35000, score=78),
        _cand("VAV_10", "VAV-4", et="VAV", hours=8000, score=76),
        _cand("VAV_11", "SV-FLATLINE", et="VAV", hours=5000, score=74),
    ]
    cands = [r[0] for r in rows]
    packets = {c.key: _pkt(c.key) for c in cands}
    assessments = {r[0].key: r[1] for r in rows}
    return cands, packets, assessments


def test_bug019_default_unscoped_buries_vav22():
    cands, packets, assessments = _b100_like()
    findings, _, _ = cluster_and_prioritize(cands, packets, assessments, max_findings=7)
    assert len(findings) == 7
    keys = {k for f in findings for k in f.candidate_keys}
    assert "VAV_22|VAV-5" not in keys  # buried under plant


def test_bug019_systems_vav_surfaces_vav22():
    cands, packets, assessments = _b100_like()
    scope = FindingScope(systems=["VAV"])
    findings, suppressed, _ = cluster_and_prioritize(
        cands, packets, assessments, max_findings=7, scope=scope
    )
    keys = {k for f in findings for k in f.candidate_keys}
    assert "VAV_22|VAV-5" in keys
    assert all("AHU" not in (f.systems or []) for f in findings)
    assert any("Out of report scope" in ";".join(r.get("reasons") or []) for r in suppressed)


def test_bug019_equipment_prefix_and_rule_ids():
    cands, packets, assessments = _b100_like()
    scope = FindingScope(equipment_prefixes=["VAV"], rule_ids=["VAV-5", "VAV-4"])
    findings, _, _ = cluster_and_prioritize(
        cands, packets, assessments, max_findings=7, scope=scope
    )
    rule_ids = {rid for f in findings for rid in f.rule_ids}
    assert "VAV-5" in rule_ids
    assert "SV-FLATLINE" not in rule_ids


def test_bug019_boost_terminal_helps_near_ties():
    cands, packets, assessments = _b100_like()
    # Unscoped with boost: VAV_22 (78+8=86) should enter top-7 vs AHU_5 (82)
    scope = FindingScope(boost_terminal=True)
    findings, _, _ = cluster_and_prioritize(
        cands, packets, assessments, max_findings=7, scope=scope
    )
    keys = {k for f in findings for k in f.candidate_keys}
    assert "VAV_22|VAV-5" in keys
    assert TERMINAL_SCORE_BOOST == 8.0


def test_bug020_gate_fails_without_raise():
    findings = []
    for i in range(12):
        findings.append(
            EngineeringFinding(
                finding_id=f"F{i+1:02d}",
                title=f"f{i}",
                classification=Classification.PROBABLE,
                priority=i + 1,
                why_it_matters="m",
                observed_behavior="o",
                evidence_bullets=["e"],
                contradicting_evidence=[],
                likely_causes=[],
                field_verification=[],
                possible_corrective=[],
                rule_ids=["R"],
                equipment_ids=[f"E{i}"],
                systems=["VAV"],
                automated_assessment={"score": 70},
                include_in_report=True,
            )
        )
    art = ReportArtifacts(
        building="B",
        analysis_period="p",
        generated_at="t",
        findings=findings,
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
    assert any("without explicit raise" in e for e in gate["errors"])


def test_bug020_gate_passes_with_allow_priority():
    findings = []
    for i in range(12):
        findings.append(
            EngineeringFinding(
                finding_id=f"F{i+1:02d}",
                title=f"f{i}",
                classification=Classification.PROBABLE,
                priority=i + 1,
                why_it_matters="m",
                observed_behavior="o",
                evidence_bullets=["e"],
                contradicting_evidence=[],
                likely_causes=[],
                field_verification=[],
                possible_corrective=[],
                rule_ids=["R"],
                equipment_ids=[f"E{i}"],
                systems=["VAV"],
                automated_assessment={"score": 70},
                include_in_report=True,
            )
        )
    art = ReportArtifacts(
        building="B",
        analysis_period="p",
        generated_at="t",
        findings=findings,
        suppressed=[],
        candidates=[],
        assessments=[],
        data_quality=[],
        comfort_summary={},
        metrics={"allow_priority": 12},
        field_checklist=[],
        assumptions={},
        quality_gate={},
    )
    gate = run_quality_gate(art, allow_priority=12)
    assert gate["ok"] is True


def test_bug020_pipeline_max12_with_raise():
    cands, packets, assessments = _b100_like()
    # Use pipeline with candidates directly
    art = build_engineering_findings(
        building="B100",
        candidates=cands,
        max_findings=12,
        allow_priority=12,
        scope=FindingScope(systems=["VAV"]),
        write_inventory=True,
    )
    included = [f for f in art.findings if f.include_in_report]
    assert len(included) <= 12
    assert art.quality_gate.get("ok") is True
    assert art.metrics.get("allow_priority") == 12


def test_bug021_pin_and_note_and_drop():
    cands, packets, assessments = _b100_like()
    findings, suppressed, _ = cluster_and_prioritize(
        cands, packets, assessments, max_findings=7
    )
    # VAV_22 buried — pin it; drop an AHU finding
    ahu_ref = "AHU_1|AHU-DUCTHI"
    out = apply_hitl_overrides(
        findings,
        pin_refs=["VAV_22:VAV-5"],
        drop_refs=[ahu_ref],
        notes={"VAV_22|VAV-5": "FD flag intermittent; verify airflow sensor"},
        candidates=cands,
        assessments=assessments,
        suppressed=suppressed,
    )
    pinned = [f for f in out if f.include_in_report and "VAV_22" in f.equipment_ids]
    assert pinned
    assert (pinned[0].engineer_override or {}).get("note", "").startswith("FD flag")
    dropped = [f for f in out if ahu_ref in (f.candidate_keys or [])]
    assert dropped and dropped[0].include_in_report is False
    ref, text = parse_note_arg("VAV_22:VAV-5=hello")
    assert ref == "VAV_22|VAV-5" and text == "hello"


def test_bug022_day_zoom_error_alias_and_gate():
    f = EngineeringFinding(
        finding_id="F01",
        title="x",
        classification=Classification.PROBABLE,
        priority=1,
        why_it_matters="m",
        observed_behavior="o",
        evidence_bullets=["e"],
        contradicting_evidence=[],
        likely_causes=[],
        field_verification=[],
        possible_corrective=[],
        rule_ids=["VAV-5"],
        equipment_ids=["VAV_1"],
        systems=["VAV"],
        automated_assessment={"score": 70},
        include_in_report=True,
        day_zoom_skip_reason="no_fault_day",
        day_zoom_label="Day-zoom unavailable: no_fault_day",
    )
    d = f.to_dict()
    assert d["day_zoom_error"] == "no_fault_day"
    # Silent skip after zoom pass → gate error
    silent = EngineeringFinding(
        finding_id="F02",
        title="y",
        classification=Classification.PROBABLE,
        priority=2,
        why_it_matters="m",
        observed_behavior="o",
        evidence_bullets=["e"],
        contradicting_evidence=[],
        likely_causes=[],
        field_verification=[],
        possible_corrective=[],
        rule_ids=["VAV-4"],
        equipment_ids=["VAV_2"],
        systems=["VAV"],
        automated_assessment={"score": 70},
        include_in_report=True,
    )
    art = ReportArtifacts(
        building="B",
        analysis_period="p",
        generated_at="t",
        findings=[f, silent],
        suppressed=[],
        candidates=[],
        assessments=[],
        data_quality=[],
        comfort_summary={},
        metrics={},
        field_checklist=[],
        assumptions={},
        quality_gate={},
        charts=[{"name": "day_zoom_F01", "skip_reason": "no_fault_day"}],
    )
    gate = run_quality_gate(art)
    assert gate["ok"] is False
    assert any("silent skip" in e for e in gate["errors"])


def test_bug023_inventory_orphans_and_in_priority():
    cands, packets, assessments = _b100_like()
    findings, suppressed, _ = cluster_and_prioritize(
        cands, packets, assessments, max_findings=7
    )
    inv = build_fault_inventory(cands, findings, suppressed=suppressed)
    assert inv["n_faults"] == len(cands)
    assert inv["n_orphans"] >= 1
    vav22 = next(r for r in inv["rows"] if r["candidate_key"] == "VAV_22|VAV-5")
    assert vav22["in_priority"] is False
    assert vav22["suppressed_reason"]
    assert "VAV" in inv["rollup_by_equipment_prefix"]
    # After scoped run, VAV_22 in priority
    scoped, _, _ = cluster_and_prioritize(
        cands, packets, assessments, max_findings=7, scope=FindingScope(systems=["VAV"])
    )
    inv2 = build_fault_inventory(cands, scoped, suppressed=[])
    vav22b = next(r for r in inv2["rows"] if r["candidate_key"] == "VAV_22|VAV-5")
    assert vav22b["in_priority"] is True
