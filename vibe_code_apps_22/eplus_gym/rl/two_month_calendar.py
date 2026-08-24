"""Calendar contract for Dec 2025–Jan 2026 two-month replay."""
from __future__ import annotations

from datetime import date, timedelta

LOOKBACK_DAY = "2025-11-30"
FIRST_SCORED_DAY = "2025-12-01"
LAST_SCORED_DAY = "2026-01-31"
EXPECTED_SCORED_DAYS = 62
EXPECTED_INTERVALS_PER_STRATEGY = EXPECTED_SCORED_DAYS * 96  # 5952


def scored_days() -> list[str]:
    out: list[str] = []
    d = date.fromisoformat(FIRST_SCORED_DAY)
    end = date.fromisoformat(LAST_SCORED_DAY)
    while d <= end:
        out.append(d.isoformat())
        d += timedelta(days=1)
    if len(out) != EXPECTED_SCORED_DAYS:
        raise ValueError(f"expected {EXPECTED_SCORED_DAYS} scored days, got {len(out)}")
    return out


def month_key(day: str) -> str:
    d = date.fromisoformat(str(day)[:10])
    return f"{d.year}-{d.month:02d}"


def validate_day_list(days: list[str]) -> None:
    expected = scored_days()
    if days != expected:
        missing = set(expected) - set(days)
        extra = set(days) - set(expected)
        dup = len(days) != len(set(days))
        raise ValueError(
            f"calendar mismatch missing={sorted(missing)[:5]} extra={sorted(extra)[:5]} dup={dup}"
        )
