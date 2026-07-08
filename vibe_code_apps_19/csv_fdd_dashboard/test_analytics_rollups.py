"""Tests for ECM analytics rollups."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from analytics_rollups import rollup_rule


def test_rollup_rule_hours():
    n = 96
    df = pd.DataFrame({
        "fault_comfort": [True] * 8 + [False] * (n - 8),
    })
    occ = pd.Series([True] * n)
    out = rollup_rule(
        df,
        "fault_comfort",
        rule_id="COMFORT",
        ecm_id="ECM-1",
        poll_seconds=900,
        occupied=occ,
    )
    assert out["fault_hours"] == 2.0
    assert out["fault_pct"] > 0
