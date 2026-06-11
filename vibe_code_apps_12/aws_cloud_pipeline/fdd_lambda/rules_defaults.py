"""
Default Arrow-native FDD rules for the Vibe12 Open-FDD PyPI cloud demo.

Rule contract: apply_faults_arrow(table, cfg, context=None) → PyArrow boolean mask.
Maintained cookbook: https://bbartling.github.io/open-fdd/rule-cookbook/
"""

from __future__ import annotations

import copy
from typing import Any

from units import config_field_meta_for_unit, normalize_temp_unit

CONFIG_FIELD_META = config_field_meta_for_unit("imperial")

DEFAULT_FAULT_RULE_PACK = "vibe12_openfdd_cloud_demo_v1"
DEFAULT_FAULT_RULE_ID = "demo_zone_temp_oob"

OPEN_FDD_DOCS = "https://bbartling.github.io/open-fdd/"
OPEN_FDD_RULE_COOKBOOK = "https://bbartling.github.io/open-fdd/rule-cookbook/"
OPEN_FDD_PYPI = "https://pypi.org/project/open-fdd/"

BRICK_ZONE_TEMP_SCOPE: dict[str, Any] = {
    "point_classes": ["Zone_Air_Temperature_Sensor"],
    "match_mode": "point_only",
}

BRICK_OUTSIDE_HUMIDITY_SCOPE: dict[str, Any] = {
    "point_classes": ["Outside_Air_Humidity_Sensor"],
    "match_mode": "point_only",
}

BRICK_DUCT_TEMP_SCOPE: dict[str, Any] = {
    "point_classes": ["Discharge_Air_Temperature_Sensor"],
    "match_mode": "point_only",
    "series_aliases": {"zone_temp": "STAT-ZN-T"},
}

BRICK_DUCT_OA_SCOPE: dict[str, Any] = {
    "point_classes": ["Discharge_Air_Temperature_Sensor"],
    "match_mode": "point_only",
    "series_aliases": {"outside_temp": "OA-T"},
}


def get_config_field_meta(unit: str | None = None) -> dict[str, dict[str, Any]]:
    return config_field_meta_for_unit(normalize_temp_unit(unit))


def default_fault_rule_reference() -> dict[str, str]:
    return {
        "rule_pack": DEFAULT_FAULT_RULE_PACK,
        "fault_rule": DEFAULT_FAULT_RULE_ID,
    }


def default_custom_rules() -> list[dict[str, Any]]:
    """Five demo rules showcasing PyPI open-fdd Arrow execution on BACnet bench points."""
    zone_scope = dict(BRICK_ZONE_TEMP_SCOPE)
    return [
        {
            "id": "demo_zone_temp_oob",
            "title": "Zone temperature out of bounds",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#f85149",
            "brick_scope": zone_scope,
            "config_fields": ["bounds_low", "bounds_high", "rolling_avg_minutes"],
            "config": {
                "bounds_low": 65.0,
                "bounds_high": 80.0,
                "rolling_avg_minutes": 1,
            },
            "backend": "arrow",
            "code": '''from open_fdd.arrow_runtime.cookbook import oob_mask


def apply_faults_arrow(table, cfg, context=None):
    mask = oob_mask(table, cfg, col="temp")
    temps = table["temp"]
    n = len(temps)
    vals = [float(v) for v in temps.to_pylist() if v is not None]
    lo = float(cfg.get("bounds_low", 65.0))
    hi = float(cfg.get("bounds_high", 80.0))
    flagged = int(mask.to_pylist().count(True))
    vmin = min(vals) if vals else float("nan")
    vmax = max(vals) if vals else float("nan")
    print(
        f"demo_zone_temp_oob: rows={n} min={vmin:.1f} max={vmax:.1f} "
        f"bounds={lo:.1f}-{hi:.1f} flagged={flagged}"
    )
    return mask
''',
        },
        {
            "id": "demo_outside_humidity_oob",
            "title": "Outside humidity out of range",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#14b8a6",
            "brick_scope": copy.deepcopy(BRICK_OUTSIDE_HUMIDITY_SCOPE),
            "config_fields": ["humidity_low", "humidity_high"],
            "config": {
                "humidity_low": 20.0,
                "humidity_high": 75.0,
            },
            "backend": "arrow",
            "code": '''from open_fdd.arrow_runtime.cookbook import oob_mask


def apply_faults_arrow(table, cfg, context=None):
    mask = oob_mask(table, cfg, col="value")
    vals = [float(v) for v in table["value"].to_pylist() if v is not None]
    lo = float(cfg.get("humidity_low", 20.0))
    hi = float(cfg.get("humidity_high", 75.0))
    flagged = int(mask.to_pylist().count(True))
    vmin = min(vals) if vals else float("nan")
    vmax = max(vals) if vals else float("nan")
    print(
        f"demo_outside_humidity_oob: rows={len(table)} rh_min={vmin:.1f} "
        f"rh_max={vmax:.1f} bounds={lo:.1f}-{hi:.1f} flagged={flagged}"
    )
    return mask
''',
        },
        {
            "id": "demo_duct_zone_delta",
            "title": "Duct vs zone temperature delta",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#d29922",
            "brick_scope": copy.deepcopy(BRICK_DUCT_TEMP_SCOPE),
            "config_fields": ["min_abs_delta_f", "max_abs_delta_f"],
            "config": {
                "min_abs_delta_f": 1.0,
                "max_abs_delta_f": 35.0,
            },
            "backend": "arrow",
            "code": '''import pyarrow as pa
import pyarrow.compute as pc


def apply_faults_arrow(table, cfg, context=None):
    duct = table["temp"]
    zone = table["zone_temp"]
    delta = pc.abs(pc.subtract(duct, zone))
    min_d = float(cfg.get("min_abs_delta_f", 1.0))
    max_d = float(cfg.get("max_abs_delta_f", 35.0))
    mask = pc.or_(pc.less(delta, min_d), pc.greater(delta, max_d))
    flagged = int(pc.sum(pc.cast(mask, pa.int64())).as_py() or 0)
    print(
        f"demo_duct_zone_delta: rows={len(table)} min_delta={min_d} "
        f"max_delta={max_d} flagged={flagged}"
    )
    return mask
''',
        },
        {
            "id": "demo_duct_outside_sanity",
            "title": "Duct vs outside air sanity",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#a371f7",
            "brick_scope": copy.deepcopy(BRICK_DUCT_OA_SCOPE),
            "config_fields": ["max_abs_delta_f"],
            "config": {"max_abs_delta_f": 25.0},
            "backend": "arrow",
            "code": '''import pyarrow as pa
import pyarrow.compute as pc


def apply_faults_arrow(table, cfg, context=None):
    duct = table["temp"]
    oa = table["outside_temp"]
    delta = pc.abs(pc.subtract(duct, oa))
    max_d = float(cfg.get("max_abs_delta_f", 25.0))
    mask = pc.greater(delta, max_d)
    flagged = int(pc.sum(pc.cast(mask, pa.int64())).as_py() or 0)
    print(
        f"demo_duct_outside_sanity: rows={len(table)} max_delta={max_d} flagged={flagged}"
    )
    return mask
''',
        },
        {
            "id": "demo_numpy_zone_temp_slope",
            "title": "NumPy demo — zone temp slope",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#ff7b72",
            "numpy_demo": True,
            "brick_scope": copy.deepcopy(BRICK_ZONE_TEMP_SCOPE),
            "config_fields": ["window_samples", "max_slope_f_per_sample"],
            "config": {
                "window_samples": 12,
                "max_slope_f_per_sample": 0.4,
            },
            "backend": "arrow",
            "code": '''import pyarrow as pa


def apply_faults_arrow(table, cfg, context=None):
    np = (context or {}).get("numpy")
    if np is None:
        print("demo_numpy_zone_temp_slope: numpy unavailable — rule skipped")
        return pa.array([False] * len(table))

    values = table["temp"].to_numpy(zero_copy_only=False)
    window = max(2, int(cfg.get("window_samples", 12)))
    max_slope = float(cfg.get("max_slope_f_per_sample", 0.4))
    n = len(values)
    mask = np.zeros(n, dtype=bool)
    max_seen = 0.0
    for i in range(1, n):
        start = max(0, i - window + 1)
        seg = values[start : i + 1]
        seg = seg[~np.isnan(seg)]
        if len(seg) < 2:
            continue
        slope = abs(float(seg[-1] - seg[0])) / max(1, len(seg) - 1)
        max_seen = max(max_seen, slope)
        if slope > max_slope:
            mask[i] = True
    flagged = int(mask.sum())
    print(
        f"demo_numpy_zone_temp_slope: numpy demo active samples={n} "
        f"max_slope={max_seen:.3f} flagged={flagged}"
    )
    return pa.array(mask.tolist())
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
    return [
        {
            "id": r["id"],
            "title": r.get("title", r["id"]),
            "color": r.get("color", "#8b949e"),
            "enabled": bool(r.get("enabled", True)),
            "plot_on_chart": bool(r.get("plot_on_chart", True)),
            "brick_scope": r.get("brick_scope"),
            "numpy_demo": bool(r.get("numpy_demo")),
            "backend": r.get("backend", "arrow"),
        }
        for r in rules
    ]
