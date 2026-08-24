import json

import pytest

from vibe23.mapping import MAPPING_SCHEMA, MappingValidationError, load_mapping


def _mapping():
    return {
        "schema_version": MAPPING_SCHEMA,
        "building_id": "LBNL_B59",
        "grid_minutes": 5,
        "dataset_doi": "10.7941/D1N33Q",
        "acquisition_manifest_sha256": "a" * 64,
        "mapping_evidence": "Inventory workbook row 12 verified by engineer.",
        "equipment": [{
            "equipment_id": "RTU_1",
            "equip_type": "ahu",
            "source_file": "clean/rtu_1.csv",
            "timestamp_column": "time",
            "source_timezone": "America/Los_Angeles",
            "points": [{
                "haystack_point": "fan-status",
                "source_column": "SF_STATUS",
                "units": "bool",
                "evidence": "Metadata point SF_STATUS.",
            }],
        }],
    }


def test_load_explicit_mapping(tmp_path):
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(_mapping()), encoding="utf-8")
    result = load_mapping(path)
    assert result.building_id == "LBNL_B59"
    assert result.equipment[0].points[0].haystack_point == "fan-status"


def test_mapping_rejects_duplicate_or_ambiguous_source_column(tmp_path):
    raw = _mapping()
    raw["equipment"][0]["points"].append({
        "haystack_point": "fan-cmd",
        "source_column": "SF_STATUS",
        "units": "pct",
        "evidence": "Wrong on purpose.",
    })
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(MappingValidationError, match="one source column"):
        load_mapping(path)


def test_mapping_rejects_unverified_weather_relabel(tmp_path):
    raw = _mapping()
    raw["equipment"][0]["equip_type"] = "weather"
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(MappingValidationError, match="weather"):
        load_mapping(path)


def test_mapping_rejects_another_dataset_doi(tmp_path):
    raw = _mapping()
    raw["dataset_doi"] = "10.0000/NOT-B59"
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(MappingValidationError, match="10.7941/D1N33Q"):
        load_mapping(path)


def test_mapping_requires_json_boolean_for_allow_nulls(tmp_path):
    raw = _mapping()
    raw["equipment"][0]["points"][0]["allow_nulls"] = "false"
    path = tmp_path / "mapping.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(MappingValidationError, match="JSON boolean"):
        load_mapping(path)
