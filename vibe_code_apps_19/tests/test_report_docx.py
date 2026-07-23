"""DOCX + JSON render smoke tests."""

import json
from pathlib import Path

from app.reporting.pipeline import build_engineering_findings, render_engineering_report


def _mini_checklist():
    return {
        "summary": {"building_name": "Liberty Building 100", "span_hours": 100},
        "fdd": {
            "all_faults": [
                {
                    "equipment_id": "VAV_22",
                    "equipment_type": "VAV",
                    "rule_id": "VAV-5",
                    "label": "Airflow bias",
                    "fault_hours": 200,
                    "fault_pct": 80,
                    "ecm_flag": "bias",
                    "missing_roles": "",
                    "notes": "",
                }
            ]
        },
        "fan_off_anomalies": [
            {
                "equipment_id": "AHU_2",
                "fan_off_p50": 7.19,
                "fan_on_p50": 1.61,
                "units": "in. w.c.",
                "note": "bad",
                "ecm_flag": "sensor",
            }
        ],
        "comfort": {
            "n_vav": 42,
            "n_below": 1,
            "rows": [
                {
                    "equipment_id": "VAV_7",
                    "in_band_pct": 0.0,
                    "mean_zone_t": 4.96,
                    "flag_dead_sensor": True,
                    "outlier": True,
                }
            ],
        },
        "unusual_faults": {
            "rows": [
                {
                    "equipment_id": "VAV_22",
                    "rule_id": "VAV-5",
                    "telemetry_spot": "damper=0.2, zone-airflow=109",
                }
            ]
        },
    }


def test_report_json_and_docx(tmp_path):
    art = build_engineering_findings(checklist=_mini_checklist())
    assert art.findings
    written = render_engineering_report(art, tmp_path, docx=True, json_out=True, charts=True)
    assert written["json"].is_file()
    data = json.loads(written["json"].read_text())
    assert "findings" in data and "suppressed" in data
    assert written["docx"].is_file()
    # OOXML zip magic
    assert written["docx"].read_bytes()[:2] == b"PK"
