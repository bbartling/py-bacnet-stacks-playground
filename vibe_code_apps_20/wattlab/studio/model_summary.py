"""Read-only model summary / assumptions for Twin (answers + published run)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wattlab.studio.ep_viz import find_run_idf
from wattlab.studio.eui_compare import load_model_eui_from_run
from wattlab.studio.g14_history import extract_run_g14
from wattlab.studio.idf_geometry import parse_idf_geometry

# Mission taxonomy (honest mapping only — never invent MEASURED).
SOURCE_CLASSES = frozenset(
    {
        "MEASURED",
        "DOCUMENTED",
        "BAS_OBSERVED",
        "UTILITY_DERIVED",
        "ENERGY_CODE_DEFAULT",
        "ENERGYPLUS_AUTOSIZED",
        "RULE_OF_THUMB",
        "INFERRED_FROM_GEOMETRY",
        "INFERRED_FROM_OPERATION",
        "TYPICAL_BUILDING_DEFAULT",
        "USER_ENTERED",
        "UNKNOWN",
    }
)

_FIELD_SOURCE_MAP = {
    "user": "USER_ENTERED",
    "human": "USER_ENTERED",
    "default": "TYPICAL_BUILDING_DEFAULT",
    "vibe19": "BAS_OBSERVED",
    "inferred": "INFERRED_FROM_OPERATION",
    "measured": "MEASURED",
    "documented": "DOCUMENTED",
    "code": "ENERGY_CODE_DEFAULT",
    "energy_code": "ENERGY_CODE_DEFAULT",
    "autosized": "ENERGYPLUS_AUTOSIZED",
    "rule_of_thumb": "RULE_OF_THUMB",
    "missing": "UNKNOWN",
}

# Impact heuristic for risk ranking (no sensitivity sims).
_IMPACT: dict[str, str] = {
    "floor_area_ft2": "HIGH",
    "wwr": "HIGH",
    "wwr_from_idf_pct": "HIGH",
    "infil_mult": "HIGH",
    "lights_w_per_m2": "HIGH",
    "equip_w_per_m2": "HIGH",
    "hvac_system": "HIGH",
    "heating_fuel": "MEDIUM",
    "climate_zone": "MEDIUM",
    "floors": "MEDIUM",
    "shgc": "HIGH",
    "building_type": "MEDIUM",
    "weather_mode": "HIGH",
    "prototype_area_scale": "HIGH",
    "design_oa": "HIGH",
    "occupancy": "HIGH",
    "schedules": "HIGH",
    "setpoints": "HIGH",
    "cooling_capacity": "HIGH",
    "heating_capacity": "HIGH",
    "fan_power": "MEDIUM",
}

_CRITICAL_PARAMS = (
    ("BUILDING", "building_type"),
    ("BUILDING", "floor_area_ft2"),
    ("GEOMETRY", "floors"),
    ("GEOMETRY", "wwr"),
    ("ENVELOPE", "infil_mult"),
    ("ENVELOPE", "shgc"),
    ("INTERNAL_LOADS", "lights_w_per_m2"),
    ("INTERNAL_LOADS", "equip_w_per_m2"),
    ("HVAC", "hvac_system"),
    ("HVAC", "heating_fuel"),
    ("WEATHER", "weather_mode"),
    ("CODE", "climate_zone"),
)


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


def map_field_source(raw: str | None) -> str:
    """Map profile field_sources labels → mission source taxonomy."""
    if not raw:
        return "UNKNOWN"
    key = str(raw).strip().lower()
    if key.upper() in SOURCE_CLASSES:
        return key.upper()
    return _FIELD_SOURCE_MAP.get(key, "UNKNOWN")


def _confidence_for_source(source: str) -> str:
    if source in {"MEASURED", "DOCUMENTED", "BAS_OBSERVED", "UTILITY_DERIVED"}:
        return "HIGH"
    if source in {"USER_ENTERED", "ENERGYPLUS_AUTOSIZED", "INFERRED_FROM_GEOMETRY"}:
        return "MEDIUM"
    if source in {
        "ENERGY_CODE_DEFAULT",
        "RULE_OF_THUMB",
        "TYPICAL_BUILDING_DEFAULT",
        "INFERRED_FROM_OPERATION",
    }:
        return "LOW"
    return "UNKNOWN"


def _impact_for(parameter: str, category: str = "") -> str:
    if parameter in _IMPACT:
        return _IMPACT[parameter]
    cat = category.upper()
    if cat in {"ENVELOPE", "VENTILATION", "SCHEDULES", "CONTROLS"}:
        return "HIGH"
    if cat in {"HVAC", "INTERNAL_LOADS", "GEOMETRY"}:
        return "MEDIUM"
    return "LOW"


def _row(
    *,
    category: str,
    parameter: str,
    value: Any,
    unit: str = "",
    source: str = "UNKNOWN",
    confidence: str | None = None,
    energyplus_object: str = "",
    verification: str = "",
    notes: str = "",
) -> dict[str, Any]:
    src = source if source in SOURCE_CLASSES else map_field_source(source)
    conf = confidence or _confidence_for_source(src)
    missing = value is None or value == "" or value == "—"
    return {
        "category": category,
        "parameter": parameter,
        "value": "—" if missing else value,
        "unit": unit,
        "source": src,
        "confidence": "UNKNOWN" if missing else conf,
        "impact": _impact_for(parameter, category),
        "energyplus_object": energyplus_object,
        "verification": verification or ("NEEDS REVIEW" if missing or conf == "LOW" else "OK"),
        "notes": notes,
        "autosized": src == "ENERGYPLUS_AUTOSIZED",
        "missing": missing,
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
    manifest = (
        _load_json(run_path / "run_manifest.json")
        if run_path and (run_path / "run_manifest.json").is_file()
        else {}
    )

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
        "climate_zone": answers.get("climate_zone")
        or profile.get("climate_zone")
        or meta.get("climate_zone"),
        "code_basis": answers.get("code_basis")
        or profile.get("code_basis")
        or meta.get("code_basis")
        or meta.get("energy_code"),
        "year_built": answers.get("year_built") or profile.get("year_built"),
        "elec_usd_per_kwh": utility.get("elec_usd_per_kwh"),
        "gas_usd_per_therm": utility.get("gas_usd_per_therm"),
    }

    run_block = {
        "run_id": model_eui.get("run_id") or (run_path.name if run_path else None),
        "weather_mode": model_eui.get("weather_mode") or manifest.get("weather_mode"),
        "prototype_area_scale": model_eui.get("prototype_area_scale"),
        "model_eui_kbtu_ft2": model_eui.get("model_eui_kbtu_ft2"),
        "peak_demand_kw": model_eui.get("peak_demand_kw"),
        "idf": str(idf_path) if idf_path else None,
        "g14": g14,
        "hypothesis": meta.get("hypothesis") or meta.get("note") or manifest.get("hypothesis"),
        "energyplus_version": manifest.get("energyplus_version"),
        "model_sha256": manifest.get("model_sha256"),
        "weather_sha256": manifest.get("weather_sha256"),
        "manifest_status": manifest.get("status"),
    }

    return {
        "project": project,
        "geometry": geom_block,
        "loads": loads,
        "hvac": hvac_block,
        "run": run_block,
        "meta": meta,
    }


def _rows_from_field_sources(profile: dict[str, Any]) -> list[dict[str, Any]]:
    fs = profile.get("field_sources") or {}
    rows: list[dict[str, Any]] = []
    for field, meta in sorted(fs.items()):
        if not isinstance(meta, dict):
            rows.append(
                _row(
                    category="PROFILE",
                    parameter=str(field),
                    value=meta,
                    source="UNKNOWN",
                    notes="field_sources scalar",
                )
            )
            continue
        rows.append(
            _row(
                category="PROFILE",
                parameter=str(field),
                value=meta.get("value"),
                unit=str(meta.get("unit") or ""),
                source=map_field_source(meta.get("source")),
                notes=str(meta.get("note") or ""),
            )
        )
    return rows


def _sizing_rows(run_path: Path | None) -> list[dict[str, Any]]:
    if run_path is None or not run_path.is_dir():
        return []
    try:
        from wattlab.energyplus.sizing import parse_sizing_inventory
    except ImportError:
        return []
    try:
        inv = parse_sizing_inventory(run_path)
    except Exception:  # noqa: BLE001 — optional artifact
        return []
    if not isinstance(inv, dict):
        return []
    rows: list[dict[str, Any]] = []
    components = inv.get("components") or inv.get("component_sizing") or []
    for c in list(components)[:25]:
        if not isinstance(c, dict):
            continue
        name = c.get("component") or c.get("name") or c.get("object") or "component"
        field = c.get("field") or c.get("description") or "autosized"
        val = c.get("value") or c.get("user_design") or c.get("calc_design")
        rows.append(
            _row(
                category="SIZING",
                parameter=f"{name}:{field}",
                value=val,
                unit=str(c.get("units") or ""),
                source="ENERGYPLUS_AUTOSIZED",
                energyplus_object=str(name),
                notes="From eplusout.eio / eplustbl sizing inventory",
            )
        )
    plant = inv.get("central_plant") or inv.get("equipment", {}).get("central_plant") or []
    if isinstance(plant, list):
        for p in plant[:10]:
            if not isinstance(p, dict):
                continue
            rows.append(
                _row(
                    category="SIZING",
                    parameter=str(p.get("name") or p.get("equipment") or "plant"),
                    value=p.get("capacity") or p.get("nominal_capacity"),
                    source="ENERGYPLUS_AUTOSIZED",
                    notes="Central plant table",
                )
            )
    return rows


def build_assumption_rows(
    answers: dict[str, Any] | None,
    run_dir: Path | str | None,
    *,
    profile: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Flatten mission-critical inputs with provenance for Twin tables."""
    answers = answers if isinstance(answers, dict) else {}
    profile = profile if isinstance(profile, dict) else {}
    summary = summary or build_model_summary(answers, run_dir, profile=profile)
    proj = summary.get("project") or {}
    geom = summary.get("geometry") or {}
    loads = summary.get("loads") or {}
    hvac = summary.get("hvac") or {}
    run = summary.get("run") or {}
    meta = summary.get("meta") or {}
    run_path = Path(run_dir) if run_dir else None

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(row: dict[str, Any]) -> None:
        key = f"{row['category']}|{row['parameter']}"
        if key in seen:
            return
        seen.add(key)
        rows.append(row)

    # Profile field_sources first (honest provenance)
    for r in _rows_from_field_sources(profile):
        _add(r)

    # Building / project
    for param, val, unit, src, notes in (
        ("building_id", proj.get("building_id"), "", "USER_ENTERED", "answers/profile"),
        ("building_type", proj.get("building_type"), "", "USER_ENTERED", "answers/profile"),
        ("city", proj.get("city"), "", "USER_ENTERED", ""),
        ("climate_zone", proj.get("climate_zone"), "", "ENERGY_CODE_DEFAULT", "reference/default basis only"),
        ("code_basis", proj.get("code_basis"), "", "ENERGY_CODE_DEFAULT", "Not a compliance claim"),
        ("year_built", proj.get("year_built"), "", "DOCUMENTED", ""),
        ("lat", proj.get("lat"), "deg", "USER_ENTERED", ""),
        ("lon", proj.get("lon"), "deg", "USER_ENTERED", ""),
    ):
        _add(_row(category="BUILDING", parameter=param, value=val, unit=unit, source=src, notes=notes))

    # Geometry — answers vs IDF
    _add(
        _row(
            category="GEOMETRY",
            parameter="floor_area_ft2",
            value=geom.get("floor_area_ft2"),
            unit="ft²",
            source="USER_ENTERED" if answers.get("floor_area_ft2") else "INFERRED_FROM_GEOMETRY",
            notes="answers / geo meta / profile",
        )
    )
    _add(
        _row(
            category="GEOMETRY",
            parameter="floors",
            value=geom.get("floors"),
            source="USER_ENTERED" if answers.get("floors") or answers.get("stories") else "UNKNOWN",
        )
    )
    _add(
        _row(
            category="GEOMETRY",
            parameter="wwr",
            value=geom.get("wwr"),
            unit="fraction",
            source="USER_ENTERED" if answers.get("wwr") else "INFERRED_FROM_GEOMETRY",
            notes="answers or geo_build_meta target",
        )
    )
    _add(
        _row(
            category="GEOMETRY",
            parameter="wwr_from_idf_pct",
            value=geom.get("wwr_from_idf_pct"),
            unit="%",
            source="INFERRED_FROM_GEOMETRY",
            energyplus_object="FenestrationSurface:Detailed",
            notes="Parsed from published model.idf",
        )
    )
    _add(
        _row(
            category="GEOMETRY",
            parameter="n_zones",
            value=geom.get("n_zones"),
            source="INFERRED_FROM_GEOMETRY",
            energyplus_object="Zone",
        )
    )
    _add(
        _row(
            category="GEOMETRY",
            parameter="wall_area_m2",
            value=geom.get("wall_area_m2"),
            unit="m²",
            source="INFERRED_FROM_GEOMETRY",
            energyplus_object="BuildingSurface:Detailed",
        )
    )
    _add(
        _row(
            category="GEOMETRY",
            parameter="window_area_m2",
            value=geom.get("window_area_m2"),
            unit="m²",
            source="INFERRED_FROM_GEOMETRY",
            energyplus_object="FenestrationSurface:Detailed",
        )
    )

    # Loads / dials
    _add(
        _row(
            category="INTERNAL_LOADS",
            parameter="lights_w_per_m2",
            value=loads.get("lights_w_per_m2"),
            unit="W/m²",
            source="INFERRED_FROM_OPERATION" if meta.get("lights_w_per_m2") is not None else "UNKNOWN",
            notes="dial_meta / answers",
        )
    )
    _add(
        _row(
            category="INTERNAL_LOADS",
            parameter="equip_w_per_m2",
            value=loads.get("equip_w_per_m2"),
            unit="W/m²",
            source="INFERRED_FROM_OPERATION" if meta.get("equip_w_per_m2") is not None else "UNKNOWN",
            notes="dial_meta / answers",
        )
    )
    _add(
        _row(
            category="ENVELOPE",
            parameter="infil_mult",
            value=loads.get("infil_mult"),
            source="INFERRED_FROM_OPERATION" if meta.get("infil_mult") is not None else "UNKNOWN",
            notes="HIGH IMPACT when guessed — dial_meta",
        )
    )
    _add(
        _row(
            category="ENVELOPE",
            parameter="shgc",
            value=loads.get("shgc"),
            source="INFERRED_FROM_GEOMETRY" if loads.get("shgc") is not None else "UNKNOWN",
            notes="geo/dial SHGC patch if present",
        )
    )

    # HVAC
    _add(
        _row(
            category="HVAC",
            parameter="hvac_system",
            value=hvac.get("hvac_system"),
            source="USER_ENTERED" if answers.get("hvac_system") or profile.get("hvac_system") else "UNKNOWN",
        )
    )
    _add(
        _row(
            category="HVAC",
            parameter="heating_fuel",
            value=hvac.get("heating_fuel"),
            source="USER_ENTERED" if answers.get("heating_fuel") or profile.get("heating_fuel") else "UNKNOWN",
        )
    )
    hints = hvac.get("hints") or {}
    for key, label in (
        ("chiller_electric", "Chiller:Electric count"),
        ("cooling_tower", "CoolingTower count"),
        ("boiler_hotwater", "Boiler:HotWater count"),
        ("airloophvac", "AirLoopHVAC count"),
        ("heatpump", "HeatPump count"),
    ):
        _add(
            _row(
                category="HVAC",
                parameter=key,
                value=hints.get(key),
                source="INFERRED_FROM_GEOMETRY",
                energyplus_object=label,
                notes="IDF inventory hint — not nameplate capacity",
            )
        )

    # Weather / calibration / repro
    g14 = run.get("g14") or {}
    _add(
        _row(
            category="WEATHER",
            parameter="weather_mode",
            value=run.get("weather_mode"),
            source="UTILITY_DERIVED" if run.get("weather_mode") else "UNKNOWN",
            notes="TMY vs AMY from report/manifest",
        )
    )
    _add(
        _row(
            category="CALIBRATION",
            parameter="model_eui_kbtu_ft2",
            value=run.get("model_eui_kbtu_ft2"),
            unit="kBtu/ft²-yr",
            source="UTILITY_DERIVED",
            notes="From published report.json",
        )
    )
    _add(
        _row(
            category="CALIBRATION",
            parameter="prototype_area_scale",
            value=run.get("prototype_area_scale"),
            source="INFERRED_FROM_GEOMETRY",
        )
    )
    _add(
        _row(
            category="CALIBRATION",
            parameter="nmbe_elec_pct",
            value=g14.get("nmbe_elec_pct"),
            unit="%",
            source="UTILITY_DERIVED",
            notes="G14 scorecard",
        )
    )
    _add(
        _row(
            category="CALIBRATION",
            parameter="cvrmse_elec_pct",
            value=g14.get("cvrmse_elec_pct"),
            unit="%",
            source="UTILITY_DERIVED",
            notes="G14 scorecard",
        )
    )
    _add(
        _row(
            category="REPRO",
            parameter="energyplus_version",
            value=run.get("energyplus_version"),
            source="DOCUMENTED",
            notes="run_manifest.json",
        )
    )
    _add(
        _row(
            category="REPRO",
            parameter="model_sha256",
            value=run.get("model_sha256"),
            source="DOCUMENTED",
            notes="run_manifest.json",
        )
    )

    for r in _sizing_rows(run_path):
        _add(r)

    # Conditioned vs gross sanity note
    area = geom.get("floor_area_ft2")
    if isinstance(area, (int, float)) and area > 0:
        _add(
            _row(
                category="GEOMETRY",
                parameter="conditioned_area_ft2",
                value=area,
                unit="ft²",
                source="UNKNOWN",
                confidence="LOW",
                notes="No separate conditioned area stamp — using gross/model area as proxy",
                verification="NEEDS REVIEW",
            )
        )

    return rows


def build_model_at_a_glance(
    summary: dict[str, Any],
    rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Level-1 engineer snapshot (~30 seconds)."""
    proj = summary.get("project") or {}
    geom = summary.get("geometry") or {}
    hvac = summary.get("hvac") or {}
    run = summary.get("run") or {}
    loads = summary.get("loads") or {}
    g14 = run.get("g14") or {}
    rows = rows or []
    low_conf = sum(1 for r in rows if str(r.get("confidence")).upper() == "LOW")
    missing = sum(1 for r in rows if r.get("missing"))
    pass_fail = g14.get("pass_fail")
    if pass_fail:
        cal = f"G14 {pass_fail}"
    elif run.get("model_eui_kbtu_ft2") is not None:
        cal = "preliminary (EUI present)"
    else:
        cal = "none"

    wwr = geom.get("wwr_from_idf_pct")
    if wwr is None and geom.get("wwr") is not None:
        try:
            w = float(geom["wwr"])
            wwr = round(100.0 * w, 1) if w <= 1.0 else round(w, 1)
        except (TypeError, ValueError):
            wwr = geom.get("wwr")

    return {
        "building_type": proj.get("building_type"),
        "year_built": proj.get("year_built"),
        "location": proj.get("city"),
        "code_basis": proj.get("code_basis") or "— (reference/default only; not a compliance claim)",
        "climate_zone": proj.get("climate_zone"),
        "weather": run.get("weather_mode"),
        "gross_floor_area_ft2": geom.get("floor_area_ft2"),
        "floors": geom.get("floors"),
        "wwr_pct": wwr,
        "n_zones": geom.get("n_zones"),
        "primary_hvac": hvac.get("hvac_system"),
        "heating": hvac.get("heating_fuel"),
        "lights_w_per_m2": loads.get("lights_w_per_m2"),
        "equip_w_per_m2": loads.get("equip_w_per_m2"),
        "infil_mult": loads.get("infil_mult"),
        "calibration": cal,
        "energyplus_version": run.get("energyplus_version"),
        "run_id": run.get("run_id"),
        "model_eui_kbtu_ft2": run.get("model_eui_kbtu_ft2"),
        "low_confidence_inputs": low_conf,
        "missing_critical_inputs": missing,
        "hypothesis": run.get("hypothesis"),
    }


def rank_assumption_risk(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """HIGH impact × LOW/UNKNOWN confidence first."""
    ranked = []
    for r in rows:
        impact = str(r.get("impact") or "LOW").upper()
        conf = str(r.get("confidence") or "UNKNOWN").upper()
        if impact == "HIGH" and conf in {"LOW", "UNKNOWN"}:
            bucket = "HIGH IMPACT / LOW CONFIDENCE"
            order = 0
        elif impact == "HIGH":
            bucket = "HIGH IMPACT / HIGH CONFIDENCE"
            order = 1
        elif conf in {"LOW", "UNKNOWN"}:
            bucket = "LOW IMPACT / LOW CONFIDENCE"
            order = 2
        else:
            bucket = "LOW IMPACT / HIGH CONFIDENCE"
            order = 3
        ranked.append({**r, "risk_bucket": bucket, "_order": order})
    ranked.sort(key=lambda x: (x["_order"], x.get("parameter") or ""))
    for r in ranked:
        r.pop("_order", None)
    return ranked


def missing_critical_inputs(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What we still don't know — critical params missing or UNKNOWN."""
    by_param = {r["parameter"]: r for r in rows}
    out: list[dict[str, Any]] = []
    for category, param in _CRITICAL_PARAMS:
        r = by_param.get(param)
        if r is None or r.get("missing") or str(r.get("confidence")).upper() in {"LOW", "UNKNOWN"}:
            out.append(
                {
                    "parameter": param,
                    "category": category,
                    "importance": _impact_for(param, category),
                    "current_fallback": (r or {}).get("value", "—"),
                    "confidence": (r or {}).get("confidence", "UNKNOWN"),
                    "how_to_improve": _how_to_improve(param),
                }
            )
    # Also any other HIGH impact missing
    for r in rows:
        if not r.get("missing"):
            continue
        if r["parameter"] in {p for _, p in _CRITICAL_PARAMS}:
            continue
        if str(r.get("impact")).upper() != "HIGH":
            continue
        out.append(
            {
                "parameter": r["parameter"],
                "category": r.get("category"),
                "importance": "HIGH",
                "current_fallback": r.get("value"),
                "confidence": r.get("confidence"),
                "how_to_improve": _how_to_improve(str(r["parameter"])),
            }
        )
    return out


def _how_to_improve(param: str) -> str:
    hints = {
        "wwr": "As-built drawings / takeoff; confirm geo-idf WWR target vs IDF fenestration",
        "infil_mult": "Blower-door / calibration; avoid leaving prototype default unlabeled",
        "lights_w_per_m2": "Lighting inventory or dial-loads from measured LPD",
        "equip_w_per_m2": "Plug-load audit or submeter; stamp dial_meta",
        "hvac_system": "Mechanical schedules / nameplates; answers.json hvac_system",
        "design_oa": "TAB report / BAS OA flow; do not treat code min as measured",
        "floor_area_ft2": "Rentable/gross drawings; answers floor_area_ft2",
        "climate_zone": "ASHRAE climate map for site lat/lon",
        "weather_mode": "Publish AMY vs TMY on run report",
        "shgc": "Window schedule / NFRC; geo SHGC patch meta",
        "building_type": "Confirm property type in answers (drives defaults)",
        "floors": "Site survey / drawings",
        "heating_fuel": "Utility accounts / plant nameplates",
    }
    return hints.get(param, "Obtain documented value; re-publish run with meta stamps")


def filter_assumption_rows(
    rows: list[dict[str, Any]],
    *,
    mode: str = "ALL",
) -> list[dict[str, Any]]:
    mode = (mode or "ALL").upper().replace(" ", "_")
    if mode in {"ALL", ""}:
        return list(rows)
    if mode == "LOW_CONFIDENCE":
        return [r for r in rows if str(r.get("confidence")).upper() in {"LOW", "UNKNOWN"}]
    if mode == "AUTOSIZED":
        return [r for r in rows if r.get("autosized") or r.get("source") == "ENERGYPLUS_AUTOSIZED"]
    if mode == "CODE_DEFAULT":
        return [
            r
            for r in rows
            if r.get("source") in {"ENERGY_CODE_DEFAULT", "TYPICAL_BUILDING_DEFAULT"}
        ]
    if mode == "NEEDS_REVIEW":
        return [r for r in rows if str(r.get("verification")).upper() == "NEEDS REVIEW" or r.get("missing")]
    return list(rows)


def render_model_summary_panel(summary: dict[str, Any], rows: list[dict[str, Any]] | None = None) -> None:
    """Streamlit Model-at-a-Glance + filterable assumptions table."""
    import pandas as pd
    import streamlit as st

    rows = rows if rows is not None else []
    glance = build_model_at_a_glance(summary, rows)
    risk = rank_assumption_risk(rows)
    missing = missing_critical_inputs(rows)

    st.caption(
        "Read-only snapshot from the **actual published run** (model.idf + dial/geo meta + "
        "answers/profile). Missing fields show as —. "
        "Code/reference basis is **not** a compliance claim. "
        "Full dump-gap provenance also on the Assumption Ledger page."
    )

    st.markdown("#### Model at a glance")
    g1, g2, g3, g4 = st.columns(4)
    g1.metric("Gross area (ft²)", _dash(glance.get("gross_floor_area_ft2")))
    g2.metric("Floors", _dash(glance.get("floors")))
    g3.metric("WWR %", _dash(glance.get("wwr_pct")))
    g4.metric("Low-confidence inputs", glance.get("low_confidence_inputs") or 0)
    glance_table = [
        {"Item": k.replace("_", " ").title(), "Value": _dash(v)}
        for k, v in glance.items()
        if k not in {"low_confidence_inputs", "missing_critical_inputs"}
    ]
    st.dataframe(pd.DataFrame(glance_table), width="stretch", hide_index=True, height=280)

    hi_low = [r for r in risk if r.get("risk_bucket") == "HIGH IMPACT / LOW CONFIDENCE"]
    st.markdown("#### Assumption risk (high impact × low confidence)")
    if hi_low:
        st.dataframe(
            pd.DataFrame(hi_low)[
                [c for c in ("parameter", "value", "unit", "source", "confidence", "impact", "notes") if c in hi_low[0]]
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.caption("No HIGH IMPACT / LOW CONFIDENCE rows in this snapshot.")

    st.markdown("#### What we still don’t know")
    if missing:
        st.dataframe(pd.DataFrame(missing), width="stretch", hide_index=True)
    else:
        st.caption("Critical Level-1 parameters appear populated.")

    st.markdown("#### Mission-critical inputs")
    mode = st.selectbox(
        "Filter",
        options=["ALL", "LOW CONFIDENCE", "AUTOSIZED", "CODE DEFAULT", "NEEDS REVIEW"],
        key="twin_assumption_filter",
    )
    filtered = filter_assumption_rows(rows, mode=mode)
    show_cols = [
        "category",
        "parameter",
        "value",
        "unit",
        "source",
        "confidence",
        "impact",
        "energyplus_object",
        "verification",
        "notes",
    ]
    if filtered:
        df = pd.DataFrame(filtered)
        cols = [c for c in show_cols if c in df.columns]
        st.dataframe(df[cols], width="stretch", hide_index=True, height=360)
    else:
        st.caption("No rows for this filter.")
