"""
Pure-Python fault rules (no pandas / open-fdd).
Bounds, flatline, rate/hr, rate/min — instant flags (no rolling_window debounce).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any


@dataclass
class RuleConfig:
    bounds_low_f: float = 65.0
    bounds_high_f: float = 80.0
    flatline_tolerance_f: float = 0.05
    flatline_window: int = 18
    max_f_per_hour: float = 15.0
    max_f_per_minute: float = 2.0
    rolling_window: int = 6

    def flag_labels(self) -> dict[str, str]:
        return {
            "temp_out_of_bounds_flag": (
                f"Out of bounds ({self.bounds_low_f:g}–{self.bounds_high_f:g} °F)"
            ),
            "temp_flatline_flag": "Flatline (stuck sensor)",
            "temp_rate_per_hour_flag": f"Rate > {self.max_f_per_hour:g} °F/hr",
            "temp_rate_per_minute_flag": f"Rate > {self.max_f_per_minute:g} °F/min",
        }

    def fault_panels(self) -> list[dict[str, str]]:
        colors = {
            "temp_out_of_bounds_flag": "#f85149",
            "temp_flatline_flag": "#d29922",
            "temp_rate_per_hour_flag": "#a371f7",
            "temp_rate_per_minute_flag": "#ff7b72",
        }
        return [
            {"key": k, "title": t, "color": colors[k]}
            for k, t in self.flag_labels().items()
        ]


DEFAULT_CONFIG = RuleConfig()

# Keys accepted in DynamoDB / dashboard JSON
CONFIG_KEYS = tuple(f.name for f in fields(RuleConfig))


def config_from_dict(data: dict[str, Any] | None) -> RuleConfig:
    if not data:
        return RuleConfig()
    base = asdict(DEFAULT_CONFIG)
    for key in CONFIG_KEYS:
        if key in data and data[key] is not None:
            val = data[key]
            if key in ("flatline_window", "rolling_window"):
                base[key] = int(val)
            else:
                base[key] = float(val)
    return RuleConfig(**base)


def config_to_dict(cfg: RuleConfig) -> dict[str, Any]:
    return asdict(cfg)


def rolling_window_flags(raw: list[bool], window: int) -> list[int]:
    """Flag only after `window` consecutive True raw hits."""
    out: list[int] = []
    run = 0
    w = max(1, int(window))
    for i, hit in enumerate(raw):
        run += 1 if hit else 0
        if i >= w:
            run -= 1 if raw[i - w] else 0
        out.append(1 if run >= w else 0)
    return out


def _raw_bounds(deg_f: list[float], cfg: RuleConfig) -> list[bool]:
    return [t < cfg.bounds_low_f or t > cfg.bounds_high_f for t in deg_f]


def _raw_flatline(deg_f: list[float], cfg: RuleConfig) -> list[bool]:
    n = len(deg_f)
    raw = [False] * n
    w = max(2, int(cfg.flatline_window))
    if n < w:
        return raw
    tol = float(cfg.flatline_tolerance_f)
    for i in range(w - 1, n):
        window = deg_f[i - w + 1 : i + 1]
        if max(window) - min(window) < tol:
            raw[i] = True
    return raw


def _raw_rate(
    deg_f: list[float],
    ts_ms: list[int],
    scale_seconds: float,
    limit: float,
) -> list[bool]:
    n = len(deg_f)
    raw = [False] * n
    for i in range(1, n):
        dt_s = (ts_ms[i] - ts_ms[i - 1]) / 1000.0
        if dt_s <= 0:
            continue
        rate = abs(deg_f[i] - deg_f[i - 1]) / (dt_s / scale_seconds)
        raw[i] = rate > limit
    return raw


def evaluate_all(
    readings: list[dict],
    config: RuleConfig | None = None,
) -> dict[str, list[int]]:
    """
    readings: sorted ascending by ts_ms; each dict has degF, ts_ms.
    Returns int 0/1 series per flag key.
    """
    cfg = config or DEFAULT_CONFIG
    deg_f = [float(r["degF"]) for r in readings]
    ts_ms = [int(r["ts_ms"]) for r in readings]
    raw_map = {
        "temp_out_of_bounds_flag": _raw_bounds(deg_f, cfg),
        "temp_flatline_flag": _raw_flatline(deg_f, cfg),
        "temp_rate_per_hour_flag": _raw_rate(deg_f, ts_ms, 3600.0, cfg.max_f_per_hour),
        "temp_rate_per_minute_flag": _raw_rate(deg_f, ts_ms, 60.0, cfg.max_f_per_minute),
    }
    return {key: [1 if h else 0 for h in raw] for key, raw in raw_map.items()}


# Back-compat module constants
FLAG_LABELS = DEFAULT_CONFIG.flag_labels()
BOUNDS_LOW_F = DEFAULT_CONFIG.bounds_low_f
BOUNDS_HIGH_F = DEFAULT_CONFIG.bounds_high_f
FLATLINE_TOLERANCE_F = DEFAULT_CONFIG.flatline_tolerance_f
FLATLINE_WINDOW = DEFAULT_CONFIG.flatline_window
MAX_F_PER_HOUR = DEFAULT_CONFIG.max_f_per_hour
MAX_F_PER_MINUTE = DEFAULT_CONFIG.max_f_per_minute
ROLLING_WINDOW = DEFAULT_CONFIG.rolling_window
