"""Characterization tests: assert known champion defects as facts (pass while open)."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from eplus_native.extract import ZONE_TEMP_COLS
from eplus_native.idf_inspect import (
    BAS_SIX,
    NINE_ZONES,
    PROGRAM_ZONES,
    champion_idf_candidates,
    inspect_idf,
)

_ROOT = Path(__file__).resolve().parents[1]
_LEDGER = _ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-eplus-defect-ledger.json"


@pytest.fixture(scope="module")
def champion_facts():
    cands = champion_idf_candidates()
    assert cands, "no champion/pinned IDF found"
    return inspect_idf(cands[0])


def test_defect_ledger_exists_and_open_ids():
    data = json.loads(_LEDGER.read_text(encoding="utf-8"))
    ids = {d["id"] for d in data["defects"]}
    required = {
        "DEF-SCH-HVAC-OFF",
        "DEF-IDEAL-NOLIMIT",
        "DEF-WEEKEND-KW-COLLAPSE",
        "DEF-ZONE-AGG-MISSING",
        "DEF-STEP0-LAG",
        "DEF-TORCH-FAKE-UNROLL",
        "DEF-RESID-HOD-UTC",
        "DEF-EPW-CALENDAR",
        "DEF-OA-UNSCHEDULED",
        "DEF-GROUND-TEMP-SILENT",
    }
    assert required <= ids
    assert data["dsm_status"] == "NO-GO"
    assert data["champion_trial_id"] == "B_equip_mult_mid"


def test_champion_has_nine_zones(champion_facts):
    assert set(NINE_ZONES) <= set(champion_facts.zones)


def test_sch_hvac_zeros_overnight_and_weekends(champion_facts):
    sch = champion_facts.sch_hvac
    assert sch is not None
    assert sch.weekend_holiday_fraction_is_zero()
    assert sch.overnight_weekday_before_0530_is_zero()


def test_all_ideal_loads_bound_to_sch_hvac_and_nolimit(champion_facts):
    assert len(champion_facts.ideal_loads) >= 9
    for il in champion_facts.ideal_loads:
        assert il.availability == "SCH_HVAC"
        assert il.heating_availability == "SCH_HVAC"
        assert il.cooling_availability == "SCH_HVAC"
        assert il.heating_limit.lower() == "nolimit"
        assert il.cooling_limit.lower() == "nolimit"


def test_extractor_omits_program_zone_aggregation():
    # DEF-ZONE-AGG-MISSING: only BAS six keys in ZONE_TEMP_COLS
    assert set(ZONE_TEMP_COLS.keys()) == set(BAS_SIX)
    for z in PROGRAM_ZONES:
        assert z not in ZONE_TEMP_COLS


def test_no_ground_temp_and_oa_unscheduled(champion_facts):
    assert not champion_facts.has_ground_temp_building_surface
    assert champion_facts.outdoor_air_specs_total >= 9
    assert champion_facts.outdoor_air_specs_with_schedule == 0


def test_weekend_kw_collapse_fact_from_site_aligned():
    site = os.environ.get("LAKESIDE_SITE_ROOT")
    if not site:
        pytest.skip("LAKESIDE_SITE_ROOT not set")
    csv = (
        Path(site)
        / "eplus"
        / "campaigns"
        / "bounded_exec_20260807"
        / "aligned_hourly.csv"
    )
    if not csv.is_file():
        pytest.skip("aligned_hourly.csv missing")
    import pandas as pd

    df = pd.read_csv(csv, parse_dates=["timestamp_utc"])
    ts = pd.to_datetime(df["timestamp_utc"], utc=True).dt.tz_convert("America/Chicago")
    w = df[ts.dt.month.isin([12, 1, 2]) & (ts.dt.dayofweek >= 5)]
    mean_mod = float(w["kw_mod"].mean())
    assert 11.0 < mean_mod < 14.0  # ~12.41 kW collapse


def test_residual_hod_uses_utc_hour():
    src = (_ROOT / "ml" / "eplus_residual_decomposition.py").read_text(encoding="utf-8")
    assert 'df["hod"] = df[ts_col].dt.hour' in src
    assert "hour of day (UTC)" in src


def test_feature_lag_same_row_fillna():
    src = (_ROOT / "ml" / "feature_compile_heating_dsm.py").read_text(encoding="utf-8")
    assert 'fillna(out[TARGET_COL])' in src or "fillna(out[TARGET_COL])" in src


def test_torch_hourcnn_is_feature_axis_not_time_unroll():
    src = (_ROOT / "ml" / "train_heating_dsm_torch.py").read_text(encoding="utf-8")
    assert "Treat feature vector as 1-channel 'sequence' of length n_features" in src
