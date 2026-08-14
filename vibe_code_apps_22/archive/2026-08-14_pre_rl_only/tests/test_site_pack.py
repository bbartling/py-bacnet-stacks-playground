"""Site pack scanner + publisher (zip/folder → readiness + site_ui_bundle)."""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from eplus_gym_app.site_pack import (
    SitePackError,
    ingest_site_pack,
    inventory_site_pack,
    publish_site_ui_bundle,
)


def _campus_doc(*, campus_id: str = "demo", meter_file: str = "electricity.csv") -> dict:
    return {
        "campus_id": campus_id,
        "label": "Demo ES",
        "lat": 43.0,
        "lon": -89.0,
        "buildings": [
            {
                "building_id": "b1",
                "floor_area_ft2": 10000,
                "property_type": "k12_school",
            }
        ],
        "meters": [
            {
                "meter_id": "elec",
                "fuel": "electricity",
                "unit": "kwh",
                "file": meter_file,
                "serves": ["b1"],
                "bill_columns": {"month": "Bill Month", "usage": "kWh Total"},
            }
        ],
    }


def _write_bills(path: Path) -> None:
    path.write_text("Bill Month,kWh Total\n2026-01,1000\n2026-02,1100\n", encoding="utf-8")


def _write_interval(path: Path) -> None:
    rows = ["timestamp_utc,kw_demand"]
    rows.extend(f"2026-01-26T{h:02d}:00:00Z,{100 + h}" for h in range(24))
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_tiny_idf(path: Path) -> None:
    path.write_text(
        "Version,24.2;\nBuilding,Demo,0,Suburbs,0.04,0.4,FullExterior,25,6;\n",
        encoding="utf-8",
    )


def _min_pack(root: Path, *, billing: bool = True, a04: bool = True) -> Path:
    util = root / "utilities"
    util.mkdir(parents=True)
    _write_bills(util / "electricity.csv")
    (util / "campus.json").write_text(
        json.dumps(_campus_doc(campus_id="interval_integrated")), encoding="utf-8"
    )
    if billing:
        _write_bills(util / "electricity_utility.csv")
        (util / "campus_utility.json").write_text(
            json.dumps(
                _campus_doc(campus_id="billing", meter_file="electricity_utility.csv")
            ),
            encoding="utf-8",
        )
    models = root / "eplus" / "models"
    models.mkdir(parents=True)
    if a04:
        _write_tiny_idf(models / "lakeside_w2a_a04_dual_champion.idf")
    _write_tiny_idf(models / "other_building.idf")
    reports = root / "reports"
    reports.mkdir(parents=True)
    _write_interval(reports / "demand_vs_web_weather_hourly.csv")
    return root


def test_inventory_prefers_billing_campus_and_a04(tmp_path: Path):
    pack = _min_pack(tmp_path / "pack")
    inv = inventory_site_pack(pack)
    assert inv.fuel_ready is True
    assert inv.twin_ready is True
    assert inv.actual_ready is True
    assert inv.campus_json is not None
    assert inv.campus_json.name == "campus_utility.json"
    assert inv.champion_idf is not None
    assert "a04" in inv.champion_idf.name.lower()
    assert inv.interval_csv is not None
    keys = {item.key: item.status for item in inv.checklist}
    assert keys["campus"] == "ok"
    assert keys["idf"] == "ok"
    assert keys["interval"] == "ok"


def test_inventory_missing_campus_not_fuel_ready(tmp_path: Path):
    root = tmp_path / "empty"
    root.mkdir()
    inv = inventory_site_pack(root)
    assert inv.fuel_ready is False
    assert any(i.key == "campus" and i.status == "missing" for i in inv.checklist)


def test_publish_missing_campus_fails_closed(tmp_path: Path):
    site = tmp_path / "site"
    site.mkdir()
    with pytest.raises(SitePackError, match="campus"):
        publish_site_ui_bundle(site)


def test_ingest_folder_writes_bundle_with_dsm_fields(tmp_path: Path):
    src = _min_pack(tmp_path / "src")
    dest = tmp_path / "site"
    inv = ingest_site_pack(src, dest)
    assert inv.fuel_ready
    manifest = dest / "reports" / "site_ui_bundle_v1.json"
    assert manifest.is_file()
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    assert doc["schema_version"] == "site_ui_bundle_v1"
    assert doc["campus_json"].endswith("campus_utility.json")
    assert doc["current_model_id"] == "A04"
    assert doc["dsm_champion"] == "A04"
    assert "dsm_farm_parquet" in doc
    assert (dest / "utilities" / "campus_utility.json").is_file()
    assert (dest / "eplus" / "models" / "lakeside_w2a_a04_dual_champion.idf").is_file()


def test_windows_wrapped_zip(tmp_path: Path):
    inner = tmp_path / "inner"
    _min_pack(inner)
    zpath = tmp_path / "pack.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        for p in inner.rglob("*"):
            if p.is_file():
                arc = "site_root\\" + str(p.relative_to(inner)).replace("/", "\\")
                zf.write(p, arcname=arc)
    dest = tmp_path / "site"
    inv = ingest_site_pack(zpath, dest)
    assert inv.fuel_ready
    assert (dest / "utilities" / "campus_utility.json").is_file()


def test_inventory_skips_campaign_idfs(tmp_path: Path):
    pack = _min_pack(tmp_path / "pack")
    camp = pack / "eplus" / "campaigns" / "old" / "trials" / "x"
    camp.mkdir(parents=True)
    _write_tiny_idf(camp / "champion_B_equip_mult_mid_model.idf")
    inv = inventory_site_pack(pack)
    assert inv.champion_idf is not None
    assert "a04" in inv.champion_idf.name.lower()
    assert "campaigns" not in str(inv.champion_idf)


def test_a04_wins_over_e20_champion_name(tmp_path: Path):
    pack = _min_pack(tmp_path / "pack", a04=True)
    models = pack / "eplus" / "models"
    _write_tiny_idf(models / "lakeside_w2a_e20_dual_champion.idf")
    inv = inventory_site_pack(pack)
    assert inv.champion_idf is not None
    assert inv.champion_idf.name == "lakeside_w2a_a04_dual_champion.idf"
    dest = tmp_path / "site"
    ingest_site_pack(pack, dest)
    doc = json.loads((dest / "reports" / "site_ui_bundle_v1.json").read_text(encoding="utf-8"))
    assert doc["dsm_champion"] == "A04"
    assert doc["idf_pin"] == "lakeside_w2a_a04_dual_champion.idf"
    assert "idf_sha256" in doc


def test_zip_slip_rejected(tmp_path: Path):
    zpath = tmp_path / "evil.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("..\\escape.txt", "nope")
    with pytest.raises(SitePackError, match="Unsafe"):
        ingest_site_pack(zpath, tmp_path / "site")
