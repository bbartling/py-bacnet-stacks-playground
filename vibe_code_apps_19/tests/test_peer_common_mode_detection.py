"""Peer common-mode detection tests."""

from app.reporting.candidates import peer_fault_counts
from app.reporting.evidence import build_evidence_packet
from app.reporting.models import CandidateDetection


def test_peer_counts_and_common_mode():
    cands = [
        CandidateDetection(
            building="B",
            equipment_id=f"VAV_{i}",
            equipment_type="VAV",
            rule_id="VAV-5",
            fault_hours=10.0,
            fault_pct=50.0,
        )
        for i in range(20)
    ]
    counts = peer_fault_counts(cands)
    assert counts["VAV-5"] == 20
    pkt = build_evidence_packet(cands[0], peer_counts=counts, fleet_size=42)
    assert pkt.peer_summary["common_mode_suspected"] is True
