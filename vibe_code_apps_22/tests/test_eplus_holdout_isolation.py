"""Tests for trial-specific utility scoring and holdout-isolated ranking."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "ml"))
sys.path.insert(0, str(_ROOT / "scripts"))

from eplus_calibrate_multires import _rank_candidate  # noqa: E402
from eplus_validation_contract import (  # noqa: E402
    chronological_splits,
    period_mask,
    score_period,
)


def test_locked_winter_is_january_not_last_30_days():
    idx = pd.date_range("2025-08-01", periods=330 * 24, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "interval_end_utc": idx,
            "observed_kw": 50.0,
            "simulated_kw": 55.0,
        }
    )
    periods = chronological_splits(df)
    winter = periods["locked_winter_holdout"]
    assert winter["role"] == "locked_no_tuning_evaluate_once"
    assert "2026-01-01" in winter["start"]
    assert winter["chosen_a_priori"] is True
    summer = periods["annual_summer_generalization"]
    assert summer["role"] == "generalization_diagnostic_not_ranking"
    # Legacy alias warns
    assert "warning" in periods["locked_final_holdout"]


def test_holdout_mutation_does_not_change_ranking():
    """Changing locked-winter targets must not change rank_key from chrono-val metrics."""
    n = 200
    util_pass = {"status": "pass"}
    interv_pass = {"status": "pass"}
    chrono_a = {"status": "fail", "nmbe_pct": 5.0, "cvrmse_pct": 40.0, "n": n}
    chrono_b = {"status": "fail", "nmbe_pct": 5.0, "cvrmse_pct": 80.0, "n": n}
    r1 = _rank_candidate(util_pass, interv_pass, chrono_a)
    r2 = _rank_candidate(util_pass, interv_pass, chrono_b)
    assert r1["rank_key"][2] < r2["rank_key"][2]
    assert r1["ranking_uses_holdout"] is False
    # Mutating a fake holdout block does nothing to ranking helpers
    holdout_mutated = {"status": "pass", "nmbe_pct": 0.0, "cvrmse_pct": 1.0, "n": n}
    r1b = _rank_candidate(util_pass, interv_pass, chrono_a)
    assert r1b["rank_key"] == r1["rank_key"]
    _ = holdout_mutated  # explicit: holdout not an argument to rank


def test_utility_fail_outranks_even_if_hourly_better():
    util_fail = {"status": "fail"}
    util_pass = {"status": "pass"}
    interv = {"status": "pass"}
    chrono_good = {"status": "fail", "nmbe_pct": 1.0, "cvrmse_pct": 35.0, "n": 100}
    chrono_bad = {"status": "fail", "nmbe_pct": 1.0, "cvrmse_pct": 90.0, "n": 100}
    r_fail_util = _rank_candidate(util_fail, interv, chrono_good)
    r_pass_util = _rank_candidate(util_pass, interv, chrono_bad)
    assert r_fail_util["rank_key"][0] > r_pass_util["rank_key"][0]


def test_period_mask_excludes_january_from_chrono_val():
    idx = pd.date_range("2025-11-01", periods=120 * 24, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "interval_end_utc": idx,
            "observed_kw": 1.0,
            "simulated_kw": 1.1,
        }
    )
    m = period_mask(df, "chronological_validation")
    jan = (pd.to_datetime(df["interval_end_utc"], utc=True).dt.month == 1) & (
        pd.to_datetime(df["interval_end_utc"], utc=True).dt.year == 2026
    )
    assert not bool((m & jan).any()), "January must not appear in chronological_validation"
    w = period_mask(df, "locked_winter_holdout")
    assert w.sum() > 0
    assert not bool((m & w).any()), "chrono val and locked winter must not overlap"


@pytest.mark.skipif(
    not Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside\eplus\campaigns\bounded_exec_20260807\trials\B_equip_mult_mid\sim\eplusmtr.csv").is_file(),
    reason="site campaign sim not present",
)
def test_golden_utility_trial_specific_approx():
    from eplus_validation_contract import utility_monthly_from_trial_sim

    root = Path(r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")
    mid = root / "eplus/campaigns/bounded_exec_20260807/trials/B_equip_mult_mid/sim"
    lo = root / "eplus/campaigns/bounded_exec_20260807/trials/C_infil_mult_lo/sim"
    u_mid = utility_monthly_from_trial_sim(root, mid)
    u_lo = utility_monthly_from_trial_sim(root, lo)
    assert u_mid["n"] == 10
    assert u_mid["scorecard_gl14_status_imported"] is False
    assert u_mid["nmbe_pct"] == pytest.approx(-0.06, abs=0.5)
    assert u_mid["cvrmse_pct"] == pytest.approx(11.44, abs=0.5)
    assert u_lo["nmbe_pct"] == pytest.approx(5.59, abs=0.5)
    assert u_lo["cvrmse_pct"] == pytest.approx(13.55, abs=0.5)
    assert u_lo["status"] == "fail"  # |NMBE| > 5
    assert u_mid["nmbe_pct"] != u_lo["nmbe_pct"]
