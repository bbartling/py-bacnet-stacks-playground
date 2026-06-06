"""Arrow-only Rule Lab + chart evaluation for VIBE12 (open-fdd 3.x PyPI)."""

from __future__ import annotations

import time
from typing import Any, Callable

from open_fdd.arrow_runtime import detect_rule_backend, run_arrow_rule
from open_fdd.arrow_runtime.backend import lint_arrow_rule
from open_fdd.playground.cookbook import ONE_HOUR_MS
from open_fdd.playground.rule_lab import (  # non-eval chart/CSV helpers
    DEFAULT_ROLLING_AVG_MINUTES,
    GO_LIVE_BATCH_HOURS,
    GO_LIVE_MAX_LOOKBACK_HOURS,
    GO_LIVE_OVERLAP_MINUTES,
    NUMPY_AVAILABLE,
    ROLLING_AVG_MINUTES_ALLOWED,
    _primary_fdd_status,
    aux_series_from_rows,
    build_readings_csv,
    count_flags_in_ts_range,
    downsample_aligned_series,
    eval_rows_preview,
    fault_analytics_from_series,
    normalize_rolling_avg_minutes,
    prepare_rows_for_evaluate,
    slim_fdd_summary,
    window_trace_events,
)
from open_fdd.playground.cookbook import attach_rolling_avg
from open_fdd.playground.series import build_series_context, readings_to_rows as _series_readings_to_rows

from arrow_series import mask_to_flags, prepare_arrow_cfg, rows_to_arrow_table
from brick_fdd_runner import align_series_to_primary, series_readings_to_rows


def evaluate_rules_on_series(
    rules: list[dict[str, Any]],
    primary_rows: list[dict[str, Any]],
    series_map: dict[str, list[dict[str, Any]]],
    *,
    default_rolling_avg_minutes: int = DEFAULT_ROLLING_AVG_MINUTES,
) -> dict[str, list[int]]:
    """Arrow-only cross-sensor evaluation aligned to primary rows."""
    n = len(primary_rows)
    if n == 0:
        return {}
    aligned_map = align_series_to_primary(primary_rows, series_map)
    out: dict[str, list[int]] = {}
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        cfg = rule.get("config") or {}
        aliases = cfg.get("series_aliases") or {}
        out[rule["id"]] = _evaluate_arrow_on_rows(
            rule, primary_rows, aligned_map=aligned_map, aliases=aliases
        )
    return out


def readings_to_rows(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Historian samples → row dicts (degF/value tolerant)."""
    if not readings:
        return []
    if "degF" in readings[0] or "value" in readings[0]:
        return series_readings_to_rows(readings)
    return _series_readings_to_rows(readings)


def lint_python(code: str) -> dict[str, Any]:
    """Arrow rule lint (replaces legacy evaluate() lint)."""
    return lint_arrow_rule(code if isinstance(code, str) else "", strict_imports=True)


def _assert_arrow_rule(code: str, rule: dict[str, Any] | None = None) -> None:
    if detect_rule_backend(code, rule) != "arrow":
        raise ValueError(
            "VIBE12 requires Arrow rules: define apply_faults_arrow(table, cfg, context=None)"
        )


def _evaluate_arrow_on_rows(
    rule: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    aligned_map: dict[str, list[dict[str, Any]]] | None = None,
    aliases: dict[str, str] | None = None,
) -> list[int]:
    code = rule.get("code") or ""
    _assert_arrow_rule(code, rule)
    cfg = dict(rule.get("config") or {})
    if aliases:
        cfg["series_aliases"] = {**(cfg.get("series_aliases") or {}), **aliases}
    arrow_cfg = prepare_arrow_cfg(rule, rows, cfg)
    table = rows_to_arrow_table(rows, aligned_map, aliases=aliases)
    result = run_arrow_rule(code, table, arrow_cfg, rule_id=str(rule.get("id") or ""))
    if result.errors:
        raise ValueError("; ".join(result.errors))
    return mask_to_flags(result.fault_mask)


def evaluate_rules_on_readings(
    rules: list[dict[str, Any]],
    readings: list[dict],
    *,
    rows: list[dict[str, Any]] | None = None,
    default_rolling_avg_minutes: int = DEFAULT_ROLLING_AVG_MINUTES,
) -> tuple[dict[str, list[int]], list[dict[str, Any]]]:
    """Evaluate enabled Arrow rules → per-row flag series keyed by rule id."""
    if rows is None:
        rows = readings_to_rows(readings)
    out: dict[str, list[int]] = {}
    minutes = normalize_rolling_avg_minutes(default_rolling_avg_minutes)
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        cfg = rule.get("config") or {}
        minutes = normalize_rolling_avg_minutes(cfg.get("rolling_avg_minutes", minutes))
        from open_fdd.playground.temp_units import effective_temp_unit

        tunit = effective_temp_unit(cfg)
        prepare_rows_for_evaluate(rows, minutes, temp_unit=tunit)
        out[rule["id"]] = _evaluate_arrow_on_rows(rule, rows)
    return out, rows


def evaluate_rules_on_readings_chunked(
    rules: list[dict[str, Any]],
    readings: list[dict],
    *,
    chunk_hours: float = GO_LIVE_BATCH_HOURS,
    overlap_minutes: int = GO_LIVE_OVERLAP_MINUTES,
    default_rolling_avg_minutes: int = DEFAULT_ROLLING_AVG_MINUTES,
    display_temp_unit: str = "imperial",
) -> tuple[dict[str, list[int]], list[dict[str, Any]]]:
    """Long-window chart eval: time chunks + overlap, OR-merge flags."""
    from open_fdd.playground.temp_units import normalize_temp_unit

    n = len(readings)
    if n == 0:
        return {}, []

    enabled = [r for r in rules if r.get("enabled", True)]
    master: dict[str, list[int]] = {r["id"]: [0] * n for r in enabled}
    rows_master = readings_to_rows(readings)

    window_start_ms = int(readings[0]["ts_ms"])
    window_end_ms = int(readings[-1]["ts_ms"]) + 1
    chunk_ms = max(1, int(float(chunk_hours) * 3600 * 1000))
    overlap_ms = max(int(overlap_minutes * 60_000), 10 * 60_000)
    cursor = window_start_ms
    i_scan = 0

    while cursor < window_end_ms:
        chunk_end = min(cursor + chunk_ms, window_end_ms)
        fetch_start = (
            max(window_start_ms, cursor - overlap_ms)
            if cursor > window_start_ms
            else window_start_ms
        )

        while i_scan < n and int(readings[i_scan]["ts_ms"]) < fetch_start:
            i_scan += 1
        i_start = i_scan
        i_end = i_start
        while i_end < n and int(readings[i_end]["ts_ms"]) < chunk_end:
            i_end += 1

        chunk_readings = readings[i_start:i_end]
        if chunk_readings:
            chunk_rows = readings_to_rows(chunk_readings)
            flag_series, _ = evaluate_rules_on_readings(
                rules,
                chunk_readings,
                rows=chunk_rows,
                default_rolling_avg_minutes=default_rolling_avg_minutes,
            )
            for rule_id, flags in flag_series.items():
                for j, hit in enumerate(flags):
                    gi = i_start + j
                    if gi < n and hit:
                        master[rule_id][gi] = 1

        cursor = chunk_end

    prepare_rows_for_evaluate(
        rows_master,
        normalize_rolling_avg_minutes(default_rolling_avg_minutes),
        temp_unit=normalize_temp_unit(display_temp_unit),
    )
    return master, rows_master


def sweep_rule(
    code: str,
    cfg: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    capture_print: bool = True,
    rolling_avg_minutes: int | None = None,
    series_ctx: dict[str, Any] | None = None,
) -> tuple[list[int], list[dict[str, Any]]]:
    """Test-rule API: run one Arrow rule over rows."""
    rule = {"id": "test", "code": code, "config": cfg, "enabled": True}
    events: list[dict[str, Any]] = []
    try:
        _assert_arrow_rule(code, rule)
    except ValueError as exc:
        return [0] * len(rows), [{"type": "error", "text": str(exc)}]

    minutes = normalize_rolling_avg_minutes(
        rolling_avg_minutes
        if rolling_avg_minutes is not None
        else cfg.get("rolling_avg_minutes", DEFAULT_ROLLING_AVG_MINUTES)
    )
    from open_fdd.playground.temp_units import effective_temp_unit, temp_unit_symbol

    tunit = effective_temp_unit(cfg)
    prepare_rows_for_evaluate(rows, minutes, temp_unit=tunit)
    unit_sym = temp_unit_symbol(tunit)
    events.append(
        {
            "type": "stdout",
            "text": (
                f"--- Arrow rule on {len(rows)} rows "
                f"(temp in {unit_sym}, rolling avg {minutes} min for chart aux) ---\n"
            ),
        }
    )

    try:
        flags = _evaluate_arrow_on_rows(rule, rows)
    except Exception as exc:
        return [0] * len(rows), [{"type": "error", "text": str(exc)}]

    for i, row in enumerate(rows):
        events.append(
            {
                "type": "row",
                "row": row.get("row", i),
                "ts": row.get("ts", ""),
                "status": "fault" if flags[i] else "ok",
                "degF": row.get("degF"),
                "raw_hit": bool(flags[i]),
            }
        )
    if capture_print:
        events.append(
            {
                "type": "stdout",
                "text": f"flagged={sum(flags)} / {len(rows)} rows\n",
            }
        )
    return flags, events


def chunked_evaluate_custom_rules(
    *,
    rules: list[dict[str, Any]],
    lookback_hours: float,
    fetch_interval: Callable[[int, int], list[dict]],
    chunk_hours: float = 6.0,
    default_rolling_avg_minutes: int = DEFAULT_ROLLING_AVG_MINUTES,
    overlap_minutes: int = 15,
    initial_flag_counts: dict[str, int] | None = None,
    window_start_ms: int | None = None,
) -> dict[str, Any]:
    """Go-live AFDD backfill — Arrow rules only, chunked fetches."""
    now_ms = int(time.time() * 1000)
    if window_start_ms is None:
        window_start_ms = now_ms - int(lookback_hours * 3600 * 1000)
    chunk_ms = max(1, int(chunk_hours * 3600 * 1000))
    overlap_ms = max(int(overlap_minutes * 60_000), 10 * 60_000)

    flag_counts: dict[str, int] = dict(initial_flag_counts or {})
    chunk_log: list[dict[str, Any]] = []
    total_samples = 0
    latest: dict[str, Any] | None = None
    cursor = window_start_ms

    enabled_rules = [r for r in rules if r.get("enabled", True)]
    flag_labels = {r["id"]: r.get("title", r["id"]) for r in enabled_rules}

    eval_log = [
        f"AFDD Arrow chunked eval: {lookback_hours}h · {chunk_hours}h chunks · overlap {overlap_minutes}m",
        f"{len(enabled_rules)} enabled rule(s)",
    ]

    chunk_index = 0
    errors: list[str] = []

    while cursor < now_ms:
        chunk_index += 1
        chunk_end = min(cursor + chunk_ms, now_ms)
        fetch_start = max(window_start_ms, cursor - overlap_ms) if cursor > window_start_ms else cursor
        t0 = time.perf_counter()
        try:
            readings = fetch_interval(fetch_start, chunk_end)
        except Exception as exc:
            err = f"chunk {chunk_index} fetch failed: {exc}"
            errors.append(err)
            eval_log.append(f"  {err}")
            chunk_log.append(
                {
                    "chunk": chunk_index,
                    "start_ms": cursor,
                    "end_ms": chunk_end,
                    "samples": 0,
                    "error": str(exc),
                    "ms": int((time.perf_counter() - t0) * 1000),
                }
            )
            cursor = chunk_end
            continue

        if not readings:
            chunk_log.append(
                {
                    "chunk": chunk_index,
                    "start_ms": cursor,
                    "end_ms": chunk_end,
                    "samples": 0,
                    "flagged_in_chunk": 0,
                    "ms": int((time.perf_counter() - t0) * 1000),
                }
            )
            eval_log.append(f"  chunk {chunk_index}: 0 samples (empty window)")
            cursor = chunk_end
            continue

        try:
            rows = readings_to_rows(readings)
            minutes = normalize_rolling_avg_minutes(default_rolling_avg_minutes)
            prepare_rows_for_evaluate(rows, minutes)
            flag_series, rows = evaluate_rules_on_readings(
                rules, readings, rows=rows, default_rolling_avg_minutes=minutes
            )
        except Exception as exc:
            err = f"chunk {chunk_index} eval failed: {exc}"
            errors.append(err)
            eval_log.append(f"  {err}")
            chunk_log.append(
                {
                    "chunk": chunk_index,
                    "start_ms": cursor,
                    "end_ms": chunk_end,
                    "fetched": len(readings),
                    "samples": 0,
                    "error": str(exc),
                    "ms": int((time.perf_counter() - t0) * 1000),
                }
            )
            cursor = chunk_end
            continue

        chunk_counts = count_flags_in_ts_range(flag_series, rows, cursor, chunk_end)
        chunk_flagged = sum(chunk_counts.values())
        for rid, n in chunk_counts.items():
            flag_counts[rid] = flag_counts.get(rid, 0) + n

        in_chunk = sum(1 for r in rows if cursor <= int(r["ts_ms"]) < chunk_end)
        total_samples += in_chunk
        for r in reversed(rows):
            if cursor <= int(r["ts_ms"]) < chunk_end:
                latest = {
                    "ts_ms": r["ts_ms"],
                    "degF": r["degF"],
                    "degC": r.get("degC"),
                }
                break

        ms = int((time.perf_counter() - t0) * 1000)
        chunk_log.append(
            {
                "chunk": chunk_index,
                "start_ms": cursor,
                "end_ms": chunk_end,
                "samples": in_chunk,
                "fetched": len(readings),
                "flagged_in_chunk": chunk_flagged,
                "ms": ms,
            }
        )
        eval_log.append(
            f"  chunk {chunk_index}: {in_chunk} samples, {chunk_flagged} flags, {ms} ms"
        )
        cursor = chunk_end

    if errors:
        eval_log.append(f"  chunk errors: {len(errors)} (see chunk_log.error)")

    active_flags: list[str] = []
    for key, count in flag_counts.items():
        if count > 0:
            active_flags.append(key)

    summary: dict[str, Any] = {
        "fdd_status": _primary_fdd_status(active_flags),
        "active_flags": active_flags,
        "flag_counts": flag_counts,
        "sample_count": total_samples,
        "lookback_hours": lookback_hours,
        "custom_rules": True,
        "flag_labels": flag_labels,
        "afdd_format": "chunked_arrow_v1",
        "chunk_hours": chunk_hours,
        "chunk_count": len(chunk_log),
        "chunk_errors": errors,
        "chunk_log": chunk_log[-40:],
        "eval_log": eval_log
        + [
            f"  total flagged (sum of chunks): {sum(flag_counts.values())}",
            "  chart lanes: live /api/readings (downsampled)",
        ],
        "evaluated_at": int(time.time()),
        "watermark_ms": now_ms,
        "fdd_backend": "arrow",
    }
    if latest:
        summary["latest_sample"] = latest
    return summary
