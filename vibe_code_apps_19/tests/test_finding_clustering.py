"""Finding clustering and prioritization."""

from app.reporting.findings import cluster_and_prioritize
from app.reporting.models import (
    CandidateDetection,
    Classification,
    EvidencePacket,
    FindingAssessment,
)


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


def test_clustering_limits_priority_findings():
    cands = []
    packets = {}
    assessments = {}
    for i in range(12):
        c = CandidateDetection(
            building="B",
            equipment_id=f"E{i}",
            equipment_type="VAV",
            rule_id="VAV-4",
            fault_hours=100 - i,
            fault_pct=40.0,
        )
        cands.append(c)
        packets[c.key] = _pkt(c.key)
        assessments[c.key] = FindingAssessment(
            candidate_key=c.key,
            classification=Classification.PROBABLE,
            score=70 - i,
            score_breakdown={},
            supporting=[f"s{i}"],
        )
    findings, suppressed, _ = cluster_and_prioritize(cands, packets, assessments, max_findings=7)
    assert len(findings) <= 7
    assert len(suppressed) >= 5


def test_fan_off_clusters_as_static_finding():
    c = CandidateDetection(
        building="B",
        equipment_id="AHU_2",
        equipment_type="AHU",
        rule_id="FAN-OFF-STATIC",
        extras={"fan_off_anomaly": {"fan_off_p50": 7.0, "fan_on_p50": 1.5}},
    )
    a = FindingAssessment(
        candidate_key=c.key,
        classification=Classification.STRONGLY_SUPPORTED,
        score=90,
        score_breakdown={},
        supporting=["fan off high"],
        field_verification=["check zero"],
    )
    findings, _, _ = cluster_and_prioritize([c], {c.key: _pkt(c.key)}, {c.key: a})
    assert findings
    assert "static" in findings[0].title.lower() or "AHU_2" in findings[0].title
