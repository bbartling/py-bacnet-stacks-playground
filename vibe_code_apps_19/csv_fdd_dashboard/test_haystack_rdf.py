"""Tests for Haystack RDF / SPARQL layer (synthetic model, no client CSV)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

APP19 = Path(__file__).resolve().parent.parent
if str(APP19) not in sys.path:
    sys.path.insert(0, str(APP19))

from haystack_rdf.model_service import ModelService
from haystack_rdf.model_sparql import column_for_role, list_equipment, query_model_summary
from haystack_rdf.model_store import ModelStore
from haystack_rdf.sparql_queries import (
    execute_model_sparql,
    predefined_catalog,
    validate_all_predefined,
    validate_readonly_sparql,
)
from haystack_rdf.ttl_service import TtlService


SAMPLE_MODEL = {
    "version": 1,
    "sites": [{"id": "TEST_SITE", "name": "Test Site"}],
    "equipment": [
        {
            "id": "AHU_1",
            "name": "AHU 1",
            "site_id": "TEST_SITE",
            "equipment_type": "AHU",
            "haystack_tag": "ahu",
            "history_subdir": "AHU_1",
            "feeds": ["VAV_101"],
        },
        {
            "id": "VAV_101",
            "name": "VAV 101",
            "site_id": "TEST_SITE",
            "equipment_type": "VAV",
            "haystack_tag": "vav",
            "history_subdir": "VAV/VAV_101",
        },
    ],
    "points": [
        {
            "id": "AHU_1__fan",
            "name": "Supply fan",
            "site_id": "TEST_SITE",
            "equipment_id": "AHU_1",
            "column": "supply_fan_speed_pct",
            "timeseries_column": "supply_fan_speed_pct",
            "point_role": "fan_cmd",
            "fdd_input": "fan_cmd",
            "rule_inputs": ["fan_cmd"],
        },
        {
            "id": "AHU_1__damper",
            "name": "OA damper",
            "site_id": "TEST_SITE",
            "equipment_id": "AHU_1",
            "column": "ex_dmpr_pos_fan_enable_pct",
            "timeseries_column": "ex_dmpr_pos_fan_enable_pct",
            "point_role": "oa_damper_pos",
            "fdd_input": "oa_damper_pos",
            "rule_inputs": ["oa_damper_pos", "oa_damper_cmd"],
        },
        {
            "id": "AHU_1__oat",
            "name": "OAT",
            "site_id": "TEST_SITE",
            "equipment_id": "AHU_1",
            "column": "outside_air_temp_f",
            "timeseries_column": "outside_air_temp_f",
            "point_role": "oat",
            "fdd_input": "oat",
        },
    ],
}


@pytest.fixture()
def model_svc(tmp_path: Path) -> ModelService:
    store = ModelStore(path=tmp_path / "model.json")
    store.save(SAMPLE_MODEL)
    ttl = TtlService(model_store=store, ttl_path=tmp_path / "data_model.ttl")
    ttl.sync()
    return ModelService(store=store, ttl=ttl)


def test_predefined_catalog_has_haystack_queries():
    cat = predefined_catalog()
    assert cat["default_query"]
    ids = {q["id"] for q in cat["queries"]}
    assert "sites" in ids
    assert "ahu_information" in ids
    assert "economizer_points" in ids


def test_ttl_sync_and_sparql_sites(model_svc: ModelService):
    result = execute_model_sparql(
        predefined_catalog()["default_query"],
        ttl=model_svc.ttl,
    )
    assert result["row_count"] >= 1
    assert any("TEST_SITE" in row.get("site_label", "") or "site" in row.get("site", "") for row in result["bindings"])


def test_column_for_role(model_svc: ModelService):
    col = column_for_role("AHU_1", "fan_cmd", ttl=model_svc.ttl)
    assert col == "supply_fan_speed_pct"


def test_list_equipment_ahu(model_svc: ModelService):
    ahus = list_equipment(model_svc.ttl, haystack_tag="ahu")
    assert len(ahus) == 1
    assert ahus[0]["id"] == "AHU_1"


def test_feeds_query(model_svc: ModelService):
    q = next(q for q in predefined_catalog()["queries"] if q["id"] == "haystack_feeds")
    result = execute_model_sparql(q["query"], ttl=model_svc.ttl)
    assert result["row_count"] >= 1


def test_validate_all_predefined_queries(model_svc: ModelService):
    result = validate_all_predefined(model_svc.ttl)
    assert not result["failed"], result["failed"]
    assert len(result["passed"]) >= len(predefined_catalog()["queries"])


def test_model_summary(model_svc: ModelService):
    summary = query_model_summary(model_svc.ttl)
    assert summary["ahus"] >= 1
    assert summary["vavs"] >= 1
    assert summary["points"] >= 2


def test_import_export_roundtrip(model_svc: ModelService, tmp_path: Path):
    out = tmp_path / "exported.json"
    model_svc.export_json(out)
    data = json.loads(out.read_text(encoding="utf-8"))
    assert len(data["equipment"]) == 2
    data["sites"].append({"id": "SITE2", "name": "Second"})
    counts = model_svc.import_json(data, replace=True)
    assert counts["sites"] == 2


def test_readonly_sparql_rejects_insert():
    with pytest.raises(ValueError):
        validate_readonly_sparql("INSERT { ?s ?p ?o } WHERE {}")


def test_flask_rdf_routes(model_svc: ModelService, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("HAYSTACK_RDF_ROOT", str(tmp_path))
    monkeypatch.setenv("HVAC_BUILDING", "TEST")
    from shared.data_config import get_config

    get_config.cache_clear()
    store = ModelStore(path=tmp_path / "TEST" / "model.json")
    store.save(SAMPLE_MODEL)
    ttl = TtlService(model_store=store, ttl_path=tmp_path / "TEST" / "data_model.ttl")
    ttl.sync()

    from app import create_app

    client = create_app("full").test_client()
    r = client.get("/api/rdf/sparql/predefined")
    assert r.status_code == 200
    assert "queries" in r.get_json()

    r2 = client.post("/api/rdf/sparql", json={"query": predefined_catalog()["default_query"]})
    if r2.status_code != 200:
        raise AssertionError(r2.get_json())
    assert r2.get_json()["row_count"] >= 1

    r3 = client.get("/data_model.html")
    assert r3.status_code == 200
