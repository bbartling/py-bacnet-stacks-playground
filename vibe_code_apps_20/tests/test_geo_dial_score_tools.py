"""Generalized geo-idf / score-monthly tools (any building)."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd
import pytest

from wattlab.energyplus.geo_idf import process_geometry, rewrite_vert_line
from wattlab.energyplus.score_monthly import last12_monthly, score_monthly_run


def test_last12_monthly_skips_extra():
    s = pd.Series([0.0] + [float(i) for i in range(1, 15)])
    out = last12_monthly(s)
    assert len(out) == 12
    assert float(out.iloc[0]) == 3.0


def test_score_monthly_vs_bills(tmp_path: Path):
    months = [f"01/{i:02d} 24:00:00" for i in range(1, 13)]
    j_per_mo = 1000.0 * 3.6e6
    g_per_mo = 10.0 * 1.05506e8
    df = pd.DataFrame(
        {
            "Date/Time": months,
            "Electricity:Facility [J](Monthly)": [j_per_mo] * 12,
            "NaturalGas:Facility [J](Monthly)": [g_per_mo] * 12,
        }
    )
    ep = tmp_path / "eplusout.csv"
    df.to_csv(ep, index=False)
    bills = tmp_path / "bills.csv"
    with bills.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["month", "kwh", "therms"])
        w.writeheader()
        for i in range(12):
            w.writerow({"month": f"2024-{i+1:02d}", "kwh": 1000, "therms": 10})
    sc = score_monthly_run(ep, bills, area_ft2=10000.0, run_id="t")
    assert sc["area_scale"] == 1.0
    assert sc["elec_delta_pct"] == pytest.approx(0.0, abs=0.2)
    assert sc["gas_delta_pct"] == pytest.approx(0.0, abs=0.2)


def test_vert_semicolon_before_comment():
    line = "    0.0,0.0,3.0;  !- X,Y,Z ==> Vertex 4 {m}\n"
    out = rewrite_vert_line(line, 1.0, 2.0, 3.5)
    assert ";" in out.split("!")[0]
    assert "1.0000,2.0000,3.5000;" in out


def test_process_geometry_scales_wall():
    idf = """  BuildingSurface:Detailed,
    WallA,                   !- Name
    Wall,                    !- Surface Type
    Const,                   !- Construction Name
    ZoneA,                   !- Zone Name
    ,                        !- Space Name
    Outdoors,                !- Outside Boundary Condition
    ,                        !- Outside Boundary Condition Object
    SunExposed,              !- Sun Exposure
    WindExposed,             !- Wind Exposure
    0.5,                     !- View Factor to Ground
    4,                       !- Number of Vertices
    0.0,0.0,0.0,  !- X,Y,Z ==> Vertex 1 {m}
    10.0,0.0,0.0,  !- X,Y,Z ==> Vertex 2 {m}
    10.0,0.0,3.0,  !- X,Y,Z ==> Vertex 3 {m}
    0.0,0.0,3.0;  !- X,Y,Z ==> Vertex 4 {m}

"""
    out, nb, _nf = process_geometry(idf, xy_scale=2.0, wwr_target=0.6)
    assert nb == 4
    assert "20.0000,0.0000,0.0000" in out
