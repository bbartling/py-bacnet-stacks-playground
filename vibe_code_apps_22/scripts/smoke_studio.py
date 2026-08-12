#!/usr/bin/env python
"""AppTest walk of Site DSM tabs (no live EnergyPlus)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))


def _minimal_site(tmp: Path) -> Path:
    (tmp / "utilities").mkdir(parents=True)
    (tmp / "reports").mkdir(parents=True)
    (tmp / "eplus" / "models").mkdir(parents=True)
    campus = {
        "campus_id": "smoke_campus",
        "label": "Smoke Campus",
        "lat": 43.0,
        "lon": -89.0,
        "buildings": [
            {
                "building_id": "b1",
                "floor_area_ft2": 50000,
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
                "bill_columns": {"month": "month", "usage": "kwh"},
            }
        ],
    }
    (tmp / "utilities" / "campus.json").write_text(json.dumps(campus), encoding="utf-8")
    (tmp / "utilities" / "electricity.csv").write_text(
        "month,kwh\n2026-01,1000\n2026-02,1100\n", encoding="utf-8"
    )
    rows = []
    for day, peak in (("2025-12-15", 180.0), ("2026-01-26", 286.0), ("2026-02-10", 210.0)):
        for h in range(24):
            rows.append(
                {
                    "hour_utc": f"{day}T{h:02d}:00:00-06:00",
                    "day_type": "Weekday",
                    "kw_avg": peak if h == 8 else 90.0 + h,
                    "oat_f": -5.0,
                }
            )
    pd.DataFrame(rows).to_csv(
        tmp / "reports" / "demand_vs_web_weather_hourly.csv", index=False
    )
    (tmp / "eplus" / "models" / "demo_champion.idf").write_text(
        "Version,24.2;\nBuilding,Demo,0,Suburbs,0.04,0.4,FullExterior,25,6;\n",
        encoding="utf-8",
    )
    (tmp / "reports" / "site_ui_bundle_v1.json").write_text(
        json.dumps(
            {
                "schema_version": "site_ui_bundle_v1",
                "campus_json": "utilities/campus.json",
                "bas_demand_oat_csv": "reports/demand_vs_web_weather_hourly.csv",
                "default_model_id": "CHAMPION",
                "current_model_id": "CHAMPION",
                "dsm_champion": "CHAMPION",
                "idf_pin": "demo_champion.idf",
                "model_catalog": [
                    {
                        "id": "CHAMPION",
                        "label": "Demo champion",
                        "family": "W2A_PHYSICAL_DSM",
                        "idf_pin": "demo_champion.idf",
                        "champion": True,
                        "dial_id": "CHAMPION",
                    }
                ],
                "dial_ladder": {"peak_day": "2026-01-26", "models": []},
                "honesty": {"bas": "BAS_INTERVAL_METER"},
            }
        ),
        encoding="utf-8",
    )
    (tmp / "reports" / "ecm_compare.json").write_text(
        json.dumps({"measures": []}), encoding="utf-8"
    )
    return tmp


def main() -> int:
    import tempfile

    from streamlit.testing.v1 import AppTest

    with tempfile.TemporaryDirectory(prefix="vibe22_smoke_") as td:
        site = _minimal_site(Path(td))
        os.environ["SITE_ROOT"] = str(site)
        os.environ["LAKESIDE_SITE_ROOT"] = str(site)
        at = AppTest.from_file(str(_APP / "eplus_gym_app" / "streamlit_app.py"))
        at.run(timeout=120)
        if at.exception:
            print("EXCEPTION", at.exception)
            return 2
        titles = " ".join(str(t.value) for t in at.title)
        assert "Site DSM" in titles
        assert "Lakeside DSM" not in titles
        for tab in ("Run DSM", "Calibration", "Fuel", "ECMs"):
            at.session_state["lakeside_main_tabs"] = tab
            at.run(timeout=90)
            assert not at.exception, tab
            assert not list(at.error), (tab, [str(e.value) for e in at.error])
            print("TAB_OK", tab)
        print("SMOKE_STUDIO_OK")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
