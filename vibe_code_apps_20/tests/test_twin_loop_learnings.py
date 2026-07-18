"""Regression tests from the live Liberty twin-loop rehearsal (2026-07-18).

Each test pins a defect found while actually running EnergyPlus 26.1 in the
energyplus-mcp-dev Docker image against the Liberty Building 100 pretend
project (scripts/agent_twin_demo.py):

1. E+ prototype savings were compared raw against proxies sized for the real
   building (5k ft2 vs 140k ft2 -> ~28x mismatch) — area_scale fixes that.
2. Result records dropped ``building_area_m2`` so the scale could never be
   computed downstream.
3. The 5ZoneAirCooled prototype only requests MeterFileOnly meters, so
   eplustbl has no monthly BUILDING ENERGY PERFORMANCE tables and the G14
   bill gate silently never ran — the monthly-meter patch plus the .mtr
   fallback parser fix that.
4. Detroit (the Liberty campus city) was missing from the city registry.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wattlab.crosscheck import crosscheck_measure, crosscheck_report, prototype_area_scale
from wattlab.energyplus.patches import apply_monthly_energy_tables
from wattlab.energyplus.results import build_result_record, parse_monthly_from_mtr


# ---------------------------------------------------------------------------
# 1) area scale math + scaled crosscheck verdicts
# ---------------------------------------------------------------------------

def test_prototype_area_scale_liberty_numbers():
    # 5ZoneAirCooled conditioned area is 927.2 m2 (~9,980 ft2);
    # Liberty 100 is 140,000 ft2 -> scale ~14.03 (observed live: x14.028).
    scale = prototype_area_scale(target_ft2=140_000.0, model_area_m2=927.2)
    assert scale == pytest.approx(14.028, abs=0.01)


def test_prototype_area_scale_none_when_unknown():
    assert prototype_area_scale(target_ft2=None, model_area_m2=927.2) is None
    assert prototype_area_scale(target_ft2=140_000.0, model_area_m2=None) is None
    assert prototype_area_scale(target_ft2=140_000.0, model_area_m2=0.0) is None


def test_crosscheck_measure_scaled_ratio_changes_verdict():
    # Raw 7,330 kWh vs 777k proxy is ratio 0.009 (investigate); with the
    # x14 area scale it becomes ~0.13 — still investigate, but the record
    # must carry the scaled values so the human sees the honest comparison.
    out = crosscheck_measure(
        measure_id="ECM-AHU-SCHED-ALIGN",
        ep_savings_kwh=7330.55,
        proxy_savings_kwh=777268.4,
        area_scale=14.028,
    )
    assert out["area_scale"] == 14.028
    assert out["ep_savings_kwh_scaled"] == pytest.approx(102833.0, abs=5.0)
    assert out["agreement_ratio"] == pytest.approx(0.132, abs=0.005)
    assert out["verdict"] == "investigate"

    # Same measure where the scaled savings land inside the band -> in_line.
    ok = crosscheck_measure(
        measure_id="M",
        ep_savings_kwh=10_000.0,
        proxy_savings_kwh=100_000.0,
        area_scale=14.0,
    )
    assert ok["verdict"] == "in_line"
    assert ok["agreement_ratio"] == pytest.approx(1.4)


def test_crosscheck_report_scales_g14_modeled_series():
    savings = [{
        "measure_id": "M1",
        "vs_previous": {"kwh_saved": 100.0, "therms_saved": 0.0},
    }]
    proxies = {"M1": {"savings_kwh": 1400.0}}
    bills = [1400.0] * 12
    modeled = [100.0] * 12  # prototype-sized; x14 makes it match the bills
    rep = crosscheck_report(
        savings, proxies,
        bills_monthly_kwh=bills, baseline_monthly_kwh=modeled,
        area_scale=14.0,
    )
    assert rep["measures"][0]["verdict"] == "in_line"
    assert rep["g14"]["area_scale_applied"] == 14.0
    assert rep["g14"]["calibrated"] is True
    assert rep["g14"]["nmbe_percent"] == 0.0


# ---------------------------------------------------------------------------
# 2) result records keep the model area
# ---------------------------------------------------------------------------

def test_build_result_record_carries_building_area(tmp_path: Path):
    idf = tmp_path / "m.idf"
    idf.write_text("Version,26.1;", encoding="utf-8")
    rec = build_result_record(
        run_id="r1",
        measure_id=None,
        idf_path=idf,
        annual={
            "electricity_kwh_year": 48433.0,
            "building_area_m2": 927.2,
            "status": "COMPLETE",
        },
    )
    assert rec["annual"]["building_area_m2"] == 927.2


# ---------------------------------------------------------------------------
# 3) monthly meters patch + .mtr fallback parser
# ---------------------------------------------------------------------------

def test_apply_monthly_energy_tables_adds_and_is_idempotent(tmp_path: Path):
    src = tmp_path / "proto.idf"
    src.write_text(
        "Version,26.1;\n"
        "Output:Meter:MeterFileOnly,Electricity:Facility,monthly;\n",
        encoding="utf-8",
    )
    once = tmp_path / "once.idf"
    meta = apply_monthly_energy_tables(src, once)
    text = once.read_text(encoding="utf-8")
    # MeterFileOnly does NOT count — the real Output:Meter must be added.
    assert "Output:Meter,Electricity:Facility,Monthly;" in text
    assert "Output:Meter,NaturalGas:Facility,Monthly;" in text
    assert len(meta["added"]) == 2

    twice = tmp_path / "twice.idf"
    meta2 = apply_monthly_energy_tables(once, twice)
    assert meta2["added"] == []
    assert twice.read_text(encoding="utf-8").count(
        "Output:Meter,Electricity:Facility,Monthly;"
    ) == 1


MTR_FIXTURE = """Program Version,EnergyPlus, Version 26.1.0-6f2e40d102, YMD=2026.07.18 14:51
1,5,Environment Title[],Latitude[deg],Longitude[deg],Time Zone[],Elevation[m]
4,2,Cumulative Days of Simulation[],Month[]  ! When Monthly Meters Requested
12,9,Electricity:Facility [J] !Monthly [Value,Min,Day,Hour,Minute,Max,Day,Hour,Minute]
1274,9,NaturalGas:Facility [J] !Monthly [Value,Min,Day,Hour,Minute,Max,Day,Hour,Minute]
24,9,Electricity:Building [J] !Monthly [Value,Min,Day,Hour,Minute,Max,Day,Hour,Minute]
End of Data Dictionary
1,RUN PERIOD 1,  41.98, -87.92,  -6.00, 201.00
4,31, 1
12,12396100000.0,1.0,1,1,15,2.0,2,2,30
1274,15367600000.0,1.0,1,1,15,2.0,2,2,30
24,9000000000.0,1.0,1,1,15,2.0,2,2,30
4,59, 2
12,11078200000.0,1.0,1,1,15,2.0,2,2,30
1274,12152000000.0,1.0,1,1,15,2.0,2,2,30
End of Data
"""


def test_parse_monthly_from_mtr_fixture(tmp_path: Path):
    p = tmp_path / "eplusout.mtr"
    p.write_text(MTR_FIXTURE, encoding="utf-8")
    rows = parse_monthly_from_mtr(p)
    assert [r["month"] for r in rows] == [1, 2]
    jan = rows[0]
    assert jan["month_name"] == "January"
    # 12.3961 GJ -> 3443.36 kWh (matches the live baseline run exactly)
    assert jan["electricity_kwh"] == pytest.approx(3443.36, abs=0.01)
    assert jan["natural_gas_therm"] == pytest.approx(145.69, abs=0.01)
    # Electricity:Building (id 24) is not a wanted facility meter — ignored.
    feb = rows[1]
    assert feb["electricity_kwh"] == pytest.approx(3077.28, abs=0.01)


def test_parse_monthly_from_mtr_missing_file(tmp_path: Path):
    assert parse_monthly_from_mtr(tmp_path / "nope.mtr") == []


# ---------------------------------------------------------------------------
# 4) Detroit is a first-class city for the Liberty campus
# ---------------------------------------------------------------------------

def test_detroit_city_resolves_with_liberty_alias():
    from wattlab.defaults import resolve_city, resolve_profile

    cid, meta = resolve_city("detroit")
    assert cid == "detroit"
    assert meta["climate_zone"] == "5A"
    # "liberty" alias routes the campus straight to the right climate.
    cid2, _ = resolve_city("liberty")
    assert cid2 == "detroit"

    profile = resolve_profile({
        "building_type": "office",
        "city": "detroit",
        "floor_area_ft2": 140_000,
    })
    assert profile["climate_city"] == "Detroit, MI"
    assert profile["conditioned_floor_area_ft2"] == 140_000.0
    # Substitute EPW must be flagged, never silent.
    assert "approximated" in profile["energyplus"]["epw_note"]
