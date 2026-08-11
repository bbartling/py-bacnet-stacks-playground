"""E2E: mutating locked-holdout targets must not change candidate ranking/champion."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "archive" / "ml"))
sys.path.insert(0, str(_ROOT / "scripts"))

from eplus_calibrate_multires import _rank_candidate  # noqa: E402
from eplus_validation_contract import (  # noqa: E402
    period_mask,
    score_aligned,
    score_period,
)


def _synthetic_year() -> pd.DataFrame:
    idx = pd.date_range("2025-08-01", periods=330 * 24, freq="h", tz="UTC")
    # Distinct chrono-val vs holdout patterns
    hod = idx.hour
    base = 40 + hod * 1.5
    df = pd.DataFrame(
        {
            "interval_end_utc": idx,
            "observed_kw": base,
            "simulated_kw": base * 1.2,
        }
    )
    return df


def test_e2e_holdout_mutation_preserves_selection_metrics():
    df = _synthetic_year()
    chrono = score_period(df, "chronological_validation")
    winter_before = score_period(df, "locked_winter_holdout")
    util = {"status": "pass"}
    interv = {"status": "pass"}
    rank_before = _rank_candidate(util, interv, chrono)

    # Radically mutate January (locked holdout) observed targets
    m_w = period_mask(df, "locked_winter_holdout")
    df2 = df.copy()
    df2.loc[m_w, "observed_kw"] = df2.loc[m_w, "observed_kw"] * 50.0 + 1000.0
    chrono_after = score_period(df2, "chronological_validation")
    winter_after = score_period(df2, "locked_winter_holdout")
    rank_after = _rank_candidate(util, interv, chrono_after)

    assert chrono_after["cvrmse_pct"] == chrono["cvrmse_pct"]
    assert chrono_after["nmbe_pct"] == chrono["nmbe_pct"]
    assert rank_after["rank_key"] == rank_before["rank_key"]
    # Only holdout report changes
    assert winter_after["cvrmse_pct"] != winter_before["cvrmse_pct"]
    assert "hourly_locked_winter_holdout" not in {
        "candidate_keys": list(chrono.keys())
    }


def test_candidate_score_period_excludes_holdout_rows():
    df = _synthetic_year()
    m_val = period_mask(df, "chronological_validation")
    m_w = period_mask(df, "locked_winter_holdout")
    assert not bool((m_val & m_w).any())
    sub = df.loc[m_val]
    block = score_aligned(sub, resolution="hourly")
    assert block["n"] == int(m_val.sum())
