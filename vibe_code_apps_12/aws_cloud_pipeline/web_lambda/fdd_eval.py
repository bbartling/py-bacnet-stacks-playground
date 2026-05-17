"""Demo FDD on a window of telemetry (matches fdd_lambda/rules/ds18b20_demo_rules.yml defaults)."""

from __future__ import annotations

import time

STALE_MINUTES = 10
FLATLINE_MAX_RANGE_C = 0.15
OUT_OF_RANGE_MIN_C = 5.0
OUT_OF_RANGE_MAX_C = 40.0
SPIKE_MAX_DELTA_C = 3.0


def evaluate_readings(readings: list[dict]) -> dict:
    """
    readings: sorted list with ts_ms, degC (and optional fields).
    Returns overall status + per-point fault flags for chart overlay.
    """
    n = len(readings)
    point_fault = [False] * n
    if n == 0:
        return {
            "status": "MISSING_DATA",
            "details": ["MISSING_DATA"],
            "point_fault": point_fault,
        }

    vals = [float(r["degC"]) for r in readings]
    ts_list = [int(r["ts_ms"]) for r in readings]
    details: list[str] = []
    now_ms = int(time.time() * 1000)

    if (now_ms - ts_list[-1]) > STALE_MINUTES * 60 * 1000:
        details.append("MISSING_DATA")
        point_fault[-1] = True

    for i in range(1, n):
        gap_min = (ts_list[i] - ts_list[i - 1]) / 60000.0
        if gap_min > STALE_MINUTES:
            details.append("MISSING_DATA")
            point_fault[i] = True

    if n >= 3 and (max(vals) - min(vals)) < FLATLINE_MAX_RANGE_C:
        details.append("FLATLINE")
        for i in range(n):
            point_fault[i] = True

    lo, hi = OUT_OF_RANGE_MIN_C, OUT_OF_RANGE_MAX_C
    for i, c in enumerate(vals):
        if c < lo or c > hi:
            if "OUT_OF_RANGE" not in details:
                details.append("OUT_OF_RANGE")
            point_fault[i] = True

    for i in range(1, n):
        if abs(vals[i] - vals[i - 1]) > SPIKE_MAX_DELTA_C:
            if "SPIKE" not in details:
                details.append("SPIKE")
            point_fault[i] = True
            point_fault[i - 1] = True

    if not details:
        details.append("NORMAL")
        status = "NORMAL"
    else:
        status = "NORMAL" if details == ["NORMAL"] else details[0]

    return {"status": status, "details": details, "point_fault": point_fault}
