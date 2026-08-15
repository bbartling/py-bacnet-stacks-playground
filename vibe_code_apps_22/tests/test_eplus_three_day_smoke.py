"""Optional 3-day EnergyPlus smoke (cold / shoulder / weekend)."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from eplus_gym.rl.live_day_worker import run_live_day_inprocess
from eplus_gym.six_zone_daily_controller import SixZoneDailyParams


@pytest.mark.eplus
def test_three_day_energyplus_smoke(tmp_path: Path):
    site_root = os.environ.get("SITE_ROOT")
    if not site_root:
        pytest.skip("SITE_ROOT is required for the EnergyPlus smoke test")
    site = Path(site_root)
    epw = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    idf = Path(__file__).resolve().parents[1] / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
    if not epw.is_file() or not idf.is_file():
        pytest.skip("site EPW or champion IDF missing")
    days = ["2026-01-26", "2026-03-16", "2026-01-25"]  # school cold, shoulder, weekend
    params = SixZoneDailyParams().to_dict()
    for day in days:
        ep_dir = tmp_path / day
        payload = run_live_day_inprocess(
            site_root=site,
            epw=epw,
            champion_idf=idf,
            day=day,
            params=params,
            ep_dir=ep_dir,
            lookback_days=1,
        )
        assert payload.get("n_rows") == 96
        assert payload.get("n_all_rows") == 192
        q = payload.get("eplus_quality") or {}
        assert q.get("severe_count") == 0
        assert q.get("fatal_count") == 0
        assert payload.get("failed") is False
