"""
Default per-rule FDD definitions — plain evaluate(), no backend rolling_window or 1-min avg.

See EXPRESSION_RULE_COOKBOOK.md for adding debounce and rolling averages in your code.
"""

from __future__ import annotations

from typing import Any

CONFIG_FIELD_META: dict[str, dict[str, Any]] = {
    "bounds_low_f": {"label": "Low °F", "type": "float", "step": 0.1},
    "bounds_high_f": {"label": "High °F", "type": "float", "step": 0.1},
    "flatline_tolerance_f": {"label": "Flatline tol °F", "type": "float", "step": 0.01},
    "flatline_window": {"label": "Flatline win", "type": "int", "step": 1},
    "max_f_per_hour": {"label": "Max °F/hr", "type": "float", "step": 0.1},
    "max_f_per_minute": {"label": "Max °F/min", "type": "float", "step": 0.1},
}


def default_custom_rules() -> list[dict[str, Any]]:
    return [
        {
            "id": "temp_out_of_bounds_flag",
            "title": "Out of bounds",
            "enabled": True,
            "color": "#f85149",
            "config_fields": ["bounds_low_f", "bounds_high_f"],
            "config": {"bounds_low_f": 65.0, "bounds_high_f": 80.0},
            "code": '''def evaluate(row, cfg, prev_row=None, rows=None):
    f = row["degF"]
    if f < cfg["bounds_low_f"] or f > cfg["bounds_high_f"]:
        print(f"{row['ts']}  OUT OF BOUNDS  {f:.2f} F")
        return True
    return False
''',
        },
        {
            "id": "temp_flatline_flag",
            "title": "Flatline (stuck sensor)",
            "enabled": True,
            "color": "#d29922",
            "config_fields": ["flatline_tolerance_f", "flatline_window"],
            "config": {"flatline_tolerance_f": 0.05, "flatline_window": 18},
            "code": '''def evaluate(row, cfg, prev_row=None, rows=None):
    w = int(cfg["flatline_window"])
    if rows is None or row["row"] < w - 1:
        return False
    i = row["row"]
    win = rows[i - w + 1 : i + 1]
    vals = [r["degF"] for r in win]
    if max(vals) - min(vals) < cfg["flatline_tolerance_f"]:
        print(f"{row['ts']}  FLATLINE  spread={max(vals)-min(vals):.3f} F")
        return True
    return False
''',
        },
        {
            "id": "temp_rate_per_hour_flag",
            "title": "Rate > limit (per hour)",
            "enabled": True,
            "color": "#a371f7",
            "config_fields": ["max_f_per_hour"],
            "config": {"max_f_per_hour": 15.0},
            "code": '''def evaluate(row, cfg, prev_row=None, rows=None):
    if not prev_row:
        return False
    dt = (row["ts_ms"] - prev_row["ts_ms"]) / 1000.0
    if dt <= 0:
        return False
    rate = abs(row["degF"] - prev_row["degF"]) / (dt / 3600.0)
    if rate > cfg["max_f_per_hour"]:
        print(f"{row['ts']}  RATE/Hr  {rate:.1f} F/hr")
        return True
    return False
''',
        },
        {
            "id": "temp_rate_per_minute_flag",
            "title": "Rate > limit (per minute)",
            "enabled": True,
            "color": "#ff7b72",
            "config_fields": ["max_f_per_minute"],
            "config": {"max_f_per_minute": 2.0},
            "code": '''def evaluate(row, cfg, prev_row=None, rows=None):
    if not prev_row:
        return False
    dt = (row["ts_ms"] - prev_row["ts_ms"]) / 1000.0
    if dt <= 0:
        return False
    rate = abs(row["degF"] - prev_row["degF"]) / (dt / 60.0)
    if rate > cfg["max_f_per_minute"]:
        print(f"{row['ts']}  RATE/min  {rate:.1f} F/min")
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
