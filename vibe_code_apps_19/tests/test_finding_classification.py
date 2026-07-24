"""Classification / false-positive / near-continuous review tests."""

from app.reporting.evidence import build_evidence_packet
from app.reporting.models import CandidateDetection, Classification
from app.reporting.reviewer import review_evidence_packet


def test_implausible_zone_t_is_data_quality_not_comfort():
    c = CandidateDetection(
        building="B100",
        equipment_id="VAV_7",
        equipment_type="VAV",
        rule_id="VAV-1",
        rule_label="Zone outside comfort",
        fault_hours=700.0,
        fault_pct=25.0,
    )
    pkt = build_evidence_packet(
        c,
        comfort_row={
            "equipment_id": "VAV_7",
            "mean_zone_t": 4.96,
            "flag_dead_sensor": True,
            "outlier": True,
            "in_band_pct": 0.0,
        },
    )
    a = review_evidence_packet(pkt)
    assert a.classification == Classification.DATA_QUALITY


def test_fan_off_static_strong_support():
    c = CandidateDetection(
        building="B100",
        equipment_id="AHU_2",
        equipment_type="AHU",
        rule_id="FAN-OFF-STATIC",
        extras={
            "fan_off_anomaly": {
                "equipment_id": "AHU_2",
                "fan_off_p50": 7.19,
                "fan_on_p50": 1.61,
                "units": "in. w.c.",
            }
        },
    )
    pkt = build_evidence_packet(c)
    a = review_evidence_packet(pkt)
    assert a.classification in {Classification.STRONGLY_SUPPORTED, Classification.PROBABLE}
    assert a.score >= 60


def test_near_continuous_without_corroboration_not_confirmed():
    c = CandidateDetection(
        building="B50",
        equipment_id="CHILLER_2",
        equipment_type="CHILLER",
        rule_id="CHW-1",
        fault_hours=2961.0,
        fault_pct=99.99,
    )
    pkt = build_evidence_packet(c, peer_counts={"CHW-1": 2}, fleet_size=2)
    a = review_evidence_packet(pkt)
    assert a.classification != Classification.STRONGLY_SUPPORTED
    assert a.common_mode_review or a.classification in {
        Classification.INCONCLUSIVE,
        Classification.LIKELY_FALSE_POSITIVE,
        Classification.PROBABLE,
    }


def test_vav5_telemetry_outranks_fault_pct_only():
    strong = CandidateDetection(
        building="B",
        equipment_id="VAVH_616",
        equipment_type="VAV",
        rule_id="VAV-5",
        fault_hours=200.0,
        fault_pct=90.0,
        telemetry_spot={"damper": 0.0, "zone-airflow": 201.0},
    )
    weak = CandidateDetection(
        building="B",
        equipment_id="VAV_116",
        equipment_type="VAV",
        rule_id="VAV-5",
        fault_hours=200.0,
        fault_pct=98.0,
        telemetry_spot={"damper": 0.0, "zone-airflow": 0.0},
    )
    a_strong = review_evidence_packet(build_evidence_packet(strong))
    a_weak = review_evidence_packet(build_evidence_packet(weak))
    assert a_strong.score > a_weak.score
