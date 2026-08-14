"""Unit tests for six-zone staging, controller, and coordinate descent (no live E+)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from eplus_gym.envs.lakeside_w2a import LakesideW2AEnv
from eplus_gym.optimize.six_zone_study import (
    ACTION_KEYS,
    GLOBAL_RECOVERY_MIN,
    GLOBAL_UNOCC,
    ZONE_MOVES,
    physical_better,
)
from eplus_gym.objective import ObjectiveResult
from eplus_gym.six_zone_daily_controller import (
    SixZoneDailyController,
    SixZoneDailyParams,
    ZoneOffsets,
    controller_hash,
)
from eplus_native.six_zone_htg_stage import (
    dsm_htg_schedule_name,
    stage_six_zone_heating_actuators,
    verify_six_zone_staging,
)


def test_action_keys_stable_order():
    assert ACTION_KEYS == ("1F_A", "1F_B", "1F_C", "1F_D", "2F_A", "2F_B")
    assert LakesideW2AEnv.ACTION_KEYS == ACTION_KEYS


def test_controller_shape_and_hash():
    ctrl = SixZoneDailyController(
        SixZoneDailyParams(unoccupied_heating_f=64.0, recovery_start_minutes_before_occupancy=60)
    )
    a = ctrl.action(0)
    assert a.shape == (6,)
    assert a.dtype == np.float32
    series = ctrl.series_f()
    assert list(series.keys()) == list(ACTION_KEYS)
    assert len(series["1F_A"]) == 96
    h1 = controller_hash(ctrl)
    h2 = controller_hash(ctrl)
    assert h1 == h2
    ctrl2 = SixZoneDailyController(
        SixZoneDailyParams(
            unoccupied_heating_f=64.0,
            recovery_start_minutes_before_occupancy=60,
            zone_offsets={"1F_A": ZoneOffsets(setback_offset_f=-1.0)},
        )
    )
    assert controller_hash(ctrl2) != h1


def test_coordinate_budget_constants():
    assert len(GLOBAL_UNOCC) * len(GLOBAL_RECOVERY_MIN) == 16
    assert len(ZONE_MOVES) == 4
    # ≤2 passes × 6 zones × 4 moves = 48; +16 global ≤ 64
    assert 16 + 2 * 6 * 4 <= 64


def test_physical_only_never_selects_on_dollars():
    base = ObjectiveResult(
        daily_kwh=100.0,
        peak_kw=50.0,
        energy_cost=999.0,
        incremental_demand_kw=0.0,
        incremental_demand_cost=999.0,
        new_billing_peak_kw=50.0,
        total_incremental_cost=1998.0,
        comfort_degree_hours=0.0,
        comfort_violations=0,
        feasible=True,
        money_mode="PHYSICAL_ONLY",
        physical_rank_key=(0, 50.0, 100.0, 0.0),
        extras={"movement_total_f": 0.0},
    )
    # Higher peak but lower $ — must NOT win
    worse_peak_cheaper = ObjectiveResult(
        daily_kwh=99.0,
        peak_kw=60.0,
        energy_cost=1.0,
        incremental_demand_kw=0.0,
        incremental_demand_cost=1.0,
        new_billing_peak_kw=60.0,
        total_incremental_cost=2.0,
        comfort_degree_hours=0.0,
        comfort_violations=0,
        feasible=True,
        money_mode="PHYSICAL_ONLY",
        physical_rank_key=(0, 60.0, 99.0, 0.0),
        extras={"movement_total_f": 0.0},
    )
    assert not physical_better(worse_peak_cheaper, base, max_kwh_penalty=100.0)
    better_peak = ObjectiveResult(
        daily_kwh=101.0,
        peak_kw=40.0,
        energy_cost=5000.0,
        incremental_demand_kw=0.0,
        incremental_demand_cost=5000.0,
        new_billing_peak_kw=40.0,
        total_incremental_cost=10000.0,
        comfort_degree_hours=0.0,
        comfort_violations=0,
        feasible=True,
        money_mode="PHYSICAL_ONLY",
        physical_rank_key=(0, 40.0, 101.0, 0.0),
        delta_kwh=-1.0,
        extras={"movement_total_f": 1.0},
    )
    assert physical_better(better_peak, base, max_kwh_penalty=100.0)


def test_six_zone_staging_on_minimal_dualsp():
    # Minimal fragment mimicking champion thermostat wiring
    from eplus_native.idf_inspect import NINE_ZONES

    shared = "Lakeside_AllZones_Tstat Dual SP Control"
    parts = [
        "ThermostatSetpoint:DualSetpoint,\n"
        f"  {shared}, !- Name\n"
        "  SCH_HtgSP, !- Heating\n"
        "  SCH_ClgSP; !- Cooling\n"
    ]
    for z in NINE_ZONES:
        parts.append(
            "ZoneControl:Thermostat,\n"
            f"  {z} Thermostat, !- Name\n"
            f"  {z}, !- Zone\n"
            "  SCH_AlwaysOn, !- Control Type Schedule\n"
            "  ThermostatSetpoint:DualSetpoint, !- Control Object Type\n"
            f"  {shared};\n"
        )
    text = "\n".join(parts)
    staged, prov = stage_six_zone_heating_actuators(text)
    assert len(prov["schedules"]) == 6
    v = verify_six_zone_staging(staged)
    assert v["ok"], v["issues"]
    for k in ACTION_KEYS:
        assert dsm_htg_schedule_name(k) in staged


def test_env_six_handles_order():
    env = object.__new__(LakesideW2AEnv)
    env.env_config = {"six_zone_actuators": True, "htg_schedule": "SCH_HtgSP"}
    env.six_zone = True
    acts = LakesideW2AEnv.get_actuators(env)
    keys = list(acts.keys())
    assert keys == [f"htg_sp_c_{k}" for k in ACTION_KEYS]
    assert LakesideW2AEnv.get_action_space(env).shape == (6,)
