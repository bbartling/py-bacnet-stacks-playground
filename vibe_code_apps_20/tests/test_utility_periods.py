"""Date-keyed billing periods: multi-year safety, overlap and gap flagging."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from wattlab.contracts import UtilityBillRecord, UtilityDataset
from wattlab.existing_building.utility_periods import (
    BillingHistory,
    BillingPeriod,
    from_utility_dataset,
)


def _period(start: date, days: int, usage: float = 1000.0, **kwargs) -> BillingPeriod:
    return BillingPeriod(
        start_date=start,
        end_date=start + timedelta(days=days - 1),
        fuel="electricity",
        unit="kwh",
        usage=usage,
        **kwargs,
    )


def _monthly_chain(start: date, n_months: int) -> list[BillingPeriod]:
    periods = []
    cursor = start
    for _ in range(n_months):
        year, month = cursor.year, cursor.month
        next_month = date(year + (month == 12), month % 12 + 1, 1)
        periods.append(
            _period(cursor, (next_month - cursor).days)
        )
        cursor = next_month
    return periods


def test_period_requires_ordered_dates_and_credible_duration():
    with pytest.raises(ValidationError, match="before"):
        BillingPeriod(
            start_date=date(2025, 3, 15),
            end_date=date(2025, 3, 1),
            fuel="electricity",
            unit="kwh",
            usage=10,
        )
    with pytest.raises(ValidationError, match="credible"):
        _period(date(2025, 1, 1), days=200)


def test_irregular_period_flagging():
    assert _period(date(2025, 1, 5), days=30).is_irregular is False
    assert _period(date(2025, 1, 5), days=15).is_irregular is True
    assert _period(date(2025, 1, 5), days=60).is_irregular is True


def test_multi_year_history_has_no_month_collision():
    """Two 'January' bills in different years must both survive intact."""
    history = BillingHistory(periods=_monthly_chain(date(2024, 1, 1), 24))
    assert len(history.periods) == 24
    assert history.coverage_start == date(2024, 1, 1)
    assert history.coverage_end == date(2025, 12, 31)
    monthly = history.usage_by_calendar_month()
    assert "2024-01" in monthly and "2025-01" in monthly
    assert len(monthly) == 24
    report = history.quality_report()
    assert report["clean"] is True
    assert report["n_periods"] == 24


def test_duplicate_period_rejected_but_same_month_different_year_ok():
    jan_2024 = _period(date(2024, 1, 1), days=31)
    with pytest.raises(ValidationError, match="duplicate"):
        BillingHistory(periods=[jan_2024, jan_2024])
    # Same calendar month, different year: fine.
    BillingHistory(periods=[jan_2024, _period(date(2025, 1, 1), days=31)])


def test_partial_overlap_is_flagged_not_hidden():
    first = _period(date(2025, 1, 3), days=30)  # ends 2025-02-01
    second = _period(date(2025, 1, 28), days=30)  # starts inside first
    history = BillingHistory(periods=[first, second])
    overlaps = history.overlaps()
    assert len(overlaps) == 1
    assert overlaps[0].overlap_days == 5
    assert overlaps[0].severity == "partial"
    report = history.quality_report()
    assert report["n_partial_overlaps"] == 1
    assert report["clean"] is False


def test_one_day_boundary_overlap_is_boundary_severity():
    first = _period(date(2025, 1, 1), days=31)  # ends 2025-01-31
    second = _period(date(2025, 1, 31), days=29)  # meter read on changeover day
    overlaps = BillingHistory(periods=[first, second]).overlaps()
    assert [o.severity for o in overlaps] == ["boundary"]


def test_gap_detection():
    first = _period(date(2025, 1, 1), days=31)
    second = _period(date(2025, 2, 10), days=28)  # 9 uncovered days
    gaps = BillingHistory(periods=[first, second]).gaps()
    assert len(gaps) == 1
    assert gaps[0].gap_days == 9
    assert gaps[0].gap_start == date(2025, 2, 1)


def test_contained_period_rejected():
    outer = _period(date(2025, 1, 1), days=60)
    inner = _period(date(2025, 1, 10), days=10)
    with pytest.raises(ValidationError, match="contained"):
        BillingHistory(periods=[outer, inner])


def test_mixed_fuel_rejected():
    elec = _period(date(2025, 1, 1), days=31)
    gas = BillingPeriod(
        start_date=date(2025, 2, 1),
        end_date=date(2025, 2, 28),
        fuel="gas",
        unit="therm",
        usage=100,
    )
    with pytest.raises(ValidationError, match="one fuel"):
        BillingHistory(periods=[elec, gas])


def test_legacy_utility_dataset_lifts_without_breaking_contract():
    bills = [
        UtilityBillRecord(month=f"2025-{m:02d}", fuel="electricity", unit="kwh", usage=1000 + m)
        for m in range(1, 13)
    ]
    dataset = UtilityDataset(
        bills=bills, floor_area_sqft=42000, provenance="synthetic_rehearsal"
    )
    history = from_utility_dataset(dataset)
    assert len(history.periods) == 12
    assert history.quality_report()["clean"] is True
    assert history.total_usage() == pytest.approx(sum(b.usage for b in bills))
    assert history.provenance == "synthetic_rehearsal"
    # February 2025 maps to the true month end.
    feb = history.periods[1]
    assert (feb.start_date, feb.end_date) == (date(2025, 2, 1), date(2025, 2, 28))
