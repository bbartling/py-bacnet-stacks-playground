"""
Bake-a-Py style sandbox: lint, execute user Python, sweep telemetry rows.

Each row is enriched with a time-based rolling avg (1, 5, or 10 min by ts_ms) before evaluate().
Optional: import numpy as np, datetime, or math in rule code.
"""

from __future__ import annotations

import ast
import builtins as _builtins
import datetime
import io
import math
import statistics
import traceback
from contextlib import redirect_stdout
from typing import Any, Callable

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    np = None  # type: ignore
    NUMPY_AVAILABLE = False

ALLOWED_IMPORT_ROOTS = frozenset({"datetime", "math", "numpy"})
ROLLING_AVG_MINUTES_ALLOWED = (1, 5, 10)
DEFAULT_ROLLING_AVG_MINUTES = 1


def normalize_rolling_avg_minutes(value: Any) -> int:
    """Clamp to allowed windows: 1, 5, or 10 minutes."""
    try:
        m = int(value)
    except (TypeError, ValueError):
        m = DEFAULT_ROLLING_AVG_MINUTES
    if m not in ROLLING_AVG_MINUTES_ALLOWED:
        return min(ROLLING_AVG_MINUTES_ALLOWED, key=lambda x: abs(x - m))
    return m


def lint_python(code: str) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    if not code.strip():
        return {"ok": True, "issues": issues}
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        line = e.lineno or 1
        col = e.offset or 1
        issues.append(
            {
                "line": line,
                "col": col,
                "end_col": col + 1,
                "message": e.msg or "invalid syntax",
                "severity": "error",
            }
        )
        return {"ok": False, "issues": issues}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root not in ALLOWED_IMPORT_ROOTS:
                    issues.append(
                        {
                            "line": node.lineno,
                            "col": node.col_offset or 1,
                            "end_col": (node.col_offset or 1) + 6,
                            "message": f"import '{alias.name}' not allowed",
                            "severity": "warning",
                        }
                    )
        elif isinstance(node, ast.ImportFrom) and node.module:
            root = node.module.split(".")[0]
            if root not in ALLOWED_IMPORT_ROOTS:
                issues.append(
                    {
                        "line": node.lineno,
                        "col": node.col_offset or 1,
                        "end_col": (node.col_offset or 1) + 6,
                        "message": f"import from '{node.module}' not allowed",
                        "severity": "warning",
                    }
                )
    return {"ok": not any(i["severity"] == "error" for i in issues), "issues": issues}


def _restricted_import(
    name: str,
    globals: Any = None,
    locals: Any = None,
    fromlist: Any = (),
    level: int = 0,
) -> Any:
    root = name.split(".")[0]
    if root not in ALLOWED_IMPORT_ROOTS:
        raise ImportError(f"import of '{name}' not allowed (allowed: {', '.join(sorted(ALLOWED_IMPORT_ROOTS))})")
    return _builtins.__import__(name, globals, locals, fromlist, level)


def _sandbox_builtins() -> dict[str, Any]:
    return {
        "print": print,
        "range": range,
        "len": len,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sum": sum,
        "enumerate": enumerate,
        "zip": zip,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "True": True,
        "False": False,
        "None": None,
        "__import__": _restricted_import,
    }


def _normalize_hit(raw: Any) -> bool:
    if raw is None or raw is False:
        return False
    if raw is True:
        return True
    if isinstance(raw, (int, float)):
        return bool(raw)
    if isinstance(raw, str):
        return True
    if isinstance(raw, dict):
        return True
    return bool(raw)


def readings_to_rows(readings: list[dict]) -> list[dict[str, Any]]:
    """Build row dicts for evaluate()."""
    rows: list[dict[str, Any]] = []
    for i, r in enumerate(readings):
        ts_iso = r.get("ts_iso") or ""
        rows.append(
            {
                "row": i,
                "ts_ms": int(r["ts_ms"]),
                "ts": ts_iso.replace("T", " ")[:19],
                "degF": float(r["degF"]),
                "degC": float(r.get("degC", 0)),
                "seq": r.get("seq"),
                "source": r.get("source"),
            }
        )
    return rows


def _median_sample_ms(rows: list[dict[str, Any]]) -> int:
    if len(rows) < 2:
        return 10_000
    dts = [
        int(rows[i]["ts_ms"]) - int(rows[i - 1]["ts_ms"])
        for i in range(1, len(rows))
        if int(rows[i]["ts_ms"]) > int(rows[i - 1]["ts_ms"])
    ]
    if not dts:
        return 10_000
    return int(statistics.median(dts))


def attach_rolling_avg(
    rows: list[dict[str, Any]],
    window_minutes: int = DEFAULT_ROLLING_AVG_MINUTES,
) -> None:
    """
    Mutates rows in place. Trailing mean of degF over samples with
    ts_ms in [row.ts_ms - window_minutes*60_000, row.ts_ms].
    """
    if not rows:
        return
    minutes = normalize_rolling_avg_minutes(window_minutes)
    window_ms = minutes * 60_000
    period_ms = _median_sample_ms(rows)
    j_start = 0
    for i, row in enumerate(rows):
        row["degF_raw"] = float(row["degF"])
        ts = int(row["ts_ms"])
        cutoff = ts - window_ms
        while j_start < i and int(rows[j_start]["ts_ms"]) < cutoff:
            j_start += 1
        window = rows[j_start : i + 1]
        row["degF_rolling_avg"] = sum(r["degF_raw"] for r in window) / len(window)
        row["sample_period_ms"] = period_ms
        row["rolling_avg_minutes"] = minutes
        row["rolling_window_ms"] = window_ms
        row["samples_in_avg"] = len(window)


def prepare_rows_for_evaluate(
    rows: list[dict[str, Any]],
    rolling_avg_minutes: int = DEFAULT_ROLLING_AVG_MINUTES,
) -> list[dict[str, Any]]:
    """Enrich rows before a sweep; recomputes when window minutes change."""
    if not rows:
        return rows
    minutes = normalize_rolling_avg_minutes(rolling_avg_minutes)
    if rows[0].get("rolling_avg_minutes") != minutes or "degF_rolling_avg" not in rows[0]:
        attach_rolling_avg(rows, minutes)
    return rows


def slim_fdd_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """
    DynamoDB item max ~400 KB. Drop full ts_ms / flag_series (7 d backfill).
    Dashboard recomputes fault_plots on each /api/readings request.
    """
    return {
        k: v
        for k, v in summary.items()
        if k not in ("ts_ms", "flag_series", "aux_series")
    }


def eval_rows_preview(rows: list[dict[str, Any]], limit: int = 200) -> list[dict[str, Any]]:
    """Slim row dicts for Rule Lab table (last N samples)."""
    slim_keys = (
        "row",
        "ts",
        "degF",
        "degF_raw",
        "degF_rolling_avg",
        "sample_period_ms",
        "rolling_avg_minutes",
        "samples_in_avg",
    )
    out: list[dict[str, Any]] = []
    for r in rows[-limit:]:
        out.append({k: r[k] for k in slim_keys if k in r})
    return out


def aux_series_from_rows(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    """Chart overlay from enriched rows or rule-authored degF_1min_avg."""
    if not rows:
        return {}
    if "degF_1min_avg" in rows[0]:
        return {
            "degF_1min_avg": [float(r["degF_1min_avg"]) for r in rows],
            "degF_raw": [float(r.get("degF_raw", r["degF"])) for r in rows],
        }
    if "degF_rolling_avg" in rows[0]:
        return {
            "degF_1min_avg": [float(r["degF_rolling_avg"]) for r in rows],
            "degF_raw": [float(r.get("degF_raw", r["degF"])) for r in rows],
        }
    return {}


def _rule_sandbox() -> dict[str, Any]:
    sandbox: dict[str, Any] = {
        "__builtins__": _sandbox_builtins(),
        "__name__": "__rule__",
        "math": math,
        "datetime": datetime,
        "timezone": datetime.timezone,
    }
    if NUMPY_AVAILABLE and np is not None:
        sandbox["np"] = np
        sandbox["numpy"] = np
    return sandbox


def compile_evaluate(code: str) -> Callable[..., Any]:
    sandbox = _rule_sandbox()
    exec(compile(code, "<rule>", "exec"), sandbox, sandbox)
    fn = sandbox.get("evaluate")
    if not callable(fn):
        raise ValueError("Rule code must define evaluate(row, cfg, prev_row=None, rows=None)")
    return fn


def sweep_rule(
    code: str,
    cfg: dict[str, Any],
    rows: list[dict[str, Any]],
    *,
    capture_print: bool = True,
    rolling_avg_minutes: int | None = None,
) -> tuple[list[int], list[dict[str, Any]]]:
    """
    Returns (flag_series 0/1 per raw row, events for console UI).
    flag_series = evaluate() result per row (no backend debounce).
    """
    events: list[dict[str, Any]] = []
    lint = lint_python(code)
    if not lint["ok"]:
        return [], [{"type": "error", "text": "syntax error — fix before run\n"}]

    minutes = normalize_rolling_avg_minutes(
        rolling_avg_minutes
        if rolling_avg_minutes is not None
        else cfg.get("rolling_avg_minutes", DEFAULT_ROLLING_AVG_MINUTES)
    )
    prepare_rows_for_evaluate(rows, minutes)
    evaluate = compile_evaluate(code)
    raw_hits: list[bool] = []
    stream_buf: list[dict[str, Any]] = []

    class _Cap(io.TextIOBase):
        def write(self, s: str) -> int:
            if s and capture_print:
                stream_buf.append({"type": "stdout", "text": s})
            return len(s or "")

    cap = _Cap()

    events.append(
        {
            "type": "stdout",
            "text": (
                f"--- sweeping {len(rows)} rows "
                f"(degF_rolling_avg on each row, {minutes} min window by ts_ms) ---\n"
            ),
        }
    )

    tripped = 0
    for i, row in enumerate(rows):
        prev = rows[i - 1] if i else None
        stream_buf.clear()
        try:
            with redirect_stdout(cap):
                hit = _normalize_hit(evaluate(row, cfg, prev, rows))
            raw_hits.append(hit)
            for ev in stream_buf:
                events.append(ev)
            status = "fault" if hit else "ok"
            if hit:
                tripped += 1
            events.append(
                {
                    "type": "row",
                    "row": row["row"],
                    "ts": row["ts"],
                    "status": status,
                    "degF": row["degF"],
                    "raw_hit": hit,
                }
            )
        except Exception as exc:
            raw_hits.append(False)
            events.append(
                {
                    "type": "row",
                    "row": row["row"],
                    "ts": row["ts"],
                    "status": "error",
                    "message": str(exc),
                }
            )
            events.append(
                {"type": "stdout", "text": f"  row {row['row']}: ERROR {exc}\n"}
            )

    flags = [1 if h else 0 for h in raw_hits]
    events.append(
        {
            "type": "summary",
            "rows": len(rows),
            "raw_tripped": tripped,
            "flagged": sum(flags),
        }
    )
    events.append(
        {
            "type": "stdout",
            "text": f"--- done: {sum(flags)} flagged, {len(rows)} rows ---\n",
        }
    )
    return flags, events


def evaluate_rules_on_readings(
    rules: list[dict[str, Any]],
    readings: list[dict],
    *,
    rows: list[dict[str, Any]] | None = None,
    default_rolling_avg_minutes: int = DEFAULT_ROLLING_AVG_MINUTES,
) -> tuple[dict[str, list[int]], list[dict[str, Any]]]:
    """All enabled rules → flag_series keyed by rule id. Returns (flags, rows) for chart aux."""
    if rows is None:
        rows = readings_to_rows(readings)
    out: dict[str, list[int]] = {}
    chart_minutes = normalize_rolling_avg_minutes(default_rolling_avg_minutes)
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        code = rule.get("code") or ""
        cfg = rule.get("config") or {}
        minutes = normalize_rolling_avg_minutes(
            cfg.get("rolling_avg_minutes", chart_minutes)
        )
        prepare_rows_for_evaluate(rows, minutes)
        flags, _events = sweep_rule(
            code, cfg, rows, capture_print=False, rolling_avg_minutes=minutes
        )
        out[rule["id"]] = flags
        chart_minutes = minutes
    if rows and "degF_rolling_avg" not in rows[0]:
        prepare_rows_for_evaluate(rows, chart_minutes)
    return out, rows
