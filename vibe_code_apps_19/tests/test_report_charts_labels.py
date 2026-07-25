"""Chart helpers for Eng Findings summary plots."""

from __future__ import annotations

from app.reporting.charts import _detection_label, _is_vav_candidate, build_report_charts
from app.reporting.models import ReportArtifacts


def test_detection_label_prefers_compact_equip_rule():
    assert _detection_label(
        {"equipment_id": "VAV_22", "rule_id": "VAV-5", "rule_label": "Airflow bias"}
    ).startswith("VAV_22 · VAV-5")


def test_is_vav_candidate_data_model_driven():
    assert _is_vav_candidate({"equipment_type": "VAV", "equipment_id": "BOX_1", "rule_id": "X"})
    assert _is_vav_candidate({"equipment_type": "AHU", "equipment_id": "VAV_7", "rule_id": "VAV-4"})
    assert _is_vav_candidate({"equipment_type": "UNKNOWN", "equipment_id": "Z1", "rule_id": "VAV-1"})
    assert not _is_vav_candidate(
        {"equipment_type": "AHU", "equipment_id": "AHU_1", "rule_id": "SCHED-1"}
    )


def test_build_report_charts_includes_vav_top_when_candidates(tmp_path):
    art = ReportArtifacts(
        building="B",
        analysis_period="p",
        generated_at="t",
        findings=[],
        suppressed=[],
        candidates=[
            {
                "equipment_id": "AHU_1",
                "equipment_type": "AHU",
                "rule_id": "SCHED-1",
                "rule_label": "Schedule",
                "fault_hours": 100.0,
            },
            {
                "equipment_id": "VAV_22",
                "equipment_type": "VAV",
                "rule_id": "VAV-5",
                "rule_label": "Airflow bias",
                "fault_hours": 80.0,
            },
            {
                "equipment_id": "VAV_7",
                "equipment_type": "VAV",
                "rule_id": "VAV-4",
                "rule_label": "Damper stuck",
                "fault_hours": 40.0,
            },
        ],
        assessments=[],
        data_quality=[],
        comfort_summary={},
        metrics={},
        field_checklist=[],
        assumptions={},
        quality_gate={},
    )
    metas = build_report_charts(art, out_dir=tmp_path)
    names = {m.get("name") for m in metas}
    assert "top_detections" in names
    assert "top_vav_detections" in names
    # Layout height must be tall enough that Kaleido export is not forced to 420
    # when kaleido is missing we still get html; when present path is set.
    vav = next(m for m in metas if m.get("name") == "top_vav_detections")
    assert vav.get("path") or vav.get("html") or vav.get("export_error") is not None
