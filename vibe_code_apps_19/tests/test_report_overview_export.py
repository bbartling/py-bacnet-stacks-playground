"""Overview export settings + optional Kaleido PNGs."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.reporting.models import ReportArtifacts
from app.reporting.overview_export import (
    build_overview_charts,
    build_overview_context,
    format_analysis_period,
    overview_settings_from_context,
)


def test_overview_settings_lean():
    ctx = build_overview_context(
        frames={"AHU_1": pd.DataFrame()},
        zone_lo_f=70,
        zone_hi_f=75,
        bare_min_occ_hours=50,
        oat_err=5.0,
        dataset_start=pd.Timestamp("2026-06-01"),
        dataset_end=pd.Timestamp("2026-06-30"),
        span_hours=720.0,
        occupancy_schedule={"mon": {"start": "08:00", "end": "17:00"}},
    )
    settings = overview_settings_from_context(ctx)
    assert "frames" not in settings
    assert settings["zone_lo_f"] == 70
    assert settings["bare_min_occ_hours"] == 50
    assert settings["dataset_start"] == "2026-06-01 00:00"
    assert settings["span_hours"] == 720.0


def test_format_analysis_period_from_span():
    ctx = build_overview_context(
        dataset_start=pd.Timestamp("2026-06-01"),
        dataset_end=pd.Timestamp("2026-06-30"),
        span_hours=720.0,
    )
    assert format_analysis_period(ctx) == "2026-06-01 → 2026-06-30 (~720 h)"


def test_pipeline_fills_analysis_period_from_overview():
    from app.reporting.pipeline import build_engineering_findings

    art = build_engineering_findings(
        building="B",
        analysis_period="",
        candidates=[],
        checklist=None,
        overview_context=build_overview_context(
            dataset_start=pd.Timestamp("2026-01-01"),
            dataset_end=pd.Timestamp("2026-01-31"),
            span_hours=744.0,
        ),
    )
    assert art.analysis_period == "2026-01-01 → 2026-01-31 (~744 h)"


def test_overview_export_registers_or_skips(tmp_path):
    """Tiny frames: soft-fail if Kaleido missing; register chart names when export works."""
    idx = pd.date_range("2026-06-01", periods=48, freq="h")
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
        prefer_web_oat=True,
        bare_min_occ_hours=40.0,
    )
    art = ReportArtifacts(
        building="T",
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
    )
    metas = build_overview_charts(art, ctx, out_dir=tmp_path)
    assert isinstance(metas, list)
    assert metas, "expected at least one overview chart attempt"
    names = {m.get("name") for m in metas}
    assert names & {
        "overview_bas_vs_web_oat",
        "overview_motor_weekly_air",
        "overview_motor_weekly_boiler",
        "overview_motor_weekly_chiller",
        "overview_mech_cooling_oat_bins",
        "overview_motor_weekly",
    }
    pngs = [m for m in metas if m.get("path")]
    if not pngs:
        pytest.skip("Kaleido/Plotly PNG export unavailable in this environment")
    assert any(
        Path(p["path"]).is_file() and Path(p["path"]).stat().st_size > 100 for p in pngs
    )
