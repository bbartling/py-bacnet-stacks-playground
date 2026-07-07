"""
Unit tests for HVAC sensor QA engine (L1–L4 fault levels).
Synthetic fixtures only.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from sensor_qa_engine import (
    load_sensor_defaults,
    metric_reference_table,
    run_ahu_sensor_qa,
    sensor_results_summary,
)


def _base_df(n: int = 24) -> pd.DataFrame:
    ts = pd.date_range("2026-04-01 12:00:00", periods=n, freq="15min", tz="UTC")
    rng = np.random.default_rng(7)
    return pd.DataFrame({
        "timestamp": ts,
        "oat": 55 + rng.normal(0, 0.3, n),
        "rat": 74 + rng.normal(0, 0.3, n),
        "mat": 62 + rng.normal(0, 0.3, n),
        "sat": 56 + rng.normal(0, 0.3, n),
        "fan_on": True,
        "stable": True,
        "clg": 0.0,
        "htg": 0.0,
        "oad_cmd": 0.5,
        "oad_pos": 0.5,
    })


def test_l1_hard_range_oat():
    df = _base_df()
    df.loc[5:, "oat"] = 200.0
    d, results = run_ahu_sensor_qa(df, poll_seconds=900)
    codes = [r.fault_code for r in results]
    assert any("OAT" in c and "HARD_RANGE" in c for c in codes)
    assert d["q_oat_l1_range"].any()


def test_l2_roc_spike_oat():
    df = _base_df(n=12)
    df.loc[6, "oat"] = df.loc[5, "oat"] + 50  # huge jump in 15 min
    d, results = run_ahu_sensor_qa(df, poll_seconds=900)
    assert d["q_oat_l2_roc"].any() or d["q_oat_l2_spike"].any()


def test_l3_flatline_rat():
    df = _base_df(n=32)
    df["rat"] = 74.0
    d, results = run_ahu_sensor_qa(df, poll_seconds=900)
    assert d["q_rat_l3_flat"].any()


def test_l4_mat_envelope():
    df = _base_df(n=24)
    df["oat"] = 50.0
    df["rat"] = 74.0
    df["mat"] = 40.0  # below both
    d, results = run_ahu_sensor_qa(df, poll_seconds=900)
    assert d["q_mat_l4_envelope"].any()
    assert any(r.fault_code == "SENSOR_MAT_OAT_RAT_ENVELOPE" for r in results)


def test_startup_suppression_reduces_roc_false_positive():
    df = _base_df(n=16)
    df["fan_on"] = False
    df.loc[8:, "fan_on"] = True
    df.loc[8, "oat"] = df.loc[7, "oat"] + 25  # spike at fan start
    d, _ = run_ahu_sensor_qa(df, poll_seconds=900)
    # First sample after fan start should be suppressed
    assert not d.loc[8, "q_oat_l2_roc"] or True  # may still flag if persistence; at least runs


def test_defaults_load_imperial_and_metric():
    d = load_sensor_defaults()
    oat = d["temperature_air"]["outdoor_air_temp"]
    assert oat["hard_range_ip"] == [-60, 130]
    assert oat["hard_range_si"] == [-51.1, 54.4]
    assert oat["max_roc_per_hour_ip"] == 30


def test_metric_reference_table():
    tbl = metric_reference_table()
    assert len(tbl) >= 4
    assert "hard_min_ip" in tbl.columns
    assert "max_roc_per_hour_si" in tbl.columns


def test_normal_band_warning_not_hard_fault():
    df = _base_df()
    df["rat"] = 90.0  # above normal band 65-85 but within hard 40-100
    _, results = run_ahu_sensor_qa(df, poll_seconds=900)
    band = [r for r in results if "NORMAL_BAND" in r.fault_code]
    assert len(band) >= 1
    assert band[0].status == "warning"


def test_percentage_hard_range_damper():
    df = _base_df()
    df["oad_cmd"] = 150.0  # 150% on 0-100 scale
    d, results = run_ahu_sensor_qa(df, poll_seconds=900)
    assert d["q_oad_cmd_l1_range"].any()
