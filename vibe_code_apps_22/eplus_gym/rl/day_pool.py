"""Seeded unique calendar days from an EPW (no EnergyPlus)."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

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
        "pool": "unique_heating",
    }


def calendar_day(day_id: str) -> str:
    """ISO calendar day from a pool id (``YYYY-MM-DD`` or ``YYYY-MM-DD__syn``)."""
    return str(day_id).split("__", 1)[0][:10]


def write_day_perturbed_epw(
    src: Path,
    dest: Path,
    day: date,
    delta_c: float,
) -> Path:
    """Copy EPW; add ``delta_c`` to dry-bulb on ``day`` only. Clamp dewpoint ≤ DB."""
    src = Path(src)
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out: list[str] = []
    for line in src.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line[0].isalpha() or line.startswith("!"):
            out.append(line)
            continue
        parts = line.split(",")
        if len(parts) < 7:
            out.append(line)
            continue
        try:
            mo, dy = int(parts[1]), int(parts[2])
        except ValueError:
            out.append(line)
            continue
        if mo == day.month and dy == day.day:
            try:
                db = float(parts[6]) + float(delta_c)
            except ValueError:
                out.append(line)
                continue
            parts[6] = f"{db:.1f}"
            if len(parts) > 7:
                try:
                    dp = float(parts[7])
                    if dp > db:
                        parts[7] = f"{db:.1f}"
                except ValueError:
                    pass
            line = ",".join(parts)
        out.append(line)
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    return dest


def build_year_plus_heating2x_pool(
    epw: Path,
    *,
    seed: int = 0,
    synth_dir: Path,
    sigma_c: float = 2.5,
    clip_c: float = 5.0,
) -> Dict[str, Any]:
    """All unique EPW dates (full AMY) plus one synthetic heating-season clone.

    Synthetic = same calendar RunPeriod, dry-bulb N(0, sigma) clipped to ±clip_c.
    That is 2× Nov–Mar plus summer/shoulder the model would also see.
    """
    epw = Path(epw)
    all_days = unique_dates_from_epw(epw)
    heating = [d for d in all_days if _in_months(d, HEATING_MONTHS)]
    rng = np.random.default_rng(int(seed))
    synth_dir = Path(synth_dir)
    synth_dir.mkdir(parents=True, exist_ok=True)
    specs: List[Dict[str, Any]] = []
    for d in all_days:
        specs.append(
            {
                "id": d.isoformat(),
                "day": d.isoformat(),
                "kind": "observed",
                "delta_c": 0.0,
                "epw": str(epw.resolve()),
            }
        )
    for d in heating:
        delta = float(np.clip(rng.normal(0.0, float(sigma_c)), -float(clip_c), float(clip_c)))
        dest = synth_dir / f"{d.isoformat()}__syn.epw"
        write_day_perturbed_epw(epw, dest, d, delta)
        specs.append(
            {
                "id": f"{d.isoformat()}__syn",
                "day": d.isoformat(),
                "kind": "synthetic",
                "delta_c": delta,
                "epw": str(dest.resolve()),
            }
        )
    ids = [s["id"] for s in specs]
    return {
        "days": ids,
        "specs": specs,
        "n_requested": len(ids),
        "n_selected": len(ids),
        "n_available": len(all_days),
        "n_observed": len(all_days),
        "n_synthetic": len(heating),
        "n_heating_core": len(heating),
        "seed": int(seed),
        "shortfall": 0,
        "pool": "year_plus_heating2x_synthetic",
        "sigma_c": float(sigma_c),
        "clip_c": float(clip_c),
    }


def spec_epw(pool: Dict[str, Any] | None, day_id: str, default: Path) -> Path:
    for spec in (pool or {}).get("specs") or []:
        if spec.get("id") == day_id:
            return Path(spec["epw"])
    return Path(default)
