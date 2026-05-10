"""In-memory trend/history helpers for the BAS demo backend."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone
from math import sin
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import Response

from .commands import get_command_state
from .demo_data import Equipment, Point, find_point, iter_equipment
from .services import get_demo_site

TREND_INTERVAL_MINUTES = 30
TREND_DEFAULT_HOURS = 4
TREND_MAX_HOURS = 24


def list_trend_points() -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for equipment in iter_equipment(get_demo_site()):
        for point in equipment.points:
            if not point.is_trended:
                continue
            points.append(
                {
                    "id": point.id,
                    "display_name": point.display_name,
                    "equipment_id": equipment.id,
                    "equipment_name": equipment.name,
                    "equipment_type": equipment.equipment_type,
                    "point_type": point.point_type,
                    "units": point.units,
                    "is_commandable": point.is_commandable,
                    "is_alarmable": point.is_alarmable,
                    "source_protocol": "simulator",
                    "last_updated": point.last_updated,
                }
            )

    return points


def _parse_point_ids(raw_point_ids: str | None) -> list[str]:
    if raw_point_ids is None:
        return []

    point_ids: list[str] = []
    seen: set[str] = set()
    for candidate in raw_point_ids.split(","):
        point_id = candidate.strip()
        if not point_id or point_id in seen:
            continue
        seen.add(point_id)
        point_ids.append(point_id)
    return point_ids


def _resolve_trend_points(point_ids: list[str]) -> list[tuple[Equipment, Point]]:
    if not point_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="point_ids query parameter is required",
        )

    resolved: list[tuple[Equipment, Point]] = []
    missing: list[str] = []
    not_trended: list[str] = []

    for point_id in point_ids:
        match = find_point(get_demo_site(), point_id)
        if match is None:
            missing.append(point_id)
            continue

        equipment, point = match
        if not point.is_trended:
            not_trended.append(point_id)
            continue

        resolved.append((equipment, point))

    if missing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"message": "One or more points were not found", "point_ids": missing},
        )

    if not_trended:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "One or more points are not trended", "point_ids": not_trended},
        )

    return resolved


def _trend_anchor(now: datetime) -> datetime:
    return now.replace(second=0, microsecond=0) - timedelta(
        minutes=now.minute % TREND_INTERVAL_MINUTES,
    )


def _trend_base_value(point: Point) -> Any:
    command_state = get_command_state(point.id)
    if command_state is not None:
        return command_state.commanded_value
    return point.present_value


def _sample_value(point: Point, base_value: Any, sample_index: int) -> Any:
    if isinstance(base_value, bool):
        return base_value
    if isinstance(base_value, (int, float)):
        seed = sum(ord(char) for char in point.id)
        wave = sin((sample_index + seed % 11) / 2.0) + sin((sample_index + seed % 7) / 3.0)
        if point.point_type.startswith("analog"):
            return round(float(base_value) + wave * 0.6, 2)
        return round(float(base_value) + wave * 0.2, 2)
    return base_value


def _build_samples(equipment: Equipment, point: Point, hours: int) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    anchor = _trend_anchor(now)
    sample_count = int((hours * 60) / TREND_INTERVAL_MINUTES) + 1
    start = anchor - timedelta(minutes=TREND_INTERVAL_MINUTES * (sample_count - 1))
    base_value = _trend_base_value(point)
    samples: list[dict[str, Any]] = []

    for sample_index in range(sample_count):
        timestamp = start + timedelta(minutes=TREND_INTERVAL_MINUTES * sample_index)
        value = _sample_value(point, base_value, sample_index)
        samples.append(
            {
                "point_id": point.id,
                "equipment_id": equipment.id,
                "equipment_name": equipment.name,
                "display_name": point.display_name,
                "units": point.units,
                "timestamp": timestamp.isoformat(),
                "value": value,
                "quality": "good",
                "status": "good",
            }
        )

    return samples


def _build_sample_payload(point_ids: str | None, hours: int) -> dict[str, Any]:
    if hours < 1 or hours > TREND_MAX_HOURS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"hours must be between 1 and {TREND_MAX_HOURS}",
        )

    requested_point_ids = _parse_point_ids(point_ids)
    resolved_points = _resolve_trend_points(requested_point_ids)
    samples: list[dict[str, Any]] = []
    point_payload: list[dict[str, Any]] = []

    for equipment, point in resolved_points:
        point_payload.append(
            {
                "id": point.id,
                "display_name": point.display_name,
                "equipment_id": equipment.id,
                "equipment_name": equipment.name,
                "equipment_type": equipment.equipment_type,
                "point_type": point.point_type,
                "units": point.units,
                "is_commandable": point.is_commandable,
                "is_alarmable": point.is_alarmable,
                "source_protocol": "simulator",
            }
        )
        samples.extend(_build_samples(equipment, point, hours))

    samples.sort(key=lambda item: (item["timestamp"], item["point_id"]))
    return {
        "points": point_payload,
        "samples": samples,
        "window_hours": hours,
        "interval_minutes": TREND_INTERVAL_MINUTES,
    }


def query_trend_samples(point_ids: str | None, hours: int = TREND_DEFAULT_HOURS) -> dict[str, Any]:
    return _build_sample_payload(point_ids, hours)


def export_trend_samples_csv(point_ids: str | None, hours: int = TREND_DEFAULT_HOURS) -> Response:
    payload = _build_sample_payload(point_ids, hours)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "point_id",
            "display_name",
            "equipment_id",
            "equipment_name",
            "units",
            "timestamp",
            "value",
            "quality",
            "status",
        ]
    )
    for sample in payload["samples"]:
        writer.writerow(
            [
                sample["point_id"],
                sample["display_name"],
                sample["equipment_id"],
                sample["equipment_name"],
                sample["units"],
                sample["timestamp"],
                sample["value"],
                sample["quality"],
                sample["status"],
            ]
        )

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bas-trends.csv"'},
    )
