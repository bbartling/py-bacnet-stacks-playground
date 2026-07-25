"""End-to-end: Overview PNGs + UTC day-zoom land in DOCX (BUG-011/012)."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd
import pytest

from app.reporting.models import Classification, EngineeringFinding, ReportArtifacts
from app.reporting.overview_export import build_overview_charts, build_overview_context
from app.reporting.day_zoom import attach_day_zoom_to_findings
from app.reporting.docx import render_docx
from app.rules.base import RuleResult


def test_overview_and_day_zoom_embed_in_docx(tmp_path):
    idx = pd.date_range("2026-06-01", periods=48, freq="h", tz="UTC")
    ahu = pd.DataFrame(
        {
            "supply-fan-status": [1, 0] * 24,
            "bas-outside-air-temp": [70.0] * 48,
            "outside-air-temp": [70.0] * 48,
        },
        index=idx,
    )
    weather = pd.DataFrame(
        {"web-outside-air-temp": [68.0 + (i % 5) for i in range(48)]}, index=idx
    )
    ctx = build_overview_context(
        frames={"AHU_1": ahu},
        role_map={},
        weather=weather,
        bare_min_occ_hours=40.0,
        dataset_start=idx.min(),
        dataset_end=idx.max(),
        span_hours=47.0,
        zone_lo_f=70.0,
        zone_hi_f=75.0,
    )
    art = ReportArtifacts(
        building="E2E",
        analysis_period="",
        generated_at="2026-01-01T00:00:00Z",
        findings=[],
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
            "dataset_end": "2026-06-02 23:00",
            "span_hours": 47.0,
            "zone_lo_f": 70.0,
            "zone_hi_f": 75.0,
            "bare_min_occ_hours": 40.0,
        },
    )
    metas = build_overview_charts(art, ctx, out_dir=tmp_path / "ov")
    png_overview = [m for m in metas if m.get("path")]
    if not png_overview:
        pytest.skip("Kaleido PNG export unavailable in this environment")

    fault_idx = pd.date_range("2026-06-28", periods=24, freq="h", tz="UTC")
    fault = pd.Series([1] * 10 + [0] * 14, index=fault_idx)
    result = RuleResult(
        rule_id="VAV-5",
        equipment_id="VAV_1",
        status="FAULT",
        applicable=True,
        confirmed_fault=fault,
        plot_series={"zone_t": pd.Series(range(24), index=fault_idx, dtype=float)},
    )
    finding = EngineeringFinding(
        finding_id="F01",
        title="UTC day zoom",
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
        equipment_ids=["VAV_1"],
        systems=["VAV"],
        candidate_keys=["VAV_1|VAV-5"],
        include_in_report=True,
    )
    attach_day_zoom_to_findings([finding], [result], out_dir=tmp_path / "dz")
    assert finding.day_zoom_path and Path(finding.day_zoom_path).is_file()
    art.findings = [finding]
    art.overview_charts = png_overview

    docx_path = render_docx(art, tmp_path / "e2e.docx")
    with zipfile.ZipFile(docx_path) as zf:
        media = [n for n in zf.namelist() if n.startswith("word/media/")]
        xml = zf.read("word/document.xml").decode("utf-8")
    assert len(media) >= 2
    assert "Dataset window" in xml
    assert "fault-h that day" in xml or "peak fault" in xml
