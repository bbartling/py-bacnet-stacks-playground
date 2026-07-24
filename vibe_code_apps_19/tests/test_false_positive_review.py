"""False-positive and peer common-mode tests."""

from app.reporting.evidence import build_evidence_packet
from app.reporting.models import CandidateDetection, Classification
from app.reporting.reviewer import review_evidence_packet


def test_peer_epidemic_applies_fleet_penalty():
    c = CandidateDetection(
        building="B",
        equipment_id="VAV_1",
        equipment_type="VAV",
        rule_id="VAV-5",
        fault_hours=100.0,
        fault_pct=96.0,
        telemetry_spot={"damper": 0.0, "zone-airflow": 0.0},
    )
    pkt = build_evidence_packet(c, peer_counts={"VAV-5": 30}, fleet_size=42)
    assert pkt.peer_summary.get("common_mode_suspected")
    a = review_evidence_packet(pkt)
    assert a.score_breakdown.get("fleet_penalty", 0) < 0


def test_missing_roles_inconclusive():
    c = CandidateDetection(
        building="B",
        equipment_id="X",
        equipment_type="VAV",
        rule_id="VAV-4",
        fault_hours=10.0,
        fault_pct=20.0,
        missing_roles=["damper-position"],
    )
    a = review_evidence_packet(build_evidence_packet(c))
    assert a.classification == Classification.INCONCLUSIVE
