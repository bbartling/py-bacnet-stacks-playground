"""Tests for vibe20-style campus fuel + pickers (viewer only)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from eplus_gym_app.campus_fuel import Campus, load_bill_csv
from eplus_gym_app.pickers import list_idf_pins, list_interval_csvs


def test_load_bill_csv_thousands(tmp_path: Path):
    p = tmp_path / "electricity.csv"
    p.write_text(
        "Bill Month,kWh Total\n2026-01,\"84,223.50\"\n2026-02,\"68,222.50\"\n",
        encoding="utf-8",
    )
    df = load_bill_csv(
        p, column_map={"month": "Bill Month", "usage": "kWh Total"}
    )
    assert list(df["month"]) == ["2026-01", "2026-02"]
    assert float(df.loc[0, "usage"]) == pytest.approx(84223.5)


def test_campus_from_json(tmp_path: Path):
    (tmp_path / "electricity.csv").write_text(
        "Bill Month,kWh Total\n2026-01,1000\n2026-02,1100\n",
        encoding="utf-8",
    )
    campus_path = tmp_path / "campus.json"
    campus_path.write_text(
        json.dumps(
            {
                "campus_id": "demo",
                "label": "Demo",
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
                        "file": "electricity.csv",
                        "serves": ["b1"],
                        "bill_columns": {
                            "month": "Bill Month",
                            "usage": "kWh Total",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    c = Campus.from_json(campus_path)
    assert c.campus_id == "demo"
    assert len(c.meters) == 1
    elec = c.electric_monthly()
    assert float(elec["usage"].sum()) == pytest.approx(2100.0)
    eui = c.site_eui_kbtu_ft2()
    assert eui is not None and eui > 0


def test_list_idf_pins_includes_a04():
    names = list_idf_pins()
    assert "lakeside_w2a_a04_dual_champion.idf" in names


def test_interval_csv_normalize_kw_demand(tmp_path: Path):
    from eplus_gym_app.load_profiles import load_bas_demand_oat

    p = tmp_path / "demand_interval_kw.csv"
    rows = [
        {"timestamp_utc": f"2026-01-26T{h:02d}:00:00Z", "kw_demand": 100 + h}
        for h in range(24)
    ]
    # also add 5-min noise hour
    pd.DataFrame(rows).to_csv(p, index=False)
    df = load_bas_demand_oat(csv_path=p)
    assert "kw_avg" in df.columns
    assert "local_day" in df.columns
    assert len(df) == 24
