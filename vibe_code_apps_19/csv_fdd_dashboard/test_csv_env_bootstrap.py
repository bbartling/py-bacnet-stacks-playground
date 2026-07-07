"""Tests for recursive CSV discovery and .env-driven bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

APP19 = Path(__file__).resolve().parent.parent
if str(APP19) not in sys.path:
    sys.path.insert(0, str(APP19))

from haystack_rdf.csv_bootstrap import build_model_from_csv
from haystack_rdf.csv_discovery import discover_historian_bundles
from haystack_rdf.sparql_queries import validate_all_predefined
from haystack_rdf.ttl_service import TtlService
from shared.data_config import DataConfig, get_config


def _write_bundle(root: Path, sub: str, cols: list[str]) -> None:
    d = root / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / "columns.csv").write_text("column,point_name\n" + "\n".join(f"{c},{c}" for c in cols), encoding="utf-8")
    (d / "history_wide.csv").write_text("timestamp_utc," + ",".join(cols) + "\n2024-01-01T00:00:00Z," + ",".join("0" for _ in cols), encoding="utf-8")


def test_discover_nested_vav(tmp_path: Path):
    building = tmp_path / "BUILDING_X"
    _write_bundle(building, "AHU_1", ["fan_pct"])
    _write_bundle(building, "VAV/VAV_101", ["flow"])
    bundles = discover_historian_bundles(building, building_dir=building)
    subs = {b.history_subdir for b in bundles}
    assert "AHU_1" in subs
    assert "VAV/VAV_101" in subs


def test_build_model_from_nested_tree(tmp_path: Path):
    data_root = tmp_path / "hvac"
    building = data_root / "B1"
    _write_bundle(building, "AHU_1", ["supply_fan_speed_pct"])
    _write_bundle(data_root, "weather", ["outside_air_temp_f"])
    cfg = DataConfig(data_root=data_root, building="B1", weather_subdir="weather")
    model = build_model_from_csv(cfg)
    eq_ids = {e["id"] for e in model["equipment"]}
    assert "AHU_1" in eq_ids
    assert "WEATHER" in eq_ids
    assert len(model["points"]) >= 2


@pytest.mark.skipif(
    not get_config().building_dir.is_dir(),
    reason="No HVAC CSV tree (.env HVAC_DATA_ROOT or junction)",
)
def test_live_env_sparql_validate_all():
    """End-to-end: .env path → recursive CSV bootstrap → all predefined SPARQL pass."""
    from haystack_rdf.auto_sync import ensure_model_synced

    cfg = get_config()
    ensure_model_synced(cfg, force=True)
    ttl = TtlService()
    result = validate_all_predefined(ttl)
    assert not result["failed"], result["failed"]
    assert len(result["passed"]) >= 10
