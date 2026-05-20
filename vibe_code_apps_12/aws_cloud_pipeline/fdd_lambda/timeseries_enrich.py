"""
Time-series enrichment for Rule Lab / FDD.

Computes bucketed rolling averages (default 1 minute) and attaches them to
each raw MQTT row so flag_series stay index-aligned with original ts_ms for plotting.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


def attach_minute_rolling_avg(
    rows: list[dict[str, Any]],
    bucket_ms: int = 60_000,
) -> None:
    """
    Mutates rows in place.

    Adds per row (same timeline as raw samples):
      - degF_raw, degC_raw — copy of instantaneous values
      - degF_1min_avg, degC_1min_avg — mean of all samples in the UTC minute bucket
      - minute_bucket_ms — bucket start (ms)
      - sample_count_in_bucket — how many MQTT points in that minute
    """
    if not rows:
        return
    bucket_ms = max(1, int(bucket_ms))
    buckets: dict[int, list[int]] = defaultdict(list)

    for i, row in enumerate(rows):
        row["degF_raw"] = float(row["degF"])
        row["degC_raw"] = float(row.get("degC", 0))
        b = (int(row["ts_ms"]) // bucket_ms) * bucket_ms
        row["minute_bucket_ms"] = b
        buckets[b].append(i)

    for _b, indices in buckets.items():
        f_vals = [rows[i]["degF_raw"] for i in indices]
        c_vals = [rows[i]["degC_raw"] for i in indices]
        n = len(indices)
        avg_f = sum(f_vals) / n
        avg_c = sum(c_vals) / n
        for i in indices:
            rows[i]["degF_1min_avg"] = avg_f
            rows[i]["degC_1min_avg"] = avg_c
            rows[i]["sample_count_in_bucket"] = n


def rolling_avg_field(row: dict[str, Any], field: str = "degF", bucket_label: str = "1min") -> float:
    """Helper for rule code: prefer enriched avg, fall back to raw."""
    key = f"{field}_{bucket_label}_avg"
    if key in row:
        return float(row[key])
    if field == "degF" and "degF_1min_avg" in row:
        return float(row["degF_1min_avg"])
    if field == "degC" and "degC_1min_avg" in row:
        return float(row["degC_1min_avg"])
    return float(row.get(field, row.get("degF_raw", 0)))
