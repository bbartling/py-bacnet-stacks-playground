"""Tests for DM hourly farm rows + feature leakage guard."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "ml"))

july_assets = ROOT / "assets" / "twin_b100_ops11"


def test_stratify_and_seed_proxy_smoke(tmp_path: Path):
    import dm_hourly_farm as farm

    epw = july_assets / "amy.epw"
    assert epw.is_file()
    stats = farm.parse_epw_day_stats(epw)
    assert len(stats) > 100
    days = farm.stratify_days(stats, n=3, seed=7)
    assert len(days) == 3
    jobs = farm.build_job_list(days, n_full=0)
    assert len(jobs) == 3 * 4  # core modes
    rows = farm.seed_proxy_farm(days, jobs, idf_sha="abc", epw_name="amy.epw")
    assert len(rows) >= 3 * 4 * 20
    assert rows[0]["schema_version"] == "vibe21.dm_hourly_row.v1"
    assert rows[0]["provenance"]["source"] == "SEEDED_SHAPE_PROXY"
    assert "facility_kw" in rows[0]["targets"]

    pq = tmp_path / "dm_hourly_rows.parquet"
    farm.write_parquet(rows, pq)
    assert pq.is_file() or pq.with_suffix(".jsonl").is_file()


def test_feature_no_future_leakage():
    from feature_compile_dm import assert_no_future_leakage

    rows = []
    for h in range(1, 25):
        rows.append(
            {
                "simulation_id": "sim_a",
                "day": "2025-07-24",
                "hour_ending": h,
                "dow": "Thursday",
                "oat_c": 20 + h * 0.5,
                "rh_pct": 40.0,
                "ghi": 100.0,
                "occupied": True,
                "strategy_id": "baseline",
                "phase": "baseline",
                "in_dr_window": False,
                "precool_f": 0.0,
                "relax_clg_f": 0.0,
                "relax_htg_f": 0.0,
                "deadband_target_f": None,
                "dat_delta_f": 0.0,
                "chw_avail": 1.0,
                "fan_avail": 1.0,
                "facility_kw": 100.0 + h,
            }
        )
    df = pd.DataFrame(rows)
    assert_no_future_leakage(df)


def test_actions_phase_precool():
    import dm_hourly_farm as farm

    a, phase, win = farm.actions_for_mode("precool_shift", 10, farm.MODE_DEFAULTS["precool_shift"])
    assert phase == "precool" and win and a["precool_f"] == 2.0
    a2, phase2, _ = farm.actions_for_mode("precool_shift", 15, farm.MODE_DEFAULTS["precool_shift"])
    assert phase2 == "relax" and a2["relax_clg_f"] == 5.0
