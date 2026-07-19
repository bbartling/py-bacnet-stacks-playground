"""responsive-defaults defaults resolver for OpenFDD WattLab.

Minimal inputs (building_type, city, code_year, area, floors, HVAC picker)
expand into a fully resolved building profile. Every field is tagged with
source = user | default | vibe19 — the programmatic version of easy-button UX
black vs blue text.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from wattlab.config import (
    DEFAULT_ELEC_RATE_USD_PER_KWH,
    DEFAULT_GAS_RATE_USD_PER_THERM,
    DEFAULT_PROTOTYPE_IDF,
    ROOT,
)

DEFAULTS_DIR = Path(__file__).resolve().parent / "data" / "defaults"
PRODUCT = "OpenFDD WattLab"
DISCLAIMER = (
    "This is a conceptual, uncalibrated screening model. "
    "It is not a design load calculation, code-compliance model, "
    "calibrated energy model, or representation of a specific property. "
    "EnergyPlus autosizes HVAC capacities so fan/plant sizing records are not required."
)


def _load_json(name: str) -> dict[str, Any]:
    return json.loads((DEFAULTS_DIR / name).read_text(encoding="utf-8"))


def load_archetypes() -> dict[str, Any]:
    return _load_json("archetypes.json")


def load_climate() -> dict[str, Any]:
    return _load_json("climate.json")


def load_codes() -> dict[str, Any]:
    return _load_json("codes.json")


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
        "small_office": "office",
        "large_office": "multistory_office",
        "multistory_office": "multistory_office",
        "multi_story_office": "multistory_office",
        "multistory": "multistory_office",
        "warehouse": "warehouse",
        "distribution": "warehouse",
        "school": "school",
        "k12": "school",
        "k_12": "school",
    }
    resolved = aliases.get(key, key if key in arch else "office")
    entry = deepcopy(arch[resolved])
    if entry.get("extends"):
        base = deepcopy(arch[entry["extends"]])
        base.update({k: v for k, v in entry.items() if k != "extends"})
        entry = base
        entry["archetype_id"] = resolved
    else:
        entry["archetype_id"] = resolved
    return resolved, entry


def resolve_city(raw: str | None, climate: dict | None = None) -> tuple[str, dict]:
    clim = climate or load_climate()
    cities = clim.get("cities") or {}
    key = _norm(raw) or clim.get("default_city") or "madison"
    if key in cities:
        return key, deepcopy(cities[key])
    for cid, meta in cities.items():
        aliases = [_norm(a) for a in (meta.get("aliases") or [])]
        label = _norm(meta.get("label"))
        if key in aliases or key == label or key in label:
            return cid, deepcopy(meta)
    # fallback
    fb = clim.get("default_city") or "madison"
    return fb, deepcopy(cities[fb])


def resolve_code(raw: str | None, codes: dict | None = None) -> tuple[str, dict]:
    catalog = codes or load_codes()
    code_map = catalog.get("codes") or {}
    key = _norm(raw) or catalog.get("default_code") or "ashrae_90_1_2013"
    # normalize ashrae_90_1_2013 ↔ ashrae_90.1_2013 keys in file
    lookup = { _norm(k).replace("_", ""): k for k in code_map }
    # also try direct
    for cid, meta in code_map.items():
        if _norm(cid) == key or _norm(meta.get("label")) == key:
            return cid, deepcopy(meta)
        for a in meta.get("aliases") or []:
            if _norm(a) == key or key in _norm(a):
                return cid, deepcopy(meta)
    # fuzzy year
    m = re.search(r"(2004|2013|2018|2019|2021)", key)
    if m:
        year = m.group(1)
        year_map = {
            "2004": "ashrae_90.1_2004",
            "2013": "ashrae_90.1_2013",
            "2018": "ashrae_90.1_2019",
            "2019": "ashrae_90.1_2019",
            "2021": "ashrae_90.1_2019",
        }
        cid = year_map[year]
        if cid in code_map:
            return cid, deepcopy(code_map[cid])
    default = catalog.get("default_code") or "ashrae_90.1_2013"
    return default, deepcopy(code_map[default])


def _epw_path(city_meta: dict) -> tuple[str, str]:
    """Prefer site-specific EPW when file exists; else bundled fallback."""
    preferred = city_meta.get("epw_preferred")
    fallback = city_meta.get("epw")
    note = city_meta.get("epw_note") or ""
    if preferred:
        pref_path = (ROOT / preferred).resolve() if not Path(preferred).is_absolute() else Path(preferred)
        if pref_path.is_file():
            return preferred, f"Using preferred EPW for {city_meta.get('label')}."
    return fallback or str(DEFAULT_PROTOTYPE_IDF), note


def resolve_profile(minimal: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Expand minimal-input minimal inputs into a WattLab building profile.

    Expected minimal keys (all optional — defaults fill gaps):
      building_type, floor_area_ft2, floors, floor_to_floor_ft, wwr,
      city, code_year, hvac: {fuel, airside, plant},
      utility: {elec_usd_per_kwh, gas_usd_per_therm},
      project_id, display_name, measures, measure_set, vibe19_evidence
    """
    m = dict(minimal or {})
    field_sources: dict[str, dict[str, Any]] = {}

    btype_raw = m.get("building_type")
    btype_id, arch = resolve_building_type(btype_raw)
    field_sources["building_type"] = _tagged(
        btype_id, "user" if btype_raw else "default"
    )

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
        val = default
        field_sources[key] = _tagged(val, "default")
        return val

    area = pick(
        "floor_area_ft2",
        arch.get("default_area_ft2") or 50000,
        cast=float,
    )
    # also accept conditioned_floor_area_ft2 as user override
    if "conditioned_floor_area_ft2" in m and m["conditioned_floor_area_ft2"]:
        area = float(m["conditioned_floor_area_ft2"])
        field_sources["floor_area_ft2"] = _tagged(area, "user")

    floors = pick("floors", arch.get("default_floors") or 3, cast=int)
    if "number_of_floors" in m and m["number_of_floors"]:
        floors = int(m["number_of_floors"])
        field_sources["floors"] = _tagged(floors, "user")

    floor_to_floor = pick(
        "floor_to_floor_ft",
        arch.get("default_floor_to_floor_ft") or 13.0,
        cast=float,
    )
    wwr = pick("wwr", arch.get("default_wwr") or 0.33, cast=float)

    hvac_in = m.get("hvac") or {}
    hvac_def = arch.get("hvac_defaults") or {}
    fuel = hvac_in.get("fuel") or hvac_def.get("fuel") or "gas"
    airside = hvac_in.get("airside") or hvac_def.get("airside") or "vav_reheat"
    plant = hvac_in.get("plant") or hvac_def.get("plant") or "air_cooled_chiller"
    field_sources["hvac.fuel"] = _tagged(
        fuel, "user" if hvac_in.get("fuel") else "default"
    )
    field_sources["hvac.airside"] = _tagged(
        airside, "user" if hvac_in.get("airside") else "default"
    )
    field_sources["hvac.plant"] = _tagged(
        plant, "user" if hvac_in.get("plant") else "default"
    )

    util_in = m.get("utility") or {}
    elec = float(
        util_in.get("elec_usd_per_kwh")
        if util_in.get("elec_usd_per_kwh") is not None
        else DEFAULT_ELEC_RATE_USD_PER_KWH
    )
    gas = float(
        util_in.get("gas_usd_per_therm")
        if util_in.get("gas_usd_per_therm") is not None
        else DEFAULT_GAS_RATE_USD_PER_THERM
    )
    field_sources["utility.elec"] = _tagged(
        elec, "user" if util_in.get("elec_usd_per_kwh") is not None else "default"
    )
    field_sources["utility.gas"] = _tagged(
        gas, "user" if util_in.get("gas_usd_per_therm") is not None else "default"
    )

    epw_rel, epw_note = _epw_path(city_meta)
    # Bring-your-own IDF: custom_idf / prototype_idf override archetype default.
    user_idf = m.get("custom_idf") or m.get("prototype_idf")
    if user_idf:
        proto = str(user_idf)
        field_sources["prototype_idf"] = _tagged(proto, "user", note="human-supplied IDF")
    else:
        proto = arch.get("prototype_idf") or "examples/prototypes/5ZoneAirCooled.idf"
        field_sources["prototype_idf"] = _tagged(proto, "default")
    user_epw = m.get("epw") or m.get("amy_epw")
    if user_epw:
        epw_rel = str(user_epw)
        epw_note = m.get("epw_note") or "User / AMY EPW override"
        field_sources["epw"] = _tagged(epw_rel, "user", note=epw_note)
    else:
        field_sources["epw"] = _tagged(epw_rel, "default", note=epw_note)

    lpd = float(arch.get("lpd_w_per_ft2") or 0.9) * float(
        code_meta.get("lpd_multiplier") or 1.0
    )
    plug = float(arch.get("plug_w_per_ft2") or 0.75)
    field_sources["lpd_w_per_ft2"] = _tagged(round(lpd, 3), "default")
    field_sources["plug_w_per_ft2"] = _tagged(plug, "default")

    project_id = m.get("project_id") or f"WATTLAB-{btype_id.upper()}-{city_id.upper()}"
    field_sources["project_id"] = _tagged(
        project_id, "user" if m.get("project_id") else "default"
    )
    display = m.get("display_name") or f"{city_meta.get('label')} {arch.get('label')}"
    field_sources["display_name"] = _tagged(
        display, "user" if m.get("display_name") else "default"
    )

    measures = list(m.get("measures") or [])
    if measures:
        for meas in measures:
            if "source" not in meas:
                meas["source"] = "user"
        field_sources["measures"] = _tagged(
            [x.get("measure_id") for x in measures],
            "vibe19"
            if any(x.get("source") == "vibe19" for x in measures)
            else "user",
        )

    measure_set = m.get("measure_set")
    if measure_set:
        field_sources["measure_set"] = _tagged(measure_set, "user")

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
        "wwr": float(wwr),
        "climate_city": city_meta.get("label"),
        "climate_state": city_meta.get("state"),
        "climate_zone": city_meta.get("climate_zone"),
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
        "hvac": {"fuel": fuel, "airside": airside, "plant": plant},
        "hvac_options": arch.get("hvac_options") or {},
        "loads": {
            "lpd_w_per_ft2": round(lpd, 3),
            "plug_w_per_ft2": plug,
            "occupant_ft2_per_person": arch.get("occupant_ft2_per_person"),
            "ventilation_cfm_per_person": arch.get("ventilation_cfm_per_person"),
            "dhw_type": arch.get("dhw_type"),
        },
        "energyplus": {
            "prototype_idf": proto,
            "epw": epw_rel,
            "epw_note": epw_note,
            "baseline_idf_patch": m.get("baseline_idf_patch") or "fan_avail_continuous",
            "calibration": {
                "status": "NEEDS_INPUT",
                "people_multiplier": 1.0,
                "lights_multiplier": float(code_meta.get("lpd_multiplier") or 1.0),
                "equipment_multiplier": 1.0,
                "infiltration_multiplier": 1.0,
                "equipment_efficiency_scalar": float(
                    code_meta.get("equipment_efficiency_scalar") or 1.0
                ),
                "note": "Code vintage applied as lights_multiplier screening proxy; plant efficiency scalar is documentary until COP patches land.",
            },
        },
        "utility": {
            "elec_usd_per_kwh": elec,
            "gas_usd_per_therm": gas,
        },
        "measures": measures,
        "field_sources": field_sources,
        "provenance": [
            {
                "source": "wattlab_defaults",
                "archetype": btype_id,
                "city": city_id,
                "code": code_id,
                "note": "Resolved from responsive-defaults minimal inputs via wattlab_defaults.resolve_profile",
            }
        ],
    }
    if measure_set:
        profile["measure_set"] = measure_set
    if m.get("vibe19_evidence"):
        profile["vibe19_evidence"] = m["vibe19_evidence"]
        for fs in field_sources.values():
            pass
        field_sources["vibe19_evidence"] = _tagged(True, "vibe19")
    return profile


def list_building_types() -> list[dict[str, str]]:
    arch = load_archetypes()
    return [
        {"id": k, "label": v.get("label") or k}
        for k, v in arch.items()
        if isinstance(v, dict) and "label" in v
    ]


def list_cities() -> list[dict[str, str]]:
    clim = load_climate()
    return [
        {
            "id": k,
            "label": v.get("label") or k,
            "climate_zone": v.get("climate_zone") or "",
        }
        for k, v in (clim.get("cities") or {}).items()
    ]


def list_codes() -> list[dict[str, str]]:
    catalog = load_codes()
    return [
        {"id": k, "label": v.get("label") or k}
        for k, v in (catalog.get("codes") or {}).items()
    ]


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="Resolve WattLab building profile defaults")
    p.add_argument("--type", default="office")
    p.add_argument("--city", default="madison")
    p.add_argument("--code", default="ashrae_90.1_2013")
    p.add_argument("--area", type=float, default=None)
    p.add_argument("--floors", type=int, default=None)
    args = p.parse_args(argv)
    minimal: dict[str, Any] = {
        "building_type": args.type,
        "city": args.city,
        "code_year": args.code,
    }
    if args.area:
        minimal["floor_area_ft2"] = args.area
    if args.floors:
        minimal["floors"] = args.floors
    print(json.dumps(resolve_profile(minimal), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
