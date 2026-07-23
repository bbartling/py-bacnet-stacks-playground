"""Read-only model summary for Twin (answers + published run artifacts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wattlab.studio.ep_viz import find_run_idf
from wattlab.studio.eui_compare import load_model_eui_from_run
from wattlab.studio.g14_history import extract_run_g14
from wattlab.studio.idf_geometry import parse_idf_geometry


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError, TypeError):
        return {}


def _dash(v: Any) -> Any:
    return "—" if v is None or v == "" else v


def _scan_meta(run_dir: Path) -> dict[str, Any]:
    """Merge first geo/dial/meta JSON found under the run."""
    merged: dict[str, Any] = {}
    patterns = ("*meta*.json", "*dial*.json", "geo_build_meta.json", "answers_stamp.json")
    for pat in patterns:
        for p in sorted(run_dir.glob(pat)):
            if not p.is_file():
                continue
            data = _load_json(p)
            for k, v in data.items():
                if k not in merged and v is not None:
                    merged[k] = v
    return merged


def _hvac_hints_from_idf_text(text: str) -> dict[str, Any]:
    return {
        "chiller_electric": text.count("Chiller:Electric"),
        "cooling_tower": text.count("CoolingTower"),
        "boiler_hotwater": text.count("Boiler:HotWater"),
        "airloophvac": text.count("AirLoopHVAC,"),
        "heatpump": text.count("HeatPump:"),
    }


def build_model_summary(
    answers: dict[str, Any] | None,
    run_dir: Path | str | None,
    *,
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate project / geometry / loads / HVAC / run blocks for UI display."""
    answers = answers if isinstance(answers, dict) else {}
    profile = profile if isinstance(profile, dict) else {}
    utility = answers.get("utility") if isinstance(answers.get("utility"), dict) else {}
    run_path = Path(run_dir) if run_dir else None
    meta = _scan_meta(run_path) if run_path and run_path.is_dir() else {}
    model_eui = load_model_eui_from_run(run_path) if run_path else {}
    g14 = extract_run_g14(run_path) if run_path else {}

    geom_block: dict[str, Any] = {
        "floor_area_ft2": answers.get("floor_area_ft2")
        or profile.get("floor_area_ft2")
        or meta.get("target_area_ft2"),
        "floors": answers.get("floors") or answers.get("stories") or meta.get("stories_above_grade"),
        "wwr": answers.get("wwr") or meta.get("wwr_target") or meta.get("wwr"),
        "n_zones": None,
        "n_fenestration": None,
        "wwr_from_idf_pct": None,
        "wall_area_m2": None,
        "window_area_m2": None,
        "bbox_ft": None,
    }
    hvac_block: dict[str, Any] = {
        "hints": {},
        "heating_fuel": answers.get("heating_fuel") or profile.get("heating_fuel"),
        "hvac_system": answers.get("hvac_system") or profile.get("hvac_system"),
    }
    idf_path = find_run_idf(run_path) if run_path else None
    if idf_path and idf_path.is_file():
        try:
            text = idf_path.read_text(encoding="utf-8", errors="replace")
            geom = parse_idf_geometry(text)
            summ = geom.summary()
            geom_block["n_zones"] = summ.get("n_zones")
            geom_block["n_fenestration"] = summ.get("n_fenestration")
            geom_block["wwr_from_idf_pct"] = summ.get("wwr_pct")
            geom_block["wall_area_m2"] = summ.get("wall_area_m2")
            geom_block["window_area_m2"] = summ.get("window_area_m2")
            geom_block["bbox_ft"] = summ.get("bbox_ft")
            if geom_block.get("wwr") is None and summ.get("wwr") is not None:
                geom_block["wwr"] = summ.get("wwr")
            hvac_block["hints"] = _hvac_hints_from_idf_text(text)
        except OSError:
            pass

    loads = {
        "lights_w_per_m2": meta.get("lights_w_per_m2")
        or answers.get("lights_w_per_m2")
        or meta.get("lights"),
        "equip_w_per_m2": meta.get("equip_w_per_m2")
        or answers.get("equip_w_per_m2")
        or meta.get("equip"),
        "infil_mult": meta.get("infil_mult") or answers.get("infil_mult"),
        "shgc": meta.get("shgc") or answers.get("shgc"),
    }

    project = {
        "building_id": answers.get("building_id") or profile.get("building_id"),
        "building_type": answers.get("building_type") or profile.get("building_type"),
        "city": answers.get("city") or profile.get("city"),
        "lat": answers.get("lat") or profile.get("lat"),
        "lon": answers.get("lon") or profile.get("lon"),
        "climate_zone": answers.get("climate_zone") or meta.get("climate_zone"),
        "elec_usd_per_kwh": utility.get("elec_usd_per_kwh"),
        "gas_usd_per_therm": utility.get("gas_usd_per_therm"),
    }

    run_block = {
        "run_id": model_eui.get("run_id") or (run_path.name if run_path else None),
        "weather_mode": model_eui.get("weather_mode"),
        "prototype_area_scale": model_eui.get("prototype_area_scale"),
        "model_eui_kbtu_ft2": model_eui.get("model_eui_kbtu_ft2"),
        "peak_demand_kw": model_eui.get("peak_demand_kw"),
        "idf": str(idf_path) if idf_path else None,
        "g14": g14,
        "hypothesis": meta.get("hypothesis") or meta.get("note"),
    }

    return {
        "project": project,
        "geometry": geom_block,
        "loads": loads,
        "hvac": hvac_block,
        "run": run_block,
    }


def render_model_summary_panel(summary: dict[str, Any]) -> None:
    """Streamlit read-only panel (import streamlit only when rendering)."""
    import streamlit as st

    st.caption(
        "Read-only snapshot from answers.json + published run (IDF / meta). "
        "Missing fields show as — until the agent stamps them."
    )
    proj = summary.get("project") or {}
    geom = summary.get("geometry") or {}
    loads = summary.get("loads") or {}
    hvac = summary.get("hvac") or {}
    run = summary.get("run") or {}

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Project**")
        st.write(
            {
                "building_id": _dash(proj.get("building_id")),
                "type": _dash(proj.get("building_type")),
                "city": _dash(proj.get("city")),
                "lat/lon": f"{_dash(proj.get('lat'))}, {_dash(proj.get('lon'))}",
                "climate": _dash(proj.get("climate_zone")),
                "elec $/kWh": _dash(proj.get("elec_usd_per_kwh")),
                "gas $/therm": _dash(proj.get("gas_usd_per_therm")),
            }
        )
    with c2:
        st.markdown("**Geometry**")
        st.write(
            {
                "area_ft2": _dash(geom.get("floor_area_ft2")),
                "floors": _dash(geom.get("floors")),
                "WWR": _dash(geom.get("wwr")),
                "WWR from IDF %": _dash(geom.get("wwr_from_idf_pct")),
                "zones": _dash(geom.get("n_zones")),
                "fenestration objs": _dash(geom.get("n_fenestration")),
                "bbox_ft": _dash(geom.get("bbox_ft")),
            }
        )
    with c3:
        st.markdown("**Loads / HVAC / run**")
        hints = hvac.get("hints") or {}
        g14 = run.get("g14") or {}
        st.write(
            {
                "lights W/m²": _dash(loads.get("lights_w_per_m2")),
                "equip W/m²": _dash(loads.get("equip_w_per_m2")),
                "infil mult": _dash(loads.get("infil_mult")),
                "SHGC": _dash(loads.get("shgc")),
                "chillers": _dash(hints.get("chiller_electric")),
                "towers": _dash(hints.get("cooling_tower")),
                "boilers": _dash(hints.get("boiler_hotwater")),
                "model EUI": _dash(run.get("model_eui_kbtu_ft2")),
                "area_scale": _dash(run.get("prototype_area_scale")),
                "NMBE elec %": _dash(g14.get("nmbe_elec_pct")),
                "CVRMSE elec %": _dash(g14.get("cvrmse_elec_pct")),
            }
        )
