"""Regression: Excel-only energy zips derive campus for Fuel."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from wattlab.energy_use import load_energy_use_package
from wattlab.energy_use.excel_campus import derive_campus_from_excel


def _write_monthly_xlsx(path: Path, *, sheet: str, fuel: str) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = sheet
    if fuel == "electricity":
        ws.append(["Bill Month", "kWh Total", "Billed Demand (kW)", "Total Current Charges ($)"])
        for i, month in enumerate(
            [
                "2024-12",
                "2025-01",
                "2025-02",
                "2025-03",
                "2025-04",
                "2025-05",
                "2025-06",
                "2025-07",
                "2025-08",
                "2025-09",
                "2025-10",
                "2025-11",
            ]
        ):
            ws.append([month, 100000 + i * 1000, 500 + i, 1000.0])
    else:
        ws.append(["Bill Month", "Usage (Mcf)", "Total Current Charges ($)"])
        for i, month in enumerate(
            [
                "2024-12",
                "2025-01",
                "2025-02",
                "2025-03",
                "2025-04",
                "2025-05",
                "2025-06",
                "2025-07",
                "2025-08",
                "2025-09",
                "2025-10",
                "2025-11",
            ]
        ):
            ws.append([month, 200 + i * 5, 800.0])
    wb.save(path)


def test_derive_campus_from_excel_monthly_workbook(tmp_path: Path):
    pkg = tmp_path / "campus_fuel_package"
    pkg.mkdir()
    _write_monthly_xlsx(pkg / "Shared_Electric.xlsx", sheet="Electric Shared", fuel="electricity")
    _write_monthly_xlsx(pkg / "Gas_A.xlsx", sheet="Gas Building A", fuel="gas")
    _write_monthly_xlsx(pkg / "Gas_B.xlsx", sheet="Gas Building B", fuel="gas")
    (pkg / "buildings.json").write_text(
        json.dumps(
            {
                "buildings": [
                    {
                        "building_id": "site_a",
                        "label": "Building A",
                        "floor_area_ft2": 120000,
                        "property_type": "office",
                    },
                    {
                        "building_id": "site_b",
                        "label": "Building B",
                        "floor_area_ft2": 90000,
                        "property_type": "office",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    result = derive_campus_from_excel(pkg, out_dir=tmp_path / "derived")
    assert result.campus_path.is_file()
    assert len(result.meters) >= 2
    campus_doc = json.loads(result.campus_path.read_text(encoding="utf-8"))
    assert {b["building_id"] for b in campus_doc["buildings"]} == {"site_a", "site_b"}
    assert "liberty" not in json.dumps(campus_doc).lower()

    loaded = load_energy_use_package(pkg, derive_dir=tmp_path / "derived2")
    assert loaded.campus is not None
    assert loaded.fuel_ready is True
    assert loaded.derived_from_excel is True
    assert not loaded.monthly_long.empty


def test_excel_only_zip_windows_paths_fuel_ready(tmp_path: Path):
    pkg = tmp_path / "fuel_use_package"
    pkg.mkdir()
    _write_monthly_xlsx(pkg / "Monthly_Electric.xlsx", sheet="Electric", fuel="electricity")
    _write_monthly_xlsx(pkg / "Monthly_Gas.xlsx", sheet="Gas Building A", fuel="gas")

    archive = tmp_path / "fuel.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        for path in pkg.iterdir():
            zf.write(path, arcname=f"fuel_use_package\\{path.name}")

    loaded = load_energy_use_package(
        archive,
        derive_dir=tmp_path / "derived_zip",
    )
    assert loaded.campus is not None
    assert loaded.fuel_ready is True
    assert loaded.derived_from_excel is True


def test_excel_workbook_without_month_table_raises(tmp_path: Path):
    from openpyxl import Workbook

    pkg = tmp_path / "bad"
    pkg.mkdir()
    wb = Workbook()
    wb.active.title = "Notes"
    wb.active.append(["hello", "world"])
    wb.save(pkg / "notes.xlsx")

    with pytest.raises(ValueError, match="no monthly bill"):
        derive_campus_from_excel(pkg, out_dir=tmp_path / "out")
