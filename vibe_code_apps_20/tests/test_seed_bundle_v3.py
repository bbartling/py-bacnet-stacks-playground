"""Vibe 20 WattLab dump loader — additive v2 + v3 compatibility."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from wattlab.seed import load_bundle

_MECH_COLS = [
    "equipment_id",
    "source",
    "source_kind",
    "series_kind",
    "series_id",
    "bin_start",
    "bin_label",
    "hours",
    "runtime_hours",
    "valid_elapsed_hours",
    "coverage_pct",
    "equipment_type",
    "cooling_technology",
    "proof_role",
    "proof_quality",
    "device_count",
]

_COV_COLS = [
    "equipment_id",
    "equipment_type",
    "cooling_technology",
    "compressor_based",
    "included",
    "eligibility_state",
    "activity_state",
    "proof_quality",
    "proof_role",
    "runtime_hours",
    "valid_elapsed_hours",
    "coverage_pct",
    "exclusion_reason",
]


def _zip_dir(root: Path, zpath: Path) -> Path:
    with zipfile.ZipFile(zpath, "w") as zf:
        for p in root.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(root).as_posix())
    return zpath


def _write_common_seed(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "model_seed.json").write_text(
        json.dumps(
            {
                "project_id": "COMPAT_B1",
                "building_type": "office",
                "city": "madison",
                "floor_area_ft2": 25000,
            }
        ),
        encoding="utf-8",
    )
    (root / "operating_signatures.csv").write_text(
        "equipment_id,bin_start,on_fraction\nAHU_1,50,0.5\n",
        encoding="utf-8",
    )
    (root / "fdd_summary.csv").write_text(
        "rule_id,equipment_id,status\nFC1,AHU_1,fault\n",
        encoding="utf-8",
    )
    (root / "fdd_findings.csv").write_text(
        "rule_id,equipment_id,status,confirmed_fault,fault_hours\n"
        "FC1,AHU_1,FAULT,True,1.0\n",
        encoding="utf-8",
    )


def _write_v2_dump(root: Path) -> Path:
    """Legacy wattlab_dump_v2 with fdd_timeseries, no shared telemetry/."""
    _write_common_seed(root)
    (root / "MANIFEST.json").write_text(
        json.dumps(
            {
                "schema_version": "wattlab_dump_v2",
                "files": [{"path": "fdd_findings.csv", "kind": "fdd"}],
            }
        ),
        encoding="utf-8",
    )
    bins = pd.DataFrame(
        [
            {
                "equipment_id": "CHILLER_2",
                "source": "CHILLER_2",
                "source_kind": "device",
                "bin_start": 70.0,
                "bin_label": "70-75",
                "hours": 2.0,
                "equipment_type": "CHW_PLANT",
            },
            {
                "equipment_id": "ALL",
                "source": "All mech cooling (total)",
                "source_kind": "total",
                "bin_start": 70.0,
                "bin_label": "70-75",
                "hours": 2.0,
                "equipment_type": "",
            },
        ]
    )
    bins.to_csv(root / "mech_cooling_oat_bins.csv", index=False)
    cov = pd.DataFrame(
        [
            {
                "equipment_id": "CHILLER_2",
                "equipment_type": "CHW_PLANT",
                "included": True,
                "runtime_hours": 2.0,
                "status": "included",
                "proof": "chiller_status",
                "reason": "",
            }
        ]
    )
    cov.to_csv(root / "mech_cooling_coverage.csv", index=False)
    ts = root / "fdd_timeseries"
    ts.mkdir(exist_ok=True)
    (ts / "FC1__AHU_1.csv").write_text(
        "timestamp,raw_fault,confirmed_fault\n2024-06-01T00:00:00Z,0,0\n",
        encoding="utf-8",
    )
    return root


def _write_v3_summary_dump(root: Path) -> Path:
    """wattlab_dump_v3 summary profile: shared telemetry, no fdd_timeseries."""
    _write_common_seed(root)
    (root / "MANIFEST.json").write_text(
        json.dumps(
            {
                "schema_version": "wattlab_dump_v3",
                "export_profile": "summary",
                "files": [
                    {"path": "telemetry/", "kind": "telemetry"},
                    {"path": "mech_cooling_oat_bins.csv", "kind": "analytics"},
                ],
                "result_status_counts": {"FAULT": 1, "PASS": 0},
                "files_written": 12,
                "files_suppressed": 6,
            }
        ),
        encoding="utf-8",
    )
    bins = pd.DataFrame(
        [
            {
                "equipment_id": "CHILLER_1",
                "source": "CHILLER_1",
                "source_kind": "device",
                "series_kind": "individual_device",
                "series_id": "CHILLER_1",
                "bin_start": 70.0,
                "bin_label": "70-75",
                "hours": 0.0,
                "runtime_hours": 0.0,
                "valid_elapsed_hours": 4.0,
                "coverage_pct": 100.0,
                "equipment_type": "CHW_PLANT",
                "cooling_technology": "chiller",
                "proof_role": "chiller_status",
                "proof_quality": "status",
                "device_count": 1,
            },
            {
                "equipment_id": "CHILLER_2",
                "source": "CHILLER_2",
                "source_kind": "device",
                "series_kind": "individual_device",
                "series_id": "CHILLER_2",
                "bin_start": 70.0,
                "bin_label": "70-75",
                "hours": 2.0,
                "runtime_hours": 2.0,
                "valid_elapsed_hours": 4.0,
                "coverage_pct": 100.0,
                "equipment_type": "CHW_PLANT",
                "cooling_technology": "chiller",
                "proof_role": "chiller_status",
                "proof_quality": "status",
                "device_count": 1,
            },
            {
                "equipment_id": "ALL",
                "source": "All mech cooling (total)",
                "source_kind": "total",
                "series_kind": "aggregate_device_hours",
                "series_id": "aggregate_device_hours",
                "bin_start": 70.0,
                "bin_label": "70-75",
                "hours": 2.0,
                "runtime_hours": 2.0,
                "valid_elapsed_hours": 4.0,
                "coverage_pct": 100.0,
                "equipment_type": "",
                "cooling_technology": "",
                "proof_role": "",
                "proof_quality": "",
                "device_count": 2,
            },
            {
                "equipment_id": "aggregate_active_hours",
                "source": "Any compressor active",
                "source_kind": "active",
                "series_kind": "aggregate_active_hours",
                "series_id": "aggregate_active_hours",
                "bin_start": 70.0,
                "bin_label": "70-75",
                "hours": 2.0,
                "runtime_hours": 2.0,
                "valid_elapsed_hours": 4.0,
                "coverage_pct": 100.0,
                "equipment_type": "",
                "cooling_technology": "",
                "proof_role": "",
                "proof_quality": "",
                "device_count": 2,
            },
        ]
    )
    assert list(bins.columns) == _MECH_COLS
    bins.to_csv(root / "mech_cooling_oat_bins.csv", index=False)

    cov = pd.DataFrame(
        [
            {
                "equipment_id": "CHILLER_1",
                "equipment_type": "CHW_PLANT",
                "cooling_technology": "chiller",
                "compressor_based": True,
                "included": True,
                "eligibility_state": "eligible_no_runtime",
                "activity_state": "no_runtime",
                "proof_quality": "status",
                "proof_role": "chiller_status",
                "runtime_hours": 0.0,
                "valid_elapsed_hours": 4.0,
                "coverage_pct": 100.0,
                "exclusion_reason": "",
            },
            {
                "equipment_id": "CHILLER_2",
                "equipment_type": "CHW_PLANT",
                "cooling_technology": "chiller",
                "compressor_based": True,
                "included": True,
                "eligibility_state": "eligible",
                "activity_state": "active",
                "proof_quality": "status",
                "proof_role": "chiller_status",
                "runtime_hours": 2.0,
                "valid_elapsed_hours": 4.0,
                "coverage_pct": 100.0,
                "exclusion_reason": "",
            },
            {
                "equipment_id": "AHU_CHW_1",
                "equipment_type": "AHU",
                "cooling_technology": "chilled_water_coil",
                "compressor_based": False,
                "included": False,
                "eligibility_state": "excluded_non_compressor",
                "activity_state": "n/a",
                "proof_quality": "",
                "proof_role": "clg_valve_pct",
                "runtime_hours": 0.0,
                "valid_elapsed_hours": 0.0,
                "coverage_pct": 0.0,
                "exclusion_reason": "chilled_water_valve_not_compressor",
            },
        ]
    )
    assert list(cov.columns) == _COV_COLS
    cov.to_csv(root / "mech_cooling_coverage.csv", index=False)

    tel = root / "telemetry"
    tel.mkdir(exist_ok=True)
    (tel / "AHU_1.csv").write_text(
        "timestamp,discharge-air-temp\n2024-06-01T00:00:00Z,55.0\n",
        encoding="utf-8",
    )
    (tel / "CHILLER_2.csv").write_text(
        "timestamp,chiller_status\n2024-06-01T00:00:00Z,1\n",
        encoding="utf-8",
    )
    # Summary profile: no fdd_timeseries directory
    assert not (root / "fdd_timeseries").exists()
    return root


def test_load_bundle_accepts_v2_zip(tmp_path: Path):
    root = _write_v2_dump(tmp_path / "v2")
    z = _zip_dir(root, tmp_path / "v2.zip")
    b = load_bundle(z, extract_dir=tmp_path / "ex_v2")
    assert b.schema_version == "wattlab_dump_v2"
    assert b.export_profile is None or b.export_profile == ""
    assert b.building_id == "COMPAT_B1"
    assert not b.table("mech_cooling_oat_bins").empty
    assert b.fdd_timeseries_dir is not None and b.fdd_timeseries_dir.is_dir()
    # v2 has no shared telemetry index
    assert b.telemetry_paths == {}


def test_load_bundle_accepts_v3_summary_without_fdd_timeseries(tmp_path: Path):
    root = _write_v3_summary_dump(tmp_path / "v3")
    z = _zip_dir(root, tmp_path / "v3.zip")
    b = load_bundle(z, extract_dir=tmp_path / "ex_v3")
    assert b.schema_version == "wattlab_dump_v3"
    assert b.export_profile == "summary"
    assert b.fdd_timeseries_dir is None
    summary = b.summary()
    assert summary["has_fdd_timeseries"] is False
    assert summary["export_profile"] == "summary"
    assert summary["schema_version"] == "wattlab_dump_v3"


def test_v3_mechanical_tables_preserve_rows_and_columns(tmp_path: Path):
    root = _write_v3_summary_dump(tmp_path / "v3")
    b = load_bundle(root)
    bins = b.table("mech_cooling_oat_bins")
    cov = b.table("mech_cooling_coverage")
    assert list(bins.columns) == _MECH_COLS
    assert len(bins) == 4
    assert set(bins["series_kind"]) == {
        "individual_device",
        "aggregate_device_hours",
        "aggregate_active_hours",
    }
    assert list(cov.columns) == _COV_COLS
    assert len(cov) == 3
    assert "eligible_no_runtime" in set(cov["eligibility_state"].astype(str))
    assert "excluded_non_compressor" in set(cov["eligibility_state"].astype(str))


def test_v3_telemetry_paths_indexed_lazily(tmp_path: Path):
    root = _write_v3_summary_dump(tmp_path / "v3")
    b = load_bundle(root)
    # Discovery is path-only — no eager DataFrame load into tables
    assert "AHU_1" not in b.tables
    assert "telemetry/AHU_1.csv" not in b.tables
    paths = b.telemetry_paths
    assert set(paths) == {"AHU_1", "CHILLER_2"}
    assert paths["AHU_1"].is_file()
    assert paths["AHU_1"].name == "AHU_1.csv"
    assert b.telemetry_dir is not None and b.telemetry_dir.is_dir()
    # Optional explicit load stays opt-in
    df = b.load_telemetry("AHU_1")
    assert list(df.columns) == ["timestamp", "discharge-air-temp"]
    assert len(df) == 1
    summary = b.summary()
    assert summary["has_telemetry"] is True
    assert summary["telemetry_file_count"] == 2


def test_neither_evidence_layout_required(tmp_path: Path):
    """Minimal dump with neither fdd_timeseries nor telemetry still loads."""
    root = tmp_path / "bare"
    _write_common_seed(root)
    (root / "MANIFEST.json").write_text(
        json.dumps({"schema_version": "wattlab_dump_v3", "export_profile": "summary"}),
        encoding="utf-8",
    )
    b = load_bundle(root)
    assert b.schema_version == "wattlab_dump_v3"
    assert b.export_profile == "summary"
    assert b.fdd_timeseries_dir is None
    assert b.telemetry_paths == {}
    assert b.summary()["has_telemetry"] is False
    assert b.summary()["has_fdd_timeseries"] is False


def test_malformed_manifest_raises_value_error(tmp_path: Path):
    root = tmp_path / "bad_manifest"
    _write_common_seed(root)
    (root / "MANIFEST.json").write_text("{not-json", encoding="utf-8")
    with pytest.raises(ValueError, match=r"MANIFEST\.json|manifest"):
        load_bundle(root)


def test_unsupported_manifest_schema_raises_value_error(tmp_path: Path):
    root = tmp_path / "future"
    _write_common_seed(root)
    (root / "MANIFEST.json").write_text(
        json.dumps({"schema_version": "wattlab_dump_v99", "files": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"wattlab_dump_v99|unsupported"):
        load_bundle(root)


def test_absent_manifest_still_loads(tmp_path: Path):
    """Legacy dumps without MANIFEST.json remain accepted."""
    root = tmp_path / "legacy"
    _write_common_seed(root)
    assert not (root / "MANIFEST.json").exists()
    b = load_bundle(root)
    assert b.schema_version == ""
    assert b.manifest == {}
    assert b.building_id == "COMPAT_B1"


def test_malformed_optional_json_does_not_raise(tmp_path: Path):
    """model_seed / other optional JSON stay soft; only MANIFEST is strict."""
    root = tmp_path / "soft_json"
    _write_common_seed(root)
    (root / "model_seed.json").write_text("{broken", encoding="utf-8")
    (root / "MANIFEST.json").write_text(
        json.dumps({"schema_version": "wattlab_dump_v3", "export_profile": "summary"}),
        encoding="utf-8",
    )
    b = load_bundle(root)
    assert b.schema_version == "wattlab_dump_v3"
    assert b.model_seed == {}


def test_v3_zip_load_telemetry_readable_for_bundle_lifetime(tmp_path: Path):
    """Extracted telemetry paths remain readable after load_bundle returns."""
    root = _write_v3_summary_dump(tmp_path / "v3")
    z = _zip_dir(root, tmp_path / "v3_summary.zip")
    b = load_bundle(z)  # temp extract_dir — must outlive returned bundle
    assert b.export_profile == "summary"
    path = b.telemetry_paths["AHU_1"]
    assert path.is_file()
    df = b.load_telemetry("AHU_1")
    assert not df.empty
    assert list(df.columns) == ["timestamp", "discharge-air-temp"]
    assert float(df["discharge-air-temp"].iloc[0]) == 55.0
    # Still readable via path after load_telemetry (bundle lifetime)
    assert path.is_file()
    again = pd.read_csv(path)
    assert len(again) == 1
