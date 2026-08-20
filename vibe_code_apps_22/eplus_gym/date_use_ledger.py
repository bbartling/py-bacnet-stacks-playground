"""Date-use ledger. January 2026 physics inspection is not an unseen holdout."""
from __future__ import annotations

from datetime import date
from typing import Iterable

NO_LOCKED_UNSEEN = "NO LOCKED UNSEEN TEST AVAILABLE"
JAN_2026_START = date(2026, 1, 1)
JAN_2026_END = date(2026, 1, 31)


def _as_date(day: str | date) -> date:
    if isinstance(day, date):
        return day
    return date.fromisoformat(str(day)[:10])


def classify_date_use(day: str | date, physics_inspected: Iterable[str] | None = None) -> str:
    d = _as_date(day)
    inspected = {_as_date(x).isoformat() for x in (physics_inspected or ())}
    if d.isoformat() in inspected or (JAN_2026_START <= d <= JAN_2026_END):
        return "development_evidence_not_holdout"
    return "unused"


def locked_unseen_available(physics_inspected: Iterable[str] | None = None) -> bool:
    inspected = {_as_date(x) for x in (physics_inspected or ())}
    jan_used = any(JAN_2026_START <= d <= JAN_2026_END for d in inspected)
    return not jan_used
