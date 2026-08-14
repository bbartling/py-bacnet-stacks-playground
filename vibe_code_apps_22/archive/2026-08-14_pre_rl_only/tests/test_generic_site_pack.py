"""Generic campus fixture inventories/publishes without Lakeside names."""
from __future__ import annotations

import json
from pathlib import Path

from eplus_gym_app.site_pack import ingest_site_pack, inventory_site_pack

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "generic_campus"


def test_generic_campus_inventory_and_publish(tmp_path: Path):
    assert _FIXTURE.is_dir()
    inv = inventory_site_pack(_FIXTURE)
    assert inv.fuel_ready is True
    assert inv.twin_ready is True
    assert inv.champion_idf is not None
    assert "champion" in inv.champion_idf.name.lower()
    assert "lakeside" not in inv.champion_idf.name.lower()
    assert inv.campus_json is not None
    assert "lakeside" not in inv.campus_json.read_text(encoding="utf-8").lower()

    dest = tmp_path / "site"
    staged = ingest_site_pack(_FIXTURE, dest)
    assert staged.champion_idf is not None
    assert "lakeside" not in staged.champion_idf.name.lower()

    manifest = dest / "reports" / "site_ui_bundle_v1.json"
    assert manifest.is_file()
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    champ = str(doc.get("dsm_champion") or "")
    assert champ in {"CHAMPION", "DEMO"}
    assert "lakeside" not in champ.lower()
    assert "lakeside" not in str(doc.get("idf_pin") or "").lower()
    assert "lakeside" not in str(doc.get("campus_json") or "").lower()
    catalog = doc.get("model_catalog") or []
    blob = json.dumps(catalog).lower()
    assert "lakeside" not in blob
