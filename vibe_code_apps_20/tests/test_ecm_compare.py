"""ECM compare contract + Liberty-shaped IDF patches."""

from __future__ import annotations

import json
from pathlib import Path

from wattlab.ecm.compare import (
    build_compare_from_cascade,
    empty_compare_stub,
    merge_full_parity_ss,
)
from wattlab.energyplus.patches.chiller_lockout import apply_chiller_lockout
from wattlab.energyplus.patches.dsp_reset import apply_dsp_reset
from wattlab.energyplus.patches.sat_reset import apply_sat_reset


def test_empty_compare_stub_has_pending_spreadsheet():
    stub = empty_compare_stub(twin_run="geo_test")
    assert stub["schema"] == "wattlab_ecm_compare_v1"
    assert stub["spreadsheet"]["status"] == "pending_external"
    assert all(m["ss_kwh"] is None for m in stub["measures"])
    assert len(stub["measures"]) == 3


def test_merge_full_parity_ss_accepts_agent_rows(tmp_path: Path):
    """BUG-ECM-015: agent writer uses top-level rows + annual_usd."""
    reports = tmp_path / "reports"
    reports.mkdir()
    parity = {
        "workbook": "ECM_FULL_PARITY.xlsx",
        "rows": [
            {
                "measure_id": "ECM-ECON-REPAIR",
                "sheet_kwh": 1000.0,
                "eplus_kwh": 900.0,
                "ss_kwh": 1000.0,
                "ep_kwh": 900.0,
                "annual_usd": 120.0,
                "status": "BALLPARK",
            },
            {
                "measure_id": "ECM-AHU-ERV",
                "sheet_kwh": 29848.0,
                "ss_kwh": 29848.0,
                "annual_usd": 3581.0,
                "status": "BALLPARK",
            },
        ],
    }
    (reports / "ecm_full_parity_compare.json").write_text(
        json.dumps(parity), encoding="utf-8"
    )
    payload = empty_compare_stub(
        measure_ids=["ECM-ECON-REPAIR", "ECM-AHU-ERV", "ECM-DSP-RESET"]
    )
    merge_full_parity_ss(payload, reports)
    by_mid = {m["measure_id"]: m for m in payload["measures"]}
    assert by_mid["ECM-ECON-REPAIR"]["ss_kwh"] == 1000.0
    assert by_mid["ECM-ECON-REPAIR"]["ss_usd"] == 120.0
    assert by_mid["ECM-AHU-ERV"]["ss_kwh"] == 29848.0
    assert by_mid["ECM-AHU-ERV"]["ss_usd"] == 3581.0
    assert payload["spreadsheet"]["status"] == "full_parity"
    assert by_mid["ECM-DSP-RESET"]["ss_kwh"] is None


def test_build_compare_from_cascade_fills_ep():
    report = {
        "twin_run": "geo_test",
        "savings_by_measure": [
            {
                "measure_id": "ECM-DSP-RESET",
                "vs_baseline": {"kwh_saved": 1000.0, "therms_saved": 0.0, "cost_saved_usd": 120.0},
            }
        ],
        "weather_suitability": {"mode": "SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY"},
    }
    cmp = build_compare_from_cascade(
        report,
        measure_ids=["ECM-DSP-RESET"],
        twin_run="geo_test",
        profile={"conditioned_floor_area_ft2": 100_000, "utility": {"elec_usd_per_kwh": 0.12}},
    )
    row = cmp["measures"][0]
    assert row["ep_kwh"] == 1000.0
    assert row["ss_kwh"] is None
    assert row["capital_usd"] is not None
    assert row["payback_yr_ep"] is not None


def test_liberty_patches_ok(tmp_path: Path):
    """Minimal IDF fragments matching Liberty Twin field layouts."""
    idf = tmp_path / "model.idf"
    idf.write_text(
        """
Fan:VariableVolume,
  VAV Sys 1 Supply Fan,
  FanAvailSched,
  0.7,
  600,                                                     !- Pressure Rise {Pa}
  autosize,
  Fraction,
  0.25,
  ,
  0.9,
  1,
  0.35,
  0.30,
  -0.54,
  0.87,
  0.000;

AvailabilityManager:LowTemperatureTurnOff,               !- Availability Manager Object Type
  Chilled Water Loop Availability Low Temp Off;            !- Availability Manager Name

AvailabilityManager:LowTemperatureTurnOff,
  Chilled Water Loop Availability Low Temp Off,            !- Name
  Chilled Water Loop Outside Air Sensor,                   !- Sensor Node Name
  7.22;                                                    !- Temperature

SetpointManager:Scheduled,
  VAV Sys 1 Cooling Supply Air Temp Manager,               !- Name
  Temperature,                                             !- Control Variable
  HVACTemplate-Always 12.8,                                !- Schedule Name
  VAV Sys 1 Supply Fan Outlet;

SetpointManager:Scheduled,
  VAV Sys 2 Cooling Supply Air Temp Manager,               !- Name
  Temperature,                                             !- Control Variable
  HVACTemplate-Always 12.8,                                !- Schedule Name
  VAV Sys 2 Supply Fan Outlet;

SetpointManager:Scheduled,
  VAV Sys 1 Heating Supply Air Temp Manager,               !- Name
  Temperature,                                             !- Control Variable
  Winter Dump DAT,                                         !- Schedule Name
  VAV Sys 1 Supply Fan Outlet;

SetpointManager:Scheduled,
  VAV Sys 2 Heating Supply Air Temp Manager,               !- Name
  Temperature,                                             !- Control Variable
  Winter Dump DAT,                                         !- Schedule Name
  VAV Sys 2 Supply Fan Outlet;
""",
        encoding="utf-8",
    )
    dsp = apply_dsp_reset(idf, tmp_path / "dsp.idf", fan_pressure_pa=450.0)
    assert dsp["ok"] and dsp["fans_patched"] == 1
    assert "450.0" in (tmp_path / "dsp.idf").read_text()

    sat = apply_sat_reset(idf, tmp_path / "sat.idf")
    assert sat["ok"], sat
    sat_txt = (tmp_path / "sat.idf").read_text()
    assert "WattLab SAT Reset Cooling" in sat_txt
    assert sat["mode"] == "liberty_cooling_spms"
    assert sat["managers_patched"] == 2
    assert sat_txt.count("WattLab SAT Reset Cooling,") == 3
    assert "Through: 3/31,\n  For: AllDays,\n  Until: 24:00,12.8," in sat_txt
    assert "Through: 9/30,\n  For: AllDays,\n  Until: 24:00,14.0," in sat_txt
    assert "Winter Dump DAT" in sat_txt

    lock = apply_chiller_lockout(idf, tmp_path / "lock.idf", oat_lockout_f=60.0)
    assert lock["ok"] and lock["managers_patched"] == 1
    assert "15.6" in (tmp_path / "lock.idf").read_text()
