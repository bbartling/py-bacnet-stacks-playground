"""Multi-site mapping, CSV profiling, and SQL source tests."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
import yaml

from app.mapping_wizard import (
    flat_role_map_from_sites,
    is_nested_role_map,
    load_site_mapping,
    migrate_flat_file,
    save_site_mapping,
    sites_from_yaml,
    wrap_flat_role_map,
)
from app.role_map import load_role_map, save_role_map
from app.rules import CANONICAL_RULE_COUNT, RULES
from app.site_model import Site, equipment_type_from_id
from app.source_profile import load_uploaded_csvs, normalize_wide_source, profile_csv_source
from app.sql_sources import SqlServerConfig, validate_readonly_sql


def test_flat_role_map_loads(tmp_path: Path):
    p = tmp_path / "flat.yaml"
    p.write_text("AHU_1:\n  sat: discharge_air_temp_f\n", encoding="utf-8")
    m = load_role_map(p)
    assert m["AHU_1"]["sat"] == "discharge_air_temp_f"


def test_nested_role_map_loads(tmp_path: Path):
    nested = {
        "sites": {
            "acme_main": {
                "name": "ACME",
                "buildings": {
                    "BUILDING_100": {
                        "equipment": {
                            "AHU_1": {"equipment_type": "AHU", "roles": {"sat": "discharge_air_temp_f"}},
                        }
                    }
                },
            }
        }
    }
    p = tmp_path / "nested.yaml"
    p.write_text(yaml.safe_dump(nested), encoding="utf-8")
    flat = load_role_map(p)
    assert flat["AHU_1"]["sat"] == "discharge_air_temp_f"
    sites = load_site_mapping(p)
    assert "acme_main" in sites


def test_flat_migrates_to_nested(tmp_path: Path):
    flat = tmp_path / "flat.yaml"
    flat.write_text("VAV_7:\n  zone_t: space_temp\n", encoding="utf-8")
    nested = tmp_path / "nested.yaml"
    sites = migrate_flat_file(flat, nested)
    assert flat_role_map_from_sites(sites)["VAV_7"]["zone_t"] == "space_temp"
    assert is_nested_role_map(yaml.safe_load(nested.read_text(encoding="utf-8")))


def test_multi_csv_upload_normalize():
    csv1 = b"timestamp,oa_t\n2024-01-01T00:00:00Z,32\n2024-01-01T00:05:00Z,33\n"
    csv2 = b"timestamp,zone_t\n2024-01-01T00:00:00Z,72\n2024-01-01T00:05:00Z,73\n"
    f1 = MagicMock(name="oa.csv", getvalue=lambda: csv1)
    f2 = MagicMock(name="vav.csv", getvalue=lambda: csv2)
    raw = load_uploaded_csvs([f1, f2])
    assert len(raw) == 2
    wide = normalize_wide_source(raw[0].df, equipment_id="AHU_1")
    assert "AHU_1" in wide
    assert "oa_t" in wide["AHU_1"].columns


def test_wide_and_long_profiles():
    wide = pd.DataFrame({"timestamp": ["2024-01-01"], "sat": [72.0]})
    assert profile_csv_source(wide).format == "wide"
    long = pd.DataFrame({"timestamp": ["2024-01-01"], "equipment_id": ["AHU_1"], "point_name": ["sat"], "value": [72.0]})
    assert profile_csv_source(long).format == "long"


def test_unsafe_sql_rejected():
    with pytest.raises(ValueError):
        validate_readonly_sql("DROP TABLE history")
    with pytest.raises(ValueError):
        validate_readonly_sql("INSERT INTO t VALUES (1)")


def test_sqlserver_config_masks_password():
    cfg = SqlServerConfig(server="localhost", database="db", username="u", password="secret")
    assert cfg.masked()["password"] == "****"


def test_site_model_serialization():
    sites = wrap_flat_role_map({"AHU_1": {"sat": "x"}}, site_id="s1", building_id="b1")
    assert sites["s1"].buildings["b1"].equipment["AHU_1"].roles["sat"] == "x"
    assert equipment_type_from_id("VAV_7") == "VAV"


def test_all_50_rules_inventory():
    assert CANONICAL_RULE_COUNT == 51
    assert len([r for r in RULES if not str(r.id).startswith("CUSTOM-")]) == 51
    assert len(RULES) >= CANONICAL_RULE_COUNT


def test_streamlit_app_imports():
    import streamlit_app  # noqa: F401
