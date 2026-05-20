"""
Bake-a-Py style sandbox: lint, execute user Python, sweep telemetry rows.

No backend rolling_window debounce or 1-min avg helpers — students implement those
in browser Python (see EXPRESSION_RULE_COOKBOOK.md).
"""

from __future__ import annotations

import ast
import io
import math
import traceback
from contextlib import redirect_stdout
from typing import Any, Callable


ALLOWED_IMPORT_ROOTS = frozenset({"math"})


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


def aux_series_from_rows(rows: list[dict[str, Any]]) -> dict[str, list[float]]:
    """
    Chart overlay when your rule code sets keys on rows (e.g. degF_1min_avg).
    The backend does not compute these — only reads what you wrote in evaluate().
    """
    if not rows or "degF_1min_avg" not in rows[0]:
        return {}
    return {
        "degF_1min_avg": [float(r["degF_1min_avg"]) for r in rows],
        "degF_raw": [float(r.get("degF_raw", r["degF"])) for r in rows],
    }


def compile_evaluate(code: str) -> Callable[..., Any]:
    sandbox: dict[str, Any] = {
        "__builtins__": _sandbox_builtins(),
        "__name__": "__rule__",
        "math": math,
    }
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
            "text": f"--- sweeping {len(rows)} rows (your evaluate() only) ---\n",
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
    out: dict[str, list[int]] = {}
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        code = rule.get("code") or ""
        cfg = rule.get("config") or {}
        flags, _events = sweep_rule(code, cfg, rows, capture_print=False)
        out[rule["id"]] = flags
    return out, rows
