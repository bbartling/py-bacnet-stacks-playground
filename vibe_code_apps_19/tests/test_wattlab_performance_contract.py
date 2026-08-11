"""Semantic WattLab export performance contract (no fragile wall-clock asserts)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from profile_wattlab_export import (  # noqa: E402
    CHECKED_IN_BASELINE_PATH,
    build_profile_fixture,
    load_before_baseline,
    measure_export,
    resolve_suppressed_combinations,
)

from app.agent_api import export_agent_bundle
from app.rules.runner import RULES
from app.wattlab_dump import NEVER_TIMESERIES_STATUSES


# Tables Vibe 20 / WattLab handoff expects in a summary package.
_VIBE20_REQUIRED = {
    "MANIFEST.json",
    "model_seed.json",
    "sensor_stats_all.csv",
    "setpoints.csv",
    "fdd_findings.csv",
    "mech_cooling_coverage.csv",
    "mech_cooling_oat_bins.csv",
    "schedule_inference.json",
}


def test_summary_file_count_below_cartesian_product(tmp_path: Path):
    dataset, run = build_profile_fixture()
    n_equip = len(dataset.frames)
    # Full cookbook × equipment is the naive Cartesian evidence explosion.
    cartesian = len(RULES) * n_equip
    assert cartesian > 100

    written = export_agent_bundle(
        dataset, run, tmp_path, include_bootstrap=False, profile="summary"
    )
    file_count = sum(1 for p in tmp_path.rglob("*") if p.is_file())
    assert file_count < cartesian

    ts_dir = tmp_path / "fdd_timeseries"
    per_rule = list(ts_dir.glob("*.csv")) if ts_dir.is_dir() else []
    assert per_rule == []
    # Even result-scoped Cartesian (every result × every equipment) must not appear.
    assert len(per_rule) < len(run.results) * n_equip

    for status in NEVER_TIMESERIES_STATUSES:
        assert not any(status.lower() in p.name.lower() for p in per_rule)

    names = {p.name for p in tmp_path.rglob("*") if p.is_file()}
    assert _VIBE20_REQUIRED <= names

    manifest = json.loads((tmp_path / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "openfdd_engineering_bundle_v1"
    assert manifest.get("legacy_schema_version") == "wattlab_dump_v3"
    assert "stage_seconds" in manifest
    assert "stage_scope" in manifest
    assert "result_status_counts" in manifest
    assert "files_suppressed" in manifest
    assert manifest["files_suppressed"] >= 3  # skip statuses in fixture
    assert "metrics_scope" in manifest
    payload_files = [p for p in tmp_path.rglob("*") if p.is_file() and p.name != "MANIFEST.json"]
    all_files = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert manifest["payload_file_count"] == len(payload_files)
    assert manifest["payload_uncompressed_bytes"] == sum(p.stat().st_size for p in payload_files)
    assert manifest["package_file_count"] == len(all_files)
    assert manifest["package_file_count"] == manifest["payload_file_count"] + 1
    assert "compressed_bytes" not in manifest
    assert "manifest" in written


def test_skip_statuses_emit_no_timeseries_under_any_profile(tmp_path: Path):
    dataset, run = build_profile_fixture()
    for profile in ("summary", "diagnostic", "forensic"):
        out = tmp_path / profile
        export_agent_bundle(dataset, run, out, include_bootstrap=False, profile=profile)
        ts_dir = out / "fdd_timeseries"
        if not ts_dir.is_dir():
            continue
        for p in ts_dir.glob("*.csv"):
            # Filenames are RULE__EQUIP — ensure skip-status results are absent
            assert "FC4__" not in p.name  # SKIPPED_MISSING_ROLES
            assert "FC5__" not in p.name  # SKIPPED_EQUIPMENT_OFF
            assert "FC6__" not in p.name  # NOT_APPLICABLE


def test_profiler_before_after_schema_includes_suppressed(tmp_path: Path):
    """Harness writes comparable before/after metrics from the same fixture."""
    before = load_before_baseline(CHECKED_IN_BASELINE_PATH)
    after = measure_export(mode="summary")
    assert after["per_rule_timeseries_count"] == 0
    # Semantic suppression: fewer (or equal) files than Cartesian pre-change dump,
    # and far below cookbook×equipment evidence explosion.
    dataset, run = build_profile_fixture()
    cartesian = len(RULES) * len(dataset.frames)
    assert after["file_count"] < cartesian
    # Bundle v1 adds parquet twins + catalog/quality/readiness; still no Cartesian TS.
    assert after["per_rule_timeseries_count"] <= before["per_rule_timeseries_count"]
    assert after["per_rule_timeseries_count"] == 0

    # Simulate CLI --baseline merge shape
    payload = {
        "runtime_seconds": {
            "before": before.get("elapsed_seconds"),
            "after": after["elapsed_seconds"],
        },
        "file_count": {"before": before.get("file_count"), "after": after["file_count"]},
        "compressed_bytes": {
            "before": before.get("compressed_bytes"),
            "after": after["compressed_bytes"],
        },
        "uncompressed_bytes": {
            "before": before.get("uncompressed_bytes"),
            "after": after["uncompressed_bytes"],
        },
        "per_rule_timeseries": {
            "before": before.get("per_rule_timeseries_count"),
            "after": after["per_rule_timeseries_count"],
        },
        "suppressed_combinations": after.get("suppressed_combinations"),
    }
    assert payload["per_rule_timeseries"]["before"] == 6
    assert payload["per_rule_timeseries"]["after"] == 0
    assert payload["suppressed_combinations"] is not None
    assert int(payload["suppressed_combinations"]) >= 3

    out = tmp_path / "wattlab_export_after.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["per_rule_timeseries"]["after"] < loaded["per_rule_timeseries"]["before"]


def test_profiler_suppressed_zero_not_overridden_by_fallback():
    """Manifest files_suppressed=0 must stay 0; fallback only when field absent."""
    assert resolve_suppressed_combinations({"files_suppressed": 0}, results=[]) == 0
    assert resolve_suppressed_combinations({"files_suppressed": 0}, results=None) == 0
    # Absent → may fall back to NEVER status count on results
    from app.rules.base import RuleResult

    results = [
        RuleResult(rule_id="FC4", equipment_id="VAV_1", status="SKIPPED_MISSING_ROLES", applicable=False),
        RuleResult(rule_id="FC1", equipment_id="AHU_1", status="FAULT", applicable=True),
    ]
    assert resolve_suppressed_combinations({}, results=results) == 1
    assert resolve_suppressed_combinations({"files_suppressed": 5}, results=results) == 5


def test_export_wall_clock_is_environment_tolerant(tmp_path: Path, monkeypatch):
    """Soft timing: only assert when VIBE19_ASSERT_EXPORT_MAX_S is set."""
    import os
    import time

    dataset, run = build_profile_fixture()
    t0 = time.perf_counter()
    export_agent_bundle(dataset, run, tmp_path, include_bootstrap=False, profile="summary")
    elapsed = time.perf_counter() - t0
    raw = os.environ.get("VIBE19_ASSERT_EXPORT_MAX_S", "").strip()
    if raw:
        assert elapsed <= float(raw)


def test_summary_retains_sensor_setpoint_model_seed_artifacts(tmp_path: Path):
    dataset, run = build_profile_fixture()
    export_agent_bundle(dataset, run, tmp_path, include_bootstrap=False, profile="summary")
    assert (tmp_path / "sensor_stats_all.csv").is_file()
    stats = pd.read_csv(tmp_path / "sensor_stats_all.csv")
    assert {"n", "mean", "p50", "valid_count", "p01", "p99", "duration_hours"} <= set(stats.columns)
    assert (tmp_path / "model_seed.json").is_file()
    seed = json.loads((tmp_path / "model_seed.json").read_text(encoding="utf-8"))
    inferred = seed.get("inferred_parameters")
    assert inferred
    assert (tmp_path / "setpoints.csv").is_file() or "zone-air-temp-sp" in set(stats["role"])
