"""Tiny in-memory audit log for the BAS demo backend."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone


_MAX_EVENTS = 100


@dataclass(frozen=True, slots=True)
class AuditEvent:
    timestamp: str
    action_type: str
    username: str
    result: str
    reason: str
    target_id: str | None = None
    old_value: object | None = None
    new_value: object | None = None


_EVENTS: list[AuditEvent] = []


def record_event(
    action_type: str,
    username: str,
    result: str,
    reason: str,
    target_id: str | None = None,
    old_value: object | None = None,
    new_value: object | None = None,
) -> AuditEvent:
    event = AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        action_type=action_type,
        username=username,
        result=result,
        reason=reason,
        target_id=target_id,
        old_value=old_value,
        new_value=new_value,
    )
    _EVENTS.insert(0, event)
    del _EVENTS[_MAX_EVENTS:]
    return event


def list_events() -> list[dict[str, str]]:
    return [asdict(event) for event in _EVENTS]


def clear_events() -> None:
    _EVENTS.clear()
