"""Deterministic fake Niagara BAS graph and Chicago-timezone history store."""

from __future__ import annotations

import datetime as dt
import hashlib
import math
import random
import re
from dataclasses import dataclass
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any

from .zinc import Marker, Quantity, Ref


UTC = dt.timezone.utc
CHICAGO = ZoneInfo("America/Chicago")


class HistoryLimitError(ValueError):
    pass


@dataclass
class FakeBASData:
    interval_minutes: int = 15
    seed: int = 3201
    timezone: str = "America/Chicago"

    def __post_init__(self) -> None:
        self.tz = _zone(self.timezone)
        self.entities = self._make_entities()

    def _make_entities(self) -> list[dict[str, Any]]:
        return [
            {"id": Ref("site-main"), "dis": "Open FDD Demo Building", "site": Marker(), "area": "Chicago", "tz": "America/Chicago"},
            {"id": Ref("equip-ahu-1"), "dis": "AHU-1", "equip": Marker(), "siteRef": Ref("site-main"), "ahu": Marker(), "navName": "AHU-1"},
            {"id": Ref("equip-vav-1"), "dis": "VAV-1 North", "equip": Marker(), "siteRef": Ref("site-main"), "vav": Marker(), "navName": "VAV-1"},
            {"id": Ref("point-ahu1-sat"), "dis": "AHU-1 Supply Air Temperature", "point": Marker(), "his": Marker(), "temp": Marker(), "sensor": Marker(), "unit": "°F", "tz": "America/Chicago", "equipRef": Ref("equip-ahu-1"), "siteRef": Ref("site-main"), "kind": "Number"},
            {"id": Ref("point-ahu1-damper"), "dis": "AHU-1 Outside Air Damper", "point": Marker(), "his": Marker(), "air": Marker(), "sensor": Marker(), "unit": "%", "tz": "America/Chicago", "equipRef": Ref("equip-ahu-1"), "siteRef": Ref("site-main"), "kind": "Number"},
            {"id": Ref("point-vav1-zone"), "dis": "VAV-1 Zone Temperature", "point": Marker(), "his": Marker(), "temp": Marker(), "sensor": Marker(), "unit": "°F", "tz": "America/Chicago", "equipRef": Ref("equip-vav-1"), "siteRef": Ref("site-main"), "kind": "Number"},
            {"id": Ref("point-vav1-damper"), "dis": "VAV-1 Damper Command", "point": Marker(), "his": Marker(), "air": Marker(), "cmd": Marker(), "unit": "%", "tz": "America/Chicago", "equipRef": Ref("equip-vav-1"), "siteRef": Ref("site-main"), "kind": "Number"},
        ]

    def read(self, filter_text: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        rows = self.entities
        if filter_text:
            rows = [row for row in rows if self._matches(row, filter_text)]
        return list(rows[:limit] if limit is not None else rows)

    def read_by_ids(self, ids: list[str]) -> list[dict[str, Any] | None]:
        by_id = {row["id"].value.lower(): row for row in self.entities if isinstance(row.get("id"), Ref)}
        return [by_id.get(item.lstrip("@").lower()) for item in ids]

    @staticmethod
    def _matches(row: dict[str, Any], filter_text: str) -> bool:
        terms = [term.strip() for term in re.split(r"\s+and\s+", filter_text.strip().replace("(", " ").replace(")", " "), flags=re.IGNORECASE)]
        lowered = {str(key).lower(): value for key, value in row.items()}
        for term in terms:
            if not term:
                continue
            if "==" in term:
                key, raw = (part.strip() for part in term.split("==", 1))
                actual = lowered.get(key.lower())
                expected = raw.strip('"')
                if isinstance(actual, Ref):
                    if actual.value.lower() != expected.lstrip("@").lower():
                        return False
                elif str(actual).lower() != expected.lower():
                    return False
            elif term.lower().startswith("not "):
                if term[4:].strip().lower() in lowered:
                    return False
            elif term.lower() not in lowered:
                return False
        return True

    def history(self, point_id: str, range_text: str, timezone: str | None = None) -> tuple[list[dict[str, Any]], dt.datetime, dt.datetime]:
        point = self._point(point_id)
        tz = _zone(timezone or self.timezone)
        start, end = self._range(range_text, tz)
        if point is None:
            return [], start, end
        rows: list[dict[str, Any]] = []
        cursor = _ceil_cadence(start.astimezone(UTC), self.interval_minutes)
        end_utc = end.astimezone(UTC)
        pid = point["id"].value
        digest = hashlib.sha256(pid.encode()).digest()
        while cursor < end_utc:
            local_ts = cursor.astimezone(tz)
            # Values are based on UTC cadence, not the requested presentation
            # timezone. This keeps a point's deterministic values unchanged
            # when a client asks for a different output timezone.
            minutes = cursor.hour * 60 + cursor.minute
            day_wave = math.sin((minutes / 1440) * math.tau - math.pi / 2)
            noise = random.Random(self.seed + int(cursor.timestamp() // (self.interval_minutes * 60)) + digest[1]).random() - 0.5
            if "damper" in pid:
                value = max(0.0, min(100.0, 35 + 22 * day_wave + 4 * noise))
            elif "zone" in pid:
                value = 72 + 2.7 * day_wave + 0.25 * noise
            else:
                value = 55 + 10 * day_wave + 0.4 * noise
            rows.append({"ts": local_ts, "val": Quantity(round(value, 3), str(point.get("unit", "")))})
            cursor += dt.timedelta(minutes=self.interval_minutes)
        return rows, start, end

    def validate_range(self, range_text: str, timezone: str | None, max_span_days: int, max_samples: int) -> tuple[dt.datetime, dt.datetime]:
        start, end = self._range(range_text, _zone(timezone or self.timezone))
        span_seconds = max(0.0, (end.astimezone(UTC) - start.astimezone(UTC)).total_seconds())
        samples = math.ceil(span_seconds / (self.interval_minutes * 60))
        if span_seconds > max_span_days * 86400:
            raise HistoryLimitError(f"history span exceeds maximum of {max_span_days} days")
        if samples > max_samples:
            raise HistoryLimitError(f"history request exceeds maximum of {max_samples} samples")
        return start, end

    def _point(self, point_id: str) -> dict[str, Any] | None:
        wanted = point_id.lstrip("@").lower()
        return next((row for row in self.entities if isinstance(row.get("id"), Ref) and row["id"].value.lower() == wanted and row.get("point")), None)

    @staticmethod
    def _range(range_text: str, tz: ZoneInfo) -> tuple[dt.datetime, dt.datetime]:
        now = dt.datetime.now(tz)
        text = range_text.strip().strip('"')
        if text == "today":
            start = dt.datetime.combine(now.date(), dt.time(), tzinfo=tz)
            return start, start + dt.timedelta(days=1)
        if text == "yesterday":
            end = dt.datetime.combine(now.date(), dt.time(), tzinfo=tz)
            return end - dt.timedelta(days=1), end
        if "," in text:
            left, right = (part.strip() for part in text.split(",", 1))
            start = _parse_boundary(left, tz)
            end = _parse_boundary(right, tz)
            if _is_date_only(right):
                end += dt.timedelta(days=1)
            return start, end
        if _is_date_only(text):
            start = dt.datetime.combine(dt.date.fromisoformat(text), dt.time(), tzinfo=tz)
            return start, start + dt.timedelta(days=1)
        return _parse_boundary(text, tz), now


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        if name in {"Chicago", "US/Central", "CST6CDT"}:
            return CHICAGO
        return CHICAGO


def _is_date_only(text: str) -> bool:
    return bool(len(text) == 10 and text[4] == "-" and text[7] == "-")


def _parse_boundary(text: str, tz: ZoneInfo) -> dt.datetime:
    if _is_date_only(text):
        return dt.datetime.combine(dt.date.fromisoformat(text), dt.time(), tzinfo=tz)
    value = text.replace("Z", "+00:00")
    parsed = dt.datetime.fromisoformat(value.split()[0])
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(tz)


def _ceil_cadence(timestamp: dt.datetime, interval_minutes: int) -> dt.datetime:
    seconds = timestamp.timestamp()
    cadence = interval_minutes * 60
    aligned = math.ceil(seconds / cadence) * cadence
    return dt.datetime.fromtimestamp(aligned, UTC)
