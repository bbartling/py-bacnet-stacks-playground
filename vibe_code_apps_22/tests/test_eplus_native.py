"""Unit tests for eplus_native fail-closed gates (no EnergyPlus binary required)."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from eplus_native.err_parse import parse_eplusout_err
from eplus_native.meters import site_electric_proxy_kw
from eplus_native.align import (
    aggregate_5min_to_15min_mean,
    aggregate_5min_to_hourly_mean,
    cvrmse_pct,
    mae_rmse_mbe,
    parse_eplus_csv_timestamp,
)
from eplus_native.validate import validate_run
from eplus_native.manifest import RunManifest
from eplus_native import EXPECTED_IDF_SHA256, EXPECTED_EPW_SHA256
from eplus_native.hashes import assert_champion_hashes


FIXTURES = Path(__file__).parent / "fixtures"


def test_err_parse_severe_counts(tmp_path: Path):
    p = tmp_path / "eplusout.err"
    p.write_text(
        "** Warning ** a\n"
        "** Severe  ** CheckWarmupConvergence\n"
        "** Severe  ** UpdateZoneSizing\n"
        "************* EnergyPlus Completed Successfully-- 1 Warning; 2 Severe Errors; Elapsed Time=00hr 00min  1.00sec\n",
        encoding="utf-8",
    )
    s = parse_eplusout_err(p)
    assert s.warnings == 1
    assert s.severes == 2
    assert s.fatals == 0
    assert s.completed_successfully


def test_validate_rejects_severe(tmp_path: Path):
    sim = tmp_path / "sim"
    sim.mkdir()
    (sim / "eplusout.err").write_text(
        "** Severe  ** x\n"
        "************* EnergyPlus Completed Successfully-- 0 Warning; 1 Severe Errors; Elapsed Time=0\n",
        encoding="utf-8",
    )
    (sim / "eplusout.csv").write_text("Date/Time\n01/01  01:00:00\n", encoding="utf-8")
    m = RunManifest(
        run_id="t",
        scenario_id="t",
        idf_path="x.idf",
        idf_sha256="A" * 64,
        epw_path="x.epw",
        epw_sha256="B" * 64,
        energyplus_exe="energyplus",
        energyplus_version="26.1",
        command=[],
        started_utc="t",
        ended_utc="t",
        runtime_sec=1.0,
        exit_code=0,
        output_dir=str(sim),
        warning_count=-1,
        severe_count=-1,
        fatal_count=-1,
        heat_cop=3.5,
        cool_cop=4.5,
    )
    m = validate_run(m, require_zero_severe=True)
    assert not m.accepted
    assert any("severe" in r for r in m.reject_reasons)


def test_proxy_kw_15min_and_hourly():
    # 1 kWh electricity in 15 min → 4 kW; with DH 3.6e6 J / COP3.5
    elec_j = 3.6e6  # 1 kWh
    dh_j = 3.6e6  # 1 kWh thermal → 1/3.5 kWh electric
    r15 = site_electric_proxy_kw(elec_j, dh_j, 0.0, interval_hours=0.25, heat_cop=3.5)
    assert math.isclose(r15["electricity_kwh"], 1.0, rel_tol=1e-9)
    assert math.isclose(r15["heating_electric_proxy_kwh"], 1.0 / 3.5, rel_tol=1e-9)
    assert math.isclose(r15["site_electric_proxy_kw"], (1.0 + 1.0 / 3.5) / 0.25, rel_tol=1e-9)
    r1 = site_electric_proxy_kw(elec_j, dh_j, 0.0, interval_hours=1.0, heat_cop=3.5)
    assert math.isclose(r1["site_electric_proxy_kw"], 1.0 + 1.0 / 3.5, rel_tol=1e-9)


def test_aggregation_5min():
    import pandas as pd

    idx = pd.date_range("2025-11-02T06:00:00Z", periods=12, freq="5min")
    df = pd.DataFrame({"timestamp_utc": idx, "kw_demand": [10.0] * 12})
    h = aggregate_5min_to_hourly_mean(df, ts_col="timestamp_utc", kw_col="kw_demand")
    q = aggregate_5min_to_15min_mean(df, ts_col="timestamp_utc", kw_col="kw_demand")
    assert len(q) >= 4
    assert math.isclose(float(q["kw_mean"].median()), 10.0)
    assert len(h) >= 1


def test_mae_rmse_cvrmse_hand():
    y = np.array([10.0, 20.0, 30.0])
    p = np.array([12.0, 18.0, 33.0])
    m = mae_rmse_mbe(y, p)
    assert m["n"] == 3
    assert math.isclose(m["mae"], (2 + 2 + 3) / 3)
    assert math.isclose(m["rmse"], math.sqrt((4 + 4 + 9) / 3))
    c = cvrmse_pct(y, p)
    assert c["denominator"] == "mean_obs"
    assert c["cvrmse_pct"] > 0


def test_eplus_24_00_parse():
    from datetime import timedelta, timezone

    dt = parse_eplus_csv_timestamp("01/05  24:00:00", year_hint=2026)
    assert dt is not None
    assert dt.day == 6
    assert dt.hour == 0
    assert dt.utcoffset() == timedelta(hours=-6)


def test_eplus_lst_fixed_cst_not_chicago_dst():
    """July would be CDT (UTC−5) under America/Chicago; E+ LST must stay CST−6."""
    from datetime import timedelta, timezone

    dt = parse_eplus_csv_timestamp("07/15  12:00:00", year_hint=2025)
    assert dt is not None
    assert dt.utcoffset() == timedelta(hours=-6)
    utc = dt.astimezone(timezone.utc)
    assert utc.hour == 18
    assert utc.day == 15


def test_stable_seed_no_python_hash():
    import importlib.util
    from pathlib import Path

    farm_path = Path(__file__).resolve().parents[1] / "scripts" / "eplus_heating_dsm_farm.py"
    spec = importlib.util.spec_from_file_location("eplus_heating_dsm_farm", farm_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    a = {"day": "2026-01-05", "strategy_id": "stagger_preheat", "arm": "dsm"}
    b = dict(a)
    s1 = mod.stable_seed_from_scenario(a)
    s2 = mod.stable_seed_from_scenario(b)
    assert s1 == s2
    assert isinstance(s1, int)
    assert mod.control_regime_for("prbs_z0") == "prbs"
    assert mod.control_regime_for("stagger_preheat") == "stagger_preheat"


def test_stale_idf_hash_rejected(tmp_path: Path):
    idf = tmp_path / "a.idf"
    epw = tmp_path / "a.epw"
    idf.write_bytes(b"not-the-champion")
    epw.write_bytes(b"not-the-epw")
    with pytest.raises(ValueError, match="EPW hash mismatch"):
        assert_champion_hashes(idf, epw)


def test_train_parquet_no_bootstrap_fallback(monkeypatch, tmp_path: Path):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ml"))
    import artifact_paths as ap

    monkeypatch.setattr(ap, "default_artifact_dir", lambda: tmp_path)
    with pytest.raises(FileNotFoundError, match="paired farm|native farm"):
        ap.train_parquet_path()
