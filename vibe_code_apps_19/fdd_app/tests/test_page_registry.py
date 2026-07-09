"""Tests for SPARQL-driven page registry."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND.parent.parent))
sys.path.insert(0, str(BACKEND))

from page_registry import (
    ahu_page_id,
    clear_registry_cache,
    discover_pages,
    is_valid_page,
    nav_tree,
    resolve_ahu_equipment,
)


def test_ahu_page_id_slug():
    assert ahu_page_id("AHU_1") == "ahu_ahu_1"


def test_discover_pages_includes_core_static():
    clear_registry_cache()
    pages = discover_pages(force=True)
    ids = {p.id for p in pages}
    assert "index" in ids
    assert "economizer" in ids
    assert "chiller_plant" in ids
    assert "boiler_plant" in ids
    assert "motor_runtime" in ids


def test_nav_tree_has_airside_group():
    clear_registry_cache()
    tree = nav_tree(interactive=True)
    groups = [n for n in tree if n.get("kind") == "group"]
    assert any(g["id"] == "airside" for g in groups)


def test_resolve_ahu_equipment_legacy():
    clear_registry_cache()
    assert resolve_ahu_equipment("ahu_1") is not None
    assert is_valid_page("index")
