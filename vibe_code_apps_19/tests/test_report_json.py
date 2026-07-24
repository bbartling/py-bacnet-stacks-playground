"""JSON artifact structure."""

from app.reporting.pipeline import build_engineering_findings


def test_report_json_structure():
    art = build_engineering_findings(
        checklist={
            "summary": {"building_name": "B", "span_hours": 10},
            "fdd": {"all_faults": []},
            "fan_off_anomalies": [],
            "comfort": {"rows": [], "n_vav": 1},
            "unusual_faults": {"rows": []},
        }
    )
    d = art.to_dict()
    for key in (
        "building",
        "findings",
        "suppressed",
        "candidates",
        "assessments",
        "data_quality",
        "metrics",
        "assumptions",
        "quality_gate",
        "disclaimer",
    ):
        assert key in d
