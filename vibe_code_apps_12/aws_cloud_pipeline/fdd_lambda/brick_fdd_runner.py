"""Run Open-FDD Arrow rules across BRICK-scoped targets using DynamoDB series."""

from __future__ import annotations

import contextlib
import io
import time
from typing import Any

import open_fdd
import pyarrow
from arrow_series import mask_to_flags, prepare_arrow_cfg, rows_to_arrow_table
from brick_rule_targets import TargetBundle, expand_brick_targets, rules_with_brick_scope
from model_schema import validate_model
from open_fdd.arrow_runtime import run_arrow_rule

try:
    import numpy as _np  # noqa: F401

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

OPEN_FDD_VERSION = getattr(open_fdd, "__version__", "unknown")
PYARROW_VERSION = getattr(pyarrow, "__version__", "unknown")
FDD_BACKEND = "arrow"


def series_readings_to_rows(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert DynamoDB samples (degF, %RH, or generic value) to historian rows."""
    rows: list[dict[str, Any]] = []
    for i, r in enumerate(readings):
        ts_iso = r.get("ts") or r.get("ts_iso") or ""
        unit = str(r.get("unit") or "")
        if "degF" in r:
            deg_f = float(r["degF"])
            deg_c = float(r.get("degC", (deg_f - 32) * 5 / 9))
        elif unit in ("%RH", "percent", "rh"):
            deg_f = float(r.get("value", 0))
            deg_c = (deg_f - 32) * 5 / 9
        else:
            deg_f = float(r.get("value", 0))
            deg_c = (deg_f - 32) * 5 / 9
        rows.append(
            {
                "row": i,
                "ts_ms": int(r["ts_ms"]),
                "ts": str(ts_iso).replace("T", " ")[:19],
                "degF": deg_f,
                "degC": deg_c,
                "temp": deg_f,
                "value": r.get("value", deg_f),
                "unit": unit,
                "series_id": r.get("series_id"),
                "source": r.get("source"),
            }
        )
    return rows


def align_series_to_primary(
    primary_rows: list[dict[str, Any]],
    series_map: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    if not primary_rows:
        return series_map
    primary_ts = [int(r["ts_ms"]) for r in primary_rows]
    aligned: dict[str, list[dict[str, Any]]] = {}
    for sid, samples in series_map.items():
        by_ts = {int(s["ts_ms"]): s for s in samples}
        aligned[sid] = [by_ts.get(t, {"ts_ms": t, "value": None}) for t in primary_ts]
    return aligned


def _run_numpy_demo_rule(
    code: str,
    table,
    cfg: dict[str, Any],
    rule_id: str,
) -> tuple[Any, list[str]]:
    """Execute NumPy demo rule outside open-fdd import sandbox (demo only)."""
    import numpy as np
    import pyarrow as pa
    from open_fdd.arrow_runtime.backend import normalize_fault_mask

    ns: dict[str, Any] = {
        "__builtins__": __builtins__,
        "pa": pa,
        "np": np,
        "print": print,
    }
    exec(code, ns)  # noqa: S102
    fn = ns.get("apply_faults_arrow")
    if not callable(fn):
        raise ValueError(f"{rule_id}: missing apply_faults_arrow")
    raw = fn(table, cfg, {"numpy": np})
    mask = normalize_fault_mask(raw, expected_len=table.num_rows)
    return mask, []


def evaluate_target(
    rule: dict[str, Any],
    target: TargetBundle,
    series_map: dict[str, list[dict[str, Any]]],
    hours: int,
) -> dict[str, Any]:
    rule_id = str(rule.get("id") or "")
    base = {
        "rule_id": rule_id,
        "title": rule.get("title", rule_id),
        "target_id": target.target_id,
        "equipment_id": target.equipment.get("id", ""),
        "equipment_type": target.equipment.get("equipment_type", ""),
        "point_class": target.point.get("brick_type", ""),
        "external_id": target.point.get("external_id", ""),
        "series_id": target.series_id,
        "hours": hours,
        "backend": FDD_BACKEND,
        "open_fdd_version": OPEN_FDD_VERSION,
        "numpy_demo": bool(rule.get("numpy_demo")),
    }

    primary = series_map.get(target.primary_series_id, [])
    if not primary:
        return {
            **base,
            "rows": 0,
            "flagged": 0,
            "flags": [],
            "debug_prints": [f"{rule_id}: no telemetry for primary series"],
            "error": "no telemetry for primary series",
        }

    rows = series_readings_to_rows(primary)
    aligned_map = align_series_to_primary(rows, series_map)
    rule_copy = dict(rule)
    cfg = dict(rule.get("config") or {})
    aliases = {**target.series_aliases, **(cfg.get("series_aliases") or {})}
    cfg["series_aliases"] = aliases
    rule_copy["config"] = cfg
    code = rule.get("code") or ""
    arrow_cfg = prepare_arrow_cfg(rule_copy, rows, cfg)
    table = rows_to_arrow_table(rows, aligned_map, aliases=aliases)

    stdout_buf = io.StringIO()
    errors: list[str] = []
    fault_mask = None
    with contextlib.redirect_stdout(stdout_buf):
        try:
            if rule.get("numpy_demo"):
                if not NUMPY_AVAILABLE:
                    errors.append("numpy unavailable")
                    fault_mask = None
                else:
                    fault_mask, _ = _run_numpy_demo_rule(code, table, arrow_cfg, rule_id)
            else:
                result = run_arrow_rule(code, table, arrow_cfg, rule_id=rule_id)
                errors = list(result.errors)
                fault_mask = result.fault_mask
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

    debug_prints = [
        ln.strip() for ln in stdout_buf.getvalue().splitlines() if ln.strip()
    ]

    if errors:
        return {
            **base,
            "rows": len(rows),
            "flagged": 0,
            "flags": [],
            "debug_prints": debug_prints,
            "error": "; ".join(errors),
        }

    import pyarrow as pa

    if fault_mask is None:
        fault_mask = pa.array([False] * len(rows))
    flags = mask_to_flags(fault_mask)
    flagged = sum(flags)
    if not debug_prints:
        debug_prints = [
            f"{rule_id}: rows={len(rows)} flagged={flagged} backend={FDD_BACKEND}"
        ]

    return {
        **base,
        "rows": len(rows),
        "flagged": flagged,
        "flags": flags,
        "debug_prints": debug_prints,
    }


def run_brick_scoped_rules(
    model: dict[str, Any],
    rules: list[dict[str, Any]],
    ts_store,
    site_id: str,
    building_id: str,
    *,
    hours: int = 24,
) -> dict[str, Any]:
    t0 = time.perf_counter()
    scoped = rules_with_brick_scope(rules)
    active_rules = [r for r in scoped if r.get("enabled", True)]

    if not scoped:
        return {
            "site_id": site_id,
            "building_id": building_id,
            "hours": hours,
            "rules_run": 0,
            "targets": [],
            "ms": 0,
            "note": "no rules with brick_scope",
            "open_fdd_version": OPEN_FDD_VERSION,
            "pyarrow_version": PYARROW_VERSION,
            "fdd_backend": FDD_BACKEND,
            "numpy_available": NUMPY_AVAILABLE,
        }

    registry_ids = {
        str(p.get("series_id"))
        for p in ts_store.list_points(site_id, building_id)
        if p.get("series_id")
    }
    health = validate_model(model, registry_series_ids=registry_ids)

    all_results: list[dict[str, Any]] = []
    for rule in active_rules:
        brick_scope = rule.get("brick_scope") or {}
        targets = expand_brick_targets(model, brick_scope)
        for target in targets:
            series_map = ts_store.get_multi_series(target.required_series_ids, hours=hours)
            all_results.append(evaluate_target(rule, target, series_map, hours))

    eval_log = [
        " ".join(r.get("debug_prints") or [f"{r.get('rule_id')}: flagged={r.get('flagged', 0)}"])
        for r in all_results
        if r.get("rows", 0) > 0 or r.get("error")
    ]

    ms = int((time.perf_counter() - t0) * 1000)
    return {
        "site_id": site_id,
        "building_id": building_id,
        "hours": hours,
        "rules_run": len(active_rules),
        "active_rules": [str(r.get("id")) for r in active_rules],
        "targets_evaluated": len(all_results),
        "total_flagged": sum(r.get("flagged", 0) for r in all_results),
        "health_score": health.get("score"),
        "results": all_results,
        "eval_log": eval_log,
        "ms": ms,
        "evaluated_at_ms": int(time.time() * 1000),
        "open_fdd_version": OPEN_FDD_VERSION,
        "pyarrow_version": PYARROW_VERSION,
        "fdd_backend": FDD_BACKEND,
        "numpy_available": NUMPY_AVAILABLE,
    }
