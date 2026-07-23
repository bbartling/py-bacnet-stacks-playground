"""Near-continuous fault review."""

from app.reporting.evidence import build_evidence_packet
from app.reporting.models import CandidateDetection, Classification
from app.reporting.reviewer import review_evidence_packet


def test_near_continuous_sets_common_mode_flag():
    c = CandidateDetection(
        building="B",
        equipment_id="AHU_2",
        equipment_type="AHU",
        rule_id="SCHED-247",
        fault_hours=2950.0,
        fault_pct=99.7,
    )
    a = review_evidence_packet(build_evidence_packet(c))
    assert a.common_mode_review is True
    assert a.classification != Classification.STRONGLY_SUPPORTED
