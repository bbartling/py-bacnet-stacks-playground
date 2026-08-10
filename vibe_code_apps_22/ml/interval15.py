"""Canonical 15-minute interval contract for BAS / E+ / Python / Rust parity.

Contract (hybrid_dsm_96_v1):
  q0  = [00:00, 00:15), prediction stamped 00:15  → step_15=0, hour_ending=0.25
  q95 = [23:45, 24:00), prediction stamped 24:00  → step_15=95, hour_ending=24.0
  96 intervals = exactly 24 h; duration_s = 900

Joins prefer UTC. Local civil / local-standard are derived metadata only.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

DURATION_S = 900
STEPS = 96
SITE_TZ = ZoneInfo("America/Chicago")
# EnergyPlus / Lakeside AMY path uses fixed CST (no DST) for simulation stamps.
SITE_STANDARD = timezone(timedelta(hours=-6), name="CST")


@dataclass(frozen=True)
class Interval15:
    interval_start_utc: datetime
    interval_end_utc: datetime
    site_date: date
    quarter_index: int
    duration_s: int = DURATION_S

    def __post_init__(self) -> None:
        if not (0 <= self.quarter_index < STEPS):
            raise ValueError(f"quarter_index must be in [0, {STEPS}), got {self.quarter_index}")
        if self.duration_s != DURATION_S:
            raise ValueError("duration_s must be 900")
        delta = (self.interval_end_utc - self.interval_start_utc).total_seconds()
        if abs(delta - DURATION_S) > 1e-6:
            raise ValueError(f"interval length must be 900s, got {delta}")

    @property
    def step_15(self) -> int:
        return self.quarter_index

    @property
    def hour_ending(self) -> float:
        """Fractional hour-ending of the interval end (0.25 .. 24.0)."""
        return hour_ending_from_quarter(self.quarter_index)

    @property
    def stamp_local_standard(self) -> str:
        """E+-style local-standard stamp for interval end (YYYY-MM-DD HH:MM)."""
        end_std = self.interval_end_utc.astimezone(SITE_STANDARD)
        # Represent 24:00 as next-calendar-day 00:00 → prior day 24:00
        if self.quarter_index == 95:
            d = self.site_date
            return f"{d.isoformat()} 24:00"
        return end_std.strftime("%Y-%m-%d %H:%M")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["interval_start_utc"] = self.interval_start_utc.isoformat()
        d["interval_end_utc"] = self.interval_end_utc.isoformat()
        d["site_date"] = self.site_date.isoformat()
        d["step_15"] = self.step_15
        d["hour_ending"] = self.hour_ending
        return d


def hour_ending_from_quarter(q: int) -> float:
    if not (0 <= q < STEPS):
        raise ValueError(f"quarter_index out of range: {q}")
    return (q + 1) / 4.0


def quarter_from_interval_end_hms(hour: int, minute: int) -> int:
    """Map interval-end clock (h, mi) → quarter_index 0..95.

    Accepts h=24, mi=0 for end-of-day. Midnight 00:00 is q95 of the *prior* site day
    (caller must set site_date accordingly).
    """
    h = int(hour)
    mi = int(minute)
    if h == 24:
        if mi != 0:
            raise ValueError("24:xx only valid as 24:00")
        return 95
    if h == 0 and mi == 0:
        return 95
    if not (0 <= h <= 23 and 0 <= mi < 60 and mi % 15 == 0):
        raise ValueError(f"invalid interval end {h:02d}:{mi:02d}")
    total_min = h * 60 + mi
    q = total_min // 15 - 1
    if not (0 <= q < STEPS):
        raise ValueError(f"quarter out of range for {h:02d}:{mi:02d}")
    return int(q)


def site_date_for_interval_end(end_local: datetime) -> date:
    """Calendar owner of the interval that ends at ``end_local``.

    00:00 stamps belong to the previous calendar day (q95 / HE24).
    """
    if end_local.hour == 0 and end_local.minute == 0 and end_local.second == 0:
        return (end_local - timedelta(days=1)).date()
    return end_local.date()


def from_interval_end_utc(end_utc: datetime, *, site_tz: ZoneInfo = SITE_TZ) -> Interval15:
    if end_utc.tzinfo is None:
        raise ValueError("end_utc must be timezone-aware")
    end_utc = end_utc.astimezone(timezone.utc)
    start_utc = end_utc - timedelta(seconds=DURATION_S)
    end_local = end_utc.astimezone(site_tz).replace(tzinfo=None)
    q = quarter_from_interval_end_hms(end_local.hour, end_local.minute)
    sd = site_date_for_interval_end(end_local)
    return Interval15(
        interval_start_utc=start_utc,
        interval_end_utc=end_utc,
        site_date=sd,
        quarter_index=q,
    )


def hour_ending_int_1_24(q: int) -> int:
    """Hour bucket 1..24 containing quarter ``q`` (q0–q3 → 1, …, q92–q95 → 24)."""
    if not (0 <= q < STEPS):
        raise ValueError(f"quarter_index out of range: {q}")
    return (q // 4) + 1


def from_eplus_stamp(stamp: str, *, year_hint: int | None = None) -> tuple[int, int, int]:
    """Parse E+ timestep stamp → (hour_ending_int_1_24, minute, quarter_index).

    Never maps 00:15/00:30 to HE=24 (legacy farm bug). Prefer
    ``hour_ending_from_quarter`` for fractional ML features.
    """
    del year_hint  # reserved for ambiguous year-less stamps
    parts = str(stamp).strip().split()
    if len(parts) < 2:
        return 0, 0, 0
    hm = parts[1].split(":")
    h = int(hm[0])
    mi = int(hm[1]) if len(hm) > 1 else 0
    q = quarter_from_interval_end_hms(h, mi)
    return hour_ending_int_1_24(q), mi, q


def calendar_features_for_step(step: int) -> dict[str, float]:
    """Clock features for prediction step ``step`` (0..95) under the contract."""
    he = hour_ending_from_quarter(step)
    return {
        "step_15": float(step),
        "sin_step": float(__import__("math").sin(2 * __import__("math").pi * step / STEPS)),
        "cos_step": float(__import__("math").cos(2 * __import__("math").pi * step / STEPS)),
        "hour_ending": float(he),
        "hours_to_occupy": float(max(0.0, (28 - step) / 4.0)),
    }


def golden_table() -> list[dict[str, Any]]:
    """Physical times used in audits/tests."""
    rows = []
    # Use a fixed winter day in standard time (no DST): 2026-01-15
    base = date(2026, 1, 15)
    cases = [
        ("00:15", 0, 15, 0, 0.25),
        ("00:30", 0, 30, 1, 0.5),
        ("01:00", 1, 0, 3, 1.0),
        ("23:45", 23, 45, 94, 23.75),
        ("24:00", 24, 0, 95, 24.0),
    ]
    for label, h, mi, q_exp, he_exp in cases:
        q = quarter_from_interval_end_hms(h, mi)
        assert q == q_exp, (label, q, q_exp)
        he = hour_ending_from_quarter(q)
        assert abs(he - he_exp) < 1e-9, (label, he, he_exp)
        if h == 24:
            end_naive = datetime(base.year, base.month, base.day, 0, 0) + timedelta(days=1)
            sd = base
        else:
            end_naive = datetime(base.year, base.month, base.day, h, mi)
            sd = site_date_for_interval_end(end_naive)
        end_utc = end_naive.replace(tzinfo=SITE_STANDARD).astimezone(timezone.utc)
        iv = Interval15(
            interval_start_utc=end_utc - timedelta(seconds=DURATION_S),
            interval_end_utc=end_utc,
            site_date=sd,
            quarter_index=q,
        )
        rows.append(
            {
                "label": label,
                "quarter_index": q,
                "step_15": iv.step_15,
                "hour_ending": he,
                "site_date": sd.isoformat(),
                "interval_end_utc": end_utc.isoformat(),
            }
        )
    # 00:00 stamp → prior day q95
    mid = datetime(2026, 1, 16, 0, 0)
    q0 = quarter_from_interval_end_hms(0, 0)
    rows.insert(
        0,
        {
            "label": "00:00",
            "quarter_index": q0,
            "step_15": q0,
            "hour_ending": hour_ending_from_quarter(q0),
            "site_date": site_date_for_interval_end(mid).isoformat(),
            "note": "belongs to previous site_date as q95",
        },
    )
    return rows
