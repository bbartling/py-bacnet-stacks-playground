"""Unit tests for WattLab defaults, measure sets, vibe19 bridge, IDF patches."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wattlab.measures.measure_sets import expand_measure_set, list_measure_sets
from wattlab.energyplus.patches import apply_chiller_lockout, apply_sat_reset
from wattlab.energyplus.results import savings_by_measure
from wattlab.bridge import merge_into_profile, suggest_from_bundle
from wattlab.defaults import resolve_profile


def test_resolve_profile_tags_sources():
    profile = resolve_profile(
        {
            "building_type": "office",
            "city": "madison",
            "code_year": "90.1-2013",
            "floor_area_ft2": 120000,
            "floors": 4,
        }
    )
    assert profile["conditioned_floor_area_ft2"] == 120000
    assert profile["number_of_floors"] == 4
    assert profile["building_type"] in {"office", "multistory_office"}
    fs = profile["field_sources"]
    assert fs["floor_area_ft2"]["source"] == "user"
    assert fs["floors"]["source"] == "user"
    assert fs["city"]["source"] == "user"
    assert fs["prototype_idf"]["source"] == "default"
    assert "energyplus" in profile
    assert profile["energyplus"]["prototype_idf"].endswith(".idf")
    assert (ROOT / profile["energyplus"]["epw"]).is_file() or (
        ROOT / profile["energyplus"]["epw"]
    ).exists() is False or True  # epw may be relative
    assert (ROOT / profile["energyplus"]["epw"]).is_file()


def test_resolve_profile_defaults_when_empty():
    profile = resolve_profile({})
    assert profile["field_sources"]["building_type"]["source"] == "default"
    assert profile["field_sources"]["city"]["source"] == "default"
    assert profile["anonymized"] is True
    assert "OpenFDD WattLab" in (profile.get("product") or "")


def test_measure_set_expansion_order():
    good = expand_measure_set("good")
    better = expand_measure_set("better")
    best = expand_measure_set("best")
    assert [m["measure_id"] for m in good] == ["ECM-AHU-SCHED-ALIGN"]
    assert [m["measure_id"] for m in better] == [
        "ECM-AHU-SCHED-ALIGN",
        "ECM-CHILLER-LOCKOUT",
    ]
    assert [m["measure_id"] for m in best] == [
        "ECM-AHU-SCHED-ALIGN",
        "ECM-CHILLER-LOCKOUT",
        "ECM-SAT-RESET",
        "ECM-GL36-AIRSIDE",
    ]
    assert all(m.get("review_status") == "approved" for m in best)
    sets = list_measure_sets()
    assert {s["id"] for s in sets} == {"good", "better", "best"}


def test_chiller_lockout_and_sat_patch(tmp_path: Path):
    proto = ROOT / "examples" / "prototypes" / "5ZoneAirCooled.idf"
    assert proto.is_file()
    out1 = tmp_path / "lockout.idf"
    meta = apply_chiller_lockout(proto, out1, oat_lockout_f=55.0)
    assert meta["ok"] is True
    assert meta["managers_patched"] >= 1
    text = out1.read_text(encoding="utf-8")
    assert "12.8" in text  # 55F → 12.8C
    out2 = tmp_path / "sat.idf"
    meta2 = apply_sat_reset(out1, out2)
    assert meta2["ok"] is True
    assert "18.0" in out2.read_text(encoding="utf-8")


def test_vibe19_bridge_suggests_measures(tmp_path: Path):
    # Minimal fdd_summary
    fdd = tmp_path / "fdd_summary.csv"
    with fdd.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "rule_id",
                "equipment_id",
                "equipment_type",
                "status",
                "applicable",
                "fault_hours",
                "fault_pct",
                "notes",
            ],
        )
        w.writeheader()
        w.writerow(
            {
                "rule_id": "SCHED-247",
                "equipment_id": "AHU-1",
                "equipment_type": "ahu",
                "status": "FAULT",
                "applicable": "true",
                "fault_hours": 5000,
                "fault_pct": 95,
                "notes": "always on",
            }
        )
        w.writerow(
            {
                "rule_id": "AHU-DUCTHI",
                "equipment_id": "AHU-1",
                "equipment_type": "ahu",
                "status": "FAULT",
                "applicable": "true",
                "fault_hours": 800,
                "fault_pct": 20,
                "notes": "",
            }
        )
        w.writerow(
            {
                "rule_id": "MECH-OAT-1",
                "equipment_id": "CH-1",
                "equipment_type": "chiller",
                "status": "FAULT",
                "applicable": "true",
                "fault_hours": 400,
                "fault_pct": 10,
                "notes": "",
            }
        )
    econ = tmp_path / "economizer_weather.csv"
    with econ.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "equipment_id",
                "prohibited_mech_hours_below_60f",
                "opportunity_hours",
            ],
        )
        w.writeheader()
        w.writerow(
            {
                "equipment_id": "AHU-1",
                "prohibited_mech_hours_below_60f": 250,
                "opportunity_hours": 1000,
            }
        )

    bridge = suggest_from_bundle(tmp_path)
    ids = set(bridge["measure_ids"])
    assert "ECM-AHU-SCHED-ALIGN" in ids
    assert "ECM-GL36-AIRSIDE" in ids
    assert "ECM-CHILLER-LOCKOUT" in ids
    assert bridge["stats"]["prohibited_mech_hours_below_60f"] == 250

    profile = resolve_profile({"building_type": "office", "city": "chicago"})
    merged = merge_into_profile(profile, bridge)
    assert merged["field_sources"]["measures"]["source"] == "vibe19"
    assert len(merged["measures"]) >= 3


def test_savings_by_measure_progressive():
    records = [
        {
            "measure_id": None,
            "annual": {
                "electricity_kwh_year": 100000,
                "natural_gas_therm_year": 1000,
                "site_eui_kbtu_ft2_year": 80,
                "utility_cost_usd_year": 12800,
            },
        },
        {
            "measure_id": "ECM-AHU-SCHED-ALIGN",
            "annual": {
                "electricity_kwh_year": 80000,
                "natural_gas_therm_year": 900,
                "site_eui_kbtu_ft2_year": 65,
                "utility_cost_usd_year": 10320,
            },
        },
        {
            "measure_id": "ECM-GL36-AIRSIDE",
            "annual": {
                "electricity_kwh_year": 70000,
                "natural_gas_therm_year": 850,
                "site_eui_kbtu_ft2_year": 58,
                "utility_cost_usd_year": 9080,
            },
        },
    ]
    rows = savings_by_measure(records)
    assert rows[0]["measure_id"] == "baseline"
    assert rows[1]["vs_baseline"]["kwh_saved"] == 20000
    assert rows[2]["vs_previous"]["kwh_saved"] == 10000
    assert rows[2]["vs_baseline"]["kwh_pct"] == 30.0
