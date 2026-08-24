import json
import zipfile

import pandas as pd
import pytest

from vibe23.mapping import MAPPING_SCHEMA, MappingValidationError
from vibe23.openfdd import ADAPTER_SCHEMA, build_openfdd_package


def _mapping():
    return {
        "schema_version": MAPPING_SCHEMA,
        "building_id": "LBNL_B59",
        "grid_minutes": 5,
        "dataset_doi": "10.7941/D1N33Q",
        "acquisition_manifest_sha256": "b" * 64,
        "mapping_evidence": "Fixture binding verified against a synthetic metadata row.",
        "equipment": [{
            "equipment_id": "RTU_1",
            "equip_type": "ahu",
            "source_file": "clean/rtu_1.csv",
            "timestamp_column": "local_time",
            "source_timezone": "America/Los_Angeles",
            "points": [
                {"haystack_point": "fan-status", "source_column": "SF_STATUS", "units": "bool", "evidence": "fixture"},
                {"haystack_point": "discharge-air-temp", "source_column": "SAT_F", "units": "degF", "evidence": "fixture"},
            ],
        }],
    }


def _write_fixture(tmp_path, *, bad_timestamp=False, reversed_timestamps=False):
    raw_root = tmp_path / "raw"
    source = raw_root / "clean" / "rtu_1.csv"
    source.parent.mkdir(parents=True)
    pd.DataFrame({
        "local_time": (
            ["2019-01-15 00:05", "2019-01-15 00:00"]
            if reversed_timestamps
            else ["2019-01-15 00:00", "not-a-time" if bad_timestamp else "2019-01-15 00:05"]
        ),
        "SF_STATUS": [1, 1],
        "SAT_F": [55.0, 55.5],
    }).to_csv(source, index=False)
    mapping_path = tmp_path / "mapping.json"
    mapping_path.write_text(json.dumps(_mapping()), encoding="utf-8")
    return raw_root, mapping_path


def test_builds_openfdd_v1_zip_with_utc_and_provenance(tmp_path):
    raw_root, mapping_path = _write_fixture(tmp_path)
    output = tmp_path / "out" / "b59.zip"
    report = build_openfdd_package(mapping_path, raw_root, output)
    assert output.is_file()
    assert report["schema_version"] == ADAPTER_SCHEMA
    with zipfile.ZipFile(output) as archive:
        assert set(archive.namelist()) == {
            "LBNL_B59/manifest.json",
            "LBNL_B59/VIBE23_OPENFDD_ADAPTER.json",
            "LBNL_B59/RTU_1/history_wide.csv",
            "LBNL_B59/RTU_1/history_wide.json",
        }
        manifest = json.loads(archive.read("LBNL_B59/manifest.json"))
        assert manifest["schema_version"] == "openfdd_package_v1"
        assert manifest["timezone"] == "UTC"
        sidecar = json.loads(archive.read("LBNL_B59/RTU_1/history_wide.json"))
        assert sidecar["points"] == {"discharge-air-temp": "SAT_F", "fan-status": "SF_STATUS"}
        rows = archive.read("LBNL_B59/RTU_1/history_wide.csv").decode().splitlines()
        assert rows[1].startswith("2019-01-15T08:00:00Z,")
        adapter = json.loads(archive.read("LBNL_B59/VIBE23_OPENFDD_ADAPTER.json"))
        assert adapter["exports"][0]["points"][0]["units"] == "bool"
        assert "unit conversion" in adapter["not_performed"]


def test_fails_closed_on_unparseable_timestamp(tmp_path):
    raw_root, mapping_path = _write_fixture(tmp_path, bad_timestamp=True)
    with pytest.raises(MappingValidationError, match="timestamps cannot be parsed"):
        build_openfdd_package(mapping_path, raw_root, tmp_path / "bad.zip")


def test_fails_closed_when_mapped_column_is_absent(tmp_path):
    raw_root, mapping_path = _write_fixture(tmp_path)
    raw = _mapping()
    raw["equipment"][0]["points"][0]["source_column"] = "NOT_REAL"
    mapping_path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(MappingValidationError, match="mapped columns not found"):
        build_openfdd_package(mapping_path, raw_root, tmp_path / "bad.zip")


def test_fails_closed_on_non_chronological_source(tmp_path):
    raw_root, mapping_path = _write_fixture(tmp_path, reversed_timestamps=True)
    with pytest.raises(MappingValidationError, match="chronological"):
        build_openfdd_package(mapping_path, raw_root, tmp_path / "bad.zip")


def test_refuses_to_write_package_inside_immutable_raw_root(tmp_path):
    raw_root, mapping_path = _write_fixture(tmp_path)
    with pytest.raises(MappingValidationError, match="immutable raw_root"):
        build_openfdd_package(mapping_path, raw_root, raw_root / "export.zip")
