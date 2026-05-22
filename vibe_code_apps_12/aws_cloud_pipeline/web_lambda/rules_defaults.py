"""
Default per-rule FDD definitions — plain evaluate(), no backend rolling_window or 1-min avg.

See EXPRESSION_RULE_COOKBOOK.md — copy/paste debounce and 1-min avg logic into your rule code.
"""

from __future__ import annotations

from typing import Any

from units import config_field_meta_for_unit, normalize_temp_unit

CONFIG_FIELD_META = config_field_meta_for_unit("imperial")


def get_config_field_meta(unit: str | None = None) -> dict[str, dict[str, Any]]:
    return config_field_meta_for_unit(normalize_temp_unit(unit))


def default_custom_rules() -> list[dict[str, Any]]:
    return [
        {
            "id": "temp_out_of_bounds_flag",
            "title": "Out of bounds",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#f85149",
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
    f = row["degF_rolling_avg"] if "degF_rolling_avg" in row else row["temp"]
    if f < low or f > high:
        print(f"{row['ts']}  OOB avg  {f:.2f} {sym}  raw={row['temp']:.2f}")
        return True
    return False
''',
        },
        {
            "id": "temp_flatline_flag",
            "title": "Flatline (stuck sensor)",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#d29922",
            "config_fields": ["flatline_tolerance", "flatline_window"],
            "config": {"flatline_tolerance": 0.05, "flatline_window": 18},
            "code": '''def evaluate(row, cfg, prev_row=None, rows=None):
    sym = temp_unit_symbol(cfg)
    w = int(cfg["flatline_window"])
    if rows is None or row["row"] < w - 1:
        return False
    i = row["row"]
    win = rows[i - w + 1 : i + 1]
    vals = [r["temp"] for r in win]
    tol = cfg_threshold(cfg, "flatline_tolerance")
    if max(vals) - min(vals) < tol:
        print(f"{row['ts']}  FLATLINE  spread={max(vals)-min(vals):.3f} {sym}")
        return True
    return False
''',
        },
        {
            "id": "temp_rate_per_hour_flag",
            "title": "Rate > limit (per hour)",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#a371f7",
            "config_fields": ["max_temp_per_hour"],
            "config": {"max_temp_per_hour": 15.0},
            "code": '''def evaluate(row, cfg, prev_row=None, rows=None):
    if not prev_row:
        return False
    sym = temp_unit_symbol(cfg)
    dt = (row["ts_ms"] - prev_row["ts_ms"]) / 1000.0
    if dt <= 0:
        return False
    rate = abs(row["temp"] - prev_row["temp"]) / (dt / 3600.0)
    lim = cfg_threshold(cfg, "max_temp_per_hour")
    if rate > lim:
        print(f"{row['ts']}  RATE/Hr  {rate:.1f} {sym}/hr")
        return True
    return False
''',
        },
        {
            "id": "temp_rate_per_minute_flag",
            "title": "Rate > limit (per minute)",
            "enabled": True,
            "plot_on_chart": True,
            "color": "#ff7b72",
            "config_fields": ["max_temp_per_minute"],
            "config": {"max_temp_per_minute": 2.0},
            "code": '''def evaluate(row, cfg, prev_row=None, rows=None):
    if not prev_row:
        return False
    sym = temp_unit_symbol(cfg)
    dt = (row["ts_ms"] - prev_row["ts_ms"]) / 1000.0
    if dt <= 0:
        return False
    rate = abs(row["temp"] - prev_row["temp"]) / (dt / 60.0)
    lim = cfg_threshold(cfg, "max_temp_per_minute")
    if rate > lim:
        print(f"{row['ts']}  RATE/min  {rate:.1f} {sym}/min")
        return True
    return False
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
        }
        for r in rules
    ]
