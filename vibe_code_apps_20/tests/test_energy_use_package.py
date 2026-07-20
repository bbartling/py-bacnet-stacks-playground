"""Tests for energy-use package + studio workspace."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from wattlab.energy_use import load_energy_use_package, normalize_column_map
from wattlab.studio.workspace import ensure_workspace, list_workspace_summary, save_upload_bytes


def test_normalize_column_map_haystack_equip_points():
    doc = {
        "version": 1,
        "equip": {
            "METER_1": {
                "equipType": "meter",
                "points": {"elec-power": "building_kw", "gas-flow": "gas_therms_per_hr"},
            }
        },
    }
    norm = normalize_column_map(doc)
    roles = norm["equipment"]["METER_1"]["column_roles"]
    assert roles["elec-power"] == "building_kw"
    assert roles["gas-flow"] == "gas_therms_per_hr"


def test_load_energy_use_package_campus_zip(tmp_path: Path):
    root = tmp_path / "pkg"
    root.mkdir()
    (root / "campus.json").write_text(
        json.dumps(
            {
                "campus_id": "demo",
                "label": "Demo",
                "lat": 42.0,
                "lon": -83.0,
                "buildings": [
                    {
                        "building_id": "b1",
                        "label": "B1",
                        "floor_area_ft2": 50000,
                        "property_type": "office",
                    }
                ],
                "meters": [
                    {
                        "meter_id": "elec",
                        "fuel": "electricity",
                        "unit": "kwh",
                        "file": "elec.csv",
                        "serves": ["b1"],
                        "bill_columns": {
                            "month": "Bill Month",
                            "usage": "kWh Total",
                            "demand_kw": "Billed Demand (kW)",
                            "cost_usd": "Total Current Charges ($)",
                        },
                    },
                    {
                        "meter_id": "gas",
                        "fuel": "gas",
                        "unit": "mcf",
                        "file": "gas.csv",
                        "serves": ["b1"],
                        "bill_columns": {
                            "month": "Bill Month",
                            "usage": "Usage (Mcf)",
                            "cost_usd": "Total Energy Charges ($)",
                        },
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    (root / "elec.csv").write_text(
        "Bill Month,kWh Total,Billed Demand (kW),Total Current Charges ($)\n"
        "2025-01,1000,50,120\n2025-02,1100,55,130\n",
        encoding="utf-8",
    )
    (root / "gas.csv").write_text(
        "Bill Month,Usage (Mcf),Total Energy Charges ($)\n2025-01,40,200\n2025-02,35,180\n",
        encoding="utf-8",
    )
    (root / "column_map.json").write_text(
        json.dumps(
            {
                "version": 1,
                "equip": {
                    "METER_1": {
                        "equipType": "meter",
                        "points": {"elec-power": "building_kw"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    zpath = tmp_path / "energy.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        for f in root.iterdir():
            zf.write(f, arcname=f"pkg/{f.name}")

    pkg = load_energy_use_package(zpath)
    assert pkg.campus is not None
    assert pkg.campus.campus_id == "demo"
    assert pkg.lat == 42.0
    assert not pkg.monthly_long.empty
    assert pkg.column_map.get("equipment")


def test_workspace_save_and_list(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("WATTLAB_STUDIO_WORKSPACE", str(tmp_path / "ws"))
    root = ensure_workspace()
    assert (root / "WORKSPACE.md").is_file()
    dest = save_upload_bytes("dump", "wattlab_dump_x.zip", b"PK\x03\x04fake")
    assert dest.is_file()
    summary = list_workspace_summary()
    assert "wattlab_dump_x.zip" in summary["dumps"]
