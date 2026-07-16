"""ECON-3 / MECH-OAT-1 / ECON-6 / CHW-NOLOAD-1 weather & load rules."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.load_satisfaction import AHU_SAT_COL, ZONE_SAT_COL, aggregate_load_satisfaction
from app.rules import RULES_BY_ID, run_rule
from app.rules.economizer_weather import (
    econ3_compute,
    econ6_compute,
    econ7_compute,
    free_cool_opportunity_mask,
    mech_oat1_compute,
)
from app.rules.runner import run_batch
from app.weather_psychrometrics import dewpoint_f_from_db_rh


def _idx(n: int = 12, freq: str = "5min") -> pd.DatetimeIndex:
    return pd.date_range("2024-06-01", periods=n, freq=freq, tz="UTC")


def test_econ3_fault_when_damper_not_integrated():
    idx = _idx(12)
    df = pd.DataFrame(
        {
            "outside-air-damper": [40.0] * 12,
            "cooling-valve": [50.0] * 12,
            "web-outside-air-temp": [65.0] * 12,
            "web-outside-air-dewpoint": [50.0] * 12,
            "fan-status": [1] * 12,
        },
        index=idx,
    )
    mask = econ3_compute(df, {"confirm_min": 0}, 300.0)
    assert bool(mask.all())


def test_econ3_pass_when_damper_integrated():
    idx = _idx(12)
    df = pd.DataFrame(
        {
            "outside-air-damper": [95.0] * 12,
            "cooling-valve": [50.0] * 12,
            "web-outside-air-temp": [65.0] * 12,
            "web-outside-air-dewpoint": [50.0] * 12,
            "fan-status": [1] * 12,
        },
        index=idx,
    )
    mask = econ3_compute(df, {}, 300.0)
    assert not bool(mask.any())


def test_econ3_boundaries_and_dp_from_rh():
    idx = _idx(4)
    # 60 inclusive / 72 exclusive
    db = pd.Series([59.9, 60.0, 71.9, 72.0], index=idx)
    dp = pd.Series([50.0, 50.0, 50.0, 50.0], index=idx)
    opp = free_cool_opportunity_mask(db, dp)
    assert list(opp.astype(int)) == [0, 1, 1, 0]

    # RH→dewpoint path
    rh = pd.Series([40.0] * 4, index=idx)
    derived = dewpoint_f_from_db_rh(pd.Series([65.0] * 4, index=idx), rh)
    df = pd.DataFrame(
        {
            "outside-air-damper": [20.0] * 4,
            "cooling-valve": [40.0] * 4,
            "web-outside-air-temp": [65.0] * 4,
            "web-outside-air-humidity": [40.0] * 4,
            "fan-status": [1] * 4,
        },
        index=idx,
    )
    mask = econ3_compute(df, {}, 300.0)
    assert df.attrs.get("econ3_weather_source") == "web_db_rh_magnus"
    assert bool(mask.any()) or float(derived.iloc[0]) >= 60.0


def test_econ3_no_bas_fallback_skips():
    idx = _idx(8)
    df = pd.DataFrame(
        {
            "outside-air-damper": [20.0] * 8,
            "cooling-valve": [40.0] * 8,
            "outside-air-temp": [65.0] * 8,  # BAS only — not enough
            "fan-status": [1] * 8,
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "AHU_1"
    df.attrs["equipment_type"] = "AHU"
    res = run_rule("ECON-3", df, {"confirm_min": 0}, 300.0, require_operational_gates=False)
    assert res.status == "SKIPPED_MISSING_ROLES"


def test_mech_oat1_fault_chiller_below_60():
    idx = _idx(12)
    df = pd.DataFrame(
        {
            "web-outside-air-temp": [55.0] * 12,
            "chiller-status": [1] * 12,
            "cooling-valve": [0.0] * 12,  # valve alone must not matter
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "CHILLER_1"
    df.attrs["equipment_type"] = "CHILLER"
    mask = mech_oat1_compute(df, {}, 300.0)
    assert bool(mask.all())


def test_mech_oat1_valve_alone_does_not_fault():
    idx = _idx(12)
    df = pd.DataFrame(
        {
            "web-outside-air-temp": [55.0] * 12,
            "cooling-valve": [80.0] * 12,
        },
        index=idx,
    )
    df.attrs["equipment_type"] = "AHU"
    mask = mech_oat1_compute(df, {}, 300.0)
    assert not bool(mask.any())


def test_mech_oat1_boundary_60_passes():
    idx = _idx(8)
    df = pd.DataFrame(
        {"web-outside-air-temp": [60.0] * 8, "compressor-status": [1] * 8},
        index=idx,
    )
    df.attrs["equipment_type"] = "AHU"
    mask = mech_oat1_compute(df, {}, 300.0)
    assert not bool(mask.any())


def test_econ6_winter_damper():
    idx = _idx(10)
    open_d = pd.DataFrame(
        {"web-outside-air-temp": [20.0] * 10, "outside-air-damper": [40.0] * 10, "fan-status": [1] * 10},
        index=idx,
    )
    min_d = pd.DataFrame(
        {"web-outside-air-temp": [20.0] * 10, "outside-air-damper": [15.0] * 10, "fan-status": [1] * 10},
        index=idx,
    )
    assert bool(econ6_compute(open_d, {}, 300.0).any())
    assert not bool(econ6_compute(min_d, {}, 300.0).any())
    # Warm weather
    warm = pd.DataFrame(
        {"web-outside-air-temp": [40.0] * 10, "outside-air-damper": [40.0] * 10},
        index=idx,
    )
    assert not bool(econ6_compute(warm, {}, 300.0).any())


def test_chw_noload_zone_path_and_confirm():
    idx = _idx(8, freq="5min")  # 35 minutes span
    # Always on / satisfied
    chiller = pd.DataFrame(
        {
            "chiller-status": [1] * 8,
            ZONE_SAT_COL: [True] * 8,
        },
        index=idx,
    )
    chiller.attrs["equipment_id"] = "CHILLER_1"
    chiller.attrs["equipment_type"] = "CHILLER"
    # 7 intervals * 5 min = 35 min; confirm 30 → FAULT
    res = run_rule(
        "CHW-NOLOAD-1",
        chiller,
        {"confirm_min": 30},
        poll_seconds=300.0,
        require_operational_gates=False,
    )
    assert res.status == "FAULT"

    short = chiller.iloc[:5].copy()  # 20 min span
    short.attrs.update(chiller.attrs)
    res2 = run_rule(
        "CHW-NOLOAD-1",
        short,
        {"confirm_min": 30},
        poll_seconds=300.0,
        require_operational_gates=False,
    )
    assert res2.status == "PASS"


def test_chw_noload_skip_missing_load_evidence():
    idx = _idx(8)
    chiller = pd.DataFrame({"chiller-status": [1] * 8}, index=idx)
    chiller.attrs["equipment_id"] = "CHILLER_1"
    chiller.attrs["equipment_type"] = "CHILLER"
    res = run_rule("CHW-NOLOAD-1", chiller, {"confirm_min": 0}, 300.0, require_operational_gates=False)
    assert res.status == "SKIPPED_MISSING_ROLES"


def test_aggregate_load_satisfaction_injection():
    idx = _idx(6)
    frames = {
        "VAV_1": pd.DataFrame({"zone-air-temp": [72.0] * 6}, index=idx),
        "AHU_1": pd.DataFrame(
            {"discharge-air-temp": [55.0] * 6, "discharge-air-temp-sp": [55.0] * 6},
            index=idx,
        ),
        "CHILLER_1": pd.DataFrame({"chiller-status": [1] * 6}, index=idx),
    }
    for eq, df in frames.items():
        df.attrs["equipment_id"] = eq
        if eq.startswith("VAV"):
            df.attrs["equipment_type"] = "VAV"
        elif eq.startswith("AHU"):
            df.attrs["equipment_type"] = "AHU"
        else:
            df.attrs["equipment_type"] = "CHILLER"
    aggregate_load_satisfaction(frames, {})
    assert ZONE_SAT_COL in frames["CHILLER_1"].columns
    assert AHU_SAT_COL in frames["CHILLER_1"].columns
    assert bool(frames["CHILLER_1"][ZONE_SAT_COL].all())
    assert bool(frames["CHILLER_1"][AHU_SAT_COL].all())


def _econ7_df(*, damper: float, valve: float, db: float, dp: float, n: int = 12) -> pd.DataFrame:
    idx = _idx(n)
    df = pd.DataFrame(
        {
            "outside-air-damper": [damper] * n,
            "cooling-valve": [valve] * n,
            "web-outside-air-temp": [db] * n,
            "web-outside-air-dewpoint": [dp] * n,
            "fan-status": [1] * n,
        },
        index=idx,
    )
    df.attrs["equipment_id"] = "AHU_1"
    df.attrs["equipment_type"] = "AHU"
    return df


def test_econ7_fault_cooling_demand_damper_closed():
    # Econ-OK: DP 45 < 60, DB 55 < 72 (above 35 floor); valve open, damper 15% — fault.
    df = _econ7_df(damper=15.0, valve=60.0, db=55.0, dp=45.0)
    assert bool(econ7_compute(df, {}, 300.0).all())


def test_econ7_pass_when_economizing_or_no_demand():
    # Damper economizing (80% ≥ 50%) — pass.
    assert not bool(econ7_compute(_econ7_df(damper=80.0, valve=60.0, db=55.0, dp=45.0), {}, 300.0).any())
    # Valve closed, no mech proof — no cooling demand, pass.
    assert not bool(econ7_compute(_econ7_df(damper=15.0, valve=0.0, db=55.0, dp=45.0), {}, 300.0).any())


def test_econ7_pass_when_weather_unfavorable():
    # Dew point too humid (65 ≥ 60) — economizing not OK.
    assert not bool(econ7_compute(_econ7_df(damper=15.0, valve=60.0, db=68.0, dp=65.0), {}, 300.0).any())
    # Dry bulb too warm (75 ≥ 72).
    assert not bool(econ7_compute(_econ7_df(damper=15.0, valve=60.0, db=75.0, dp=50.0), {}, 300.0).any())
    # Below freeze-guard floor (30 < 35).
    assert not bool(econ7_compute(_econ7_df(damper=15.0, valve=60.0, db=30.0, dp=20.0), {}, 300.0).any())


def test_econ7_param_sensitivity():
    # Damper at 55%: default threshold 0.50 → pass; stricter 0.70 → fault.
    df = _econ7_df(damper=55.0, valve=60.0, db=55.0, dp=45.0)
    assert not bool(econ7_compute(df, {}, 300.0).any())
    assert bool(econ7_compute(df, {"econ7_damper_min": 0.70}, 300.0).all())
    # DP at 58: default dp_max 60 → fault; tighter 55 → pass.
    humid = _econ7_df(damper=15.0, valve=60.0, db=55.0, dp=58.0)
    assert bool(econ7_compute(humid, {}, 300.0).all())
    assert not bool(econ7_compute(humid, {"econ7_dp_max": 55.0}, 300.0).any())


def test_econ7_dewpoint_from_web_rh():
    idx = _idx(8)
    df = pd.DataFrame(
        {
            "outside-air-damper": [15.0] * 8,
            "cooling-valve": [60.0] * 8,
            "web-outside-air-temp": [55.0] * 8,
            "web-outside-air-humidity": [40.0] * 8,  # dry — DP well under 60
            "fan-status": [1] * 8,
        },
        index=idx,
    )
    df.attrs["equipment_type"] = "AHU"
    mask = econ7_compute(df, {}, 300.0)
    assert df.attrs.get("econ7_weather_source") == "web_db_rh_magnus"
    assert bool(mask.all())


def test_econ7_run_rule_fault_and_skip():
    df = _econ7_df(damper=15.0, valve=60.0, db=55.0, dp=45.0)
    res = run_rule("ECON-7", df, {"confirm_min": 0}, 300.0, require_operational_gates=False)
    assert res.status == "FAULT"

    # No web weather → SKIPPED_MISSING_ROLES (BAS OAT is not a substitute).
    idx = _idx(8)
    bas_only = pd.DataFrame(
        {
            "outside-air-damper": [15.0] * 8,
            "cooling-valve": [60.0] * 8,
            "outside-air-temp": [55.0] * 8,
            "fan-status": [1] * 8,
        },
        index=idx,
    )
    bas_only.attrs["equipment_id"] = "AHU_1"
    bas_only.attrs["equipment_type"] = "AHU"
    res2 = run_rule("ECON-7", bas_only, {"confirm_min": 0}, 300.0, require_operational_gates=False)
    assert res2.status == "SKIPPED_MISSING_ROLES"

    # No cooling demand signal at all → SKIPPED_MISSING_ROLES.
    no_demand = pd.DataFrame(
        {
            "outside-air-damper": [15.0] * 8,
            "web-outside-air-temp": [55.0] * 8,
            "web-outside-air-dewpoint": [45.0] * 8,
            "fan-status": [1] * 8,
        },
        index=idx,
    )
    no_demand.attrs["equipment_id"] = "AHU_1"
    no_demand.attrs["equipment_type"] = "AHU"
    res3 = run_rule("ECON-7", no_demand, {"confirm_min": 0}, 300.0, require_operational_gates=False)
    assert res3.status == "SKIPPED_MISSING_ROLES"


def test_new_rules_registered():
    for rid in ("ECON-3", "ECON-6", "ECON-7", "MECH-OAT-1", "CHW-NOLOAD-1"):
        assert rid in RULES_BY_ID
