"""One-shot generator for tests/fixtures/shared_meter_campus (not shipped to users)."""
from __future__ import annotations

import json
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "shared_meter_campus"
root.mkdir(parents=True, exist_ok=True)

elec_window = [
    ("2024-12", 171857, 588),
    ("2025-01", 206892, 553),
    ("2025-02", 209818, 553),
    ("2025-03", 205933, 743),
    ("2025-04", 200179, 670),
    ("2025-05", 233247, 691),
    ("2025-06", 255206, 757),
    ("2025-07", 340067, 802),
    ("2025-08", 349188, 819),
    ("2025-09", 255598, 727),
    ("2025-10", 281155, 778),
    ("2025-11", 219758, 702),
]
elec_extra = [("2015-01", 281890, 594)]

g50_window = [
    ("2024-12", 467.8),
    ("2025-01", 836.8),
    ("2025-02", 1028.0),
    ("2025-03", 685.8),
    ("2025-04", 438.1),
    ("2025-05", 176.8),
    ("2025-06", 88.1),
    ("2025-07", 3.8),
    ("2025-08", 7.5),
    ("2025-09", 22.4),
    ("2025-10", 57.4),
    ("2025-11", 394.4),
]
g50_extra = [("2016-03", 1189.4)]

g100_window = [
    ("2024-12", 574.4),
    ("2025-01", 823.6),
    ("2025-02", 1129.7),
    ("2025-03", 786.7),
    ("2025-04", 600.4),
    ("2025-05", 354.5),
    ("2025-06", 254.0),
    ("2025-07", 110.1),
    ("2025-08", 77.9),
    ("2025-09", 198.6),
    ("2025-10", 146.3),
    ("2025-11", 425.5),
]
g100_extra = [("2016-03", 1260.9), ("2019-07", 71.1), ("2019-07", 14.7)]


def write_elec(path: Path, rows: list[tuple]) -> None:
    lines = ["Bill Month,kWh Total,Billed Demand (kW),Total Current Charges ($)"]
    for m, u, d in rows:
        lines.append(f'{m},"{u:,}",{d},"1,000.00"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_gas(path: Path, rows: list[tuple]) -> None:
    lines = ["Bill Month,Usage (Mcf),Avg Daily Mcf,Total Energy Charges ($),$/Mcf"]
    for m, u in rows:
        usage = f'"{u:,}"' if u >= 1000 else str(u)
        lines.append(f'{m},{usage},1.0,"100.00",5.0')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


write_elec(root / "shared_electric_summary.csv", elec_extra + elec_window)
write_gas(root / "building_a_gas_summary.csv", g50_extra + g50_window)
write_gas(root / "building_b_gas_summary.csv", g100_extra + g100_window)

campus = {
    "campus_id": "shared_meter_demo",
    "label": "Synthetic shared-electric + per-building-gas campus (CI fixture)",
    "notes": (
        "Privacy-safe fixture with stable golden anchors. "
        "Local Liberty CSVs under examples/liberty remain gitignored."
    ),
    "buildings": [
        {
            "building_id": "liberty_50",
            "label": "Building A",
            "floor_area_ft2": 140000,
            "property_type": "office",
        },
        {
            "building_id": "liberty_100",
            "label": "Building B",
            "floor_area_ft2": 140000,
            "property_type": "office",
        },
    ],
    "meters": [
        {
            "meter_id": "elec_shared",
            "fuel": "electricity",
            "unit": "kwh",
            "file": "shared_electric_summary.csv",
            "serves": ["liberty_50", "liberty_100"],
            "allocation": {"method": "area_weighted"},
        },
        {
            "meter_id": "gas_50",
            "fuel": "gas",
            "unit": "mcf",
            "file": "building_a_gas_summary.csv",
            "serves": ["liberty_50"],
        },
        {
            "meter_id": "gas_100",
            "fuel": "gas",
            "unit": "mcf",
            "file": "building_b_gas_summary.csv",
            "serves": ["liberty_100"],
        },
    ],
}
(root / "campus.json").write_text(json.dumps(campus, indent=2) + "\n", encoding="utf-8")
print("wrote", root)
