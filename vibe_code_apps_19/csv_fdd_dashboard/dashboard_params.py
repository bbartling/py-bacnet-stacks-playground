"""Tunable fault-detection parameters for the Building 100 dashboard."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULTS_PATH = ROOT / "fault_tune_defaults.json"
SESSION_PATH = ROOT / "analyst_session.json"

# Each param: label, unit, min, max, step, pages (page_id list), group
PARAM_DEFS: dict[str, dict[str, Any]] = {
    "comfort_setpoint_f": {
        "label": "Comfort setpoint",
        "unit": "°F",
        "min": 68,
        "max": 76,
        "step": 0.5,
        "default": 72.0,
        "pages": ["index", "zones"],
        "group": "Comfort",
    },
    "comfort_band_f": {
        "label": "Comfort band (±)",
        "unit": "°F",
        "min": 1,
        "max": 4,
        "step": 0.5,
        "default": 2.0,
        "pages": ["index", "zones"],
        "group": "Comfort",
    },
    "unocc_zone_lo_f": {
        "label": "Unoccupied zone low",
        "unit": "°F",
        "min": 65,
        "max": 72,
        "step": 0.5,
        "default": 70.0,
        "pages": ["index", "excess_runtime"],
        "group": "Excess fan",
    },
    "unocc_zone_hi_f": {
        "label": "Unoccupied zone high",
        "unit": "°F",
        "min": 72,
        "max": 78,
        "step": 0.5,
        "default": 75.0,
        "pages": ["index", "excess_runtime"],
        "group": "Excess fan",
    },
    "unocc_zone_pct": {
        "label": "Zones satisfied fraction",
        "unit": "%",
        "min": 50,
        "max": 100,
        "step": 5,
        "default": 80.0,
        "pages": ["index", "excess_runtime"],
        "group": "Excess fan",
    },
    "weather_fault_delta_f": {
        "label": "BAS vs Open-Meteo fault |Δ|",
        "unit": "°F",
        "min": 2,
        "max": 15,
        "step": 0.5,
        "default": 5.0,
        "pages": ["weather"],
        "group": "Weather",
    },
    "mix_tol_f": {
        "label": "Mixed-air tolerance (FC2–FC13)",
        "unit": "°F",
        "min": 0.5,
        "max": 3.0,
        "step": 0.05,
        "default": 1.15,
        "pages": ["ahu_1", "ahu_2", "economizer"],
        "group": "AHU economizer",
    },
    "supply_tol_f": {
        "label": "Supply-air tolerance",
        "unit": "°F",
        "min": 0.5,
        "max": 3.0,
        "step": 0.05,
        "default": 1.15,
        "pages": ["ahu_1", "ahu_2", "economizer"],
        "group": "AHU economizer",
    },
    "fan_hi_pct": {
        "label": "FC1 high fan speed",
        "unit": "%",
        "min": 70,
        "max": 95,
        "step": 1,
        "default": 87.0,
        "pages": ["ahu_1", "ahu_2"],
        "group": "AHU faults",
    },
    "duct_static_err_inwc": {
        "label": "FC1 duct static error",
        "unit": "in. w.c.",
        "min": 0.05,
        "max": 0.5,
        "step": 0.01,
        "default": 0.20,
        "pages": ["ahu_1", "ahu_2"],
        "group": "AHU faults",
    },
    "free_cool_chw_min_pct": {
        "label": "Free-cool opp. CHW min",
        "unit": "%",
        "min": 5,
        "max": 40,
        "step": 1,
        "default": 20.0,
        "pages": ["index", "economizer"],
        "group": "Free cooling",
    },
    "free_cool_oat_cap_f": {
        "label": "Free-cool OAT cap",
        "unit": "°F",
        "min": 50,
        "max": 70,
        "step": 1,
        "default": 60.0,
        "pages": ["index", "economizer"],
        "group": "Free cooling",
    },
    "chiller_free_cool_oat_f": {
        "label": "Chiller excess OAT threshold",
        "unit": "°F",
        "min": 45,
        "max": 65,
        "step": 1,
        "default": 55.0,
        "pages": ["index", "central_plant", "economizer"],
        "group": "Central plant",
    },
    "free_cool_dp_max_f": {
        "label": "Free-cool avail. dew point max",
        "unit": "°F",
        "min": 50,
        "max": 65,
        "step": 1,
        "default": 60.0,
        "pages": ["index", "economizer"],
        "group": "Free cooling",
    },
    "free_cool_oat_avail_f": {
        "label": "Free-cool avail. OAT max",
        "unit": "°F",
        "min": 65,
        "max": 78,
        "step": 1,
        "default": 72.0,
        "pages": ["index", "economizer"],
        "group": "Free cooling",
    },
    "chw_low_delta_t_f": {
        "label": "Chiller low ΔT",
        "unit": "°F",
        "min": 2,
        "max": 8,
        "step": 0.5,
        "default": 4.0,
        "pages": ["central_plant"],
        "group": "Central plant",
    },
    "boiler_warm_oat_f": {
        "label": "Boiler warm-weather OAT",
        "unit": "°F",
        "min": 50,
        "max": 70,
        "step": 1,
        "default": 60.0,
        "pages": ["central_plant"],
        "group": "Central plant",
    },
    "fault_persist_minutes": {
        "label": "Fault persistence",
        "unit": "min",
        "min": 5,
        "max": 60,
        "step": 5,
        "default": 10.0,
        "pages": ["weather", "ahu_1", "ahu_2", "economizer", "central_plant"],
        "group": "Global",
    },
    "flatline_tol_f": {
        "label": "SV6 flatline tolerance",
        "unit": "°F",
        "min": 0.05,
        "max": 0.5,
        "step": 0.05,
        "default": 0.10,
        "pages": ["ahu_1", "ahu_2"],
        "group": "Sensor QA",
    },
    "spike_limit_f": {
        "label": "SV7 spike limit (15 min)",
        "unit": "°F",
        "min": 5,
        "max": 25,
        "step": 1,
        "default": 16.0,
        "pages": ["ahu_1", "ahu_2"],
        "group": "Sensor QA",
    },
}

PAGE_IDS = [
    "index",
    "zones",
    "weather",
    "ahu_1",
    "ahu_2",
    "economizer",
    "economizer_diagnostics",
    "central_plant",
    "excess_runtime",
]

PAGE_TITLES = {
    "index": "Overview",
    "zones": "Zones & Comfort",
    "weather": "Weather Sensors",
    "ahu_1": "AHU 1",
    "ahu_2": "AHU 2",
    "economizer": "Economizer / Free Cooling",
    "economizer_diagnostics": "Economizer Diagnostics",
    "central_plant": "Central Plant",
    "excess_runtime": "Excess Fan Runtime",
}


def default_params() -> dict[str, float]:
    return {k: float(v["default"]) for k, v in PARAM_DEFS.items()}


def params_for_page(page_id: str) -> list[dict[str, Any]]:
    out = []
    for key, meta in PARAM_DEFS.items():
        if page_id in meta["pages"]:
            out.append({"key": key, **meta})
    return out


def merge_params(overrides: dict[str, Any] | None) -> dict[str, float]:
    merged = default_params()
    if overrides:
        for k, v in overrides.items():
            if k in merged and v is not None:
                merged[k] = float(v)
    return merged


def clamp_param(key: str, value: float) -> float:
    meta = PARAM_DEFS[key]
    return max(float(meta["min"]), min(float(meta["max"]), float(value)))


def validate_params(params: dict[str, Any]) -> dict[str, float]:
    return {k: clamp_param(k, v) for k, v in merge_params(params).items()}


def apply_to_generate_dashboard(gd_module, params: dict[str, float]) -> None:
    """Push tuned values into generate_dashboard module globals."""
    p = validate_params(params)
    gd_module.COMFORT_SETPOINT_F = p["comfort_setpoint_f"]
    gd_module.COMFORT_BAND_F = p["comfort_band_f"]
    gd_module.COMFORT_LO_F = p["comfort_setpoint_f"] - p["comfort_band_f"]
    gd_module.COMFORT_HI_F = p["comfort_setpoint_f"] + p["comfort_band_f"]
    gd_module.UNOCC_ZONE_LO_F = p["unocc_zone_lo_f"]
    gd_module.UNOCC_ZONE_HI_F = p["unocc_zone_hi_f"]
    gd_module.UNOCC_ZONE_PCT = p["unocc_zone_pct"] / 100.0
    gd_module.WEATHER_FAULT_DELTA_F = p["weather_fault_delta_f"]
    gd_module.MIX_TOL = p["mix_tol_f"]
    gd_module.SUPPLY_TOL = p["supply_tol_f"]
    gd_module.FAN_HI = p["fan_hi_pct"] / 100.0
    gd_module.DUCT_STATIC_ERR = p["duct_static_err_inwc"]
    gd_module.FREE_COOL_CHW_MIN = p["free_cool_chw_min_pct"] / 100.0
    gd_module.FREE_COOL_OAT_CAP_F = p["free_cool_oat_cap_f"]
    gd_module.CHILLER_FREE_COOL_OAT_F = p["chiller_free_cool_oat_f"]
    gd_module.FREE_COOL_DP_MAX_F = p["free_cool_dp_max_f"]
    gd_module.FREE_COOL_OAT_AVAIL_F = p["free_cool_oat_avail_f"]
    gd_module.CHW_LOW_DELTA_T = p["chw_low_delta_t_f"]
    gd_module.BOILER_WARM_OAT_F = p["boiler_warm_oat_f"]
    gd_module.FAULT_PERSIST_SEC = int(p["fault_persist_minutes"] * 60)
    gd_module.FLATLINE_TOL = p["flatline_tol_f"]
    gd_module.SPIKE_LIMIT = p["spike_limit_f"]


def params_summary_html(params: dict[str, float], page_id: str | None = None) -> str:
    rows = []
    for key, meta in PARAM_DEFS.items():
        if page_id and page_id not in meta["pages"]:
            continue
        val = params.get(key, meta["default"])
        unit = meta["unit"]
        rows.append(
            f"<tr><td>{meta['label']}</td><td><strong>{val:g}</strong> {unit}</td></tr>"
        )
    if not rows:
        return ""
    return (
        "<details class='tune-summary'><summary>Tuned fault parameters</summary>"
        f"<table><thead><tr><th>Parameter</th><th>Value</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></details>"
    )


def load_session() -> dict[str, Any]:
    if SESSION_PATH.exists():
        data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        data["params"] = validate_params(data.get("params", {}))
        data.setdefault("notes", {})
        data.setdefault("analyst_name", "")
        data.setdefault("package_title", "Building 100 RCx Dashboard")
        return data
    return {
        "params": default_params(),
        "notes": {},
        "analyst_name": "",
        "package_title": "Building 100 RCx Dashboard",
    }


def save_session(session: dict[str, Any]) -> None:
    payload = deepcopy(session)
    payload["params"] = validate_params(payload.get("params", {}))
    SESSION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_defaults_file() -> None:
    payload = {
        "schema_version": "1.0",
        "description": "Default fault tune parameters for Building 100 dashboard",
        "params": default_params(),
        "param_defs": {
            k: {kk: vv for kk, vv in v.items() if kk != "pages"}
            | {"pages": v["pages"]}
            for k, v in PARAM_DEFS.items()
        },
    }
    DEFAULTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
