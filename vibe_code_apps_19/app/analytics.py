"""Dataset analytics: date span and motor / fan / pump run hours."""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.role_map import apply_role_map

# Logical roles treated as motor / fan / pump runtime signals (0–100% or bool).
MOTOR_SIGNAL_ROLES: tuple[str, ...] = (
    "fan_cmd",
    "fan_status",
    "chw_pump_cmd",
    "hw_pump_cmd",
    "pump_cmd",
)


def _is_on(series: pd.Series) -> pd.Series:
    """True when a command/status indicates the motor is running."""
    num = pd.to_numeric(series, errors="coerce")
    if num.notna().any():
        scaled = num.where(num <= 1.5, num / 100.0)
        return scaled.fillna(0) > 0.05
    return series.fillna(False).astype(bool)


def dataset_time_span(frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    starts: list[pd.Timestamp] = []
    ends: list[pd.Timestamp] = []
    for df in frames.values():
        if df is None or df.empty or not isinstance(df.index, pd.DatetimeIndex):
            continue
        starts.append(df.index.min())
        ends.append(df.index.max())
    if not starts:
        return {"start": None, "end": None, "span_hours": 0.0}
    start = min(starts)
    end = max(ends)
    span_h = float((end - start).total_seconds() / 3600.0) if end > start else 0.0
    return {"start": start, "end": end, "span_hours": span_h}


def motor_run_hours_for_frame(
    df: pd.DataFrame,
    *,
    poll_seconds: float,
    equipment_id: str = "",
) -> list[dict[str, Any]]:
    """Accumulate on-hours for each motor-like role present on one equipment frame."""
    poll = max(float(poll_seconds), 1.0)
    rows: list[dict[str, Any]] = []
    for role in MOTOR_SIGNAL_ROLES:
        if role not in df.columns or df[role].notna().sum() == 0:
            continue
        on = _is_on(df[role])
        hours = float(on.sum() * poll / 3600.0)
        kind = "fan" if "fan" in role else "pump"
        rows.append(
            {
                "equipment_id": equipment_id,
                "signal": role,
                "motor_kind": kind,
                "run_hours": round(hours, 2),
                "on_samples": int(on.sum()),
                "samples": int(len(df)),
            }
        )
    return rows


def motor_run_hours_table(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
) -> pd.DataFrame:
    """Build a per-equipment motor run-hours table across the loaded dataset."""
    from app.data_loader import infer_poll_seconds

    rows: list[dict[str, Any]] = []
    for eq_id, raw in frames.items():
        mapped = apply_role_map(raw, eq_id, role_map)
        poll = float(raw.attrs.get("poll_seconds") or infer_poll_seconds(raw))
        rows.extend(motor_run_hours_for_frame(mapped, poll_seconds=poll, equipment_id=eq_id))
    if not rows:
        return pd.DataFrame(
            columns=["equipment_id", "signal", "motor_kind", "run_hours", "on_samples", "samples"]
        )
    return pd.DataFrame(rows).sort_values(["motor_kind", "equipment_id", "signal"])


def motor_run_hours_totals(table: pd.DataFrame) -> dict[str, float]:
    if table is None or table.empty:
        return {"fan_hours": 0.0, "pump_hours": 0.0, "total_hours": 0.0}
    prefer = table.copy()
    drop_idx: list = []
    for _eq, grp in prefer.groupby("equipment_id"):
        signals = set(grp["signal"])
        if "fan_status" in signals and "fan_cmd" in signals:
            drop_idx.extend(grp.index[grp["signal"] == "fan_cmd"].tolist())
    prefer = prefer.drop(index=drop_idx)
    fan = float(prefer.loc[prefer["motor_kind"] == "fan", "run_hours"].sum())
    pump = float(prefer.loc[prefer["motor_kind"] == "pump", "run_hours"].sum())
    return {
        "fan_hours": round(fan, 1),
        "pump_hours": round(pump, 1),
        "total_hours": round(fan + pump, 1),
    }


def sensor_fault_summary(
    df: pd.DataFrame,
    results: list,
    *,
    equipment_id: str,
    poll_seconds: float = 300.0,
) -> pd.DataFrame:
    """Summary statistics for sensors involved in FAULT sensor-validation results."""
    rows: list[dict] = []
    sensor_rules = {"SV-RANGE", "SV-FLATLINE", "SV-SPIKE", "SV-STALE"}
    for r in results:
        if getattr(r, "equipment_id", None) != equipment_id:
            continue
        if r.rule_id not in sensor_rules or r.status != "FAULT":
            continue
        series_map = getattr(r, "plot_series", None) or {}
        fault = getattr(r, "confirmed_fault", None)
        for name, s in series_map.items():
            num = pd.to_numeric(s, errors="coerce")
            if num.notna().sum() == 0:
                continue
            fault_vals = num
            if fault is not None:
                mask = fault.reindex(num.index).fillna(False).astype(bool)
                if mask.any():
                    fault_vals = num[mask]
            rows.append(
                {
                    "equipment_id": equipment_id,
                    "rule_id": r.rule_id,
                    "sensor": name,
                    "fault_hours": getattr(r, "fault_hours", None),
                    "n": int(num.notna().sum()),
                    "n_fault_samples": int(fault_vals.notna().sum()) if fault is not None else None,
                    "mean": round(float(num.mean()), 3),
                    "std": round(float(num.std(ddof=0)), 3) if num.notna().sum() > 1 else 0.0,
                    "min": round(float(num.min()), 3),
                    "p50": round(float(num.quantile(0.5)), 3),
                    "max": round(float(num.max()), 3),
                    "fault_mean": round(float(fault_vals.mean()), 3) if fault_vals.notna().any() else None,
                    "fault_min": round(float(fault_vals.min()), 3) if fault_vals.notna().any() else None,
                    "fault_max": round(float(fault_vals.max()), 3) if fault_vals.notna().any() else None,
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "equipment_id",
                "rule_id",
                "sensor",
                "fault_hours",
                "n",
                "n_fault_samples",
                "mean",
                "std",
                "min",
                "p50",
                "max",
                "fault_mean",
                "fault_min",
                "fault_max",
            ]
        )
    return pd.DataFrame(rows)
