"""Seeded unique calendar days from an EPW (no EnergyPlus)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

import numpy as np

HEATING_MONTHS = (11, 12, 1, 2, 3)
SHOULDER_INNER = (10,)
SHOULDER_OUTER = (4,)


def unique_dates_from_epw(epw: Path) -> List[date]:
    """Unique civil dates in EPW data rows (year, month, day)."""
    seen: dict[Tuple[int, int, int], date] = {}
    text = Path(epw).read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in text:
        if not line or line[0].isalpha() or line.startswith("!"):
            continue
        parts = line.split(",")
        if len(parts) < 4:
            continue
        try:
            year, mo, dy = int(parts[0]), int(parts[1]), int(parts[2])
            if not (1 <= mo <= 12 and 1 <= dy <= 31):
                continue
            key = (year, mo, dy)
            if key not in seen:
                seen[key] = date(year, mo, dy)
        except ValueError:
            continue
    return sorted(seen.values())


def _in_months(d: date, months: Sequence[int]) -> bool:
    return int(d.month) in set(int(m) for m in months)


def _take_seeded(pool: Sequence[date], n: int, rng: np.random.Generator) -> List[date]:
    if n <= 0 or not pool:
        return []
    if len(pool) <= n:
        return list(pool)
    idx = rng.choice(len(pool), size=n, replace=False)
    picked = [pool[int(i)] for i in idx]
    return sorted(picked)


def sample_unique_heating_days(
    epw: Path,
    n: int = 100,
    *,
    seed: int = 0,
) -> dict:
    """Prefer Nov–Mar, then Oct, then Apr, then remaining unique EPW dates.

    Never silently recycles a 7-day week. If EPW has fewer than ``n`` unique
    dates, returns all available.
    """
    all_days = unique_dates_from_epw(Path(epw))
    rng = np.random.default_rng(int(seed))
    chosen: List[date] = []
    used: set[date] = set()

    def add_from(months: Iterable[int] | None, remaining: int) -> None:
        nonlocal chosen
        if remaining <= 0:
            return
        if months is None:
            pool = [d for d in all_days if d not in used]
        else:
            pool = [d for d in all_days if d not in used and _in_months(d, list(months))]
        take = _take_seeded(pool, remaining, rng)
        for d in take:
            used.add(d)
            chosen.append(d)

    add_from(HEATING_MONTHS, int(n))
    add_from(SHOULDER_INNER, int(n) - len(chosen))
    add_from(SHOULDER_OUTER, int(n) - len(chosen))
    add_from(None, int(n) - len(chosen))
    chosen = sorted(chosen)[: int(n)]
    iso = [d.isoformat() for d in chosen]
    return {
        "days": iso,
        "n_requested": int(n),
        "n_selected": len(iso),
        "n_available": len(all_days),
        "seed": int(seed),
        "shortfall": max(0, int(n) - len(iso)),
    }
