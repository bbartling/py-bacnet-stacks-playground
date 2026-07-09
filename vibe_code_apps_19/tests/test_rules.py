"""Tests for pandas FDD rule helpers."""

from __future__ import annotations

import pandas as pd
import pytest

from app.rules.base import confirm_fault, hours_true


def test_confirm_fault_and_hours():
    raw = pd.Series([False, True, True, True, False], index=range(5))
    confirmed = confirm_fault(raw, poll_seconds=300, confirm_seconds=600)
    assert confirmed.tolist() == [False, False, True, True, False]
    assert hours_true(confirmed, 300) == pytest.approx(2 * 300 / 3600)
