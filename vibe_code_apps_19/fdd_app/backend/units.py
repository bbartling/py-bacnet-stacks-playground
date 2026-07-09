"""Display-layer unit conversion — canonical compute stays in °F / in.w.c."""

from __future__ import annotations

import re
from typing import Any

DISPLAY_UNITS = "imperial"  # imperial | metric

_TEMP_UNITS = frozenset({"°F", "F", "degF"})
_PRESSURE_UNITS = frozenset({"in. w.c.", "in w.c.", "inwc"})


def set_display_units(mode: str) -> None:
    global DISPLAY_UNITS
    DISPLAY_UNITS = "metric" if str(mode).lower() == "metric" else "imperial"


def is_metric() -> bool:
    return DISPLAY_UNITS == "metric"


def temp_unit() -> str:
    return "°C" if is_metric() else "°F"


def pressure_unit() -> str:
    return "Pa" if is_metric() else "in. w.c."


def f_to_c(value: float) -> float:
    return (float(value) - 32.0) * 5.0 / 9.0


def inwc_to_pa(value: float) -> float:
    return float(value) * 249.08891


def disp_temp(value_f: float, *, digits: int = 1) -> float:
    if is_metric():
        return round(f_to_c(value_f), digits)
    return round(float(value_f), digits)


def fmt_temp(value_f: float, *, digits: int = 1) -> str:
    v = disp_temp(value_f, digits=digits)
    d = digits if is_metric() else (0 if float(value_f).is_integer() else digits)
    return f"{v:.{d}f}{temp_unit()}"


def fmt_pressure(value_inwc: float, *, digits: int = 2) -> str:
    if is_metric():
        return f"{inwc_to_pa(value_inwc):.{0 if value_inwc >= 1 else digits}f}{pressure_unit()}"
    return f"{float(value_inwc):.{digits}f}{pressure_unit()}"


def convert_param_def(meta: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of a PARAM_DEF with display units applied to slider bounds."""
    out = dict(meta)
    unit = str(meta.get("unit", ""))
    if unit in _TEMP_UNITS:
        out["unit"] = temp_unit()
        if is_metric():
            out["min"] = round(f_to_c(meta["min"]), 1)
            out["max"] = round(f_to_c(meta["max"]), 1)
            out["step"] = max(0.1, round(meta["step"] * 5 / 9, 2))
    elif unit in _PRESSURE_UNITS:
        out["unit"] = pressure_unit()
        if is_metric():
            out["min"] = round(inwc_to_pa(meta["min"]))
            out["max"] = round(inwc_to_pa(meta["max"]))
            out["step"] = max(1, round(inwc_to_pa(meta["step"])))
    return out


def display_param_value(key: str, value: float, meta: dict[str, Any]) -> float:
    unit = str(meta.get("unit", ""))
    if unit in _TEMP_UNITS and is_metric():
        return round(f_to_c(value), 2)
    if unit in _PRESSURE_UNITS and is_metric():
        return round(inwc_to_pa(value), 2)
    return float(value)


def canonical_param_value(key: str, value: float, meta: dict[str, Any]) -> float:
    """Convert display-layer slider value back to canonical for compute."""
    unit = str(meta.get("unit", ""))
    if unit in _TEMP_UNITS and is_metric():
        return float(value) * 9.0 / 5.0 + 32.0
    if unit in _PRESSURE_UNITS and is_metric():
        return float(value) / 249.08891
    return float(value)


def substitute_temp_text(text: str) -> str:
    """Replace °F literals in fault-equation strings for metric display."""

    def _repl(m: re.Match[str]) -> str:
        val = float(m.group(1))
        return fmt_temp(val)

    return re.sub(r"(-?\d+(?:\.\d+)?)\s*°F", _repl, text)


def _trace_looks_like_temp(trace: Any) -> bool:
    y = getattr(trace, "y", None)
    if y is None or len(y) == 0:
        return False
    try:
        nums = [float(v) for v in y if v is not None]
    except (TypeError, ValueError):
        return False
    if not nums:
        return False
    lo, hi = min(nums), max(nums)
    return -60 <= lo <= 250 and -60 <= hi <= 250


def apply_fig_display_units(fig: Any) -> Any:
    """Convert temperature traces/axes in a Plotly figure for metric display."""
    if not is_metric():
        return fig

    for trace in fig.data:
        if _trace_looks_like_temp(trace) and getattr(trace, "y", None) is not None:
            trace.y = [f_to_c(v) if v is not None else None for v in trace.y]
        if getattr(trace, "y0", None) is not None and _trace_looks_like_temp(trace):
            trace.y0 = f_to_c(trace.y0)
        if getattr(trace, "y1", None) is not None and _trace_looks_like_temp(trace):
            trace.y1 = f_to_c(trace.y1)

    for shape in list(fig.layout.shapes or []):
        if shape.y0 is not None and -60 <= float(shape.y0) <= 250:
            shape.y0 = f_to_c(shape.y0)
        if shape.y1 is not None and -60 <= float(shape.y1) <= 250:
            shape.y1 = f_to_c(shape.y1)

    for ann in list(fig.layout.annotations or []):
        if ann.y is not None and -60 <= float(ann.y) <= 250:
            ann.y = f_to_c(ann.y)
        if ann.text:
            ann.text = substitute_temp_text(str(ann.text))

    layout = fig.layout
    if layout.yaxis and layout.yaxis.title and layout.yaxis.title.text:
        t = str(layout.yaxis.title.text)
        if "°F" in t or "temp" in t.lower():
            layout.yaxis.title.text = re.sub(r"°F", "°C", t)
    # layout.yaxis2 raises AttributeError (not None) when the figure has a single
    # y-axis in this plotly version, so use getattr to fall back safely.
    yaxis2 = getattr(layout, "yaxis2", None)
    if yaxis2 and yaxis2.title and yaxis2.title.text:
        t = str(yaxis2.title.text)
        if "°F" in t:
            yaxis2.title.text = re.sub(r"°F", "°C", t)

    if layout.title and layout.title.text:
        layout.title.text = substitute_temp_text(str(layout.title.text))

    return fig
