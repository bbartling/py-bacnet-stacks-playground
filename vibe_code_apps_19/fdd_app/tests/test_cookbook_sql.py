"""Tests for SQL rule catalog loader."""

import cookbook_sql as csql


def test_sql_catalog_has_batch_rules():
    cat = csql.sql_catalog()
    for rid in ["SV-RANGE", "SV-FLATLINE", "VAV-1", "OAT-METEO", "MOTOR-EXCESS"]:
        assert rid in cat, rid
        assert cat[rid].get("sql")


def test_bind_sql_substitutes_params():
    sql = csql.bind_sql("VAV-1", equipment_id="VAV_1", params={"zone_lo": 70, "zone_hi": 75})
    assert sql is not None
    assert "VAV_1" in sql
    assert "70" in sql
    assert "75" in sql


def test_has_sql_unknown():
    assert csql.has_sql("VAV-1") is True
    assert csql.has_sql("NOT-A-RULE") is False
