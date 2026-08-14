"""Phase 0 / Economic MPC unit tests (no live EnergyPlus required)."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from eplus_gym.objective import ComfortGates, incremental_demand, score_trajectory
from eplus_gym.parametric_daily_controller import (
    ParametricDailyController,
    ParametricDailyParams,
    build_htg_sp_series_f,
)
from eplus_gym.simulate import (
    day_for_step,
    detect_synthetic_step_dating,
    validate_live_trajectory_calendar,
)
from eplus_gym.tariff_contract import TariffContract, latex_cost_equations
from eplus_native.idf_stage import disable_sizing_periods

_ROOT = Path(__file__).resolve().parents[1]


def test_disable_sizing_periods_forces_no():
    text = (
        "SimulationControl,\n"
        "    Yes,\n"
        "    Yes,\n"
        "    Yes,                      !- Run Simulation for Sizing Periods\n"
        "    No,\n"
        "    Yes;\n"
    )
    out = disable_sizing_periods(text)
    assert "Yes,                      !- Run Simulation for Sizing Periods" not in out
    assert "No,                      !- Run Simulation for Sizing Periods" in out or (
        "No," in out and "Run Simulation for Sizing Periods" in out
    )


def test_reject_contaminated_oat_pattern():
    rows = []
    for i in range(96):
        oat = -17.8 if i < 48 else 24.65
        rows.append(
            {
                "step": i,
                "oat_c": oat,
                "kind_of_sim": 3,
                "warmup": 0.0,
                "ep_year": 2026,
                "ep_month": 1,
                "ep_day": 26,
                "ep_hour": i // 4,
                "ep_minute": (i % 4) * 15,
            }
        )
    cal = validate_live_trajectory_calendar(rows, expected_day="2026-01-26")
    assert not cal["ok"]
    assert any("contaminated OAT" in x for x in cal["issues"])


def test_multi_day_calendar_allows_period_span():
    rows = []
    # 2 days × 96 steps
    for day_i, day in enumerate((1, 2)):
        for i in range(96):
            rows.append(
                {
                    "step": day_i * 96 + i,
                    "kind_of_sim": 3,
                    "warmup": 0.0,
                    "ep_year": 2025,
                    "ep_month": 12,
                    "ep_day": day,
                    "ep_hour": i // 4,
                    "ep_minute": (i % 4) * 15,
                    "oat_c": -10.0,
                }
            )
    cal = validate_live_trajectory_calendar(
        rows,
        expected_day="2025-12-01",
        expected_end="2025-12-02",
        expect_steps=192,
    )
    assert cal["ok"], cal["issues"]


def test_multi_day_rejects_single_day_equality_bug():
    """Regression: winter period must not require every row == begin day."""
    rows = []
    for day in range(1, 4):
        for i in range(96):
            rows.append(
                {
                    "step": (day - 1) * 96 + i,
                    "kind_of_sim": 3,
                    "warmup": 0.0,
                    "ep_year": 2025,
                    "ep_month": 12,
                    "ep_day": day,
                    "ep_hour": i // 4,
                    "ep_minute": (i % 4) * 15,
                }
            )
    # Old bug path: expected_day only + expect_steps>96 without end still ok via inferred end
    cal = validate_live_trajectory_calendar(
        rows, expected_day="2025-12-01", expect_steps=288
    )
    assert cal["ok"], cal["issues"]


def test_reject_synthetic_step_dating():
    begin = "2026-01-26"
    rows = [
        {"step": i, "day": day_for_step(begin, i)}
        for i in range(5)
    ]
    assert detect_synthetic_step_dating(rows, begin)


def test_parametric_recovery_raises_htg_before_occ():
    p = ParametricDailyParams(
        occupied_heating_f=70.0,
        unoccupied_heating_f=60.0,
        recovery_start_minutes_before_occupancy=120,
        recovery_ramp_minutes=60,
        occupancy_start_step=28,
        occupancy_end_step=68,
    )
    series = build_htg_sp_series_f(p)
    assert series[0] == pytest.approx(60.0)
    # mid-ramp before occupancy
    assert 60.0 < series[26] < 70.0
    assert series[28] == pytest.approx(70.0)
    ctrl = ParametricDailyController(p)
    assert len(ctrl.series_f()) == 96
    assert "hvac_start" in ctrl.provenance()["note"]


def test_incremental_demand_billing_floor():
    new_p, inc_kw, inc_cost = incremental_demand(100.0, 120.0, 15.0)
    assert new_p == 120.0
    assert inc_kw == 20.0
    assert inc_cost == 300.0
    new_p2, inc_kw2, inc_cost2 = incremental_demand(100.0, 80.0, 15.0)
    assert inc_kw2 == 0.0
    assert inc_cost2 == 0.0


def test_physical_only_zero_dollars_still_ranks():
    df = pd.DataFrame(
        {
            "facility_kw": [100.0] * 96,
            "step": list(range(96)),
            **{f"zone_temp_{z}_f": [70.0] * 96 for z in ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")},
        }
    )
    tariff = TariffContract.physical_only(existing_billing_peak_kw=90.0)
    scored = score_trajectory(df, tariff)
    assert scored.money_mode == "PHYSICAL_ONLY"
    assert scored.energy_cost == 0.0
    assert scored.incremental_demand_cost == 0.0
    assert scored.daily_kwh == pytest.approx(2400.0)
    assert scored.feasible


def test_refuse_zero_cost_on_empty():
    tariff = TariffContract.physical_only()
    with pytest.raises(ValueError, match="empty"):
        score_trajectory(pd.DataFrame(), tariff)


def test_latex_equations_present():
    eq = latex_cost_equations()
    assert "C_" in eq["total"] or r"C_" in eq["total"]
    assert "MTD" in eq["demand"] or "demand" in eq["demand"]


def test_optimize_tomorrow_pure_helpers(tmp_path: Path):
    from eplus_gym_app.optimize_tomorrow import (
        approve_recommendation,
        list_studies,
    )

    assert list_studies(tmp_path) == []
    root = tmp_path / "reports" / "eplus_gym" / "optimization" / "s1"
    root.mkdir(parents=True)
    (root / "recommendation.json").write_text(
        json.dumps({"recommended": {"feasible": True, "peak_kw": 1.0}}),
        encoding="utf-8",
    )
    out = approve_recommendation(root)
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["approved"] is True
    assert "Site Config" in doc["approved_note"]
    # Site config untouched
    assert not (tmp_path / "reports" / "eplus_gym" / "site_dsm_config.json").is_file()

