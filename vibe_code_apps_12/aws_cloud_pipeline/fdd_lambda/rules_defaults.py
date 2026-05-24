"""
Default per-rule FDD definitions — BRICK Zone_Air_Temperature_Sensor bundle.

See EXPRESSION_RULE_COOKBOOK.md for recipe patterns (1h flatline, OOB, 15m swing, 24h peak swing).
"""

from __future__ import annotations

from typing import Any

from units import config_field_meta_for_unit, normalize_temp_unit

CONFIG_FIELD_META = config_field_meta_for_unit("imperial")

BRICK_ZONE_TEMP_SCOPE: dict[str, Any] = {
    "point_classes": ["Zone_Air_Temperature_Sensor"],
    "match_mode": "point_only",
}


def get_config_field_meta(unit: str | None = None) -> dict[str, dict[str, Any]]:
    return config_field_meta_for_unit(normalize_temp_unit(unit))


def default_custom_rules() -> list[dict[str, Any]]:
    """Shipped defaults: four BRICK-scoped zone temperature rules (see cookbook)."""
    scope = dict(BRICK_ZONE_TEMP_SCOPE)
    return [
        {
            "id": "brick_zone_oob",
            "title": "Zone temp out of bounds",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#f85149",
            "brick_scope": scope,
            "config_fields": ["bounds_low", "bounds_high", "rolling_avg_minutes"],
            "config": {
                "bounds_low": 65.0,
                "bounds_high": 80.0,
                "rolling_avg_minutes": 1,
            },
            "code": '''def evaluate(row, cfg, prev_row=None, rows=None):
    sym = temp_unit_symbol(cfg)
    low = cfg_threshold(cfg, "bounds_low")
    high = cfg_threshold(cfg, "bounds_high")

    if "temp_rolling_avg" in row:
        v = row["temp_rolling_avg"]
        kind = "avg"
    elif "degF_rolling_avg" in row:
        v = row["degF_rolling_avg"]
        kind = "degF_avg"
    else:
        v = row["temp"]
        kind = "raw"

    if v < low or v > high:
        print(
            f"{row['ts']}  OOB {kind}  {v:.2f} {sym}  "
            f"(band {low:.1f}–{high:.1f}, raw={row['temp']:.2f})"
        )
        return True

    return False
''',
        },
        {
            "id": "brick_zone_flatline_1h",
            "title": "Zone flatline (1 h stuck sensor)",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#d29922",
            "brick_scope": scope,
            "config_fields": ["flatline_tolerance"],
            "config": {"flatline_tolerance": 0.10},
            "code": '''ONE_HOUR_MS = 60 * 60 * 1000
FILL_RATIO = 0.95


def get_last_1_hour(row, rows):
    now_ms = row["ts_ms"]
    start_ms = now_ms - ONE_HOUR_MS
    return [r for r in rows if start_ms <= r["ts_ms"] <= now_ms]


def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    window_rows = get_last_1_hour(row, rows)
    if len(window_rows) < 2:
        return False

    span_ms = window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]
    if span_ms < ONE_HOUR_MS * FILL_RATIO:
        return False

    sym = temp_unit_symbol(cfg)
    vals = [r["temp"] for r in window_rows]
    spread = max(vals) - min(vals)
    tol = cfg_threshold(cfg, "flatline_tolerance")

    if spread < tol:
        print(
            f"row={row['row']} ts={row['ts']} "
            f"FLATLINE 1h spread={spread:.3f} {sym} < tol={tol:.3f}"
        )
        return True, window_rows

    return False
''',
        },
        {
            "id": "brick_zone_swing_15m",
            "title": "Zone excessive swing (15 min)",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#a371f7",
            "brick_scope": scope,
            "config_fields": ["max_spread_15min"],
            "config": {"max_spread_15min": 2.5},
            "code": '''FIFTEEN_MIN_MS = 15 * 60 * 1000
FILL_RATIO = 0.95


def get_last_15_min(row, rows):
    now_ms = row["ts_ms"]
    start_ms = now_ms - FIFTEEN_MIN_MS
    return [r for r in rows if start_ms <= r["ts_ms"] <= now_ms]


def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    window_rows = get_last_15_min(row, rows)
    if not window_rows:
        return False

    span_ms = window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]
    if span_ms < FIFTEEN_MIN_MS * FILL_RATIO:
        return False

    sym = temp_unit_symbol(cfg)
    vals = [r["temp"] for r in window_rows]
    lo, hi = min(vals), max(vals)
    spread = hi - lo
    lim = cfg_threshold(cfg, "max_spread_15min")

    print(
        f"row={row['row']} ts={row['ts']} "
        f"spread={spread:.2f} {sym} (min={lo:.2f} max={hi:.2f})"
    )

    if spread > lim:
        print(f"SPREAD/15m: painting {len(window_rows)} rows")
        return True, window_rows

    return False
''',
        },
        {
            "id": "brick_zone_peak_swing_24h",
            "title": "Zone peak swing (24 h)",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#ff7b72",
            "brick_scope": scope,
            "config_fields": ["max_spread_24h"],
            "config": {"max_spread_24h": 12.0},
            "code": '''TWENTY_FOUR_HOUR_MS = 24 * 60 * 60 * 1000
FILL_RATIO = 0.95


def get_last_24_hours(row, rows):
    now_ms = row["ts_ms"]
    start_ms = now_ms - TWENTY_FOUR_HOUR_MS
    return [r for r in rows if start_ms <= r["ts_ms"] <= now_ms]


def evaluate(row, cfg, prev_row=None, rows=None):
    if rows is None:
        return False

    window_rows = get_last_24_hours(row, rows)
    if not window_rows:
        return False

    span_ms = window_rows[-1]["ts_ms"] - window_rows[0]["ts_ms"]
    if span_ms < TWENTY_FOUR_HOUR_MS * FILL_RATIO:
        return False

    sym = temp_unit_symbol(cfg)
    vals = [r["temp"] for r in window_rows]
    lo, hi = min(vals), max(vals)
    spread = hi - lo
    lim = cfg_threshold(cfg, "max_spread_24h")

    print(
        f"row={row['row']} ts={row['ts']} "
        f"peak spread 24h={spread:.2f} {sym} (min={lo:.2f} max={hi:.2f})"
    )

    if spread > lim:
        print(f"PEAK/24h: painting {len(window_rows)} rows")
        return True, window_rows

    return False
''',
        },
    ]


def legacy_ds18b20_rules() -> list[dict[str, Any]]:
    """Legacy single-series Pi rules (disabled); kept for reference / manual enable."""
    return [
        {
            "id": "temp_out_of_bounds_flag",
            "title": "Out of bounds (legacy Pi)",
            "enabled": False,
            "plot_on_chart": False,
            "color": "#8b949e",
            "config_fields": ["bounds_low", "bounds_high", "rolling_avg_minutes"],
            "config": {"bounds_low": 65.0, "bounds_high": 80.0, "rolling_avg_minutes": 1},
            "code": "",
        },
        {
            "id": "temp_flatline_flag",
            "title": "Flatline N samples (legacy Pi)",
            "enabled": False,
            "plot_on_chart": False,
            "color": "#8b949e",
            "config_fields": ["flatline_tolerance", "flatline_window"],
            "config": {"flatline_tolerance": 0.05, "flatline_window": 18},
            "code": "",
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
