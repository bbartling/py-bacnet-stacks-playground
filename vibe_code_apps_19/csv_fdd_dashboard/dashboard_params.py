"""Tunable fault-detection parameters — one slider per rule threshold (Open-FDD cookbook parity)."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DEFAULTS_PATH = ROOT / "fault_tune_defaults.json"
SESSION_PATH = ROOT / "analyst_session.json"

# rule: Open-FDD rule id shown on grouped slider box
# group: section title inside the box
# pages: dashboard pages where this slider appears
PARAM_DEFS: dict[str, dict[str, Any]] = {
    # --- Global ---
    "fault_persist_minutes": {
        "label": "Fault confirmation delay",
        "unit": "min",
        "min": 5,
        "max": 60,
        "step": 5,
        "default": 10.0,
        "rule": "GLOBAL",
        "group": "All rules",
        "pages": ["index", "weather", "ahu_1", "ahu_2", "economizer", "economizer_diagnostics", "central_plant", "zones", "excess_runtime"],
    },
    # --- Comfort / zones ---
    "comfort_setpoint_f": {
        "label": "Comfort setpoint",
        "unit": "°F",
        "min": 68,
        "max": 76,
        "step": 0.5,
        "default": 72.0,
        "rule": "COMFORT",
        "group": "Zone comfort",
        "pages": ["index", "zones"],
    },
    "comfort_band_f": {
        "label": "Comfort band (±)",
        "unit": "°F",
        "min": 1,
        "max": 4,
        "step": 0.5,
        "default": 2.0,
        "rule": "COMFORT",
        "group": "Zone comfort",
        "pages": ["index", "zones"],
    },
    "zone_temp_lo_f": {
        "label": "SV-1 zone temp low",
        "unit": "°F",
        "min": 50,
        "max": 65,
        "step": 1,
        "default": 55.0,
        "rule": "SV-1",
        "group": "Sensor validation",
        "pages": ["zones", "ahu_1", "ahu_2"],
    },
    "zone_temp_hi_f": {
        "label": "SV-1 zone temp high",
        "unit": "°F",
        "min": 85,
        "max": 95,
        "step": 1,
        "default": 90.0,
        "rule": "SV-1",
        "group": "Sensor validation",
        "pages": ["zones", "ahu_1", "ahu_2"],
    },
    # --- Weather ---
    "weather_fault_delta_f": {
        "label": "WS — BAS vs Open-Meteo |Δ|",
        "unit": "°F",
        "min": 2,
        "max": 15,
        "step": 0.5,
        "default": 5.0,
        "rule": "WS-OAT",
        "group": "Weather station",
        "pages": ["weather", "economizer_diagnostics"],
    },
    "oat_hard_lo_f": {
        "label": "SV-2 OAT hard low",
        "unit": "°F",
        "min": -50,
        "max": 50,
        "step": 1,
        "default": -40.0,
        "rule": "SV-2",
        "group": "Sensor validation",
        "pages": ["weather", "ahu_1", "ahu_2"],
    },
    "oat_hard_hi_f": {
        "label": "SV-2 OAT hard high",
        "unit": "°F",
        "min": 100,
        "max": 140,
        "step": 1,
        "default": 130.0,
        "rule": "SV-2",
        "group": "Sensor validation",
        "pages": ["weather", "ahu_1", "ahu_2"],
    },
    # --- Sensor validation ---
    "mix_tol_f": {
        "label": "SV-4 / FC2–FC13 mixed-air tolerance",
        "unit": "°F",
        "min": 0.5,
        "max": 3.0,
        "step": 0.05,
        "default": 1.15,
        "rule": "SV-4",
        "group": "MAT envelope",
        "pages": ["ahu_1", "ahu_2", "economizer", "economizer_diagnostics"],
    },
    "flatline_window_hours": {
        "label": "SV-6 flatline window",
        "unit": "h",
        "min": 1,
        "max": 8,
        "step": 0.5,
        "default": 4.0,
        "rule": "SV-6",
        "group": "Flatline (stuck sensor)",
        "pages": ["ahu_1", "ahu_2", "economizer_diagnostics"],
    },
    "flatline_tol_f": {
        "label": "SV-6 flatline tolerance",
        "unit": "°F",
        "min": 0.05,
        "max": 0.5,
        "step": 0.05,
        "default": 0.10,
        "rule": "SV-6",
        "group": "Flatline (stuck sensor)",
        "pages": ["ahu_1", "ahu_2", "economizer_diagnostics"],
    },
    "spike_limit_oat_f": {
        "label": "SV-7 OAT/MAT spike limit",
        "unit": "°F",
        "min": 5,
        "max": 25,
        "step": 1,
        "default": 16.0,
        "rule": "SV-7",
        "group": "Rate-of-change spike",
        "pages": ["ahu_1", "ahu_2", "weather"],
    },
    "spike_limit_zone_f": {
        "label": "SV-7 zone temp spike limit",
        "unit": "°F",
        "min": 2,
        "max": 15,
        "step": 0.5,
        "default": 5.0,
        "rule": "SV-7",
        "group": "Rate-of-change spike",
        "pages": ["zones", "ahu_1", "ahu_2"],
    },
    # --- FC1 ---
    "fan_hi_pct": {
        "label": "FC1 high fan speed",
        "unit": "%",
        "min": 70,
        "max": 95,
        "step": 1,
        "default": 87.0,
        "rule": "FC1",
        "group": "Duct static at full fan",
        "pages": ["ahu_1", "ahu_2"],
    },
    "duct_static_err_inwc": {
        "label": "FC1 duct static error",
        "unit": "in. w.c.",
        "min": 0.05,
        "max": 0.5,
        "step": 0.01,
        "default": 0.20,
        "rule": "FC1",
        "group": "Duct static at full fan",
        "pages": ["ahu_1", "ahu_2"],
    },
    # --- FC2 / FC3 ---
    "fc23_confirm_minutes": {
        "label": "FC2 / FC3 confirmation",
        "unit": "min",
        "min": 5,
        "max": 30,
        "step": 5,
        "default": 10.0,
        "rule": "FC2",
        "group": "MAT below OAT/RAT envelope",
        "pages": ["ahu_1", "ahu_2", "economizer"],
    },
    # --- FC4 hunting ---
    "fc4_confirm_minutes": {
        "label": "FC4 confirmation",
        "unit": "min",
        "min": 30,
        "max": 120,
        "step": 15,
        "default": 60.0,
        "rule": "FC4",
        "group": "PID / command hunting",
        "pages": ["ahu_1", "ahu_2"],
    },
    "fc4_reversals_per_h": {
        "label": "FC4 reversals per hour",
        "unit": "count",
        "min": 3,
        "max": 12,
        "step": 1,
        "default": 6.0,
        "rule": "FC4",
        "group": "PID / command hunting",
        "pages": ["ahu_1", "ahu_2"],
    },
    "fc4_p2p_pct": {
        "label": "FC4 peak-to-peak swing",
        "unit": "%",
        "min": 5,
        "max": 25,
        "step": 1,
        "default": 10.0,
        "rule": "FC4",
        "group": "PID / command hunting",
        "pages": ["ahu_1", "ahu_2"],
    },
    "fc4_command_deadband_pct": {
        "label": "FC4 command deadband",
        "unit": "%",
        "min": 1,
        "max": 10,
        "step": 0.5,
        "default": 3.0,
        "rule": "FC4",
        "group": "PID / command hunting",
        "pages": ["ahu_1", "ahu_2"],
    },
    "ahu_min_oa_dpr_pct": {
        "label": "Min OA damper (FC4 / FC8–13)",
        "unit": "%",
        "min": 0,
        "max": 15,
        "step": 1,
        "default": 5.0,
        "rule": "FC4",
        "group": "Operating modes",
        "pages": ["ahu_1", "ahu_2", "economizer", "economizer_diagnostics"],
    },
    # --- FC8–FC13 ---
    "supply_tol_f": {
        "label": "FC8–FC13 supply-air tolerance",
        "unit": "°F",
        "min": 0.5,
        "max": 3.0,
        "step": 0.05,
        "default": 1.15,
        "rule": "FC8",
        "group": "Economizer mechanical faults",
        "pages": ["ahu_1", "ahu_2", "economizer", "economizer_diagnostics"],
    },
    "delta_supply_fan_f": {
        "label": "FC8–FC13 SAT fan delta",
        "unit": "°F",
        "min": 0.2,
        "max": 2.0,
        "step": 0.05,
        "default": 0.55,
        "rule": "FC8",
        "group": "Economizer mechanical faults",
        "pages": ["ahu_1", "ahu_2", "economizer"],
    },
    "fc813_confirm_minutes": {
        "label": "FC8–FC13 confirmation",
        "unit": "min",
        "min": 5,
        "max": 30,
        "step": 5,
        "default": 10.0,
        "rule": "FC8",
        "group": "Economizer mechanical faults",
        "pages": ["ahu_1", "ahu_2", "economizer"],
    },
    "fc13_sat_deadband_f": {
        "label": "FC13 SAT above setpoint",
        "unit": "°F",
        "min": 0.5,
        "max": 3.0,
        "step": 0.25,
        "default": 1.0,
        "rule": "FC13",
        "group": "Full cooling SAT",
        "pages": ["ahu_1", "ahu_2", "economizer"],
    },
    # --- Free cooling / economizer availability ---
    "free_cool_dp_max_f": {
        "label": "Free-cool avail. dew point max",
        "unit": "°F",
        "min": 50,
        "max": 65,
        "step": 1,
        "default": 60.0,
        "rule": "ECON-AVAIL",
        "group": "Open-Meteo free-cool gate",
        "pages": ["index", "economizer", "economizer_diagnostics", "ahu_1", "ahu_2", "central_plant"],
    },
    "free_cool_oat_avail_f": {
        "label": "Free-cool avail. OAT max",
        "unit": "°F",
        "min": 65,
        "max": 78,
        "step": 1,
        "default": 72.0,
        "rule": "ECON-AVAIL",
        "group": "Open-Meteo free-cool gate",
        "pages": ["index", "economizer", "economizer_diagnostics", "ahu_1", "ahu_2", "central_plant"],
    },
    "economizer_low_limit_f": {
        "label": "Economizer min Open-Meteo OAT",
        "unit": "°F",
        "min": 25,
        "max": 45,
        "step": 1,
        "default": 35.0,
        "rule": "ECON-AVAIL",
        "group": "Open-Meteo free-cool gate",
        "pages": ["economizer", "economizer_diagnostics", "ahu_1", "ahu_2", "index"],
    },
    "free_cool_chw_min_pct": {
        "label": "ECON-3 / free-cool CHW min",
        "unit": "%",
        "min": 5,
        "max": 40,
        "step": 1,
        "default": 20.0,
        "rule": "ECON-3",
        "group": "Mechanical cooling during free cool",
        "pages": ["index", "economizer", "economizer_diagnostics", "ahu_1", "ahu_2"],
    },
    "oa_min_expected_pct": {
        "label": "ECON-2 min OA damper",
        "unit": "%",
        "min": 10,
        "max": 40,
        "step": 1,
        "default": 20.0,
        "rule": "ECON-2",
        "group": "Ventilation / leakage",
        "pages": ["economizer", "economizer_diagnostics", "ahu_1", "ahu_2"],
    },
    "oa_max_economizer_pct": {
        "label": "Full economizer OA damper",
        "unit": "%",
        "min": 80,
        "max": 100,
        "step": 1,
        "default": 95.0,
        "rule": "ECON-3",
        "group": "Mechanical cooling during free cool",
        "pages": ["economizer", "economizer_diagnostics", "ahu_1", "ahu_2"],
    },
    "oat_favorable_delta_f": {
        "label": "ECON favorable OAT delta",
        "unit": "°F",
        "min": 1,
        "max": 8,
        "step": 0.5,
        "default": 3.0,
        "rule": "ECON-1",
        "group": "Economizer diagnostics",
        "pages": ["economizer_diagnostics"],
    },
    "damper_deadband_pct": {
        "label": "OA damper deadband",
        "unit": "%",
        "min": 2,
        "max": 15,
        "step": 1,
        "default": 8.0,
        "rule": "ECON-DMP",
        "group": "Economizer diagnostics",
        "pages": ["economizer_diagnostics"],
    },
    "damper_stuck_tol_pct": {
        "label": "Damper stuck tolerance",
        "unit": "%",
        "min": 2,
        "max": 15,
        "step": 1,
        "default": 5.0,
        "rule": "ECON-DMP",
        "group": "Economizer diagnostics",
        "pages": ["economizer_diagnostics"],
    },
    "mat_residual_db_f": {
        "label": "MAT residual deadband",
        "unit": "°F",
        "min": 1,
        "max": 5,
        "step": 0.25,
        "default": 2.5,
        "rule": "ECON-MAT",
        "group": "Economizer diagnostics",
        "pages": ["economizer_diagnostics"],
    },
    "temp_deadband_f": {
        "label": "Temperature deadband",
        "unit": "°F",
        "min": 0.5,
        "max": 5,
        "step": 0.25,
        "default": 2.0,
        "rule": "ECON-MAT",
        "group": "Economizer diagnostics",
        "pages": ["economizer_diagnostics"],
    },
    "oat_rat_min_delta_f": {
        "label": "OAT vs RAT min split",
        "unit": "°F",
        "min": 2,
        "max": 10,
        "step": 0.5,
        "default": 5.0,
        "rule": "ECON-MAT",
        "group": "Economizer diagnostics",
        "pages": ["economizer_diagnostics"],
    },
    "gap_max_samples": {
        "label": "Max data gap samples",
        "unit": "samples",
        "min": 1,
        "max": 12,
        "step": 1,
        "default": 4.0,
        "rule": "DATA-QA",
        "group": "Data quality",
        "pages": ["economizer_diagnostics"],
    },
    # --- Excess fan ---
    "unocc_zone_lo_f": {
        "label": "Unoccupied zone low",
        "unit": "°F",
        "min": 65,
        "max": 72,
        "step": 0.5,
        "default": 70.0,
        "rule": "EXCESS-FAN",
        "group": "Unoccupied fan runtime",
        "pages": ["index", "excess_runtime", "motor_runtime"],
    },
    "unocc_zone_hi_f": {
        "label": "Unoccupied zone high",
        "unit": "°F",
        "min": 72,
        "max": 78,
        "step": 0.5,
        "default": 75.0,
        "rule": "EXCESS-FAN",
        "group": "Unoccupied fan runtime",
        "pages": ["index", "excess_runtime", "motor_runtime"],
    },
    "unocc_zone_pct": {
        "label": "Zones satisfied fraction",
        "unit": "%",
        "min": 50,
        "max": 100,
        "step": 5,
        "default": 80.0,
        "rule": "EXCESS-FAN",
        "group": "Unoccupied fan runtime",
        "pages": ["index", "excess_runtime", "motor_runtime"],
    },
    # --- Central plant ---
    "chw_low_delta_t_f": {
        "label": "Chiller low ΔT",
        "unit": "°F",
        "min": 2,
        "max": 8,
        "step": 0.5,
        "default": 4.0,
        "rule": "CHILLER-DT",
        "group": "Chiller performance",
        "pages": ["central_plant", "chiller_plant"],
    },
    "chiller_enable_delta_f": {
        "label": "Below enable setpoint Δ",
        "unit": "°F",
        "min": 1,
        "max": 8,
        "step": 0.5,
        "default": 3.0,
        "rule": "CHILLER-EN",
        "group": "Chiller enable",
        "pages": ["central_plant", "chiller_plant"],
    },
    "boiler_warm_oat_f": {
        "label": "Boiler warm-weather OAT",
        "unit": "°F",
        "min": 50,
        "max": 70,
        "step": 1,
        "default": 60.0,
        "rule": "BOILER-WARM",
        "group": "Boiler plant",
        "pages": ["central_plant", "boiler_plant"],
    },
    "hw_low_delta_f": {
        "label": "Boiler low HW ΔT",
        "unit": "°F",
        "min": 5,
        "max": 20,
        "step": 1,
        "default": 10.0,
        "rule": "BOILER-DT",
        "group": "Boiler plant",
        "pages": ["central_plant", "boiler_plant"],
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


def refresh_page_registry() -> None:
    """Reload PAGE_IDS / PAGE_TITLES from SPARQL model."""
    global PAGE_IDS, PAGE_TITLES
    from page_registry import clear_registry_cache, page_ids, page_titles

    clear_registry_cache()
    PAGE_IDS = page_ids()
    PAGE_TITLES = page_titles()


try:
    refresh_page_registry()
except Exception:
    PAGE_TITLES = {
        "index": "Overview",
        "zones": "Comfort / Zones",
        "weather": "Weather Sensors",
        "ahu_1": "AHU 1",
        "ahu_2": "AHU 2",
        "economizer": "Economizer / Free Cooling",
        "economizer_diagnostics": "Economizer Diagnostics",
        "central_plant": "Central Plant",
        "excess_runtime": "Excess Fan Runtime",
        "chiller_plant": "Chiller Plant",
        "boiler_plant": "Boiler Plant",
        "motor_runtime": "Motor Runtime",
    }


def default_params() -> dict[str, float]:
    return {k: float(v["default"]) for k, v in PARAM_DEFS.items()}


def _param_page_id(page_id: str) -> str:
    if page_id.startswith("ahu_") and page_id not in ("ahu_1", "ahu_2"):
        return "ahu_1"
    return page_id


def params_for_page(page_id: str) -> list[dict[str, Any]]:
    pid = _param_page_id(page_id)
    out = []
    for key, meta in PARAM_DEFS.items():
        if pid in meta["pages"]:
            out.append({"key": key, **meta})
    return out


def params_by_rule(page_id: str) -> list[dict[str, Any]]:
    """Grouped rule boxes for inline tune panels."""
    pid = _param_page_id(page_id)
    by_rule: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for key, meta in PARAM_DEFS.items():
        if pid not in meta["pages"]:
            continue
        rule = meta.get("rule", "OTHER")
        if rule not in by_rule:
            by_rule[rule] = []
            order.append(rule)
        by_rule[rule].append({"key": key, **meta})
    return [{"rule": rule, "group": by_rule[rule][0].get("group", rule), "params": by_rule[rule]} for rule in order]


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


def apply_to_generate_dashboard(gd_module, params: dict[str, float], site_settings: dict[str, Any] | None = None) -> None:
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
    gd_module.FREE_COOL_DP_MAX_F = p["free_cool_dp_max_f"]
    gd_module.FREE_COOL_OAT_AVAIL_F = p["free_cool_oat_avail_f"]
    gd_module.ECONOMIZER_LOW_LIMIT_F = p["economizer_low_limit_f"]
    gd_module.OA_MIN_EXPECTED_PCT = p["oa_min_expected_pct"]
    gd_module.OA_MAX_ECONOMIZER_PCT = p["oa_max_economizer_pct"]
    gd_module.CHW_LOW_DELTA_T = p["chw_low_delta_t_f"]
    gd_module.BOILER_WARM_OAT_F = p["boiler_warm_oat_f"]
    gd_module.FAULT_PERSIST_SEC = int(p["fault_persist_minutes"] * 60)
    gd_module.FLATLINE_TOL = p["flatline_tol_f"]
    gd_module.FLATLINE_WINDOW = max(4, int(round(p["flatline_window_hours"] * 3600 / gd_module.POLL_SECONDS)))
    gd_module.SPIKE_LIMIT_OAT = p["spike_limit_oat_f"]
    gd_module.SPIKE_LIMIT_ZONE = p["spike_limit_zone_f"]
    gd_module.ZONE_TEMP_LO_F = p["zone_temp_lo_f"]
    gd_module.ZONE_TEMP_HI_F = p["zone_temp_hi_f"]
    gd_module.OAT_HARD_LO_F = p["oat_hard_lo_f"]
    gd_module.OAT_HARD_HI_F = p["oat_hard_hi_f"]
    gd_module.FC23_CONFIRM_SEC = int(p["fc23_confirm_minutes"] * 60)
    gd_module.FC813_CONFIRM_SEC = int(p["fc813_confirm_minutes"] * 60)
    gd_module.FC4_CONFIRM_SEC = int(p["fc4_confirm_minutes"] * 60)
    gd_module.FC4_REVERSALS = int(p["fc4_reversals_per_h"])
    gd_module.FC4_P2P_PCT = p["fc4_p2p_pct"]
    gd_module.FC4_CMD_DEADBAND = p["fc4_command_deadband_pct"]
    gd_module.AHU_MIN_OA_DPR = p["ahu_min_oa_dpr_pct"] / 100.0
    gd_module.DELTA_SUPPLY_FAN = p["delta_supply_fan_f"]
    gd_module.FC13_SAT_DEADBAND_F = p["fc13_sat_deadband_f"]
    gd_module.CHILLER_ENABLE_DELTA_F = p["chiller_enable_delta_f"]
    gd_module.HW_LOW_DELTA_F = p["hw_low_delta_f"]
    if site_settings:
        from shared.occupancy import merge_site_settings
        from shared.data_config import get_config

        merged = merge_site_settings(site_settings, timezone=get_config().site_timezone())
        gd_module.SITE_SETTINGS = merged
        gd_module._OCC_SCHEDULE = merged.get("occupancy")
        if merged.get("comfort_setpoint_f") is not None:
            gd_module.COMFORT_SETPOINT_F = float(merged["comfort_setpoint_f"])
            gd_module.COMFORT_LO_F = gd_module.COMFORT_SETPOINT_F - gd_module.COMFORT_BAND_F
            gd_module.COMFORT_HI_F = gd_module.COMFORT_SETPOINT_F + gd_module.COMFORT_BAND_F
        if merged.get("comfort_band_f") is not None:
            gd_module.COMFORT_BAND_F = float(merged["comfort_band_f"])
            gd_module.COMFORT_LO_F = gd_module.COMFORT_SETPOINT_F - gd_module.COMFORT_BAND_F
            gd_module.COMFORT_HI_F = gd_module.COMFORT_SETPOINT_F + gd_module.COMFORT_BAND_F


def params_summary_html(params: dict[str, float], page_id: str | None = None) -> str:
    rows = []
    for key, meta in PARAM_DEFS.items():
        if page_id and page_id not in meta["pages"]:
            continue
        val = params.get(key, meta["default"])
        unit = meta["unit"]
        rule = meta.get("rule", "")
        rows.append(
            f"<tr><td>{rule}</td><td>{meta['label']}</td><td><strong>{val:g}</strong> {unit}</td></tr>"
        )
    if not rows:
        return ""
    return (
        "<details class='tune-summary'><summary>Tuned fault parameters</summary>"
        f"<table><thead><tr><th>Rule</th><th>Parameter</th><th>Value</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></details>"
    )


def load_session() -> dict[str, Any]:
    from shared.data_config import get_config
    from shared.occupancy import default_site_settings, merge_site_settings

    tz = get_config().site_timezone()
    if SESSION_PATH.exists():
        data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
        merged = merge_params(data.get("params", {}))
        data["params"] = validate_params(merged)
        data.setdefault("notes", {})
        data.setdefault("analyst_name", "")
        data.setdefault("package_title", "Open FDD Vibe Coder")
        data["site_settings"] = merge_site_settings(data.get("site_settings"), timezone=tz)
        data.setdefault("package_locked", False)
        data.setdefault("engineer_logged_in", False)
        return data
    return {
        "params": default_params(),
        "notes": {},
        "analyst_name": "",
        "package_title": "Open FDD Vibe Coder",
        "site_settings": default_site_settings(timezone=tz),
        "package_locked": False,
        "engineer_logged_in": False,
    }


def save_session(session: dict[str, Any]) -> None:
    payload = deepcopy(session)
    payload["params"] = validate_params(payload.get("params", {}))
    SESSION_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def economizer_engine_params(params: dict[str, float] | None = None) -> dict[str, float]:
    """Map analyst tune panel values to economizer_fdd_engine thresholds."""
    p = validate_params(params or {})
    try:
        from shared.data_config import get_config

        poll = get_config().poll_seconds()
    except Exception:
        poll = 900
    flatline_samples = max(4, int(round(p["flatline_window_hours"] * 3600 / poll)))
    return {
        "poll_seconds": poll,
        "confirm_minutes": p["fault_persist_minutes"],
        "smooth_minutes": p["fault_persist_minutes"],
        "temp_deadband_f": p["temp_deadband_f"],
        "damper_deadband_pct": p["damper_deadband_pct"],
        "mat_residual_db_f": p["mat_residual_db_f"],
        "temp_min_f": p["oat_hard_lo_f"],
        "temp_max_f": p["oat_hard_hi_f"],
        "flatline_window_samples": flatline_samples,
        "flatline_tol_f": p["flatline_tol_f"],
        "oat_rat_min_delta_f": p["oat_rat_min_delta_f"],
        "economizer_high_limit_f": p["free_cool_oat_avail_f"] + 3.0,
        "economizer_low_limit_f": p["economizer_low_limit_f"],
        "free_cool_dp_max_f": p["free_cool_dp_max_f"],
        "free_cool_oat_avail_f": p["free_cool_oat_avail_f"],
        "oat_favorable_delta_f": p["oat_favorable_delta_f"],
        "fan_on_pct": p["ahu_min_oa_dpr_pct"],
        "cooling_active_pct": p["free_cool_chw_min_pct"],
        "oa_max_economizer_pct": p["oa_max_economizer_pct"],
        "oa_min_expected_pct": p["oa_min_expected_pct"],
        "damper_stuck_tol_pct": p["damper_stuck_tol_pct"],
        "hunting_reversals_per_hour": p["fc4_reversals_per_h"],
        "hunting_p2p_pct": p["fc4_p2p_pct"],
        "weather_fault_f": p["weather_fault_delta_f"],
        "gap_max_samples": int(p["gap_max_samples"]),
    }


def write_defaults_file() -> None:
    payload = {
        "schema_version": "2.0",
        "description": "Open-FDD Vibe Coder rule tune parameters (cookbook parity)",
        "params": default_params(),
        "param_defs": {
            k: {kk: vv for kk, vv in v.items() if kk != "pages"} | {"pages": v["pages"]}
            for k, v in PARAM_DEFS.items()
        },
    }
    DEFAULTS_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
