"""Day-zoom worst-fault day picker + PNG + DOCX media."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from app.reporting.day_zoom import (
    attach_day_zoom_to_findings,
    render_day_zoom_png,
    worst_fault_day,
)
from app.reporting.docx import render_docx
from app.reporting.models import Classification, EngineeringFinding, ReportArtifacts
from app.rules.base import RuleResult


def test_worst_fault_day_picks_peak_day():
    idx = pd.date_range("2026-06-27", periods=72, freq="h", tz="UTC")
    # Day 28 has 20 fault hours; day 27 has 5; day 29 has 10
    vals = [0] * 24 + [1] * 20 + [0] * 4 + [1] * 10 + [0] * 14
    fault = pd.Series(vals, index=idx)
    assert worst_fault_day(fault) == date(2026, 6, 28)


def test_worst_fault_day_empty():
    assert worst_fault_day(None) is None
    assert worst_fault_day(pd.Series(dtype=float)) is None
    idx = pd.date_range("2026-01-01", periods=5, freq="h")
    assert worst_fault_day(pd.Series([0, 0, 0, 0, 0], index=idx)) is None


def test_render_day_zoom_png(tmp_path):
    idx = pd.date_range("2026-06-28", periods=24, freq="h")
    fault = pd.Series([0, 0, 1, 1, 1, 0] + [0] * 18, index=idx)
    series = {"zone_t": pd.Series(range(24), index=idx, dtype=float)}
    result = RuleResult(
        rule_id="VAV-5",
        equipment_id="VAV_22",
        status="FAULT",
        applicable=True,
        confirmed_fault=fault,
        plot_series=series,
    )
    out = tmp_path / "zoom.png"
    rendered = render_day_zoom_png(result, date(2026, 6, 28), out)
    assert rendered is not None
    path, hours = rendered
    assert path.is_file()
    assert path.stat().st_size > 500
    assert hours >= 0


def test_render_day_zoom_png_utc_aware_index(tmp_path):
    """BUG-012: UTC-aware DatetimeIndex must not crash against naive day bounds."""
    idx = pd.date_range("2026-06-28", periods=24, freq="h", tz="UTC")
    fault = pd.Series([0, 0, 1, 1, 1, 0] + [0] * 18, index=idx)
    series = {"zone_t": pd.Series(range(24), index=idx, dtype=float)}
    result = RuleResult(
        rule_id="VAV-5",
        equipment_id="VAV_22",
        status="FAULT",
        applicable=True,
        confirmed_fault=fault,
        plot_series=series,
    )
    day = worst_fault_day(fault)
    assert day == date(2026, 6, 28)
    rendered = render_day_zoom_png(result, day, tmp_path / "utc_zoom.png")
    assert rendered is not None
    path, _hours = rendered
    assert path.is_file() and path.stat().st_size > 500


def test_docx_embeds_day_zoom_media(tmp_path):
    idx = pd.date_range("2026-06-28", periods=24, freq="h")
    fault = pd.Series([1] * 12 + [0] * 12, index=idx)
    result = RuleResult(
        rule_id="VAV-5",
        equipment_id="VAV_22",
        status="FAULT",
        applicable=True,
        confirmed_fault=fault,
        plot_series={"zone_t": pd.Series(range(24), index=idx, dtype=float)},
    )
    finding = EngineeringFinding(
        finding_id="F01",
        title="Test finding",
        classification=Classification.PROBABLE,
        priority=1,
        why_it_matters="x",
        observed_behavior="y",
        evidence_bullets=["e"],
        contradicting_evidence=[],
        likely_causes=["c"],
        field_verification=["f"],
        possible_corrective=["p"],
        rule_ids=["VAV-5"],
        equipment_ids=["VAV_22"],
        systems=["VAV"],
        candidate_keys=["VAV_22|VAV-5"],
        include_in_report=True,
    )
    attach_day_zoom_to_findings([finding], [result], out_dir=tmp_path / "dz")
    assert finding.day_zoom_path and Path(finding.day_zoom_path).is_file()

    art = ReportArtifacts(
        building="Test",
        analysis_period="",
        generated_at="2026-01-01T00:00:00Z",
        findings=[finding],
        suppressed=[],
        candidates=[],
        assessments=[],
        data_quality=[],
        comfort_summary={},
        metrics={"n_candidates": 1},
        field_checklist=[],
        assumptions={},
        quality_gate={"ok": True},
    )
    docx_path = render_docx(art, tmp_path / "out.docx")
    import zipfile

    with zipfile.ZipFile(docx_path) as zf:
        media = [n for n in zf.namelist() if n.startswith("word/media/")]
    assert media, "expected day-zoom PNG in word/media"
