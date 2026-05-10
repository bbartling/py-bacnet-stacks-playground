"""Seeded in-memory alarm data for the BAS demo backend."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from io import StringIO
import csv

from fastapi import HTTPException, status

from .audit import record_event
from .auth import DemoUser


_ALARM_ROLES = {"Admin", "Engineer", "Operator"}


@dataclass(slots=True)
class AlarmRecord:
    id: str
    point_id: str | None
    equipment_id: str | None
    alarm_type: str
    severity: str
    state: str
    message: str
    active_timestamp: str
    acknowledged_timestamp: str | None = None
    returned_to_normal_timestamp: str | None = None
    acknowledged_by: str | None = None
    shelved_until: str | None = None
    operator_message: str | None = None


def _build_active_alarms() -> list[AlarmRecord]:
    return [
        AlarmRecord(
            id="alm-sat-high",
            point_id="pt-sat",
            equipment_id="eq-ahu-1",
            alarm_type="analog_high",
            severity="high",
            state="active",
            message="Supply air temperature high",
            active_timestamp="2026-05-10T03:00:00+00:00",
        ),
        AlarmRecord(
            id="alm-zone-temp-low",
            point_id="pt-zone-temp",
            equipment_id="eq-vav-1",
            alarm_type="analog_low",
            severity="medium",
            state="active",
            message="Zone temperature low",
            active_timestamp="2026-05-10T03:12:00+00:00",
            acknowledged_timestamp="2026-05-10T03:14:00+00:00",
            acknowledged_by="operator",
            operator_message="Verified against occupied setback schedule",
        ),
        AlarmRecord(
            id="alm-light-mismatch",
            point_id="pt-light-enable",
            equipment_id="eq-light-1",
            alarm_type="command_status_mismatch",
            severity="low",
            state="active",
            message="Lighting panel command and status do not match",
            active_timestamp="2026-05-10T03:22:00+00:00",
            shelved_until="2026-05-10T04:22:00+00:00",
        ),
    ]


def _build_history_alarms() -> list[AlarmRecord]:
    return [
        AlarmRecord(
            id="alm-fan-fault-cleared",
            point_id="pt-fan",
            equipment_id="eq-ahu-1",
            alarm_type="binary_fault",
            severity="high",
            state="resolved",
            message="Supply fan status failed to prove",
            active_timestamp="2026-05-09T23:10:00+00:00",
            acknowledged_timestamp="2026-05-09T23:12:00+00:00",
            returned_to_normal_timestamp="2026-05-09T23:20:00+00:00",
            acknowledged_by="engineer",
            operator_message="Fan starter reset at panel",
        ),
        AlarmRecord(
            id="alm-mixed-air-stale",
            point_id="pt-mat",
            equipment_id="eq-ahu-1",
            alarm_type="stale_value",
            severity="medium",
            state="resolved",
            message="Mixed air temperature value became stale",
            active_timestamp="2026-05-09T21:40:00+00:00",
            acknowledged_timestamp="2026-05-09T21:44:00+00:00",
            returned_to_normal_timestamp="2026-05-09T22:05:00+00:00",
            acknowledged_by="operator",
        ),
    ]


_ACTIVE_ALARMS: list[AlarmRecord] = _build_active_alarms()
_HISTORY_ALARMS: list[AlarmRecord] = _build_history_alarms()

_CSV_FIELDS = [
    "alarm_id",
    "point_id",
    "equipment_id",
    "alarm_type",
    "severity",
    "state",
    "message",
    "active_timestamp",
    "acknowledged_timestamp",
    "returned_to_normal_timestamp",
    "acknowledged_by",
    "shelved_until",
    "operator_message",
]


def _serialize(record: AlarmRecord) -> dict[str, object]:
    payload = asdict(record)
    payload["alarm_id"] = payload.pop("id")
    return payload


def reset_alarm_state() -> None:
    _ACTIVE_ALARMS[:] = _build_active_alarms()
    _HISTORY_ALARMS[:] = _build_history_alarms()


def list_active_alarms() -> list[dict[str, object]]:
    return [_serialize(record) for record in _ACTIVE_ALARMS]


def list_alarm_history() -> list[dict[str, object]]:
    return [_serialize(record) for record in _HISTORY_ALARMS]


def list_alarm_export_rows() -> list[dict[str, object]]:
    return [_serialize(record) for record in (*_ACTIVE_ALARMS, *_HISTORY_ALARMS)]


def export_alarm_csv() -> str:
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for row in list_alarm_export_rows():
        writer.writerow(row)
    return buffer.getvalue()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _find_active_alarm(alarm_id: str) -> AlarmRecord | None:
    return next((record for record in _ACTIVE_ALARMS if record.id == alarm_id), None)


def _require_alarm_access(user: DemoUser, alarm_id: str, action_type: str, alarm: AlarmRecord | None) -> None:
    if user.role == "ReadOnly":
        record_event(action_type, user.username, "failure", "read_only_role", target_id=alarm_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="read_only_role")
    if user.role not in _ALARM_ROLES:
        record_event(action_type, user.username, "failure", "role_not_authorized", target_id=alarm_id)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="role_not_authorized")
    if alarm is None:
        record_event(action_type, user.username, "failure", "alarm_not_found", target_id=alarm_id)
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="alarm_not_found")
    if alarm.state != "active":
        record_event(action_type, user.username, "failure", "alarm_not_active", target_id=alarm_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="alarm_not_active")


def _require_reason(action_type: str, user: DemoUser, alarm_id: str, reason: object) -> str:
    reason_text = "" if reason is None else str(reason).strip()
    if not reason_text:
        record_event(action_type, user.username, "failure", "reason_required", target_id=alarm_id)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reason_required")
    return reason_text


def _update_alarm(action_type: str, user: DemoUser, alarm: AlarmRecord, reason_text: str, shelved: bool = False) -> dict[str, object]:
    previous_state = asdict(alarm)
    now = _utc_now().isoformat()
    alarm.acknowledged_timestamp = alarm.acknowledged_timestamp or now
    alarm.acknowledged_by = alarm.acknowledged_by or user.username
    alarm.operator_message = reason_text
    if shelved:
        alarm.shelved_until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    record_event(
        action_type,
        user.username,
        "success",
        reason_text,
        target_id=alarm.id,
        old_value=previous_state,
        new_value=asdict(alarm),
    )
    return _serialize(alarm)


def ack_alarm(user: DemoUser, alarm_id: str, reason: object) -> dict[str, object]:
    alarm = _find_active_alarm(alarm_id)
    _require_alarm_access(user, alarm_id, "alarm.ack", alarm)
    reason_text = _require_reason("alarm.ack", user, alarm_id, reason)
    return _update_alarm("alarm.ack", user, alarm, reason_text)


def shelve_alarm(user: DemoUser, alarm_id: str, reason: object) -> dict[str, object]:
    alarm = _find_active_alarm(alarm_id)
    _require_alarm_access(user, alarm_id, "alarm.shelve", alarm)
    reason_text = _require_reason("alarm.shelve", user, alarm_id, reason)
    return _update_alarm("alarm.shelve", user, alarm, reason_text, shelved=True)
