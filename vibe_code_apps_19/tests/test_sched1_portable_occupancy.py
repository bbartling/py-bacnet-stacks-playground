"""SCHED-1 portable occupancy (open-fdd #710) — numeric unoccupied + fan on → fault."""
from __future__ import annotations

import pandas as pd

from open_fdd.rules.cookbook_catalog import sched1


def test_sched1_numeric_zero_unoccupied_with_fan_on_is_fault():
    idx = pd.date_range("2026-01-01", periods=4, freq="15min")
    d = pd.DataFrame(
        {
            "occupied": [0, 0.0, 1, 0],
            "fan-status": [True, True, True, False],
        },
        index=idx,
    )
    out = sched1(d, {}, poll=900)
    # first two rows: unoccupied + fan on → True; occupied fan → False; unocc fan off → False
    assert bool(out.iloc[0]) is True
    assert bool(out.iloc[1]) is True
    assert bool(out.iloc[2]) is False
    assert bool(out.iloc[3]) is False


def test_sched1_string_unoccupied_still_faults():
    idx = pd.date_range("2026-01-01", periods=2, freq="15min")
    d = pd.DataFrame(
        {"occupied": ["unoccupied", "Occupied"], "fan-status": [True, True]},
        index=idx,
    )
    out = sched1(d, {}, poll=900)
    assert bool(out.iloc[0]) is True
    assert bool(out.iloc[1]) is False
