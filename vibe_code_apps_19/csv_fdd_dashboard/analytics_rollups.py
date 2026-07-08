"""ECM / rule analytics rollups for engineer export."""

from __future__ import annotations

from typing import Any

import pandas as pd

from generate_dashboard import FAULT_EQUATIONS


def _hours(series: pd.Series, poll_seconds: float) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(series.fillna(False).astype(bool).sum()) * poll_seconds / 3600.0


def _sensor_stats(df: pd.DataFrame, mask: pd.Series, columns: list[str]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for col in columns:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        fault_vals = s[mask]
        ok_vals = s[~mask]
        out[col] = {
            "mean_fault": float(fault_vals.mean()) if fault_vals.notna().any() else None,
            "mean_ok": float(ok_vals.mean()) if ok_vals.notna().any() else None,
            "min": float(s.min()) if s.notna().any() else None,
            "max": float(s.max()) if s.notna().any() else None,
        }
    return out


def rollup_rule(
    df: pd.DataFrame,
    fault_col: str,
    *,
    rule_id: str,
    ecm_id: str,
    poll_seconds: float,
    occupied: pd.Series | None = None,
    sensor_cols: list[str] | None = None,
) -> dict[str, Any]:
    if fault_col not in df.columns:
        return {
            "rule_id": rule_id,
            "ecm_id": ecm_id,
            "total_hours": 0.0,
            "fault_hours": 0.0,
            "fault_pct": 0.0,
            "equation": FAULT_EQUATIONS.get(rule_id, ""),
        }
    fault = df[fault_col].fillna(False).astype(bool)
    total_h = len(df) * poll_seconds / 3600.0
    fault_h = _hours(fault, poll_seconds)
    occ_fault_h = unocc_fault_h = 0.0
    if occupied is not None and len(occupied) == len(fault):
        occ_fault_h = _hours(fault & occupied, poll_seconds)
        unocc_fault_h = _hours(fault & ~occupied, poll_seconds)
    return {
        "rule_id": rule_id,
        "ecm_id": ecm_id,
        "total_hours": round(total_h, 2),
        "fault_hours": round(fault_h, 2),
        "fault_pct": round(100.0 * fault_h / total_h, 2) if total_h else 0.0,
        "occupied_fault_hours": round(occ_fault_h, 2),
        "unoccupied_fault_hours": round(unocc_fault_h, 2),
        "equation": FAULT_EQUATIONS.get(rule_id, ""),
        "sensors": _sensor_stats(df, fault, sensor_cols or []),
    }


def rollup_ahu(df: pd.DataFrame, *, poll_seconds: float, occupied: pd.Series | None = None) -> list[dict[str, Any]]:
    rules = [
        ("COMFORT", "ECM-1", "fault_comfort"),
        ("SAT_RESET", "ECM-2", "fault_sat_reset"),
        ("STATIC", "ECM-3", "fault_static"),
        ("ECONOMIZER", "ECM-4", "fault_economizer"),
        ("FREE_COOL", "ECM-5", "fault_free_cool"),
    ]
    cols = [c for c in df.columns if c.endswith("_f") or c in ("SAT", "RAT", "OAT", "SAT_SP", "STATIC_SP")]
    return [
        rollup_rule(df, col, rule_id=r, ecm_id=e, poll_seconds=poll_seconds, occupied=occupied, sensor_cols=cols)
        for r, e, col in rules
        if col in df.columns
    ]


def analytics_html(ecms: list[dict[str, Any]]) -> str:
    if not ecms:
        return "<p class='text-muted small'>No analytics for this view.</p>"
    rows = []
    for e in ecms:
        rows.append(
            f"<tr><td>{e.get('ecm_id','')}</td><td>{e.get('rule_id','')}</td>"
            f"<td>{e.get('fault_hours',0):.1f} h</td><td>{e.get('fault_pct',0):.1f}%</td></tr>"
        )
    return (
        "<table class='table table-sm ecm-analytics-table mb-0'>"
        "<thead><tr><th>ECM</th><th>Rule</th><th>Fault hrs</th><th>%</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def export_records(pages: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for page_id, ecms in pages.items():
        for e in ecms:
            row = {"page_id": page_id, **e}
            out.append(row)
    return out
