"""Utility billing periods keyed by full start/end dates.

The legacy ``wattlab.contracts.UtilityDataset`` keys bills by month-number
strings ("YYYY-MM"), which cannot represent real read cycles (a "January"
bill often runs Dec 28 – Jan 27) and collides across multi-year histories.
This module is the additive replacement for investigation work:

- ``BillingPeriod``  — one bill with explicit start/end dates and duration guards
- ``BillingHistory`` — a multi-year, single-fuel history with overlap/gap analysis
- ``from_utility_dataset`` — lift a legacy 12-month ``UtilityDataset`` into a
  ``BillingHistory`` (calendar-month periods) without breaking existing users

Overlaps between consecutive bills of a day or two are common (meter read on
the boundary day) and are *flagged*, never silently merged or dropped.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from wattlab.contracts import FuelKind, UnitKind, UtilityDataset

#: Duration band for a "normal" monthly read cycle, in days.
TYPICAL_MIN_DAYS = 25
TYPICAL_MAX_DAYS = 36

#: Hard duration limits; anything outside is rejected as data-entry error.
ABSOLUTE_MIN_DAYS = 1
ABSOLUTE_MAX_DAYS = 92


class BillingPeriod(BaseModel):
    """One utility bill covering an explicit, inclusive date range."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start_date: date
    end_date: date
    fuel: FuelKind
    unit: UnitKind
    usage: float = Field(ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    demand_kw: float | None = Field(default=None, ge=0)
    estimated_read: bool = False

    @model_validator(mode="after")
    def _dates_and_duration(self) -> "BillingPeriod":
        if self.end_date < self.start_date:
            raise ValueError(
                f"end_date {self.end_date.isoformat()} is before "
                f"start_date {self.start_date.isoformat()}"
            )
        days = self.days
        if days < ABSOLUTE_MIN_DAYS or days > ABSOLUTE_MAX_DAYS:
            raise ValueError(
                f"billing period of {days} days "
                f"({self.start_date.isoformat()}..{self.end_date.isoformat()}) "
                f"is outside the credible range "
                f"[{ABSOLUTE_MIN_DAYS}, {ABSOLUTE_MAX_DAYS}]"
            )
        return self

    @property
    def days(self) -> int:
        """Inclusive length of the period in days."""
        return (self.end_date - self.start_date).days + 1

    @property
    def is_irregular(self) -> bool:
        """True when the read cycle falls outside the typical monthly band."""
        return not (TYPICAL_MIN_DAYS <= self.days <= TYPICAL_MAX_DAYS)

    @property
    def usage_per_day(self) -> float:
        return self.usage / self.days

    @property
    def midpoint(self) -> date:
        return self.start_date + timedelta(days=(self.end_date - self.start_date).days // 2)

    def overlap_days(self, other: "BillingPeriod") -> int:
        """Number of calendar days covered by both periods (inclusive dates)."""
        latest_start = max(self.start_date, other.start_date)
        earliest_end = min(self.end_date, other.end_date)
        return max(0, (earliest_end - latest_start).days + 1)


class PeriodOverlap(BaseModel):
    """A flagged partial overlap between two adjacent bills."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    first_start: date
    second_start: date
    overlap_days: int = Field(gt=0)
    severity: Literal["boundary", "partial"]


class PeriodGap(BaseModel):
    """A flagged gap of uncovered days between two adjacent bills."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gap_start: date
    gap_end: date
    gap_days: int = Field(gt=0)


class BillingHistory(BaseModel):
    """Multi-year, single-fuel billing history keyed by real dates.

    Because periods carry full dates, two "January" bills from different
    years can never collide, and 24+ month histories are first-class.
    Duplicate periods (same start *and* end) are rejected; a bill fully
    contained within another is rejected; partial overlaps are flagged
    via :meth:`overlaps` for the analyst to resolve.
    """

    model_config = ConfigDict(extra="forbid")

    periods: list[BillingPeriod] = Field(min_length=1)
    floor_area_sqft: float | None = Field(default=None, gt=0)
    provenance: Literal["actual", "synthetic_rehearsal"] = "actual"

    @model_validator(mode="after")
    def _single_fuel_sorted_no_duplicates(self) -> "BillingHistory":
        fuels = {p.fuel for p in self.periods}
        if len(fuels) > 1:
            raise ValueError(
                f"all periods must share one fuel (got {sorted(fuels)}); "
                "use one BillingHistory per fuel"
            )
        units = {p.unit for p in self.periods}
        if len(units) > 1:
            raise ValueError(
                f"all periods must share one unit (got {sorted(units)}); "
                "convert to a consistent unit before validation"
            )
        ordered = sorted(self.periods, key=lambda p: (p.start_date, p.end_date))
        keys = [(p.start_date, p.end_date) for p in ordered]
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        if dupes:
            pretty = ", ".join(f"{s.isoformat()}..{e.isoformat()}" for s, e in dupes)
            raise ValueError(f"duplicate billing periods: {pretty}")
        for prev, curr in zip(ordered, ordered[1:]):
            if curr.end_date <= prev.end_date:
                raise ValueError(
                    f"period {curr.start_date.isoformat()}.."
                    f"{curr.end_date.isoformat()} is fully contained within "
                    f"{prev.start_date.isoformat()}..{prev.end_date.isoformat()}"
                )
        object.__setattr__(self, "periods", ordered)
        return self

    @property
    def fuel(self) -> FuelKind:
        return self.periods[0].fuel

    @property
    def unit(self) -> UnitKind:
        return self.periods[0].unit

    @property
    def coverage_start(self) -> date:
        return self.periods[0].start_date

    @property
    def coverage_end(self) -> date:
        return self.periods[-1].end_date

    def overlaps(self) -> list[PeriodOverlap]:
        """Partial overlaps between adjacent bills, flagged not fixed.

        A 1-day overlap is classified ``boundary`` (a meter read on the
        changeover day, very common); anything longer is ``partial`` and
        deserves analyst attention before daily-normalizing.
        """
        found: list[PeriodOverlap] = []
        for prev, curr in zip(self.periods, self.periods[1:]):
            days = prev.overlap_days(curr)
            if days > 0:
                found.append(
                    PeriodOverlap(
                        first_start=prev.start_date,
                        second_start=curr.start_date,
                        overlap_days=days,
                        severity="boundary" if days == 1 else "partial",
                    )
                )
        return found

    def gaps(self) -> list[PeriodGap]:
        """Uncovered day ranges between adjacent bills."""
        found: list[PeriodGap] = []
        for prev, curr in zip(self.periods, self.periods[1:]):
            first_uncovered = prev.end_date + timedelta(days=1)
            if curr.start_date > first_uncovered:
                found.append(
                    PeriodGap(
                        gap_start=first_uncovered,
                        gap_end=curr.start_date - timedelta(days=1),
                        gap_days=(curr.start_date - first_uncovered).days,
                    )
                )
        return found

    def irregular_periods(self) -> list[BillingPeriod]:
        return [p for p in self.periods if p.is_irregular]

    def total_usage(self) -> float:
        return sum(p.usage for p in self.periods)

    def quality_report(self) -> dict[str, object]:
        """Serializable data-quality summary for run artifacts."""
        overlaps = self.overlaps()
        gaps = self.gaps()
        irregular = self.irregular_periods()
        return {
            "fuel": self.fuel,
            "unit": self.unit,
            "n_periods": len(self.periods),
            "coverage_start": self.coverage_start.isoformat(),
            "coverage_end": self.coverage_end.isoformat(),
            "n_overlaps": len(overlaps),
            "n_partial_overlaps": sum(1 for o in overlaps if o.severity == "partial"),
            "n_gaps": len(gaps),
            "gap_days_total": sum(g.gap_days for g in gaps),
            "n_irregular_periods": len(irregular),
            "n_estimated_reads": sum(1 for p in self.periods if p.estimated_read),
            "clean": not overlaps and not gaps and not irregular,
        }

    def usage_by_calendar_month(self) -> dict[str, float]:
        """Day-weighted allocation of usage onto calendar months.

        Keys are full "YYYY-MM" strings, so multi-year histories never
        collide. Each bill's usage is spread uniformly over its days and
        summed per calendar month — the standard prorating used before
        comparing to monthly simulation output.
        """
        allocation: dict[str, float] = {}
        for p in self.periods:
            per_day = p.usage_per_day
            day = p.start_date
            while day <= p.end_date:
                key = f"{day.year:04d}-{day.month:02d}"
                allocation[key] = allocation.get(key, 0.0) + per_day
                day += timedelta(days=1)
        return dict(sorted(allocation.items()))


def _last_day_of_month(year: int, month: int) -> date:
    if month == 12:
        return date(year, 12, 31)
    return date(year, month + 1, 1) - timedelta(days=1)


def from_utility_dataset(dataset: UtilityDataset) -> BillingHistory:
    """Lift a legacy 12-month ``UtilityDataset`` into a ``BillingHistory``.

    Legacy bills carry only "YYYY-MM", so each is mapped to the full
    calendar month. This keeps the school rehearsal inputs usable by the
    new investigation pipeline without touching ``wattlab.contracts``.
    """
    periods = []
    for bill in dataset.bills:
        year, month = (int(part) for part in bill.month.split("-"))
        periods.append(
            BillingPeriod(
                start_date=date(year, month, 1),
                end_date=_last_day_of_month(year, month),
                fuel=bill.fuel,
                unit=bill.unit,
                usage=bill.usage,
                cost_usd=bill.cost_usd,
                demand_kw=bill.demand_kw,
            )
        )
    return BillingHistory(
        periods=periods,
        floor_area_sqft=dataset.floor_area_sqft,
        provenance=dataset.provenance,
    )
