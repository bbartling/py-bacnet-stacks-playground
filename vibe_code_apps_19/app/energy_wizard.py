"""OpenFDD WattLab energy wizard — responsive defaults, schedule/ECM prefill, quick savings.

Self-contained inside vibe19 (no vibe20 required). EnergyPlus simulation remains an
optional external step (sidecar or outside AI agent + EnergyPlus-MCP).
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import zipfile
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd

DEFAULTS_DIR = Path(__file__).resolve().parents[1] / "configs" / "energy_defaults"
PRODUCT = "OpenFDD WattLab"
DISCLAIMER = (
    "This is a conceptual, uncalibrated screening model. "
    "It is not a design load calculation, code-compliance model, "
    "calibrated energy model, or representation of a specific property. "
    "EnergyPlus autosizes HVAC capacities so fan/plant sizing records are not required."
)
DEFAULT_ELEC = 0.09
DEFAULT_GAS = 0.693


def _load_json(name: str) -> dict[str, Any]:
    return json.loads((DEFAULTS_DIR / name).read_text(encoding="utf-8"))


def load_archetypes() -> dict[str, Any]:
    return _load_json("archetypes.json")


def load_climate() -> dict[str, Any]:
    return _load_json("climate.json")


def load_codes() -> dict[str, Any]:
    return _load_json("codes.json")


def load_measures() -> dict[str, Any]:
    return _load_json("measures.json")


def _norm(s: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_")


def _tagged(value: Any, source: str, *, note: str | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"value": value, "source": source}
    if note:
        out["note"] = note
    return out


def resolve_building_type(raw: str | None, archetypes: dict | None = None) -> tuple[str, dict]:
    arch = archetypes or load_archetypes()
    key = _norm(raw) or "office"
    aliases = {
        "office": "office",
        "medium_office": "office",
        "office_medium": "office",
        "small_office": "office_small",
        "office_small": "office_small",
        "large_office": "office_large",
        "office_large": "office_large",
        "multistory_office": "multistory_office",
        "warehouse": "warehouse",
        "school": "school",
        "school_primary": "school_primary",
        "k12": "school",
        "k_12": "school",
        "retail": "retail",
        "multifamily": "multifamily",
        "parking": "parking_garage",
        "parking_garage": "parking_garage",
    }
    resolved = aliases.get(key, key if key in arch else "office")
    entry = deepcopy(arch[resolved])
    if entry.get("extends"):
        base = deepcopy(arch[entry["extends"]])
        base.update({k: v for k, v in entry.items() if k != "extends"})
        entry = base
    entry["archetype_id"] = resolved
    return resolved, entry


def resolve_city(raw: str | None, climate: dict | None = None) -> tuple[str, dict]:
    clim = climate or load_climate()
    cities = clim.get("cities") or {}
    key = _norm(raw) or clim.get("default_city") or "chicago"
    if key in cities:
        return key, deepcopy(cities[key])
    for cid, meta in cities.items():
        aliases = [_norm(a) for a in (meta.get("aliases") or [])]
        label = _norm(meta.get("label"))
        if key in aliases or key == label or key in label:
            return cid, deepcopy(meta)
    fb = clim.get("default_city") or "chicago"
    return fb, deepcopy(cities[fb])


def resolve_code(raw: str | None, codes: dict | None = None) -> tuple[str, dict]:
    catalog = codes or load_codes()
    code_map = catalog.get("codes") or {}
    key = _norm(raw) or catalog.get("default_code") or "iecc_2018"
    for cid, meta in code_map.items():
        if _norm(cid) == key or _norm(meta.get("label")) == key:
            return cid, deepcopy(meta)
        for a in meta.get("aliases") or []:
            if _norm(a) == key or key in _norm(a):
                return cid, deepcopy(meta)
    m = re.search(r"(2004|2013|2018|2019|2021)", key)
    if m:
        year = m.group(1)
        year_map = {
            "2004": "ashrae_90.1_2004",
            "2013": "ashrae_90.1_2013",
            "2018": "iecc_2018",
            "2019": "ashrae_90.1_2019",
            "2021": "iecc_2021",
        }
        cid = year_map[year]
        if cid in code_map:
            return cid, deepcopy(code_map[cid])
    default = catalog.get("default_code") or "iecc_2018"
    return default, deepcopy(code_map[default])


def form_options() -> dict[str, Any]:
    """Options for Streamlit selects — always available (no vibe20)."""
    arch = load_archetypes()
    clim = load_climate()
    codes = load_codes()
    meas = load_measures()
    building_types = []
    for bid, meta in arch.items():
        if bid.startswith("_"):
            continue
        entry = deepcopy(meta)
        if entry.get("extends") and entry["extends"] in arch:
            base = deepcopy(arch[entry["extends"]])
            base.update({k: v for k, v in entry.items() if k != "extends"})
            entry = base
        building_types.append(
            {
                "id": bid,
                "label": entry.get("label") or bid,
                "default_area_ft2": entry.get("default_area_ft2"),
                "default_floors": entry.get("default_floors"),
                "default_floor_to_floor_ft": entry.get("default_floor_to_floor_ft"),
                "default_wwr": entry.get("default_wwr"),
                "hvac_defaults": entry.get("hvac_defaults") or {},
                "hvac_options": entry.get("hvac_options") or {},
            }
        )
    cities = [
        {
            "id": cid,
            "label": meta.get("label") or cid,
            "climate_zone": meta.get("climate_zone"),
            "state": meta.get("state"),
            "lat": meta.get("lat"),
            "lon": meta.get("lon"),
        }
        for cid, meta in (clim.get("cities") or {}).items()
    ]
    code_list = [
        {"id": cid, "label": meta.get("label") or cid}
        for cid, meta in (codes.get("codes") or {}).items()
    ]
    sets = [
        {"id": sid, "label": meta.get("label") or sid, "description": meta.get("description") or ""}
        for sid, meta in meas.items()
        if sid in {"good", "better", "best"}
    ]
    return {
        "building_types": building_types,
        "cities": cities,
        "codes": code_list,
        "measure_sets": sets,
        "default_city": clim.get("default_city") or "chicago",
        "default_code": codes.get("default_code") or "iecc_2018",
        "catalog": meas.get("catalog") or {},
    }


def resolve_profile(minimal: dict[str, Any] | None = None) -> dict[str, Any]:
    """Expand minimal inputs into a full building profile with field_sources provenance."""
    m = dict(minimal or {})
    field_sources: dict[str, dict[str, Any]] = {}

    btype_raw = m.get("building_type")
    btype_id, arch = resolve_building_type(btype_raw)
    field_sources["building_type"] = _tagged(btype_id, "user" if btype_raw else "default")

    city_raw = m.get("city") or m.get("climate_city")
    city_id, city_meta = resolve_city(city_raw)
    field_sources["city"] = _tagged(city_id, "user" if city_raw else "default")

    code_raw = m.get("code_year") or m.get("energy_code")
    code_id, code_meta = resolve_code(code_raw)
    field_sources["code_year"] = _tagged(code_id, "user" if code_raw else "default")

    def pick(key: str, default: Any, *, cast=None) -> Any:
        if key in m and m[key] is not None and m[key] != "":
            val = cast(m[key]) if cast else m[key]
            field_sources[key] = _tagged(val, "user")
            return val
        field_sources[key] = _tagged(default, "default")
        return default

    area = pick("floor_area_ft2", arch.get("default_area_ft2") or 50000, cast=float)
    if m.get("conditioned_floor_area_ft2"):
        area = float(m["conditioned_floor_area_ft2"])
        field_sources["floor_area_ft2"] = _tagged(area, "user")
    floors = pick("floors", arch.get("default_floors") or 3, cast=int)
    if m.get("number_of_floors"):
        floors = int(m["number_of_floors"])
        field_sources["floors"] = _tagged(floors, "user")
    floor_to_floor = pick(
        "floor_to_floor_ft", arch.get("default_floor_to_floor_ft") or 13.0, cast=float
    )
    wwr = pick("wwr", arch.get("default_wwr") or 0.31, cast=float)
    aspect = pick("aspect_ratio", arch.get("default_aspect_ratio") or 1.5, cast=float)
    perimeter = pick(
        "perimeter_depth_ft", arch.get("default_perimeter_depth_ft") or 15.0, cast=float
    )

    hvac_in = m.get("hvac") or {}
    hvac_def = arch.get("hvac_defaults") or {}
    fuel = hvac_in.get("fuel") or hvac_def.get("fuel") or "gas"
    airside = hvac_in.get("airside") or hvac_def.get("airside") or "vav_reheat"
    plant = hvac_in.get("plant") or hvac_def.get("plant") or "air_cooled_chiller"
    doas = hvac_in.get("doas") or hvac_def.get("doas") or "none"
    field_sources["hvac.fuel"] = _tagged(fuel, "user" if hvac_in.get("fuel") else "default")
    field_sources["hvac.airside"] = _tagged(airside, "user" if hvac_in.get("airside") else "default")
    field_sources["hvac.plant"] = _tagged(plant, "user" if hvac_in.get("plant") else "default")
    field_sources["hvac.doas"] = _tagged(doas, "user" if hvac_in.get("doas") else "default")

    util_in = m.get("utility") or {}
    elec = float(util_in["elec_usd_per_kwh"]) if util_in.get("elec_usd_per_kwh") is not None else DEFAULT_ELEC
    gas = float(util_in["gas_usd_per_therm"]) if util_in.get("gas_usd_per_therm") is not None else DEFAULT_GAS
    field_sources["utility.elec"] = _tagged(
        elec, "user" if util_in.get("elec_usd_per_kwh") is not None else "default"
    )
    field_sources["utility.gas"] = _tagged(
        gas, "user" if util_in.get("gas_usd_per_therm") is not None else "default"
    )

    env = dict(code_meta.get("envelope") or {})
    user_env = m.get("envelope") or {}
    for k, v in user_env.items():
        if v is not None:
            env[k] = v
            field_sources[f"envelope.{k}"] = _tagged(v, "user")
    for k, v in list(env.items()):
        field_sources.setdefault(f"envelope.{k}", _tagged(v, "default"))

    lpd_mult = float(code_meta.get("lpd_multiplier") or 1.0)
    fan_scalar = float(code_meta.get("fan_w_per_cfm_scalar") or 1.0)
    lpd = float(arch.get("lpd_w_per_ft2") or 0.9) * lpd_mult
    if m.get("lpd_w_per_ft2") is not None:
        lpd = float(m["lpd_w_per_ft2"])
        field_sources["lpd_w_per_ft2"] = _tagged(lpd, "user")
    else:
        field_sources["lpd_w_per_ft2"] = _tagged(round(lpd, 3), "default")
    plug = float(m["plug_w_per_ft2"]) if m.get("plug_w_per_ft2") is not None else float(arch.get("plug_w_per_ft2") or 0.75)
    field_sources["plug_w_per_ft2"] = _tagged(
        plug, "user" if m.get("plug_w_per_ft2") is not None else "default"
    )
    fan_w = float(arch.get("fan_w_per_cfm") or 1.0) * fan_scalar
    if m.get("fan_w_per_cfm") is not None:
        fan_w = float(m["fan_w_per_cfm"])
        field_sources["fan_w_per_cfm"] = _tagged(fan_w, "user")
    else:
        field_sources["fan_w_per_cfm"] = _tagged(round(fan_w, 3), "default")

    cooling_eer = float(m["cooling_eer"]) if m.get("cooling_eer") is not None else float(arch.get("cooling_eer") or 9.8)
    heating_et = float(m["heating_et_pct"]) if m.get("heating_et_pct") is not None else float(arch.get("heating_et_pct") or 80)
    vav_min = float(m["vav_box_min"]) if m.get("vav_box_min") is not None else float(arch.get("vav_box_min") or 0.3)
    vent = float(m["ventilation_cfm_per_person"]) if m.get("ventilation_cfm_per_person") is not None else float(
        arch.get("ventilation_cfm_per_person") or 17
    )
    field_sources["cooling_eer"] = _tagged(cooling_eer, "user" if m.get("cooling_eer") is not None else "default")
    field_sources["heating_et_pct"] = _tagged(heating_et, "user" if m.get("heating_et_pct") is not None else "default")
    field_sources["vav_box_min"] = _tagged(vav_min, "user" if m.get("vav_box_min") is not None else "default")
    field_sources["ventilation_cfm_per_person"] = _tagged(
        vent, "user" if m.get("ventilation_cfm_per_person") is not None else "default"
    )

    project_id = m.get("project_id") or f"WATTLAB-{btype_id.upper()}-{city_id.upper()}"
    display = m.get("display_name") or f"{city_meta.get('label')} {arch.get('label')}"
    field_sources["project_id"] = _tagged(project_id, "user" if m.get("project_id") else "default")
    field_sources["display_name"] = _tagged(display, "user" if m.get("display_name") else "default")

    measure_set = m.get("measure_set") or "best"
    field_sources["measure_set"] = _tagged(measure_set, "user" if m.get("measure_set") else "default")

    schedules = m.get("schedules") or {}
    sched_src = schedules.get("source") or ("data-derived" if schedules.get("from_inference") else "default")

    profile: dict[str, Any] = {
        "project_id": project_id,
        "display_name": display,
        "product": PRODUCT,
        "anonymized": bool(m.get("anonymized", True)),
        "model_purpose": "conceptual ECM screening",
        "calibration_status": "uncalibrated",
        "disclaimer": m.get("disclaimer") or DISCLAIMER,
        "building_type": btype_id,
        "conditioned_floor_area_ft2": float(area),
        "number_of_floors": int(floors),
        "floor_to_floor_ft": float(floor_to_floor),
        "aspect_ratio": float(aspect),
        "perimeter_depth_ft": float(perimeter),
        "wwr": float(wwr),
        "climate_city": city_meta.get("label"),
        "climate_state": city_meta.get("state"),
        "climate_zone": city_meta.get("climate_zone"),
        "lat": city_meta.get("lat"),
        "lon": city_meta.get("lon"),
        "energy_code": code_meta.get("label") or code_id,
        "code_id": code_id,
        "shells": [
            {
                "shell_id": "SHELL-1",
                "served_area_ft2": float(area),
                "program": btype_id,
                "hvac_summary": f"{fuel} / {airside} / {plant}",
            }
        ],
        "hvac": {"fuel": fuel, "airside": airside, "plant": plant, "doas": doas},
        "hvac_options": arch.get("hvac_options") or {},
        "envelope": env,
        "loads": {
            "lpd_w_per_ft2": round(lpd, 3),
            "plug_w_per_ft2": plug,
            "occupant_ft2_per_person": arch.get("occupant_ft2_per_person"),
            "occupant_sensible_btu_per_hr": arch.get("occupant_sensible_btu_per_hr", 250),
            "occupant_latent_btu_per_hr": arch.get("occupant_latent_btu_per_hr", 250),
            "ventilation_cfm_per_person": vent,
            "dhw_type": arch.get("dhw_type"),
            "dhw_gal_per_ft2_year": arch.get("dhw_gal_per_ft2_year"),
            "dhw_btu_per_hr_person": arch.get("dhw_btu_per_hr_person"),
            "lighting_controls_pct": float(m.get("lighting_controls_pct") or 22),
            "daylighting": bool(m.get("daylighting", True)),
        },
        "equipment": {
            "cooling_eer": cooling_eer,
            "heating_et_pct": heating_et,
            "fan_w_per_cfm": round(fan_w, 3),
            "vav_box_min": vav_min,
            "humidity_max_pct": float(m.get("humidity_max_pct") or 60),
            "airside_economizer": bool(m.get("airside_economizer", True)),
            "dcv": bool(m.get("dcv", False)),
            "erv": bool(m.get("erv", False)),
        },
        "utility": {
            "elec_usd_per_kwh": elec,
            "gas_usd_per_therm": gas,
            "water_usd_per_1000gal": float((m.get("utility") or {}).get("water_usd_per_1000gal") or 0),
        },
        "emissions": {
            "elec_source_site": float((m.get("emissions") or {}).get("elec_source_site") or 2.8),
            "gas_source_site": float((m.get("emissions") or {}).get("gas_source_site") or 1.05),
            "elec_kg_co2e_per_kwh": float((m.get("emissions") or {}).get("elec_kg_co2e_per_kwh") or 0.371),
            "gas_kg_co2e_per_therm": float((m.get("emissions") or {}).get("gas_kg_co2e_per_therm") or 5.3),
        },
        "schedules": schedules,
        "schedule_source": sched_src,
        "energyplus": {
            "prototype_idf": arch.get("prototype_idf") or "examples/prototypes/5ZoneAirCooled.idf",
            "epw": city_meta.get("epw"),
            "epw_note": city_meta.get("epw_note") or "",
            "baseline_idf_patch": "fan_avail_continuous",
        },
        "measure_set": measure_set,
        "measures": list(m.get("measures") or []),
        "field_sources": field_sources,
        "provenance": {
            "product": PRODUCT,
            "resolver": "app.energy_wizard.resolve_profile",
            "defaults_dir": str(DEFAULTS_DIR),
        },
    }
    if m.get("vibe19_evidence"):
        profile["vibe19_evidence"] = m["vibe19_evidence"]
    return profile


# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------


def _hourly_block(start: int, stop: int, occupied: float = 1.0, unoccupied: float = 0.0) -> list[float]:
    """24 hourly fractions; start inclusive, stop exclusive (stop=24 means through midnight)."""
    start = int(max(0, min(24, start)))
    stop = int(max(0, min(24, stop)))
    out = [unoccupied] * 24
    if start == stop == 0:
        return out
    if start == 0 and stop == 24:
        return [occupied] * 24
    if start <= stop:
        for h in range(start, stop):
            out[h] = occupied
    else:
        for h in range(start, 24):
            out[h] = occupied
        for h in range(0, stop):
            out[h] = occupied
    return out


def default_schedules_for_archetype(arch: dict | None = None) -> dict[str, Any]:
    sched = dict((arch or {}).get("schedule_defaults") or {})
    wd_start = int(sched.get("weekday_start_hour", 7))
    wd_stop = int(sched.get("weekday_stop_hour", 18))
    we_start = int(sched.get("weekend_start_hour", 0))
    we_stop = int(sched.get("weekend_stop_hour", 0))
    occ_wd = _hourly_block(wd_start, wd_stop)
    occ_we = _hourly_block(we_start, we_stop)
    return {
        "from_inference": False,
        "source": "default",
        "weekday_start_hour": wd_start,
        "weekday_stop_hour": wd_stop,
        "weekend_start_hour": we_start,
        "weekend_stop_hour": we_stop,
        "cool_occupied_f": float(sched.get("cool_occupied_f", 75)),
        "cool_unoccupied_f": float(sched.get("cool_unoccupied_f", 85)),
        "heat_occupied_f": float(sched.get("heat_occupied_f", 70)),
        "heat_unoccupied_f": float(sched.get("heat_unoccupied_f", 60)),
        "weekday": {
            "occupancy": occ_wd,
            "ventilation": list(occ_wd),
            "lighting": list(occ_wd),
            "plug": [max(0.2, x) for x in occ_wd],
            "dhw": list(occ_wd),
        },
        "weekend": {
            "occupancy": occ_we,
            "ventilation": list(occ_we),
            "lighting": list(occ_we),
            "plug": [max(0.15, x) if x else 0.15 for x in occ_we] if any(occ_we) else [0.15] * 24,
            "dhw": list(occ_we),
        },
    }


def schedules_from_inference(
    schedule_payload: dict[str, Any] | None,
    *,
    arch: dict | None = None,
) -> dict[str, Any]:
    """Prefill weekday/weekend hours from model_seed.infer_schedules; fall back to archetype."""
    base = default_schedules_for_archetype(arch)
    if not schedule_payload:
        return base
    equipment = schedule_payload.get("equipment") or {}
    # Prefer first AHU-like row with usable hours
    pick = None
    for eq_id, row in equipment.items():
        if not isinstance(row, dict):
            continue
        et = str(row.get("equipment_type") or "").upper()
        if et in {"AHU", "RTU", "HP"} or "AHU" in eq_id.upper():
            pick = row
            break
    if pick is None and equipment:
        pick = next(iter(equipment.values()))
    if not isinstance(pick, dict):
        return base
    if pick.get("likely_always_on"):
        base["weekday_start_hour"] = 0
        base["weekday_stop_hour"] = 24
        base["weekend_start_hour"] = 0
        base["weekend_stop_hour"] = 24
        base["from_inference"] = True
        base["source"] = "data-derived"
        base["inference_signal"] = pick.get("signal")
        base["always_on_fraction"] = pick.get("always_on_fraction")
        occ = [1.0] * 24
        for day in ("weekday", "weekend"):
            base[day]["occupancy"] = list(occ)
            base[day]["ventilation"] = list(occ)
            base[day]["lighting"] = list(occ)
        return base
    wd_s = pick.get("weekday_start_hour")
    wd_e = pick.get("weekday_stop_hour")
    we_s = pick.get("weekend_start_hour")
    we_e = pick.get("weekend_stop_hour")
    if wd_s is not None and wd_e is not None:
        base["weekday_start_hour"] = int(wd_s)
        base["weekday_stop_hour"] = int(wd_e)
        occ = _hourly_block(int(wd_s), int(wd_e))
        base["weekday"]["occupancy"] = occ
        base["weekday"]["ventilation"] = list(occ)
        base["weekday"]["lighting"] = list(occ)
        base["from_inference"] = True
        base["source"] = "data-derived"
        base["inference_signal"] = pick.get("signal")
    if we_s is not None and we_e is not None:
        base["weekend_start_hour"] = int(we_s)
        base["weekend_stop_hour"] = int(we_e)
        occ = _hourly_block(int(we_s), int(we_e))
        base["weekend"]["occupancy"] = occ
        base["weekend"]["ventilation"] = list(occ)
        base["weekend"]["lighting"] = list(occ)
        base["from_inference"] = True
        base["source"] = "data-derived"
    return base


# ---------------------------------------------------------------------------
# ECM prefill + quick bin-hour savings
# ---------------------------------------------------------------------------


def suggest_measures_from_fdd(
    *,
    batch_results: list | None = None,
    results_summary: pd.DataFrame | None = None,
    measure_set: str = "best",
) -> list[dict[str, Any]]:
    """Map FAULT rules → ECM briefs; always include the selected measure set."""
    meas = load_measures()
    catalog = meas.get("catalog") or {}
    rule_map = meas.get("rule_to_measure") or {}
    sets = meas.get(measure_set) or meas.get("best") or {}
    set_ids = list(sets.get("measure_ids") or [])

    fault_rules: set[str] = set()
    if results_summary is not None and not results_summary.empty and "rule_id" in results_summary.columns:
        status_col = "status" if "status" in results_summary.columns else None
        for _, row in results_summary.iterrows():
            rid = str(row.get("rule_id") or "")
            st = str(row.get(status_col) or "") if status_col else ""
            if st in {"FAULT", "WARNING"}:
                fault_rules.add(rid)
    for r in batch_results or []:
        status = str(getattr(r, "status", "") or "")
        if status in {"FAULT", "WARNING"}:
            fault_rules.add(str(getattr(r, "rule_id", "") or ""))

    chosen: dict[str, dict[str, Any]] = {}
    for mid in set_ids:
        if mid in catalog:
            brief = deepcopy(catalog[mid])
            brief["source"] = "measure_set"
            brief["enabled"] = True
            chosen[mid] = brief
    for rid in fault_rules:
        mid = rule_map.get(rid)
        if not mid or mid not in catalog:
            continue
        if mid not in chosen:
            brief = deepcopy(catalog[mid])
            brief["source"] = "vibe19"
            brief["enabled"] = True
            brief["trigger_rules"] = [rid]
            chosen[mid] = brief
        else:
            chosen[mid].setdefault("trigger_rules", [])
            if rid not in chosen[mid]["trigger_rules"]:
                chosen[mid]["trigger_rules"].append(rid)
            if chosen[mid].get("source") == "measure_set":
                chosen[mid]["source"] = "measure_set+vibe19"
    return list(chosen.values())


def estimate_runtime_reduction(
    *,
    fan_run_hours: float,
    data_span_hours: float,
    proposed_daily_hours: float = 11.0,
    fan_kw: float = 15.0,
    elec_usd_per_kwh: float = DEFAULT_ELEC,
) -> dict[str, Any]:
    """Annualize partial-year fan runtime and estimate schedule-alignment savings."""
    if data_span_hours <= 0:
        return {"status": "skipped", "reason": "no_data_window"}
    scale = 8760.0 / float(data_span_hours)
    annual_observed = float(fan_run_hours) * scale
    # Proposed: weekday 11h × 5 × 52 ≈ 2860; weekends off → ~2860 h/year
    annual_proposed = float(proposed_daily_hours) * 5.0 * 52.0
    avoided = max(0.0, annual_observed - annual_proposed)
    kwh = avoided * float(fan_kw)
    return {
        "status": "ok",
        "estimator": "runtime_reduction",
        "data_span_hours": round(data_span_hours, 1),
        "observed_run_hours": round(fan_run_hours, 1),
        "annualized_run_hours": round(annual_observed, 1),
        "proposed_annual_hours": round(annual_proposed, 1),
        "avoided_hours": round(avoided, 1),
        "fan_kw_assumed": fan_kw,
        "kwh_savings": round(kwh, 0),
        "usd_savings": round(kwh * elec_usd_per_kwh, 0),
        "notes": "Affinity not applied — assumes constant fan kW while on. Screening-grade only.",
    }


def estimate_gl36_trim_respond(
    *,
    duct_static_mean_iwc: float | None = None,
    proposed_static_iwc: float = 0.75,
    fan_kw: float = 15.0,
    annual_fan_hours: float = 3000.0,
    elec_usd_per_kwh: float = DEFAULT_ELEC,
) -> dict[str, Any]:
    """Fan affinity (speed³ ≈ pressure^1.5 for centrifugal) screening estimate."""
    if duct_static_mean_iwc is None or duct_static_mean_iwc <= 0:
        return {"status": "skipped", "reason": "no_duct_static"}
    p0 = float(duct_static_mean_iwc)
    p1 = float(proposed_static_iwc)
    if p1 >= p0:
        return {
            "status": "ok",
            "estimator": "gl36_trim_respond",
            "baseline_static_iwc": p0,
            "proposed_static_iwc": p1,
            "kwh_savings": 0.0,
            "usd_savings": 0.0,
            "notes": "Proposed static not below observed mean — no affinity savings.",
        }
    # Power ratio ≈ (P1/P0)^1.5 as proxy for trim-and-respond
    ratio = (p1 / p0) ** 1.5
    baseline_kwh = float(fan_kw) * float(annual_fan_hours)
    savings = baseline_kwh * (1.0 - ratio)
    return {
        "status": "ok",
        "estimator": "gl36_trim_respond",
        "baseline_static_iwc": round(p0, 3),
        "proposed_static_iwc": p1,
        "power_ratio": round(ratio, 3),
        "annual_fan_hours": annual_fan_hours,
        "fan_kw_assumed": fan_kw,
        "kwh_savings": round(max(0.0, savings), 0),
        "usd_savings": round(max(0.0, savings) * elec_usd_per_kwh, 0),
        "notes": "Screening affinity proxy — not a calibrated EnergyPlus result.",
    }


def estimate_mech_cool_lockout(
    *,
    prohibited_hours: float,
    data_span_hours: float,
    plant_kw: float = 40.0,
    elec_usd_per_kwh: float = DEFAULT_ELEC,
) -> dict[str, Any]:
    """Annualize prohibited mech-cooling hours below 60°F and estimate plant kWh."""
    if data_span_hours <= 0:
        return {"status": "skipped", "reason": "no_data_window"}
    scale = 8760.0 / float(data_span_hours)
    annual_hours = float(prohibited_hours) * scale
    kwh = annual_hours * float(plant_kw)
    return {
        "status": "ok",
        "estimator": "mech_cool_lockout",
        "prohibited_hours_in_window": round(prohibited_hours, 1),
        "annualized_hours": round(annual_hours, 1),
        "plant_kw_assumed": plant_kw,
        "kwh_savings": round(kwh, 0),
        "usd_savings": round(kwh * elec_usd_per_kwh, 0),
        "notes": "Uses idle-plant kW × annualized prohibited hours (MECH-OAT / economizer weather).",
    }


def attach_quick_estimates(
    measures: list[dict[str, Any]],
    *,
    fan_run_hours: float = 0.0,
    data_span_hours: float = 0.0,
    duct_static_mean_iwc: float | None = None,
    prohibited_mech_hours: float = 0.0,
    schedules: dict[str, Any] | None = None,
    elec_usd_per_kwh: float = DEFAULT_ELEC,
    fan_kw: float = 15.0,
    plant_kw: float = 40.0,
) -> list[dict[str, Any]]:
    """Attach screening-grade quick_estimate blobs onto ECM briefs."""
    sched = schedules or {}
    wd_s = int(sched.get("weekday_start_hour", 7))
    wd_e = int(sched.get("weekday_stop_hour", 18))
    proposed_daily = max(0, wd_e - wd_s) if wd_e >= wd_s else (24 - wd_s + wd_e)
    out = []
    for m in measures:
        brief = deepcopy(m)
        est_name = brief.get("quick_estimator")
        if est_name == "runtime_reduction":
            brief["quick_estimate"] = estimate_runtime_reduction(
                fan_run_hours=fan_run_hours,
                data_span_hours=data_span_hours,
                proposed_daily_hours=float(proposed_daily or 11),
                fan_kw=fan_kw,
                elec_usd_per_kwh=elec_usd_per_kwh,
            )
        elif est_name == "gl36_trim_respond":
            annual_hours = (
                float(fan_run_hours) * (8760.0 / data_span_hours) if data_span_hours > 0 else 3000.0
            )
            brief["quick_estimate"] = estimate_gl36_trim_respond(
                duct_static_mean_iwc=duct_static_mean_iwc,
                fan_kw=fan_kw,
                annual_fan_hours=annual_hours,
                elec_usd_per_kwh=elec_usd_per_kwh,
            )
        elif est_name == "mech_cool_lockout":
            brief["quick_estimate"] = estimate_mech_cool_lockout(
                prohibited_hours=prohibited_mech_hours,
                data_span_hours=data_span_hours,
                plant_kw=plant_kw,
                elec_usd_per_kwh=elec_usd_per_kwh,
            )
        out.append(brief)
    return out


# ---------------------------------------------------------------------------
# Export package
# ---------------------------------------------------------------------------


def write_energy_model_package(
    out_dir: Path,
    *,
    profile: dict[str, Any],
    schedules: dict[str, Any] | None = None,
    measures: list[dict[str, Any]] | None = None,
    schedule_inference: dict | None = None,
    operating_signatures: pd.DataFrame | None = None,
    weather: pd.DataFrame | None = None,
    utility_bills: pd.DataFrame | None = None,
    quick_savings_summary: dict | None = None,
) -> Path:
    """Write Energy Model Package folder + zip for an outside EnergyPlus agent."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = deepcopy(profile)
    if schedules:
        payload["schedules"] = schedules
    (out_dir / "building_profile.json").write_text(
        json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8"
    )
    (out_dir / "ecm_briefs.json").write_text(
        json.dumps({"measures": measures or []}, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    if schedule_inference:
        (out_dir / "schedule_inference.json").write_text(
            json.dumps(schedule_inference, indent=2, default=str) + "\n", encoding="utf-8"
        )
    if operating_signatures is not None and not operating_signatures.empty:
        operating_signatures.to_csv(out_dir / "operating_signatures.csv", index=False)
    if weather is not None and not weather.empty:
        weather.to_csv(out_dir / "weather_observed.csv")
    if utility_bills is not None and not utility_bills.empty:
        utility_bills.to_csv(out_dir / "utility_bills.csv", index=False)
    if quick_savings_summary:
        (out_dir / "quick_savings.json").write_text(
            json.dumps(quick_savings_summary, indent=2, default=str) + "\n", encoding="utf-8"
        )
    readme = """# OpenFDD WattLab — Energy Model Package

This package is produced by vibe19 (OpenFDD Streamlit) for an **outside AI agent**
to build / calibrate an EnergyPlus model (EnergyPlus-MCP or vibe20).

## Contents

- `building_profile.json` — resolved geometry, HVAC, envelope, loads, rates, provenance
- `ecm_briefs.json` — recommended measures with evidence + quick bin-hour savings estimates
- `schedule_inference.json` / `operating_signatures.csv` — data-derived schedules & OAT bins
- `weather_observed.csv` — optional AMY / Open-Meteo overlap window
- `utility_bills.csv` — optional monthly kWh/therms
- `quick_savings.json` — screening-grade kWh/$$ totals (not EnergyPlus results)

## Agent next steps

1. Map `building_profile.json` onto a DOE prototype IDF (or existing seed).
2. Apply schedule / lockout / GL36 / SAT patches from `ecm_briefs.json` `idf_patch` hints.
3. Prefer AMY EPW from `weather_observed.csv` for overlap-window calibration when present.
4. Report NMBE/CVRMSE vs `operating_signatures.csv` and monthly bills when available.

Screening estimates inside this package are **not** calibrated EnergyPlus results.
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")

    zip_path = out_dir.with_suffix(".zip")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in out_dir.rglob("*"):
            if p.is_file() and p != zip_path:
                zf.write(p, arcname=p.relative_to(out_dir).as_posix())
    return zip_path


def profile_fingerprint(profile: dict[str, Any]) -> str:
    blob = json.dumps(profile, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
