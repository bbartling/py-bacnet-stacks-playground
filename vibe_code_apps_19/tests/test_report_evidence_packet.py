"""Evidence packet construction tests."""

from app.reporting.candidates import candidates_from_checklist_json
from app.reporting.evidence import build_evidence_packet
from app.reporting.models import CandidateDetection


def test_vav5_corroboration_when_damper_closed_nonzero_flow():
    c = CandidateDetection(
        building="B100",
        equipment_id="VAV_22",
        equipment_type="VAV",
        rule_id="VAV-5",
        rule_label="Airflow bias",
        fault_hours=100.0,
        fault_pct=50.0,
        telemetry_spot={"damper": 0.2, "zone-airflow": 109.0},
    )
    pkt = build_evidence_packet(c)
    assert any(i.source == "telemetry" and i.weight > 0 for i in pkt.corroboration)
    assert pkt.telemetry_evidence.get("airflow") == 109.0


def test_vav5_contradiction_when_flow_near_zero():
    c = CandidateDetection(
        building="B100",
        equipment_id="VAV_X",
        equipment_type="VAV",
        rule_id="VAV-5",
        fault_hours=50.0,
        fault_pct=97.0,
        telemetry_spot={"damper": 0.0, "zone-airflow": 0.0},
    )
    pkt = build_evidence_packet(c)
    assert any(i.source == "telemetry" and i.weight < 0 for i in pkt.contradiction)


def test_checklist_json_loads_fan_off():
    payload = {
        "summary": {"building_name": "Liberty 100", "span_hours": 2961},
        "fdd": {"all_faults": []},
        "fan_off_anomalies": [
            {
                "equipment_id": "AHU_2",
                "fan_off_p50": 7.19,
                "fan_on_p50": 1.61,
                "units": "in. w.c.",
                "note": "bad static",
            }
        ],
        "comfort": {"rows": [], "n_vav": 42},
        "unusual_faults": {"rows": []},
    }
    cands, ctx = candidates_from_checklist_json(payload)
    assert any(c.rule_id == "FAN-OFF-STATIC" for c in cands)
    assert ctx["building"] == "Liberty 100"
