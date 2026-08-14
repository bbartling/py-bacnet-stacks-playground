"""Site Config JSON + staged people/HVAC/setpoint patches."""
from __future__ import annotations

from pathlib import Path

from eplus_gym_app.site_config import (
    default_site_dsm_config,
    load_site_dsm_config,
    normalize_occupancy_schedule,
    normalize_site_dsm_config,
    optimum_start_lead_hours,
    save_site_dsm_config,
    setpoints_summary,
    site_config_feedback_rows,
    validate_setpoints_f,
)
from eplus_native.schedule_calendar_repair import (
    _f_to_c,
    apply_site_people_hvac_schedules,
    apply_site_setpoints,
)


def _stub_schedule(name: str) -> str:
    return (
        f"Schedule:Compact,\n"
        f"    {name},\n"
        f"    Fraction,\n"
        f"    Through: 12/31,\n"
        f"    For: AllDays,\n"
        f"    Until: 24:00,\n"
        f"    1;\n"
    )


def test_site_config_round_trip(tmp_path: Path):
    cfg = default_site_dsm_config()
    cfg["setpoints_f"]["occupied_heating_f"] = 68.0
    cfg["peak_day_override"] = "2026-01-26"
    cfg["optimum_start"] = True
    path = save_site_dsm_config(tmp_path, cfg)
    assert path.is_file()
    loaded = load_site_dsm_config(tmp_path)
    assert loaded["setpoints_f"]["occupied_heating_f"] == 68.0
    assert loaded["peak_day_override"] == "2026-01-26"
    assert loaded["apply_people_plug_schedules"] is True
    assert loaded["apply_hvac_schedules"] is True
    assert loaded["optimum_start"] is True
    assert "people_start" in loaded["occupancy_schedule"]["days"]["mon"]
    assert "hvac_start" in loaded["occupancy_schedule"]["days"]["mon"]
    assert "occ heat" in setpoints_summary(loaded)


def test_migrate_legacy_start_end_to_people():
    raw = {
        "days": {
            "mon": {"occupied": True, "start": "07:00", "end": "16:00"},
        }
    }
    days = normalize_occupancy_schedule(raw)["days"]
    assert days["mon"]["people_start"] == "07:00"
    assert days["mon"]["people_end"] == "16:00"
    assert days["mon"]["hvac_start"] == "06:15"  # 45 min earlier
    assert days["mon"]["hvac_end"] == "16:30"  # 30 min later


def test_optimum_start_lead_math():
    cfg = default_site_dsm_config()
    cfg["optimum_start"] = True
    cfg["setpoints_f"]["occupied_heating_f"] = 70.0
    cfg["setpoints_f"]["unoccupied_heating_f"] = 60.0  # 10 F deadband
    cfg["optimum_start_f_per_min"] = 0.10
    cfg["optimum_start_max_h"] = 4.0
    # 10 / (0.10 * 60) = 1.666... h
    lead = optimum_start_lead_hours(cfg)
    assert abs(lead - (10.0 / 6.0)) < 1e-6
    cfg["setpoints_f"]["unoccupied_heating_f"] = 40.0  # 30 F -> would be 5 h, capped 4
    assert optimum_start_lead_hours(cfg) == 4.0
    cfg["optimum_start"] = False
    assert optimum_start_lead_hours(cfg) == 0.0


def test_validate_setpoints_rejects_inverted():
    errs = validate_setpoints_f(
        {
            "occupied_heating_f": 76.0,
            "unoccupied_heating_f": 65.0,
            "occupied_cooling_f": 75.0,
            "unoccupied_cooling_f": 85.0,
        }
    )
    assert errs


def test_apply_site_setpoints_writes_htg_and_clg():
    stub = "Building,\n    X,\n    0.0;\n"
    out = apply_site_setpoints(
        stub,
        {
            "setpoints_f": {
                "occupied_heating_f": 70.0,
                "unoccupied_heating_f": 60.0,
                "occupied_cooling_f": 76.0,
                "unoccupied_cooling_f": 88.0,
            }
        },
    )
    assert "SCH_HtgSP" in out
    assert "SCH_ClgSP" in out
    assert f"{_f_to_c(70.0):.2f}" in out
    assert f"{_f_to_c(76.0):.2f}" in out
    assert f"{_f_to_c(60.0):.2f}" in out
    assert f"{_f_to_c(88.0):.2f}" in out


def test_apply_people_hvac_schedules_and_opt_start_lead():
    stub = (
        "Building,\n    X,\n    0;\n"
        + _stub_schedule("SCH_Occ_Class")
        + _stub_schedule("SCH_Equip")
        + _stub_schedule("SCH_HeatAvail")
        + _stub_schedule("SCH_FanProxy")
    )
    cfg = normalize_site_dsm_config(
        {
            "apply_people_plug_schedules": True,
            "apply_hvac_schedules": True,
            "optimum_start": True,
            "optimum_start_f_per_min": 0.10,
            "optimum_start_max_h": 4.0,
            "setpoints_f": {
                "occupied_heating_f": 70.0,
                "unoccupied_heating_f": 60.0,
            },
            "occupancy_schedule": {
                "days": {
                    "mon": {
                        "occupied": True,
                        "people_start": "06:45",
                        "people_end": "15:30",
                        "hvac_start": "06:00",
                        "hvac_end": "16:00",
                    }
                }
            },
        }
    )
    out, report = apply_site_people_hvac_schedules(stub, cfg)
    assert any(a["schedule"] == "SCH_Occ_Class" for a in report["applied"])
    assert any(a["schedule"] == "SCH_HeatAvail" for a in report["applied"])
    assert any(a.get("kind") == "hvac_heat_always_on" for a in report["applied"])
    assert any(a["schedule"] == "SCH_FanProxy" for a in report["applied"])
    assert "Until: 06:45" in out
    assert "Until: 15:30" in out
    # 10 F / 6 = 1.666 h ≈ 100 min → people 06:45 - 100 min = 05:05 on FanProxy
    assert abs(report["optimum_start_lead_h"] - (10.0 / 6.0)) < 1e-6
    assert "Until: 05:05" in out
    # HeatAvail stays always-on for WAHP unocc SP hold
    assert "For: AllDays" in out
    assert "SCH_FanProxy" in out


def test_stage_idf_applies_site_config(tmp_path: Path):
    from eplus_gym_app.dsm_console import stage_idf_for_period

    src = tmp_path / "champ.idf"
    src.write_text(
        "RunPeriod,\n    Annual,\n    1,1,2026,12,31,2026;\nBuilding,\n    X,\n    0;\n"
        + _stub_schedule("SCH_Occ_Class")
        + _stub_schedule("SCH_HeatAvail")
        + _stub_schedule("SCH_FanProxy"),
        encoding="utf-8",
    )
    save_site_dsm_config(
        tmp_path,
        {
            "setpoints_f": {
                "occupied_heating_f": 71.0,
                "unoccupied_heating_f": 62.0,
                "occupied_cooling_f": 74.0,
                "unoccupied_cooling_f": 86.0,
            },
            "apply_people_plug_schedules": True,
            "apply_hvac_schedules": True,
            "occupancy_schedule": {
                "days": {
                    "tue": {
                        "occupied": True,
                        "people_start": "07:15",
                        "people_end": "14:00",
                        "hvac_start": "06:30",
                        "hvac_end": "15:00",
                    }
                }
            },
        },
    )
    dest = tmp_path / "staged.idf"
    stage_idf_for_period(src, dest, "2026-01-26", "2026-01-26", site_root=tmp_path)
    text = dest.read_text(encoding="utf-8")
    assert "SCH_HtgSP" in text
    assert "SCH_ClgSP" in text
    assert "Until: 07:15" in text
    # HeatAvail always-on; FanProxy gets HVAC window
    assert "Until: 06:30" in text
    assert src.read_text(encoding="utf-8").count("SCH_HtgSP") == 0
    assert "Until: 07:15" not in src.read_text(encoding="utf-8")
    report_path = tmp_path / "reports" / "eplus_gym" / "site_config_apply_report.json"
    assert report_path.is_file()


def test_feedback_rows_include_people_hvac():
    cfg = default_site_dsm_config()
    cfg["optimum_start"] = True
    rows = site_config_feedback_rows(cfg)
    blob = " ".join(r["field"] for r in rows)
    assert "people" in blob.lower() or any("People" in r["field"] for r in rows)
    assert any("HVAC" in r["field"] for r in rows)
    assert any("optimum_start" in r["field"] for r in rows)
