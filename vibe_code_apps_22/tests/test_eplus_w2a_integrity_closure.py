"""Integrity-closure tests: live knobs, uniqueness, improvement gate, rolling origin."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from eplus_native.w2a_plant_knobs import (
    W2APlantKnobs,
    apply_w2a_plant_knobs,
    detect_duplicate_models,
    refuse_dead_knobs,
)
from eplus_validation_contract import (
    reserved_final_winter_audit_mask,
    rolling_origin_selection_mask,
    score_rolling_origin_selection,
)

_ROOT = Path(__file__).resolve().parents[1]


def _minimal_expanded_idf() -> str:
    return """\
Coil:Heating:WaterToAirHeatPump:EquationFit,
  ZoneA WAHP Heating Coil, !- Name
  ,                        !- Availability Schedule Name
  Win,                     !- Water Inlet Node Name
  Wout,                    !- Water Outlet Node Name
  Ain,                     !- Air Inlet Node Name
  Aout,                    !- Air Outlet Node Name
  Autosize,                !- Rated Air Flow Rate {m3/s}
  Autosize,                !- Rated Water Flow Rate {m3/s}
  autosize,                !- Rated Heating Capacity {W}
  4.2,                     !- Rated Heating Coefficient of Performance
  20.0,                    !- Rated Entering Water Temperature
  20.0,                    !- Rated Entering Air Dry-Bulb Temperature
  1.0,                     !- Ratio of Rated Heating Capacity to Rated Cooling Capacity
  CapCurve,                !- Heating Capacity Curve Name
  PowCurve,                !- Heating Power Consumption Curve Name
  PLFCurve;                !- Heating Part Load Fraction Correlation Curve Name

Fan:OnOff,
  ZoneA WAHP Supply Fan,   !- Name
  AlwaysOn,                !- Availability Schedule Name
  0.7,                     !- Fan Efficiency
  75,                      !- Pressure Rise {Pa}
  autosize,                !- Maximum Flow Rate {m3/s}
  0.9,                     !- Motor Efficiency
  1,                       !- Motor in Airstream Fraction
  Ain,                     !- Air Inlet Node Name
  Aout;                    !- Air Outlet Node Name

Pump:ConstantSpeed,
  Only Water Loop Mixed Supply Pump, !- Name
  Inlet,                   !- Inlet Node Name
  Outlet,                  !- Outlet Node Name
  autosize,                !- Rated Volumetric Flow Rate {m3/s}
  179352,                  !- Rated Pump Head {Pa}
  autosize,                !- Rated Power Consumption {W}
  0.9,                     !- Motor Efficiency
  0,                       !- Fraction of Motor Inefficiencies to Fluid Stream
  Intermittent,            !- Pump Control Type
  ;                        !- End

Schedule:Compact,
  HVACTemplate-Always 34,  !- Name
  Any Number,              !- Schedule Type Limits Name
  Through: 12/31,          !- Field 1
  For: AllDays,            !- Field 2
  Until: 24:00,            !- Field 3
  34,                      !- Field 4
  ;

Schedule:Compact,
  SCH_OA,                  !- Name
  Fraction,                !- Schedule Type Limits Name
  Through: 12/31,          !- Field 1
  For: Weekdays,           !- Field 2
  Until: 07:30,            !- Field 3
  0.0,                     !- Field 4
  Until: 13:30,            !- Field 5
  1.0,                     !- Field 6
  Until: 24:00,            !- Field 7
  0.0,                     !- Field 8
  ;

Schedule:Compact,
  SCH_HtgSP,               !- Name
  Temperature,             !- Schedule Type Limits Name
  Through: 12/31,          !- Field 1
  For: Weekdays,           !- Field 2
  Until: 06:00,            !- Field 3
  18.33,                   !- Field 4
  Until: 07:30,            !- Field 5
  21.11,                   !- Field 6
  Until: 24:00,            !- Field 7
  18.33,                   !- Field 8
  ;
"""


def test_refuse_dead_knobs():
    with pytest.raises(ValueError, match="dead"):
        refuse_dead_knobs({"heating_capacity_mmbtu_h": 2.7})


def test_knob_mutator_changes_sha_and_ledger():
    base = _minimal_expanded_idf()
    a = apply_w2a_plant_knobs(base, W2APlantKnobs(htg_coil_capacity_mult=1.0))
    b = apply_w2a_plant_knobs(base, W2APlantKnobs(htg_coil_capacity_mult=1.25, fan_delta_p_mult=1.5))
    assert a["n_fields_changed"] > 0
    assert b["n_fields_changed"] > 0
    assert a["expanded_idf_sha256"] != b["expanded_idf_sha256"]
    types = {f["object_type"] for f in b["fields_changed"]}
    assert "Coil:Heating:WaterToAirHeatPump:EquationFit" in types
    assert "Fan:OnOff" in types


def test_duplicate_knob_same_sha_fails_campaign():
    base = _minimal_expanded_idf()
    a = apply_w2a_plant_knobs(base, W2APlantKnobs(htg_coil_capacity_mult=1.1))
    # Same SHA, different knob dict → fail closed
    trials = [
        {
            "trial_id": "T0",
            "knobs": {"htg_coil_capacity_mult": 1.1},
            "expanded_idf_sha256": a["expanded_idf_sha256"],
            "fields_changed": a["fields_changed"],
        },
        {
            "trial_id": "T1",
            "knobs": {"htg_coil_capacity_mult": 1.2},  # claimed different
            "expanded_idf_sha256": a["expanded_idf_sha256"],
            "fields_changed": a["fields_changed"],
        },
    ]
    uniq = detect_duplicate_models(trials)
    assert uniq["fail_closed"] is True
    assert uniq["duplicate_collisions"]


def test_improvement_to_observed_rejects_overshoot():
    from eplus_schedule_sanity_campaign import gate_structural

    baseline = {
        "metrics": {
            "structural": {
                "winter_weekend_kw_mod_mean": 12.4,
                "winter_weekend_kw_meas_mean": 64.0,
                "winter_overnight_kw_mod_mean": 12.4,
                "winter_overnight_kw_meas_mean": 74.0,
            }
        }
    }
    repaired = {
        "metrics": {
            "structural": {
                "winter_weekend_kw_mod_mean": 167.5,
                "winter_weekend_kw_meas_mean": 64.0,
                "winter_overnight_kw_mod_mean": 190.0,
                "winter_overnight_kw_meas_mean": 74.0,
            }
        }
    }
    gate = gate_structural(baseline, repaired)
    assert gate["hourly_structure_improved"] is False
    assert gate["weekend"]["overshoot_fail"] is True
    assert gate["gate_kind"] == "improvement_to_observed"


def test_rolling_origin_excludes_reserved_february():
    idx = pd.date_range("2025-11-01", periods=120 * 24, freq="h", tz="UTC")
    df = pd.DataFrame(
        {
            "interval_end_utc": idx,
            "observed_kw": 100.0,
            "simulated_kw": 110.0,
        }
    )
    # Nov 15 fold score window should not touch Feb
    mask = rolling_origin_selection_mask(df, origin_local="2025-11-15", horizon_days=10)
    feb = reserved_final_winter_audit_mask(df)
    assert not bool((mask & feb).any())
    # Selection score path also guards
    out = score_rolling_origin_selection(df)
    assert out["excludes_reserved_february"] is True
    assert out["january_holdout_consumed"] is True
    # Feb mask itself is non-empty in this synthetic span? 120 days from Nov 1 covers Feb
    assert bool(feb.any())
