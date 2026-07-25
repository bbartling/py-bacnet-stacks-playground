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


def test_docx_embeds_overview_and_finding_pictures(tmp_path):
    """With mocked chart paths on artifacts, §2/§3 pictures land in word/media."""
    import zipfile

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from app.reporting.docx import render_docx
    from app.reporting.models import Classification, EngineeringFinding, ReportArtifacts

    def _write_png(path: Path, color: str) -> None:
        fig, ax = plt.subplots(figsize=(2, 1))
        ax.set_facecolor(color)
        ax.set_xticks([])
        ax.set_yticks([])
        fig.savefig(path, dpi=80)
        plt.close(fig)

    png = tmp_path / "fake.png"
    png2 = tmp_path / "fake2.png"
    _write_png(png, "#2b6cb0")
    _write_png(png2, "#c53030")
    finding = EngineeringFinding(
        finding_id="F01",
        title="Mock finding",
        classification=Classification.PROBABLE,
        priority=1,
        why_it_matters="w",
        observed_behavior="o",
        evidence_bullets=["e"],
        contradicting_evidence=[],
        likely_causes=[],
        field_verification=[],
        possible_corrective=[],
        rule_ids=["VAV-5"],
        equipment_ids=["VAV_22"],
        systems=["VAV"],
        day_zoom_path=str(png2),
        day_zoom_label="2026-06-28 · peak fault day",
        include_in_report=True,
    )
    art = ReportArtifacts(
        building="Liberty",
        analysis_period="",
        generated_at="2026-01-01T00:00:00Z",
        findings=[finding],
        suppressed=[],
        candidates=[],
        assessments=[],
        data_quality=[],
        comfort_summary={},
        metrics={},
        field_checklist=[],
        assumptions={},
        quality_gate={"ok": True},
        overview_settings={
            "dataset_start": "2026-06-01 00:00",
            "dataset_end": "2026-06-30 23:00",
            "span_hours": 720.0,
            "zone_lo_f": 70.0,
            "zone_hi_f": 75.0,
            "bare_min_occ_hours": 50.0,
        },
        overview_charts=[
            {"name": "overview_bas_vs_web_oat", "path": str(png), "title": "BAS vs web"}
        ],
        charts=[],
    )
    out = render_docx(art, tmp_path / "with_pics.docx")
    with zipfile.ZipFile(out) as zf:
        media = [n for n in zf.namelist() if n.startswith("word/media/")]
        xml = zf.read("word/document.xml").decode("utf-8")
    assert len(media) >= 2
    assert "Dataset window" in xml
    assert "BAS vs web" in xml
    assert "peak fault day" in xml


def test_docx_has_rule_descriptions_and_fp_appendix(tmp_path):
    checklist = _mini_checklist()
    checklist["fdd"]["all_faults"].append(
        {
            "equipment_id": "AHU_2",
            "equipment_type": "AHU",
            "rule_id": "OAT-METEO",
            "label": "OAT",
            "fault_hours": 50,
            "fault_pct": 5,
            "ecm_flag": "",
            "missing_roles": "",
            "notes": "",
        }
    )
    art = build_engineering_findings(checklist=checklist)
    # Unrelated AHU rule must not inherit duct-static evidence
    oat = next((f for f in art.findings if "OAT-METEO" in f.rule_ids), None)
    if oat:
        joined = " ".join(oat.evidence_bullets).lower()
        assert "fan-off" not in joined and "duct static fan-off" not in joined
    written = render_engineering_report(art, tmp_path, docx=True, json_out=False, charts=False)
    import zipfile

    with zipfile.ZipFile(written["docx"]) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")
    assert "Fault / rule description legend" in xml
    assert "Likely false positives" in xml
    assert "Description" in xml
    assert "FDD Engineering Findings Report" in xml
