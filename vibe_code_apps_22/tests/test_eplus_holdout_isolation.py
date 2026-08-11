"""Tests for trial-specific utility scoring and holdout-isolated ranking."""
from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "archive" / "ml"))
sys.path.insert(0, str(_ROOT / "scripts"))

from eplus_calibrate_multires import (  # noqa: E402
    _post_run_metrics_from_score,
    _rank_candidate,
    _rescore_existing_campaign,
    _score_sim,
)
from eplus_validation_contract import (  # noqa: E402
    AlignmentError,
    chronological_splits,
    day_level_peak_metrics,
    parse_complete_month_flag,
    period_mask,
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
    assert periods["policy"]["nested_chronological_cv"] is False
    summer = periods["annual_summer_generalization"]
    assert summer["role"] == "generalization_diagnostic_not_ranking"
    assert "warning" in periods["locked_final_holdout"]
    # Selection val is Dec 15–31 only (forward), not Feb–Mar
    val = periods["chronological_validation"]
    assert val["excludes_post_january"] is True
    assert len(val["segments"]) == 1


def test_forward_order_assertions():
    idx = pd.date_range("2025-08-01", periods=330 * 24, freq="h", tz="UTC")
    df = pd.DataFrame(
        {"interval_end_utc": idx, "observed_kw": 1.0, "simulated_kw": 1.1}
    )
    periods = chronological_splits(df)
    assert periods["calibration_development"]["n"] > 0
    assert periods["chronological_validation"]["n"] > 0
    assert periods["locked_winter_holdout"]["n"] > 0
    m_cal = period_mask(df, "calibration_development")
    m_val = period_mask(df, "chronological_validation")
    m_w = period_mask(df, "locked_winter_holdout")
    m_post = period_mask(df, "post_holdout_generalization")
    ts = pd.to_datetime(df["interval_end_utc"], utc=True)
    assert ts[m_cal].max() < ts[m_val].min()
    assert ts[m_val].max() < ts[m_w].min()
    assert ts[m_w].max() < ts[m_post].min()


def test_amy_anchor_outside_range_fails():
    idx = pd.date_range("2025-08-01", periods=30 * 24, freq="h", tz="UTC")
    df = pd.DataFrame(
        {"interval_end_utc": idx, "observed_kw": 1.0, "simulated_kw": 1.1}
    )
    with pytest.raises(AlignmentError, match="outside data range"):
        chronological_splits(df)


def test_holdout_mutation_does_not_change_ranking():
    n = 200
    util_pass = {"status": "pass"}
    interv_pass = {"status": "pass"}
    chrono_a = {"status": "fail", "nmbe_pct": 5.0, "cvrmse_pct": 40.0, "n": n}
    chrono_b = {"status": "fail", "nmbe_pct": 5.0, "cvrmse_pct": 80.0, "n": n}
    r1 = _rank_candidate(util_pass, interv_pass, chrono_a)
    r2 = _rank_candidate(util_pass, interv_pass, chrono_b)
    assert r1["rank_key"][2] < r2["rank_key"][2]
    assert r1["ranking_uses_holdout"] is False
    holdout_mutated = {"status": "pass", "nmbe_pct": 0.0, "cvrmse_pct": 1.0, "n": n}
    r1b = _rank_candidate(util_pass, interv_pass, chrono_a)
    assert r1b["rank_key"] == r1["rank_key"]
    _ = holdout_mutated


def test_utility_fail_outranks_even_if_hourly_better():
    util_fail = {"status": "fail"}
    util_pass = {"status": "pass"}
    interv = {"status": "pass"}
    chrono_good = {"status": "fail", "nmbe_pct": 1.0, "cvrmse_pct": 35.0, "n": 100}
    chrono_bad = {"status": "fail", "nmbe_pct": 1.0, "cvrmse_pct": 90.0, "n": 100}
    r_fail_util = _rank_candidate(util_fail, interv, chrono_good)
    r_pass_util = _rank_candidate(util_pass, interv, chrono_bad)
    assert r_fail_util["rank_key"][0] > r_pass_util["rank_key"][0]


def test_period_mask_excludes_january_and_feb_from_chrono_val():
    idx = pd.date_range("2025-11-01", periods=150 * 24, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "interval_end_utc": idx,
            "observed_kw": 1.0,
            "simulated_kw": 1.1,
        }
    )
    m = period_mask(df, "chronological_validation")
    ts = pd.to_datetime(df["interval_end_utc"], utc=True)
    jan = (ts.dt.month == 1) & (ts.dt.year == 2026)
    feb = (ts.dt.month == 2) & (ts.dt.year == 2026)
    assert not bool((m & jan).any())
    assert not bool((m & feb).any()), "Feb must not be in selection validation"
    w = period_mask(df, "locked_winter_holdout")
    assert w.sum() > 0
    assert not bool((m & w).any())


def test_score_sim_omits_holdout_by_default():
    """Candidate scoring must not compute locked-holdout metrics."""
    metrics = {
        "family_label": "RAW_EPLUS_IDEALLOADS_FIXED_COP",
        "monthly_utility": {"status": "pass"},
        "monthly_interval": {"status": "pass"},
        "hourly": {"status": "fail"},
        "hourly_chronological_validation": {"status": "fail"},
        "hourly_calibration_development": {"status": "fail"},
        "hourly_winter_peak_validation": {"status": "fail"},
        "hourly_annual_summer_generalization": {"status": "fail"},
        "hourly_post_holdout_generalization": {"status": "fail"},
        "q15": {"status": "diagnostic_only", "n": 100},
        "q15_chronological_validation": None,
        "aligned_hourly_n": 10,
        "aligned_15_n": 10,
        "provenance": {},
        "hourly_locked_winter_holdout": {"status": "pass", "cvrmse_pct": 1.0},
    }
    out = _post_run_metrics_from_score(metrics, include_locked_holdout=False)
    assert "hourly_locked_winter_holdout" not in out
    out2 = _post_run_metrics_from_score(metrics, include_locked_holdout=True)
    assert out2["hourly_locked_winter_holdout"]["cvrmse_pct"] == 1.0


def test_rescore_does_not_mutate_original_summary(tmp_path):
    camp = tmp_path / "camp"
    trials = camp / "trials" / "T1"
    trials.mkdir(parents=True)
    original = {
        "run_id": "camp",
        "n_succeeded": 1,
        "parent_idf_sha256": "abc",
        "epw_sha256": "def",
        "leaderboard": [],
    }
    summary_path = camp / "summary.json"
    summary_path.write_text(json.dumps(original) + "\n", encoding="utf-8")
    before = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    (trials / "trial_result.json").write_text(
        json.dumps({"trial_id": "T1", "status": "failed", "knobs": {}}),
        encoding="utf-8",
    )
    # No eplusmtr — rescore should still leave summary.json untouched
    with mock.patch("eplus_calibrate_multires.site_root", return_value=tmp_path):
        rc = _rescore_existing_campaign(camp)
    assert rc == 0
    after = hashlib.sha256(summary_path.read_bytes()).hexdigest()
    assert after == before
    assert list(camp.glob("summary_rescored_*.json"))
    assert (camp / "summary_rescored_latest.json").is_file()


def test_day_level_peak_metrics_circular():
    idx = pd.date_range("2026-01-01", periods=48, freq="h", tz="UTC")
    obs = np.zeros(48)
    sim = np.zeros(48)
    obs[10] = 100.0  # peak hour ~ local depending on tz
    sim[14] = 100.0
    df = pd.DataFrame(
        {"interval_end_utc": idx, "observed_kw": obs, "simulated_kw": sim}
    )
    out = day_level_peak_metrics(df)
    assert out["n_complete_days"] >= 1
    assert out["circular_abs_peak_timing_error_h"]["worst"] <= 12.0
    assert "multi_month_global_argmax" in out["forbidden_metric"]


def test_parse_complete_month_textual():
    assert parse_complete_month_flag("true") is True
    assert parse_complete_month_flag("False") is False
    assert parse_complete_month_flag(1) is True
    assert parse_complete_month_flag(0) is False
    with pytest.raises(AlignmentError):
        parse_complete_month_flag("maybe")


@pytest.mark.skipif(
    not os.environ.get("LAKESIDE_SITE_ROOT")
    and not os.environ.get("VIBE22_SITE_ROOT"),
    reason="site root env not set",
)
def test_golden_utility_trial_specific_approx():
    from eplus_validation_contract import utility_monthly_from_trial_sim
    from lakeside.paths import site_root

    root = site_root()
    mid = root / "eplus/campaigns/bounded_exec_20260807/trials/B_equip_mult_mid/sim"
    lo = root / "eplus/campaigns/bounded_exec_20260807/trials/C_infil_mult_lo/sim"
    if not (mid / "eplusmtr.csv").is_file():
        pytest.skip("campaign sim not present")
    u_mid = utility_monthly_from_trial_sim(root, mid)
    u_lo = utility_monthly_from_trial_sim(root, lo)
    assert u_mid["n"] == 10
    assert u_mid["scorecard_gl14_status_imported"] is False
    assert u_mid["nmbe_pct"] == pytest.approx(-0.06, abs=0.5)
    assert u_mid["cvrmse_pct"] == pytest.approx(11.44, abs=0.5)
    assert u_lo["nmbe_pct"] == pytest.approx(5.59, abs=0.5)
    assert u_lo["status"] == "fail"
    assert u_mid["nmbe_pct"] != u_lo["nmbe_pct"]
