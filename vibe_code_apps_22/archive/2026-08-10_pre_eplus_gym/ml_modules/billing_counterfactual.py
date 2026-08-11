"""Billing-period peak helpers for historical counterfactuals.

``existing_billing_peak_kw`` for a target day must be the peak established
*before* that day in the billing month — never the actual peak of the day
being resimulated.
"""
from __future__ import annotations

from typing import Mapping


def mtd_peak_before_day(daily_peaks: Mapping[str, float], target_day: str) -> float:
    """Max daily peak for days in the same YYYY-MM strictly before ``target_day``.

    Returns 0.0 when no prior days exist (first day of month / empty map).
    """
    if len(target_day) < 10:
        raise ValueError(f"expected YYYY-MM-DD, got {target_day!r}")
    month = target_day[:7]
    prior = [
        float(v)
        for d, v in daily_peaks.items()
        if isinstance(d, str) and d[:7] == month and d < target_day and v is not None
    ]
    return float(max(prior)) if prior else 0.0
