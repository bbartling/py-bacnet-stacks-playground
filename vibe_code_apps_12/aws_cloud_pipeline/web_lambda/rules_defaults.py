"""
Default per-rule FDD definitions — BRICK Zone_Air_Temperature_Sensor bundle.

See EXPRESSION_RULE_COOKBOOK.md for recipe patterns (1h flatline, OOB, 15m swing, 24h peak swing).
"""

from __future__ import annotations

import copy
from typing import Any

from units import config_field_meta_for_unit, normalize_temp_unit

CONFIG_FIELD_META = config_field_meta_for_unit("imperial")

DEFAULT_FAULT_RULE_PACK = "brick_zone_temp_basic_v1"
DEFAULT_FAULT_RULE_ID = "brick_zone_oob"

BRICK_ZONE_TEMP_SCOPE: dict[str, Any] = {
    "point_classes": ["Zone_Air_Temperature_Sensor"],
    "match_mode": "point_only",
}

BRICK_OUTSIDE_HUMIDITY_SCOPE: dict[str, Any] = {
    "point_classes": ["Outside_Air_Humidity_Sensor"],
    "match_mode": "point_only",
}


def get_config_field_meta(unit: str | None = None) -> dict[str, dict[str, Any]]:
    return config_field_meta_for_unit(normalize_temp_unit(unit))


def default_fault_rule_reference() -> dict[str, str]:
    """Default site-level link from the canonical model to the shipped FDD bundle."""
    return {
        "rule_pack": DEFAULT_FAULT_RULE_PACK,
        "fault_rule": DEFAULT_FAULT_RULE_ID,
    }


def default_custom_rules() -> list[dict[str, Any]]:
    """Shipped defaults: four zone temperature rules plus one humidity bounds rule."""
    return [
        {
            "id": "brick_zone_oob",
            "title": "Zone temp out of bounds",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#f85149",
            "brick_scope": copy.deepcopy(BRICK_ZONE_TEMP_SCOPE),
            "config_fields": ["bounds_low", "bounds_high", "rolling_avg_minutes"],
            "config": {
                "bounds_low": 65.0,
                "bounds_high": 80.0,
                "rolling_avg_minutes": 1,
            },
            "backend": "arrow",
            "code": '''from open_fdd.arrow_runtime.cookbook import oob_mask


def apply_faults_arrow(table, cfg, context=None):
    return oob_mask(table, cfg, col="temp")
''',
        },
        {
            "id": "brick_outside_humidity_oob",
            "title": "Outside humidity bounds",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#14b8a6",
            "brick_scope": copy.deepcopy(BRICK_OUTSIDE_HUMIDITY_SCOPE),
            "config_fields": ["humidity_low", "humidity_high"],
            "config": {
                "humidity_low": 30.0,
                "humidity_high": 60.0,
            },
            "backend": "arrow",
            "code": '''from open_fdd.arrow_runtime.cookbook import oob_mask


def apply_faults_arrow(table, cfg, context=None):
    return oob_mask(table, cfg, col="value")
''',
        },
        {
            "id": "brick_zone_flatline_1h",
            "title": "Zone flatline (1 h stuck sensor)",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#d29922",
            "brick_scope": copy.deepcopy(BRICK_ZONE_TEMP_SCOPE),
            "config_fields": ["flatline_tolerance"],
            "config": {"flatline_tolerance": 0.10},
            "backend": "arrow",
            "code": '''from open_fdd.arrow_runtime.cookbook import flatline_1h_mask


def apply_faults_arrow(table, cfg, context=None):
    return flatline_1h_mask(table, cfg, col="temp")
''',
        },
        {
            "id": "brick_zone_swing_15m",
            "title": "Zone excessive swing (15 min)",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#a371f7",
            "brick_scope": copy.deepcopy(BRICK_ZONE_TEMP_SCOPE),
            "config_fields": ["max_spread_15min"],
            "config": {"max_spread_15min": 2.5},
            "backend": "arrow",
            "code": '''from open_fdd.arrow_runtime.cookbook import spread_1h_mask


def apply_faults_arrow(table, cfg, context=None):
    return spread_1h_mask(table, cfg, col="temp")
''',
        },
        {
            "id": "brick_zone_peak_swing_24h",
            "title": "Zone peak swing (24 h)",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#ff7b72",
            "brick_scope": copy.deepcopy(BRICK_ZONE_TEMP_SCOPE),
            "config_fields": ["max_spread_24h"],
            "config": {"max_spread_24h": 12.0},
            "backend": "arrow",
            "code": '''from open_fdd.arrow_runtime.cookbook import spread_1h_mask


def apply_faults_arrow(table, cfg, context=None):
    return spread_1h_mask(table, cfg, col="temp")
''',
        },
    ]


def rules_to_panels(rules: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        {
            "key": r["id"],
            "title": r.get("title", r["id"]),
            "color": r.get("color", "#8b949e"),
        }
        for r in rules
        if r.get("enabled", True)
    ]


def chart_guides_from_rules(
    rules: list[dict[str, Any]], display_unit: str = "imperial"
) -> dict[str, Any]:
    """Bounds band for dashboard guide lines (values in display_unit)."""
    from units import effective_temp_unit, resolve_cfg_threshold, to_display_temp

    du = normalize_temp_unit(display_unit)
    for r in rules:
        cfg = r.get("config") or {}
        try:
            ru = effective_temp_unit(cfg, du)
            low = resolve_cfg_threshold(cfg, "bounds_low", ru)
            high = resolve_cfg_threshold(cfg, "bounds_high", ru)
            low_d = to_display_temp(low, ru, du)
            high_d = to_display_temp(high, ru, du)
            out: dict[str, Any] = {
                "bounds_low": low_d,
                "bounds_high": high_d,
                "temp_unit": du,
            }
            if du == "imperial":
                out["bounds_low_f"] = low_d
                out["bounds_high_f"] = high_d
            return out
        except KeyError:
            continue
    if du == "metric":
        return {"bounds_low": 18.0, "bounds_high": 27.0, "temp_unit": "metric"}
    return {
        "bounds_low": 65.0,
        "bounds_high": 80.0,
        "temp_unit": "imperial",
        "bounds_low_f": 65.0,
        "bounds_high_f": 80.0,
    }


def rules_meta(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Lightweight rule list for dashboard plot toggles (synced with Rule Lab)."""
    return [
        {
            "id": r["id"],
            "title": r.get("title", r["id"]),
            "color": r.get("color", "#8b949e"),
            "enabled": bool(r.get("enabled", True)),
            "plot_on_chart": bool(r.get("plot_on_chart", True)),
            "brick_scope": r.get("brick_scope"),
        }
        for r in rules
    ]
