"""Unit tests for school calendar contract + IdealLoads schedule repair (no E+ binary)."""
from __future__ import annotations

import json
from pathlib import Path

from eplus_native.idf_inspect import inspect_idf
from eplus_native.schedule_calendar_repair import (
    apply_schedule_calendar_repair,
    load_calendar_contract,
)

_ROOT = Path(__file__).resolve().parents[1]
_PINNED = _ROOT / "models" / "eplus" / "lakeside_6zone_gshp_best.idf"
_CAL = _ROOT / "contracts" / "eplus_school_calendar_v1.json"


def test_calendar_contract_shape():
    cal = load_calendar_contract(_CAL)
    assert cal["contract_version"] == "eplus_school_calendar_v1"
    assert cal["timezone"] == "America/Chicago"
    assert cal["never_fit_calendar_to_facility_kw"] is True
    assert cal["heating_capacity_mmbtu_h_variants"] == [2.3, 2.7, 3.2]
    assert len(cal["ground_temperature_building_surface_c"]["jan_dec_c"]) == 12


def test_repair_separates_heat_avail_from_oa_and_bounds_capacity():
    text = _PINNED.read_text(encoding="utf-8", errors="replace")
    repaired = apply_schedule_calendar_repair(text, heating_capacity_mmbtu_h=2.7)
    facts = inspect_idf(_write_tmp(repaired))
    assert facts.sch_hvac is not None
    # Heating availability must not be the old weekend-off SCH_HVAC pattern on IdealLoads
    for il in facts.ideal_loads:
        assert il.heating_availability == "SCH_HeatAvail"
        assert il.availability == "SCH_SysAvail"
        assert il.cooling_availability == "SCH_CoolAvail"
        assert il.heating_limit.lower() == "limitcapacity"
    assert facts.has_ground_temp_building_surface
    assert "SCH_OA" in repaired
    assert "SCH_HeatAvail" in repaired
    assert "Site:GroundTemperature:BuildingSurface" in repaired


def _write_tmp(text: str) -> Path:
    import tempfile

    p = Path(tempfile.mkdtemp()) / "repaired.idf"
    p.write_text(text, encoding="utf-8")
    return p


def test_nine_to_six_contract():
    path = _ROOT / "contracts" / "eplus_nine_to_six_zone_agg_v1.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["contract_version"] == "eplus_nine_to_six_zone_agg_v1"
    assert "1F_Library_IMC" in data["aggregation"]["1F_Area_A"]["members"]
    assert "1F_Cafe_Kitchen" in data["aggregation"]["1F_Area_C"]["members"]
    assert "1F_Gym" in data["aggregation"]["1F_Area_D"]["members"]
