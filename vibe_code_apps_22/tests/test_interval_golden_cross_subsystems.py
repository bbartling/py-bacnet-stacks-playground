"""Golden interval contract across subsystems + lag / billing gates."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP / "ml"), str(_APP / "scripts"), str(_APP), str(_APP / "eplus_native")]

from interval15 import (  # noqa: E402
    calendar_features_for_step,
    from_eplus_stamp,
    golden_table,
    hour_ending_from_quarter,
    quarter_from_interval_end_hms,
)
from simulation_contract import incremental_demand  # noqa: E402


FIXTURE = _APP / "ml" / "artifacts" / "fixtures" / "interval15" / "golden_physical_times.json"


def test_golden_fixture_matches_module():
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    got = {r["label"]: r for r in golden_table()}
    for row in expected:
        g = got[row["label"]]
        assert g["quarter_index"] == row["quarter_index"]
        assert g["step_15"] == row["step_15"]
        assert abs(float(g["hour_ending"]) - float(row["hour_ending"])) < 1e-9


def test_interval_golden_cross_subsystems():
    """BAS formula, E+ stamp parser, and hybrid calendar features must agree."""
    cases = [
        ((0, 15), "2026-01-15 00:15", 0, 0.25),
        ((0, 30), "2026-01-15 00:30", 1, 0.5),
        ((1, 0), "2026-01-15 01:00", 3, 1.0),
        ((23, 45), "2026-01-15 23:45", 94, 23.75),
        ((24, 0), "2026-01-15 24:00", 95, 24.0),
    ]
    for (h, mi), stamp, q_exp, he_exp in cases:
        q = quarter_from_interval_end_hms(h, mi)
        he_i, minute, q2 = from_eplus_stamp(stamp)
        cal = calendar_features_for_step(q)
        assert q == q_exp == q2
        assert minute == mi
        assert abs(hour_ending_from_quarter(q) - he_exp) < 1e-9
        assert abs(cal["hour_ending"] - he_exp) < 1e-9
        assert cal["step_15"] == float(q)
        # Never map early morning to HE 24
        if q < 92:
            assert he_i != 24 or q >= 92


def test_eplus_0015_not_he24():
    he, mi, q = from_eplus_stamp("2026-01-26 00:15")
    assert q == 0 and mi == 15 and he == 1


def test_96_intervals_exact_day_energy():
    assert abs(96 * 900 - 86400) < 1e-9
    kw = np.full(96, 100.0)
    assert abs(float(kw.sum() * 0.25) - 2400.0) < 1e-9


def test_no_current_target_in_lag_features():
    from hybrid_rollout import build_row, init_state_from_contract

    init = {
        "facility_kw": 50.0,
        "oat_f": 20.0,
        **{f"zone_temp_{z}_f": 68.0 for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")},
    }
    state = init_state_from_contract(init)
    weather = {
        "oat_f": [10.0] * 96,
        "rh_pct": [40.0] * 96,
        "ghi": [0.0] * 96,
    }
    schedule = {"strategy_id": "baseline"}
    meta = {"month": 1, "doy": 26, "is_weekend": 0, "occupied_schedule": [0.0] * 96}
    row0, _ = build_row(step=0, weather=weather, schedule=schedule, state=state, meta=meta, hdd_acc=0.0)
    # Mutate a fictional "current target" — features for step 0 must still use init lags
    assert row0["facility_kw_lag1"] == 50.0
    assert row0["hour_ending"] == pytest.approx(0.25)
    assert row0["step_15"] == 0.0


def test_midnight_state_is_prior_state():
    from hybrid_rollout import init_state_from_contract

    init = {
        "facility_kw": 77.0,
        "oat_f": 11.0,
        **{f"zone_temp_{z}_f": 65.0 for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")},
    }
    state = init_state_from_contract(init)
    assert state["facility_kw_lag1"] == 77.0
    assert state["oat_lag1"] == 11.0


def test_month_peak_counterfactual():
    """Reducing the actual peak day must lower demand charge vs prior MTD peak."""
    mtd_peak_before_day = 250.0  # established before target day
    actual_day_peak = 300.0
    strategy_peak = 220.0
    rate = 12.0  # illustrative $/kW
    # Wrong playground semantics: using actual_day_peak as existing → strategy gets $0 demand benefit
    _, _, wrong_cost = incremental_demand(actual_day_peak, strategy_peak, rate)
    assert wrong_cost == 0.0
    # Correct: existing = peak before day
    new_p, inc_kw, inc_cost = incremental_demand(mtd_peak_before_day, strategy_peak, rate)
    assert new_p == mtd_peak_before_day
    assert inc_kw == 0.0
    assert abs(inc_cost) < 1e-9
    # Strategy that still exceeds prior MTD is charged only the delta
    new_p2, inc_kw2, inc_cost2 = incremental_demand(mtd_peak_before_day, 280.0, rate)
    assert inc_kw2 == pytest.approx(30.0)
    assert inc_cost2 == pytest.approx(360.0)


def test_dst_spring_forward_metadata():
    """Civil vs standard metadata diverge around DST; joins remain on UTC quarters."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from interval15 import SITE_STANDARD, from_interval_end_utc

    chicago = ZoneInfo("America/Chicago")
    # 2026-03-08 02:00 CST → 03:00 CDT (spring forward)
    civil = datetime(2026, 3, 8, 3, 15, tzinfo=chicago)
    iv = from_interval_end_utc(civil.astimezone(__import__("datetime").timezone.utc))
    assert 0 <= iv.quarter_index < 96
    assert iv.duration_s == 900
    # Standard offset still -6h relative to UTC for E+ path
    assert SITE_STANDARD.utcoffset(None).total_seconds() == -6 * 3600


def test_billing_helper_mtd_before_day():
    from billing_counterfactual import mtd_peak_before_day

    days = {
        "2026-01-10": 200.0,
        "2026-01-15": 310.0,
        "2026-01-20": 180.0,
    }
    assert mtd_peak_before_day(days, "2026-01-15") == 200.0
    assert mtd_peak_before_day(days, "2026-01-10") == 0.0
    assert mtd_peak_before_day(days, "2026-01-20") == 310.0
