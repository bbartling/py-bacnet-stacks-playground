"""Parser smoke tests for twin I/O eplusout.csv columns."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))


def _write_fixture(path: Path) -> None:
    header = [
        "Date/Time",
        "Electricity:Facility [J](Hourly)",
        "Cooling:Electricity [J](Hourly)",
        "FLOOR_1_AHU1:Zone Mean Air Temperature [C](Hourly)",
        "FLOOR_1_AHU2:Zone Mean Air Temperature [C](Hourly)",
        "VAV SYS 1 SUPPLY FAN OUTLET:System Node Temperature [C](Hourly)",
        "VAV SYS 1 MIXED AIR OUTLET:System Node Temperature [C](Hourly)",
        "VAV SYS 1 AIR LOOP INLET:System Node Temperature [C](Hourly)",
        "VAV SYS 1 OUTSIDE AIR INLET:System Node Temperature [C](Hourly)",
        "VAV SYS 1 SUPPLY FAN:Fan Electricity Rate [W](Hourly)",
        "VAV SYS 1:Air System Outdoor Air Flow Fraction [](Hourly)",
        "VAV SYS 2 SUPPLY FAN OUTLET:System Node Temperature [C](Hourly)",
        "VAV SYS 2 MIXED AIR OUTLET:System Node Temperature [C](Hourly)",
        "VAV SYS 2 AIR LOOP INLET:System Node Temperature [C](Hourly)",
        "VAV SYS 2 OUTSIDE AIR INLET:System Node Temperature [C](Hourly)",
        "VAV SYS 2 SUPPLY FAN:Fan Electricity Rate [W](Hourly)",
        "VAV SYS 2:Air System Outdoor Air Flow Fraction [](Hourly)",
        "MAIN CHILLER CHW OUTLET:System Node Temperature [C](Hourly)",
        "MAIN CHILLER CHW INLET:System Node Temperature [C](Hourly)",
        "CHILLED WATER LOOP CHW SUPPLY PUMP:Pump Electricity Rate [W](Hourly)",
        "CHILLED WATER LOOP CNDW SUPPLY PUMP:Pump Electricity Rate [W](Hourly)",
        "MAIN TOWER:Cooling Tower Fan Electricity Rate [W](Hourly)",
        "MAIN TOWER CNDW OUTLET:System Node Temperature [C](Hourly)",
    ]
    # 15:00–16:00 stamp → hour-ending 16 in E+ style " 07/24  16:00:00"
    # Two hours so PLR normalization has a peak
    rows = []
    for hour, fan_w in ((15, 5000.0), (16, 10000.0)):
        row = [f" 07/24  {hour:02d}:00:00"] + [
            str(v)
            for v in [
                3600_000_000.0,
                720_000_000.0,
                24.0,
                24.5,
                12.8,
                23.5,
                24.0,
                35.0,
                fan_w,
                0.25,
                12.5,
                23.8,
                24.2,
                35.1,
                fan_w * 0.9,
                0.22,
                6.7,
                12.1,
                2000.0 if hour == 16 else 1000.0,
                1500.0 if hour == 16 else 750.0,
                3000.0 if hour == 16 else 1500.0,
                29.4,
            ]
        ]
        rows.append(row)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        for row in rows:
            w.writerow(row)


def test_parse_hourly_twin_io_fixture(tmp_path: Path):
    import july_demand_profiles_eplus as july

    csv_path = tmp_path / "eplusout.csv"
    _write_fixture(csv_path)
    rows = july.parse_hourly_twin_io(csv_path)
    assert len(rows) == 2
    r = rows[1]  # hour 16 = peak fan
    assert r["hour"] == 16
    assert abs(r["facility_kw"] - 1000.0) < 0.01
    assert abs(r["cooling_kw"] - 200.0) < 0.01
    assert abs(r["zone_temp_ahu1_mean_c"] - 24.0) < 0.01
    assert abs(r["ahu1_dat_c"] - 12.8) < 0.01
    assert abs(r["ahu1_fan_plr"] - 1.0) < 0.001
    assert abs(rows[0]["ahu1_fan_plr"] - 0.5) < 0.001
    assert abs(r["chw_supply_c"] - 6.7) < 0.01
    assert abs(r["tower_leaving_c"] - 29.4) < 0.01
    assert abs(r["chw_pump_plr"] - 1.0) < 0.001


def test_ensure_twin_io_outputs_idempotent():
    import july_demand_profiles_eplus as july

    text = "Output:Variable,*,Zone Mean Air Temperature,Hourly;\n"
    once = july._ensure_twin_io_outputs(text)
    twice = july._ensure_twin_io_outputs(once)
    assert once.count("!- vibe21 twin_io outputs v2") == 1
    assert twice.count("!- vibe21 twin_io outputs v2") == 1
    assert "Fan Electricity Rate" in once
    assert "VAV Sys 1 Supply Fan Outlet" in once
