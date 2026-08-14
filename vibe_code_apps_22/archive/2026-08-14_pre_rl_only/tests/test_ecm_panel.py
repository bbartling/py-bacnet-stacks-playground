"""Energy ECMs compare contract + publish helpers."""
from __future__ import annotations

import json
from pathlib import Path

from eplus_gym_app.ecm_panel import ecm_compare_table, load_ecm_compare
from eplus_gym_app.ecm_publish import (
    from_twin_compare,
    normalize_compare_payload,
    normalize_measure,
    save_ecm_compare,
)


def test_normalize_twin_compare_measures():
    twin = {
        "measures": [
            {
                "measure_id": "ECM-CHILLER-LOCKOUT",
                "fitted_sheet_kwh": 1000.0,
                "eplus_kwh": 980.0,
                "capital_usd": 5000.0,
                "fitted_sheet_usd": 145.0,
                "eplus_usd": 142.1,
            }
        ]
    }
    rows = from_twin_compare(twin)
    assert rows[0]["ss_kwh"] == 1000.0
    assert rows[0]["ep_kwh"] == 980.0
    assert rows[0]["payback_yr_ss"] is not None


def test_save_and_load_round_trip(tmp_path: Path):
    save_ecm_compare(
        tmp_path,
        {
            "measures": [
                {
                    "measure_id": "ECM-AHU-SCHED-ALIGN",
                    "ss_kwh": 10.0,
                    "ep_kwh": 9.0,
                    "ss_usd": 1.0,
                    "ep_usd": 0.9,
                    "capital_usd": 5.0,
                }
            ]
        },
    )
    loaded = load_ecm_compare(tmp_path)
    assert loaded["schema"] == "site_ecm_compare_v1"
    assert len(loaded["measures"]) == 1
    table = ecm_compare_table(loaded)
    assert not table.empty
    assert table.iloc[0]["measure"] == "ECM-AHU-SCHED-ALIGN"


def test_fixture_loads():
    fixture = (
        Path(__file__).resolve().parent / "fixtures" / "ecm_compare_fixture.json"
    )
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    doc = normalize_compare_payload(raw)
    assert len(doc["measures"]) == 2
    assert normalize_measure(doc["measures"][1])["status"] == "CONCEPTUAL"
