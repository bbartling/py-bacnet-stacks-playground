"""Data-contract audit tests (quality / columns / topology / package health)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from app.data_contract import (
    PackageHealthReport,
    audit_columns_vs_history,
    audit_package_dir,
    audit_quality_window,
    load_vav_to_ahu_map,
)
from app.package_io import load_package_from_dir


def test_columns_intersect_warns_on_missing_history_cols(tmp_path: Path):
    idx = pd.date_range("2026-07-01", periods=3, freq="5min", tz="UTC")
    df = pd.DataFrame({"sat": [55.0, 56.0, 57.0]}, index=idx)
    cols = tmp_path / "columns.csv"
    cols.write_text(
        "col,point_role\nsat,sat\nphantom_point,zone_t\nother_missing,oa_t\n",
        encoding="utf-8",
    )
    warnings, present, issue = audit_columns_vs_history("AHU_1", df, cols)
    assert "sat" in present
    assert "phantom_point" not in present
    assert any("absent from history_wide" in w for w in warnings)
    assert issue is not None
    assert issue.code == "columns.metadata_only"
    assert issue.count == 2


def test_quality_trusted_after_data_end_warns_keeps_rows():
    idx = pd.date_range("2026-07-01", periods=48, freq="h", tz="UTC")
    df = pd.DataFrame({"sat": 55.0}, index=idx)
    quality = {"trusted_start_utc": "2026-07-07T00:00:00Z"}
    warnings, issues = audit_quality_window("VAV_1", df, quality)
    assert any("0 trusted rows" in w for w in warnings)
    assert len(df) == 48  # never filtered here
    assert any(i.code == "quality.trusted_empty" for i in issues)


def _messy_building(tmp_path: Path) -> Path:
    root = tmp_path / "B1"
    (root / "AHU_1").mkdir(parents=True)
    (root / "VAV" / "VAV_A").mkdir(parents=True)
    (root / "VAV" / "VAV_ORPHAN").mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "openfdd_package_v1",
                "building_id": "B1",
                "grid_minutes": 5,
                "timezone": "UTC",
            }
        ),
        encoding="utf-8",
    )
    hist = "timestamp_utc,sat\n2026-07-01T00:00:00Z,55\n2026-07-01T00:05:00Z,56\n"
    (root / "AHU_1" / "history_wide.csv").write_text(hist, encoding="utf-8")
    (root / "AHU_1" / "columns.csv").write_text(
        "col,point_role\nsat,sat\nmissing_meta,zone_t\n", encoding="utf-8"
    )
    (root / "AHU_1" / "quality.json").write_text(
        json.dumps({"trusted_start_utc": "2026-07-07T00:00:00Z"}), encoding="utf-8"
    )
    (root / "VAV" / "VAV_A" / "history_wide.csv").write_text(
        "timestamp_utc,zone_t\n2026-07-01T00:00:00Z,72\n2026-07-03T16:00:00Z,73\n",
        encoding="utf-8",
    )
    (root / "VAV" / "VAV_A" / "columns.csv").write_text(
        "col,point_role\nzone_t,zone_t\n", encoding="utf-8"
    )
    (root / "VAV" / "VAV_A" / "quality.json").write_text(
        json.dumps({"trusted_start_utc": "2026-07-07T00:00:00Z"}), encoding="utf-8"
    )
    (root / "VAV" / "VAV_ORPHAN" / "history_wide.csv").write_text(
        "timestamp_utc,zone_t\n2026-07-01T00:00:00Z,70\n", encoding="utf-8"
    )
    (root / "VAV" / "VAV_ORPHAN" / "columns.csv").write_text(
        "col,point_role\nzone_t,zone_t\n", encoding="utf-8"
    )
    (root / "vav_to_ahu_simple.csv").write_text(
        "vav,ahu\nVAV_A,AHU_1\nVAV_GHOST,AHU_1\nAHU_1,AHU_1\nAHU_2,AHU_2\n",
        encoding="utf-8",
    )
    return root


def test_topology_and_package_audit(tmp_path: Path):
    root = _messy_building(tmp_path)
    result = load_package_from_dir(root)
    assert len(result.frames) == 3
    joined = " | ".join(result.warnings)
    assert "0 trusted rows" in joined
    assert "absent from history_wide" in joined
    assert "not in vav_to_ahu_simple" in joined or "VAV_ORPHAN" in joined
    assert "no VAV folder" in joined or "VAV_GHOST" in joined
    assert result.report.get("data_contract_warning_count", 0) >= 1

    health = result.report.get("package_health")
    assert isinstance(health, dict)
    assert health["grade"] in {"degraded", "incomplete"}
    assert health["topology"]["missing_map_count"] >= 1
    assert health["topology"]["stale_map_id_count"] >= 1
    assert health["columns"]["total_ignored_points"] >= 1
    codes = {i["code"] for i in health["issues"]}
    assert "topology.missing_vav_map" in codes
    assert "topology.stale_map_ids" in codes
    assert "columns.metadata_only" in codes
    # Summary is short; details stay in detail_lines
    assert 1 <= len(health["summary_lines"]) <= 5
    assert len(health["detail_lines"]) >= 1
    assert result.report.get("package_health_grade") == health["grade"]


def test_package_health_aggregates_many_missing_vavs(tmp_path: Path):
    root = tmp_path / "B2"
    (root / "AHU_1").mkdir(parents=True)
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "openfdd_package_v1",
                "building_id": "B2",
                "grid_minutes": 5,
                "timezone": "UTC",
            }
        ),
        encoding="utf-8",
    )
    hist = "timestamp_utc,sat\n2026-07-01T00:00:00Z,55\n2026-07-01T00:05:00Z,56\n"
    (root / "AHU_1" / "history_wide.csv").write_text(hist, encoding="utf-8")
    for i in range(20):
        vdir = root / "VAV" / f"VAV_{i}"
        vdir.mkdir(parents=True)
        (vdir / "history_wide.csv").write_text(
            "timestamp_utc,zone_t\n2026-07-01T00:00:00Z,70\n2026-07-01T00:05:00Z,71\n",
            encoding="utf-8",
        )
    (root / "vav_to_ahu_simple.csv").write_text("vav,ahu\nVAV_0,AHU_1\n", encoding="utf-8")

    result = load_package_from_dir(root)
    health = PackageHealthReport.model_validate(result.report["package_health"])
    assert health.topology.missing_map_count == 19
    assert health.topology.coverage_pct == 5.0
    assert health.grade == "incomplete"
    missing_issues = [i for i in health.issues if i.code == "topology.missing_vav_map"]
    assert len(missing_issues) == 1
    assert missing_issues[0].count == 19
    assert len(health.summary_lines) <= 6
    assert any("coverage" in line.lower() or "19" in line for line in health.summary_lines)


def test_vav_map_loads(tmp_path: Path):
    p = tmp_path / "vav_to_ahu_simple.csv"
    p.write_text("vav,ahu\nVAV_1,AHU_2\n", encoding="utf-8")
    root = tmp_path
    assert load_vav_to_ahu_map(root) == {"VAV_1": "AHU_2"}
