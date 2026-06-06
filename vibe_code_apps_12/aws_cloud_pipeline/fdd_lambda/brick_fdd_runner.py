"""Run Bake-a-Py rules across BRICK-scoped targets using DynamoDB series."""

from __future__ import annotations

import time
from typing import Any

import open_fdd
from arrow_series import mask_to_flags, prepare_arrow_cfg, rows_to_arrow_table
from brick_rule_targets import TargetBundle, expand_brick_targets, rules_with_brick_scope
from model_schema import validate_model
from open_fdd.arrow_runtime import run_arrow_rule


def series_readings_to_rows(readings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert DynamoDB samples (degF or generic value) to evaluate rows."""
    rows: list[dict[str, Any]] = []
    for i, r in enumerate(readings):
        ts_iso = r.get("ts") or r.get("ts_iso") or ""
        if "degF" in r:
            deg_f = float(r["degF"])
            deg_c = float(r.get("degC", 0))
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
                "unit": r.get("unit", ""),
                "series_id": r.get("series_id"),
                "source": r.get("source"),
            }
        )
    return rows


def align_series_to_primary(
    primary_rows: list[dict[str, Any]],
    series_map: dict[str, list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    """Re-index each series to primary row timestamps (fill None gaps)."""
    if not primary_rows:
        return series_map
    primary_ts = [int(r["ts_ms"]) for r in primary_rows]
    aligned: dict[str, list[dict[str, Any]]] = {}
    for sid, samples in series_map.items():
        by_ts = {int(s["ts_ms"]): s for s in samples}
        aligned[sid] = [by_ts.get(t, {"ts_ms": t, "value": None}) for t in primary_ts]
    return aligned


def evaluate_target(
    rule: dict[str, Any],
    target: TargetBundle,
    series_map: dict[str, list[dict[str, Any]]],
    hours: int,
) -> dict[str, Any]:
    primary = series_map.get(target.primary_series_id, [])
    if not primary:
        return {
            "target_id": target.target_id,
            "equipment_type": target.equipment.get("equipment_type", ""),
            "point_class": target.point.get("brick_type", ""),
            "series_id": target.series_id,
            "hours": hours,
            "rows": 0,
            "flagged": 0,
            "flags": [],
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
    result = run_arrow_rule(code, table, arrow_cfg, rule_id=str(rule["id"]))
    if result.errors:
        return {
            "target_id": target.target_id,
            "equipment_id": target.equipment.get("id", ""),
            "equipment_type": target.equipment.get("equipment_type", ""),
            "point_class": target.point.get("brick_type", ""),
            "external_id": target.point.get("external_id", ""),
            "series_id": target.series_id,
            "hours": hours,
            "rows": len(rows),
            "flagged": 0,
            "flags": [],
            "backend": "arrow",
            "error": "; ".join(result.errors),
        }
    flags = mask_to_flags(result.fault_mask)
    backend = "arrow"

    return {
        "target_id": target.target_id,
        "equipment_id": target.equipment.get("id", ""),
        "equipment_type": target.equipment.get("equipment_type", ""),
        "point_class": target.point.get("brick_type", ""),
        "external_id": target.point.get("external_id", ""),
        "series_id": target.series_id,
        "hours": hours,
        "rows": len(rows),
        "flagged": sum(flags),
        "flags": flags,
        "backend": backend,
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
    """Evaluate all brick-scoped rules across expanded targets."""
    t0 = time.perf_counter()
    scoped = rules_with_brick_scope(rules)
    if not scoped:
        return {
            "site_id": site_id,
            "building_id": building_id,
            "hours": hours,
            "rules_run": 0,
            "targets": [],
            "ms": 0,
            "note": "no rules with brick_scope",
        }

    registry_ids = {
        str(p.get("series_id"))
        for p in ts_store.list_points(site_id, building_id)
        if p.get("series_id")
    }
    health = validate_model(model, registry_series_ids=registry_ids)

    all_results: list[dict[str, Any]] = []
    for rule in scoped:
        if not rule.get("enabled", True):
            continue
        brick_scope = rule.get("brick_scope") or {}
        targets = expand_brick_targets(model, brick_scope)
        for target in targets:
            series_map = ts_store.get_multi_series(target.required_series_ids, hours=hours)
            all_results.append(evaluate_target(rule, target, series_map, hours))

    ms = int((time.perf_counter() - t0) * 1000)
    summary = {
        "site_id": site_id,
        "building_id": building_id,
        "hours": hours,
        "rules_run": len(scoped),
        "targets_evaluated": len(all_results),
        "total_flagged": sum(r.get("flagged", 0) for r in all_results),
        "health_score": health.get("score"),
        "results": all_results,
        "ms": ms,
        "evaluated_at_ms": int(time.time() * 1000),
        "open_fdd_version": getattr(open_fdd, "__version__", "unknown"),
        "fdd_backend": "arrow",
    }
    return summary
