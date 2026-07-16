"""Tests for AMY EPW builder, RunPeriod patch, and calibration scorecard math."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from calibrate import compare_signature_maps, nmbe_cvrmse
from idf_patches import apply_hourly_outputs, apply_run_period
from weather_epw import build_amy_epw


def test_nmbe_cvrmse_perfect_match():
    obs = [100.0, 200.0, 300.0]
    sim = [100.0, 200.0, 300.0]
    s = nmbe_cvrmse(obs, sim)
    assert s["n"] == 3
    assert s["nmbe_pct"] == pytest.approx(0.0, abs=1e-6)
    assert s["cvrmse_pct"] == pytest.approx(0.0, abs=1e-6)


def test_nmbe_cvrmse_known_bias():
    obs = [100.0, 100.0, 100.0, 100.0]
    sim = [90.0, 90.0, 90.0, 90.0]  # 10% low → NMBE = +10%
    s = nmbe_cvrmse(obs, sim)
    assert s["nmbe_pct"] == pytest.approx(10.0, abs=0.01)


def test_compare_signature_maps():
    obs = {50: 0.8, 55: 0.7, 60: 0.6}
    sim = {50: 0.8, 55: 0.7, 60: 0.6, 65: 0.5}
    cmp_ = compare_signature_maps(obs, sim)
    assert cmp_["bins_compared"] == 3
    assert cmp_["pass_fail"] == "pass"


def test_build_amy_epw(tmp_path: Path):
    idx = pd.date_range("2024-06-01", periods=48, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "web-outside-air-temp": [70.0 + (i % 10) for i in range(48)],
            "web-outside-air-humidity": [50.0] * 48,
            "web-outside-air-dewpoint": [50.0] * 48,
            "wind_speed_mph": [5.0] * 48,
            "shortwave_radiation_wm2": [200.0] * 48,
            "direct_normal_irradiance_wm2": [150.0] * 48,
            "diffuse_radiation_wm2": [50.0] * 48,
        },
        index=idx,
    )
    out = tmp_path / "amy.epw"
    meta = build_amy_epw(df, out, lat=42.33, lon=-83.05, location_name="Detroit_AMY")
    assert out.is_file()
    assert meta["rows"] == 48
    text = out.read_text(encoding="utf-8")
    lines = text.strip().splitlines()
    assert lines[0].startswith("LOCATION,")
    assert "DATA PERIODS" in lines[7]
    assert len(lines) == 8 + 48
    # EPW data row: 6 date/source fields + 29 weather fields = 35
    data = lines[8].split(",")
    assert len(data) == 35
    assert data[0] == "2024"
    assert data[1] == "6"
    assert data[3] == "1"  # EPW hour 1 for 00:00


def test_run_period_and_hourly_outputs(tmp_path: Path):
    proto = ROOT / "examples" / "prototypes" / "5ZoneAirCooled.idf"
    assert proto.is_file()
    out1 = tmp_path / "rp.idf"
    meta = apply_run_period(
        proto,
        out1,
        begin="2024-06-01T00:00:00+00:00",
        end="2024-06-15T23:00:00+00:00",
    )
    assert meta["begin"] == "2024-06-01"
    assert meta["end"] == "2024-06-15"
    text = out1.read_text(encoding="utf-8")
    assert "RunPeriod" in text
    # Begin month 6 and begin day 1 should appear near RunPeriod
    assert ",                       !- Begin Month" in text or "6," in text
    assert "6," in text and "15," in text

    out2 = tmp_path / "out.idf"
    meta2 = apply_hourly_outputs(out1, out2)
    text2 = out2.read_text(encoding="utf-8")
    assert "Fan Electricity Rate" in text2
    # Second apply is idempotent
    out3 = tmp_path / "out2.idf"
    meta3 = apply_hourly_outputs(out2, out3)
    assert meta3["added"] == []
