"""Simulator-only command and release helpers for the BAS demo backend."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status

from .audit import record_event
from .auth import DemoUser
from .demo_data import Equipment, Point, find_point, point_detail


_COMMAND_ROLES = {"Admin", "Engineer", "Operator"}


@dataclass(frozen=True, slots=True)
class CommandState:
    point_id: str
    commanded_value: Any
    commanded_by: str
    command_timestamp: str
    original_value: Any
    reason: str


_COMMAND_STATES: dict[str, CommandState] = {}


def clear_command_states() -> None:
    _COMMAND_STATES.clear()


def get_command_state(point_id: str) -> CommandState | None:
    return _COMMAND_STATES.get(point_id)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_point(point_id: str) -> tuple[Equipment, Point] | None:
    from .services import get_demo_site

    match = find_point(get_demo_site(), point_id)
    if match is None:
        return None
    return match


def _reject(point_id: str, action_type: str, username: str, result: str, reason: str, status_code: int) -> None:
    record_event(action_type, username, result, reason, target_id=point_id)
    raise HTTPException(status_code=status_code, detail=reason)


def _require_command_access(user: DemoUser, point_id: str, point: Point, action_type: str) -> None:
    if user.role == "ReadOnly":
        _reject(point_id, action_type, user.username, "failure", "read_only_role", status.HTTP_403_FORBIDDEN)
    if user.role not in _COMMAND_ROLES:
        _reject(point_id, action_type, user.username, "failure", "role_not_authorized", status.HTTP_403_FORBIDDEN)
    if not point.is_commandable:
        _reject(point_id, action_type, user.username, "failure", "point_not_commandable", status.HTTP_400_BAD_REQUEST)


def command_point(user: DemoUser, point_id: str, value: Any, reason: Any, confirmed: Any) -> dict[str, Any]:
    match = _resolve_point(point_id)
    if match is None:
        _reject(point_id, "point.command", user.username, "failure", "point_not_found", status.HTTP_404_NOT_FOUND)

    equipment, point = match
    _require_command_access(user, point_id, point, "point.command")

    reason_text = "" if reason is None else str(reason).strip()
    if not reason_text:
        _reject(point_id, "point.command", user.username, "failure", "reason_required", status.HTTP_400_BAD_REQUEST)
    if confirmed is not True:
        _reject(
            point_id,
            "point.command",
            user.username,
            "failure",
            "confirmation_required",
            status.HTTP_400_BAD_REQUEST,
        )

    previous_state = get_command_state(point_id)
    original_value = previous_state.original_value if previous_state is not None else point.present_value
    state = CommandState(
        point_id=point_id,
        commanded_value=value,
        commanded_by=user.username,
        command_timestamp=_utc_now(),
        original_value=original_value,
        reason=reason_text,
    )
    _COMMAND_STATES[point_id] = state
    record_event(
        "point.command",
        user.username,
        "success",
        reason_text,
        target_id=point_id,
        old_value=original_value,
        new_value=value,
    )
    return point_detail(equipment, point, command_state=state)


def release_point(user: DemoUser, point_id: str, reason: Any) -> dict[str, Any]:
    match = _resolve_point(point_id)
    if match is None:
        _reject(point_id, "point.release", user.username, "failure", "point_not_found", status.HTTP_404_NOT_FOUND)

    equipment, point = match
    _require_command_access(user, point_id, point, "point.release")

    reason_text = "" if reason is None else str(reason).strip()
    if not reason_text:
        _reject(point_id, "point.release", user.username, "failure", "reason_required", status.HTTP_400_BAD_REQUEST)

    previous_state = _COMMAND_STATES.pop(point_id, None)
    old_value = previous_state.commanded_value if previous_state is not None else point.present_value
    new_value = previous_state.original_value if previous_state is not None else point.present_value
    record_event(
        "point.release",
        user.username,
        "success",
        reason_text,
        target_id=point_id,
        old_value=old_value,
        new_value=new_value,
    )
    return point_detail(equipment, point, command_state=None)
