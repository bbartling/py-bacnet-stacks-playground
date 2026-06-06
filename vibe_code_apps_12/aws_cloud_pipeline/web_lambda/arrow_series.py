"""DynamoDB series → PyArrow tables for open-fdd 3.x Arrow rules."""

from __future__ import annotations

import re
import statistics
from typing import Any

import pyarrow as pa

ONE_HOUR_MS = 60 * 60 * 1000
FIFTEEN_MIN_MS = 15 * 60 * 1000
TWENTY_FOUR_HOUR_MS = 24 * ONE_HOUR_MS
FILL_RATIO = 0.95


def median_sample_ms(rows: list[dict[str, Any]]) -> int:
    if len(rows) < 2:
        return 300_000
    dts = [
        int(rows[i]["ts_ms"]) - int(rows[i - 1]["ts_ms"])
        for i in range(1, len(rows))
        if int(rows[i]["ts_ms"]) > int(rows[i - 1]["ts_ms"])
    ]
    return int(statistics.median(dts)) if dts else 300_000


def window_samples_for_span(rows: list[dict[str, Any]], span_ms: int) -> int:
    dt = median_sample_ms(rows)
    return max(2, int(span_ms * FILL_RATIO / dt))


def _safe_column_name(name: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9_]+", "_", str(name).strip())
    return out or "series"


def rows_to_arrow_table(
    rows: list[dict[str, Any]],
    aligned_map: dict[str, list[dict[str, Any]]] | None = None,
    *,
    aliases: dict[str, str] | None = None,
) -> pa.Table:
    """Build a historian table from primary rows plus aligned cross-sensor series."""
    if not rows:
        return pa.table({"ts_ms": pa.array([], type=pa.int64())})

    columns: dict[str, list[Any]] = {
        "ts_ms": [int(r["ts_ms"]) for r in rows],
        "ts": [str(r.get("ts") or "") for r in rows],
        "temp": [float(r["temp"]) if r.get("temp") is not None else None for r in rows],
        "degF": [float(r["degF"]) if r.get("degF") is not None else None for r in rows],
        "degC": [float(r["degC"]) if r.get("degC") is not None else None for r in rows],
        "value": [float(r["value"]) if r.get("value") is not None else None for r in rows],
    }

    aligned_map = aligned_map or {}
    alias_to_sid = aliases or {}
    sid_to_alias = {v: k for k, v in alias_to_sid.items()}

    for sid, samples in aligned_map.items():
        if sid == rows[0].get("series_id"):
            continue
        col_names = {_safe_column_name(sid)}
        alias = sid_to_alias.get(sid)
        if alias:
            col_names.add(_safe_column_name(alias))
        values = [
            float(s["value"]) if s.get("value") is not None else None for s in samples
        ]
        for col in col_names:
            columns[col] = list(values)

    return pa.table(columns)


def prepare_arrow_cfg(
    rule: dict[str, Any],
    rows: list[dict[str, Any]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Map vibe12 rule config to open-fdd Arrow cookbook keys."""
    out = dict(cfg)
    rule_id = str(rule.get("id") or "")

    if "humidity_low" in out and "bounds_low_rh" not in out:
        out["bounds_low_rh"] = out["humidity_low"]
    if "humidity_high" in out and "bounds_high_rh" not in out:
        out["bounds_high_rh"] = out["humidity_high"]
    if rule_id == "brick_outside_humidity_oob" or out.get("value_kind") == "rh":
        out.setdefault("value_kind", "rh")
        out.setdefault("value_column", "value")

    if "max_spread_15min" in out and "max_spread" not in out:
        out["max_spread"] = out["max_spread_15min"]
    if "max_spread_24h" in out and "max_spread" not in out:
        out["max_spread"] = out["max_spread_24h"]

    if rule_id.endswith("swing_15m") or "max_spread_15min" in out:
        out["window_samples"] = window_samples_for_span(rows, FIFTEEN_MIN_MS)
    elif rule_id.endswith("peak_swing_24h") or "max_spread_24h" in out:
        out["window_samples"] = window_samples_for_span(rows, TWENTY_FOUR_HOUR_MS)
    elif rule_id.endswith("flatline_1h") or "flatline_tolerance" in out:
        out["window_samples"] = window_samples_for_span(rows, ONE_HOUR_MS)

    return out


def mask_to_flags(mask: pa.Array | pa.ChunkedArray) -> list[int]:
    flat = mask.combine_chunks() if isinstance(mask, pa.ChunkedArray) else mask
    return [1 if bool(v) else 0 for v in flat.to_pylist()]
