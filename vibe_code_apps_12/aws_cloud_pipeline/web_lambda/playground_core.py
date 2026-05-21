"""
Bake-a-Py style sandbox: lint, execute user Python, sweep telemetry rows.

Each row is enriched with adaptive rolling avg (~60s window) before evaluate().
Optional: import numpy as np in rule code (see web_lambda/requirements.txt).
"""

from __future__ import annotations

import ast
import builtins as _builtins
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

ALLOWED_IMPORT_ROOTS = frozenset({"math", "numpy"})
ROLLING_TARGET_MS = 60_000


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


def attach_adaptive_rolling_avg(
    rows: list[dict[str, Any]],
    target_window_ms: int = ROLLING_TARGET_MS,
) -> None:
    """
    Mutates rows in place. Adds degF_raw, degF_rolling_avg, sample_period_ms,
    rolling_window_samples (same metadata on every row for easy rule access).
    """
    if not rows:
        return
    period_ms = _median_sample_ms(rows)
    window_n = 2
    if len(rows) >= 2:
        window_n = max(
            2,
            min(round(target_window_ms / period_ms), 900),
        )
    for i, row in enumerate(rows):
        row["degF_raw"] = float(row["degF"])
        start = max(0, i - window_n + 1)
        window = rows[start : i + 1]
        row["degF_rolling_avg"] = sum(r["degF_raw"] for r in window) / len(window)
        row["sample_period_ms"] = period_ms
        row["rolling_window_samples"] = window_n
        row["rolling_target_ms"] = target_window_ms


def prepare_rows_for_evaluate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich rows once before a sweep (idempotent)."""
    if rows and "degF_rolling_avg" not in rows[0]:
        attach_adaptive_rolling_avg(rows)
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
        "rolling_window_samples",
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
) -> tuple[list[int], list[dict[str, Any]]]:
    """
    Returns (flag_series 0/1 per raw row, events for console UI).
    flag_series = evaluate() result per row (no backend debounce).
    """
    events: list[dict[str, Any]] = []
    lint = lint_python(code)
    if not lint["ok"]:
        return [], [{"type": "error", "text": "syntax error — fix before run\n"}]

    prepare_rows_for_evaluate(rows)
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
                f"(degF_rolling_avg on each row, ~{ROLLING_TARGET_MS // 1000}s window) ---\n"
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
) -> tuple[dict[str, list[int]], list[dict[str, Any]]]:
    """All enabled rules → flag_series keyed by rule id. Returns (flags, rows) for chart aux."""
    if rows is None:
        rows = readings_to_rows(readings)
    prepare_rows_for_evaluate(rows)
    out: dict[str, list[int]] = {}
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        code = rule.get("code") or ""
        cfg = rule.get("config") or {}
        flags, _events = sweep_rule(code, cfg, rows, capture_print=False)
        out[rule["id"]] = flags
    return out, rows
