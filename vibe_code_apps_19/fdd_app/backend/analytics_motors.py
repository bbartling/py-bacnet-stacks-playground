"""Motor / fan runtime discovery and excess hours."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

MOTOR_POINT_ROLES = (
    "supply_fan_speed_pct",
    "fan_cmd",
    "pump_on",
    "chiller_cmd",
    "boiler_cmd",
    "fan_status",
)


@dataclass
class MotorSpec:
    equipment_id: str
    label: str
    point_role: str
    column: str | None = None


def discover_motors(resolver) -> list[MotorSpec]:
    motors: list[MotorSpec] = []
    try:
        resolver.ensure_model()
        for eq in resolver.list_equipment():
            eq_id = eq["id"]
            for role in MOTOR_POINT_ROLES:
                col = resolver.column_for_role(eq_id, role)
                if col:
                    motors.append(MotorSpec(eq_id, eq_id.replace("_", " "), role, col))
    except Exception:
        pass
    return motors


def motor_running(series: pd.Series, role: str) -> pd.Series:
    s = pd.to_numeric(series, errors="coerce")
    if role.endswith("_pct"):
        return s.fillna(0) > 5
    return s.fillna(0) > 0.5


def compute_motor_runtime(
    df: pd.DataFrame,
    column: str,
    *,
    role: str,
    occupied: pd.Series,
    poll_seconds: float,
) -> dict[str, Any]:
    if column not in df.columns:
        return {"total_hours": 0, "unoccupied_hours": 0, "excess_hours": 0}
    run = motor_running(df[column], role)
    total = float(run.sum()) * poll_seconds / 3600.0
    unocc = float((run & ~occupied).sum()) * poll_seconds / 3600.0
    return {
        "total_hours": round(total, 2),
        "unoccupied_hours": round(unocc, 2),
        "excess_hours": round(unocc, 2),
    }
