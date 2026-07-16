"""Unit tests for in-app energy wizard (defaults, schedules, quick savings, export)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.energy_wizard import (
    attach_quick_estimates,
    default_schedules_for_archetype,
    estimate_gl36_trim_respond,
    estimate_mech_cool_lockout,
    estimate_runtime_reduction,
    form_options,
    resolve_building_type,
    resolve_code,
    resolve_profile,
    schedules_from_inference,
    suggest_measures_from_fdd,
    write_energy_model_package,
)


def test_form_options_self_contained():
    opts = form_options()
    assert opts["building_types"]
    assert opts["cities"]
    assert opts["codes"]
    assert any(t["id"] == "office" for t in opts["building_types"])
    assert opts["default_city"]
    assert opts["default_code"]


def test_resolve_profile_responsive_defaults():
    p = resolve_profile({"building_type": "office", "city": "chicago", "code_year": "iecc_2018"})
    assert p["building_type"] == "office"
    assert p["climate_zone"] == "5A"
    assert p["conditioned_floor_area_ft2"] == 50000
    assert p["field_sources"]["building_type"]["source"] == "user"
    assert p["field_sources"]["floor_area_ft2"]["source"] == "default"
    assert "roof_u" in p["envelope"]
    assert p["loads"]["lpd_w_per_ft2"] > 0


def test_resolve_profile_user_overrides():
    p = resolve_profile(
        {
            "building_type": "school",
            "city": "madison",
            "floor_area_ft2": 120000,
            "floors": 4,
            "hvac": {"fuel": "electric", "airside": "psz_ac", "plant": "dx"},
            "utility": {"elec_usd_per_kwh": 0.12, "gas_usd_per_therm": 0.8},
        }
    )
    assert p["conditioned_floor_area_ft2"] == 120000
    assert p["number_of_floors"] == 4
    assert p["hvac"]["fuel"] == "electric"
    assert p["utility"]["elec_usd_per_kwh"] == 0.12
    assert p["field_sources"]["floor_area_ft2"]["source"] == "user"


def test_code_and_type_aliases():
    cid, meta = resolve_code("IECC 2018")
    assert cid == "iecc_2018"
    assert "envelope" in meta
    bid, arch = resolve_building_type("K-12")
    assert bid in {"school", "school_primary"}
    assert arch.get("label")


def test_schedules_from_inference_prefills_hours():
    payload = {
        "equipment": {
            "AHU_1": {
                "equipment_type": "AHU",
                "signal": "fan-status",
                "weekday_start_hour": 6,
                "weekday_stop_hour": 19,
                "weekend_start_hour": 0,
                "weekend_stop_hour": 0,
                "likely_always_on": False,
            }
        }
    }
    sched = schedules_from_inference(payload)
    assert sched["from_inference"] is True
    assert sched["weekday_start_hour"] == 6
    assert sched["weekday_stop_hour"] == 19
    assert sched["weekday"]["occupancy"][6] == 1.0
    assert sched["weekday"]["occupancy"][5] == 0.0


def test_default_schedules_fallback():
    _, arch = resolve_building_type("office")
    sched = default_schedules_for_archetype(arch)
    assert len(sched["weekday"]["occupancy"]) == 24
    assert sched["from_inference"] is False


def test_quick_savings_estimators():
    rt = estimate_runtime_reduction(fan_run_hours=2000, data_span_hours=2000, fan_kw=10, proposed_daily_hours=11)
    assert rt["status"] == "ok"
    assert rt["kwh_savings"] >= 0
    gl = estimate_gl36_trim_respond(duct_static_mean_iwc=1.5, proposed_static_iwc=0.75, fan_kw=10, annual_fan_hours=3000)
    assert gl["status"] == "ok"
    assert gl["kwh_savings"] > 0
    mc = estimate_mech_cool_lockout(prohibited_hours=100, data_span_hours=2000, plant_kw=40)
    assert mc["status"] == "ok"
    assert mc["kwh_savings"] > 0


def test_suggest_measures_and_attach_estimates():
    class _R:
        def __init__(self, rid, status):
            self.rule_id = rid
            self.status = status

    measures = suggest_measures_from_fdd(
        batch_results=[_R("SCHED-247", "FAULT"), _R("MECH-OAT-1", "FAULT")],
        measure_set="best",
    )
    ids = {m["measure_id"] for m in measures}
    assert "ECM-AHU-SCHED-ALIGN" in ids
    assert "ECM-CHILLER-LOCKOUT" in ids
    assert "ECM-GL36-AIRSIDE" in ids  # from best set
    enriched = attach_quick_estimates(
        measures,
        fan_run_hours=1500,
        data_span_hours=2000,
        prohibited_mech_hours=80,
        duct_static_mean_iwc=1.2,
    )
    assert any((m.get("quick_estimate") or {}).get("status") == "ok" for m in enriched)


def test_write_energy_model_package(tmp_path: Path):
    profile = resolve_profile({"building_type": "office", "city": "chicago"})
    measures = suggest_measures_from_fdd(measure_set="good")
    zpath = write_energy_model_package(
        tmp_path / "pkg",
        profile=profile,
        schedules=default_schedules_for_archetype(),
        measures=measures,
        schedule_inference={"equipment": {}},
        operating_signatures=pd.DataFrame(
            [{"equipment_id": "AHU_1", "kind": "fan", "bin_label": "60-65", "on_fraction": 0.5}]
        ),
        quick_savings_summary={"total_kwh": 1000},
    )
    assert zpath.is_file()
    assert (tmp_path / "pkg" / "building_profile.json").is_file()
    assert (tmp_path / "pkg" / "ecm_briefs.json").is_file()
    assert (tmp_path / "pkg" / "README.md").is_file()
