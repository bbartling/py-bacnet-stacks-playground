"""WattLab export profiles, shared telemetry, and baseline profiler."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from profile_wattlab_export import build_profile_fixture, measure_export  # noqa: E402

from app.rules.base import RuleResult
from app.wattlab_dump import write_fdd_evidence, write_shared_telemetry


def _idx(n: int = 4) -> pd.DatetimeIndex:
    return pd.date_range("2024-03-04 08:00", periods=n, freq="1h", tz="UTC")


def all_status_results() -> list[RuleResult]:
    idx = _idx()
    mask = pd.Series([False, True, True, False], index=idx)
    series = pd.Series([55.0, 56.0, 57.0, 58.0], index=idx)
    return [
        RuleResult(
            rule_id="FC1",
            equipment_id="AHU_1",
            status="FAULT",
            applicable=True,
            equipment_type="AHU",
            raw_fault=mask,
            confirmed_fault=mask,
            plot_series={"discharge-air-temp": series},
            sample_count=4,
        ),
        RuleResult(
            rule_id="FC2",
            equipment_id="AHU_1",
            status="PASS",
            applicable=True,
            equipment_type="AHU",
            raw_fault=pd.Series(False, index=idx),
            confirmed_fault=pd.Series(False, index=idx),
            plot_series={"discharge-air-temp": series},
            sample_count=4,
        ),
        RuleResult(
            rule_id="FC3",
            equipment_id="AHU_1",
            status="ERROR",
            applicable=True,
            equipment_type="AHU",
            plot_series={"discharge-air-temp": series},
            sample_count=4,
        ),
        RuleResult(
            rule_id="FC4",
            equipment_id="VAV_1",
            status="SKIPPED_MISSING_ROLES",
            applicable=False,
            equipment_type="VAV",
            missing_roles=["fan-status"],
            sample_count=4,
        ),
        RuleResult(
            rule_id="FC5",
            equipment_id="AHU_1",
            status="SKIPPED_EQUIPMENT_OFF",
            applicable=False,
            equipment_type="AHU",
            sample_count=4,
        ),
        RuleResult(
            rule_id="FC6",
            equipment_id="VAV_1",
            status="NOT_APPLICABLE_EQUIPMENT_TYPE",
            applicable=False,
            equipment_type="VAV",
            sample_count=4,
        ),
    ]


def test_profile_fixture_covers_equipment_and_statuses():
    dataset, run = build_profile_fixture()
    assert set(dataset.frames) == {
        "CHW_PLANT_1",
        "AHU_DX_1",
        "AHU_CHW_1",
        "HP_1",
        "VAV_1",
    }
    statuses = {r.status for r in run.results}
    assert {
        "FAULT",
        "PASS",
        "ERROR",
        "SKIPPED_MISSING_ROLES",
        "SKIPPED_EQUIPMENT_OFF",
        "NOT_APPLICABLE_EQUIPMENT_TYPE",
    } <= statuses


def test_measure_export_metrics_schema(tmp_path: Path):
    metrics = measure_export(mode="current")
    required = {
        "elapsed_seconds",
        "file_count",
        "compressed_bytes",
        "uncompressed_bytes",
        "result_status_counts",
        "per_rule_timeseries_count",
    }
    assert required <= set(metrics)
    assert metrics["file_count"] > 0
    assert metrics["uncompressed_bytes"] > 0
    assert metrics["compressed_bytes"] > 0
    assert metrics["result_status_counts"]["FAULT"] == 1
    # Default export profile is summary → no Cartesian per-rule timeseries.
    assert metrics["per_rule_timeseries_count"] == 0
    out = tmp_path / "wattlab_export_metrics.json"
    out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    assert out.is_file()


def test_prechange_baseline_artifact_exists():
    """Captured before production profile changes; do not regenerate/commit."""
    baseline = ROOT / ".artifacts" / "wattlab_export_before.json"
    assert baseline.is_file(), "run: python scripts/profile_wattlab_export.py --mode current --out .artifacts/wattlab_export_before.json"
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert payload["per_rule_timeseries_count"] >= 1
    assert payload["file_count"] > 0
    assert "result_status_counts" in payload


def test_summary_suppresses_cartesian_timeseries(tmp_path: Path):
    counts = write_fdd_evidence(all_status_results(), tmp_path, profile="summary")
    assert list((tmp_path / "fdd_timeseries").glob("*.csv")) == []
    assert counts.suppressed_status["NOT_APPLICABLE_EQUIPMENT_TYPE"] == 1
    assert counts.suppressed_status["SKIPPED_MISSING_ROLES"] == 1
    assert counts.suppressed_status["SKIPPED_EQUIPMENT_OFF"] == 1


def test_diagnostic_writes_fault_error_and_selected(tmp_path: Path):
    results = all_status_results()
    counts = write_fdd_evidence(
        results,
        tmp_path,
        profile="diagnostic",
        selected_evidence={("FC2", "AHU_1")},
    )
    names = sorted(p.name for p in (tmp_path / "fdd_timeseries").glob("*.csv"))
    assert names == ["FC1__AHU_1.csv", "FC2__AHU_1.csv", "FC3__AHU_1.csv"]
    assert counts.suppressed_status["NOT_APPLICABLE_EQUIPMENT_TYPE"] == 1
    assert counts.suppressed_status["SKIPPED_MISSING_ROLES"] == 1
    assert counts.suppressed_status["SKIPPED_EQUIPMENT_OFF"] == 1


def test_forensic_writes_applicable_not_pointless_skips(tmp_path: Path):
    counts = write_fdd_evidence(all_status_results(), tmp_path, profile="forensic")
    names = sorted(p.name for p in (tmp_path / "fdd_timeseries").glob("*.csv"))
    assert names == ["FC1__AHU_1.csv", "FC2__AHU_1.csv", "FC3__AHU_1.csv"]
    assert counts.suppressed_status["NOT_APPLICABLE_EQUIPMENT_TYPE"] == 1
    assert counts.suppressed_status["SKIPPED_MISSING_ROLES"] == 1
    assert counts.suppressed_status["SKIPPED_EQUIPMENT_OFF"] == 1


def test_evidence_references_shared_telemetry_not_copy(tmp_path: Path):
    idx = _idx()
    series = pd.Series([55.0, 56.0, 57.0, 58.0], index=idx)
    result = RuleResult(
        rule_id="FC1",
        equipment_id="AHU_1",
        status="FAULT",
        applicable=True,
        equipment_type="AHU",
        raw_fault=pd.Series([False, True, True, False], index=idx),
        confirmed_fault=pd.Series([False, False, True, False], index=idx),
        plot_series={"discharge-air-temp": series},
        sample_count=4,
    )
    frames = {
        "AHU_1": pd.DataFrame(
            {
                "discharge-air-temp": series,
                "fan-status": [1, 1, 1, 1],
                "noise-raw": [9.0, 9.0, 9.0, 9.0],
            },
            index=idx,
        )
    }
    role_map = {
        "AHU_1": {
            "discharge-air-temp": "discharge-air-temp",
            "fan-status": "fan-status",
            "equipment_type": "AHU",
        }
    }
    tel = write_shared_telemetry(frames, role_map, tmp_path, profile="summary")
    assert list(tel) == ["AHU_1"]
    tel_path = tel["AHU_1"]
    assert tel_path.name == "AHU_1.csv"
    assert tel_path.parent.name == "telemetry"

    counts = write_fdd_evidence(
        [result],
        tmp_path,
        profile="diagnostic",
        frames=frames,
        role_map=role_map,
    )
    assert len(counts.written) == 1
    ts = pd.read_csv(counts.written[0])
    assert "raw_fault" in ts.columns and "confirmed_fault" in ts.columns
    assert "telemetry_path" in ts.columns
    assert str(ts["telemetry_path"].iloc[0]).replace("\\", "/") == "telemetry/AHU_1.csv"
    # Compact evidence must not duplicate full plot/live telemetry columns.
    assert "discharge-air-temp" not in ts.columns
    assert "noise-raw" not in ts.columns


def test_shared_telemetry_one_file_per_equipment_deterministic(tmp_path: Path):
    idx = _idx()
    frames = {
        "AHU_B": pd.DataFrame(
            {"discharge-air-temp": [55.0] * 4, "fan-status": [1] * 4, "extra": [1] * 4},
            index=idx,
        ),
        "AHU_A": pd.DataFrame(
            {"discharge-air-temp": [56.0] * 4, "fan-status": [0] * 4, "extra": [2] * 4},
            index=idx,
        ),
    }
    role_map = {
        "AHU_A": {
            "discharge-air-temp": "discharge-air-temp",
            "fan-status": "fan-status",
            "equipment_type": "AHU",
        },
        "AHU_B": {
            "discharge-air-temp": "discharge-air-temp",
            "fan-status": "fan-status",
            "equipment_type": "AHU",
        },
    }
    written = write_shared_telemetry(frames, role_map, tmp_path, profile="summary")
    assert list(written) == ["AHU_A", "AHU_B"]
    paths = [written[k] for k in written]
    assert [p.name for p in paths] == ["AHU_A.csv", "AHU_B.csv"]

    summary_df = pd.read_csv(written["AHU_A"])
    assert list(summary_df.columns)[0] == "timestamp"
    assert "discharge-air-temp" in summary_df.columns
    assert "fan-status" in summary_df.columns
    assert "extra" not in summary_df.columns  # unmapped raw excluded in summary

    forensic = write_shared_telemetry(frames, role_map, tmp_path / "forensic", profile="forensic")
    forensic_df = pd.read_csv(forensic["AHU_A"])
    assert "extra" in forensic_df.columns
    assert list(forensic_df.columns).count("timestamp") == 1
