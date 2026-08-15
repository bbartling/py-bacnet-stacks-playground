"""Thin Streamlit adapter for canonical OpenFDD VAV health (no local equations)."""

from __future__ import annotations

from typing import Any, Mapping

import pandas as pd

from open_fdd.analytics.occupancy import OccupancySchedule
from open_fdd.analytics.vav_health import (
    SCHEMA_VERSION,
    VavHealthConfig,
    vav_health_matrix,
    vav_health_summary,
)

from app.data_loader import infer_poll_seconds
from app.openfdd_runtime import installed_open_fdd_version, require_supported_open_fdd
from app.role_map import apply_role_map

ENGINE_PANDAS = "pandas"


def mapped_frames(
    frames: Mapping[str, pd.DataFrame],
    role_map: Mapping[str, Mapping[str, str]] | None,
) -> dict[str, pd.DataFrame]:
    rm = role_map or {}
    out: dict[str, pd.DataFrame] = {}
    for eq_id, raw in frames.items():
        out[str(eq_id)] = apply_role_map(raw, str(eq_id), rm)  # type: ignore[arg-type]
    return out


def rule_results_frame(batch_results: list[Any] | None) -> pd.DataFrame:
    if not batch_results:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for r in batch_results:
        status = getattr(r, "status", None)
        rows.append(
            {
                "rule_id": str(getattr(r, "rule_id", "")),
                "equipment_id": str(getattr(r, "equipment_id", "")),
                "status": str(status) if status is not None else "",
                "fault_hours": getattr(r, "fault_hours", None),
            }
        )
    return pd.DataFrame(rows)


def occupancy_from_session(raw: Any) -> OccupancySchedule:
    if isinstance(raw, OccupancySchedule):
        return raw
    if isinstance(raw, dict):
        return OccupancySchedule.from_dict(raw)
    return OccupancySchedule()


def poll_seconds_from_frames(frames: Mapping[str, pd.DataFrame]) -> float:
    for df in frames.values():
        tagged = df.attrs.get("poll_seconds") if hasattr(df, "attrs") else None
        if tagged:
            return float(tagged)
        return float(infer_poll_seconds(df))
    return 300.0


def config_from_session(
    *,
    zone_lo_f: float,
    zone_hi_f: float,
    poll_seconds: float,
) -> VavHealthConfig:
    return VavHealthConfig(
        comfort_low_f=float(zone_lo_f),
        comfort_high_f=float(zone_hi_f),
        poll_seconds=float(poll_seconds),
    )


def compute_vav_health_matrix(
    frames: Mapping[str, pd.DataFrame],
    *,
    building_id: str,
    batch_results: list[Any] | None,
    occupancy: Any,
    role_map: Mapping[str, Mapping[str, str]] | None,
    parent_ahu: Mapping[str, str] | None,
    zone_lo_f: float,
    zone_hi_f: float,
    poll_seconds: float | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], VavHealthConfig]:
    """Call OpenFDD ``vav_health_matrix``; never coerce missing evidence to False."""
    require_supported_open_fdd()
    mapped = mapped_frames(frames, role_map)
    poll = float(poll_seconds) if poll_seconds is not None else poll_seconds_from_frames(mapped)
    cfg = config_from_session(zone_lo_f=zone_lo_f, zone_hi_f=zone_hi_f, poll_seconds=poll)
    matrix = vav_health_matrix(
        mapped,
        building_id=building_id or "HVAC_BUILDING",
        rule_results=rule_results_frame(batch_results),
        occupancy=occupancy_from_session(occupancy),
        role_map=role_map,
        parent_ahu=dict(parent_ahu or {}),
        config=cfg,
        engine=ENGINE_PANDAS,
    )
    summary = vav_health_summary(matrix)
    return matrix, summary, cfg


def provenance_caption(cfg: VavHealthConfig) -> str:
    ver = installed_open_fdd_version()
    return (
        f"OpenFDD {ver} · schema {SCHEMA_VERSION} · config fingerprint `{cfg.fingerprint()}`"
    )


__all__ = [
    "SCHEMA_VERSION",
    "VavHealthConfig",
    "compute_vav_health_matrix",
    "config_from_session",
    "mapped_frames",
    "occupancy_from_session",
    "provenance_caption",
    "rule_results_frame",
    "vav_health_matrix",
    "vav_health_summary",
]
