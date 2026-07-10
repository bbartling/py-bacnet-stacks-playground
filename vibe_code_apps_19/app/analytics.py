"""Dataset analytics: date span, motor hours, mech-cooling OAT bins."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from app.role_map import apply_role_map
from app.site_model import equipment_type_from_id

# Logical roles treated as motor / fan / pump runtime signals (0–100% or bool).
MOTOR_SIGNAL_ROLES: tuple[str, ...] = (
    "fan_cmd",
    "fan_status",
    "chw_pump_cmd",
    "hw_pump_cmd",
    "pump_cmd",
)

# Mechanical cooling proof — chillers / DX compressors only (NOT hydronic cool valves).
CHILLER_RUN_ROLES: tuple[str, ...] = (
    "compressor_status",
    "chiller_status",
    "equipment_enable",
    "chw_pump_cmd",
    "pump_status",
    "pump_cmd",
)
DX_RUN_ROLES: tuple[str, ...] = (
    "compressor_status",
    "dx_cool_cmd",
    "dx_cooling",
    "cool_stage",
    "dx_stage",
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


def _first_on_mask(df: pd.DataFrame, roles: tuple[str, ...]) -> pd.Series | None:
    for role in roles:
        if role in df.columns and df[role].notna().any():
            return _is_on(df[role])
    return None


def _oat_series(df: pd.DataFrame, weather: pd.DataFrame | None) -> pd.Series | None:
    for col in ("oa_t", "wx_oa_t"):
        if col in df.columns and df[col].notna().any():
            return pd.to_numeric(df[col], errors="coerce")
    if weather is not None and not weather.empty:
        for col in ("wx_oa_t", "oa_t", "dry_bulb_f"):
            if col in weather.columns:
                s = pd.to_numeric(weather[col], errors="coerce").reindex(df.index)
                if s.notna().any():
                    return s
    return None


def mech_cooling_oat_bins(
    frames: dict[str, pd.DataFrame],
    role_map: dict,
    *,
    weather: pd.DataFrame | None = None,
    bin_width_f: float = 5.0,
) -> pd.DataFrame:
    """
    Mechanical cooling run hours binned by OAT (5°F).

    Includes chillers and AHUs with DX compressor proof.
    Excludes AHUs that only have a hydronic cooling valve (clg_valve_pct).
    """
    from app.data_loader import infer_poll_seconds

    rows: list[dict[str, Any]] = []
    for eq_id, raw in frames.items():
        et = str(raw.attrs.get("equipment_type") or equipment_type_from_id(eq_id)).upper()
        mapped = apply_role_map(raw, eq_id, role_map)
        poll = float(raw.attrs.get("poll_seconds") or infer_poll_seconds(raw))
        oat = _oat_series(mapped, weather)
        if oat is None:
            continue

        run: pd.Series | None = None
        source_kind = ""
        if et in {"CHW_PLANT", "CHILLER"} or "CHILLER" in eq_id.upper() or eq_id.upper().startswith("CHW"):
            run = _first_on_mask(mapped, CHILLER_RUN_ROLES)
            source_kind = "chiller"
        elif et == "AHU":
            run = _first_on_mask(mapped, DX_RUN_ROLES)
            source_kind = "ahu_dx"
        elif et == "HEATPUMP" or eq_id.upper().startswith("HP"):
            run = _first_on_mask(mapped, DX_RUN_ROLES + ("compressor_status",))
            source_kind = "heatpump"

        if run is None or not bool(run.any()):
            continue

        oat_on = oat.where(run).dropna()
        if oat_on.empty:
            continue
        clamped = oat_on.clip(40, 110)
        bin_start = (np.floor(clamped.to_numpy(dtype=float) / bin_width_f) * bin_width_f).astype(int)
        tmp = pd.DataFrame({"oat": oat_on.to_numpy(), "bin_start": bin_start}, index=oat_on.index)
        for b, g in tmp.groupby("bin_start"):
            if pd.isna(b):
                continue
            b_i = int(b)
            hours = float(len(g) * poll / 3600.0)
            rows.append(
                {
                    "equipment_id": eq_id,
                    "source": f"{eq_id} ({source_kind})",
                    "source_kind": source_kind,
                    "bin_start": b_i,
                    "bin_label": f"{b_i}-{b_i + int(bin_width_f) - 1}",
                    "hours": round(hours, 2),
                }
            )

    if not rows:
        return pd.DataFrame(
            columns=["equipment_id", "source", "source_kind", "bin_start", "bin_label", "hours"]
        )
    return pd.DataFrame(rows).sort_values(["source", "bin_start"])


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
