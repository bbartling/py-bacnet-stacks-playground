"""Tests for AMY EPW builder, RunPeriod patch, calibration scorecard math, alignment, holdout."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from wattlab.calibrate import (
    compare_signature_maps,
    detect_hour_shift,
    nmbe_cvrmse,
    resolve_calibration_status,
    split_bills_for_holdout,
)
from wattlab.config import (
    ACTUAL_YEAR_CALIBRATION,
    DEFAULT_EPW_NOTE,
    DEFAULT_MADISON_EPW,
    STATUS_CALIBRATED_NOT_VALIDATED,
    STATUS_CONCEPTUAL_ONLY,
    STATUS_FAILED_VALIDATION,
    STATUS_VALIDATED,
    SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY,
    TYPICAL_YEAR_SCREENING,
    weather_suitability,
)
from wattlab.energyplus.patches import apply_hourly_outputs, apply_run_period
from wattlab.energyplus.manifest import build_run_manifest, write_run_manifest
from wattlab.weather.epw import build_amy_epw


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
    data = lines[8].split(",")
    assert len(data) == 35
    assert data[0] == "2024"
    assert data[1] == "6"
    assert data[3] == "1"  # EPW hour 1 for 00:00


def test_build_amy_epw_leap_year_and_gap(tmp_path: Path):
    """Leap-day window + a gap should still produce a valid EPW (missing-value codes OK)."""
    idx = pd.date_range("2024-02-28", periods=72, freq="1h", tz="UTC")  # includes Feb 29
    temps = [40.0 + (i % 12) for i in range(72)]
    # Punch a 6-hour gap mid-series
    keep = [i for i in range(72) if not (30 <= i < 36)]
    df = pd.DataFrame(
        {
            "web-outside-air-temp": [temps[i] for i in keep],
            "web-outside-air-humidity": [50.0] * len(keep),
            "web-outside-air-dewpoint": [30.0] * len(keep),
            "wind_speed_mph": [5.0] * len(keep),
            "shortwave_radiation_wm2": [100.0] * len(keep),
            "direct_normal_irradiance_wm2": [50.0] * len(keep),
            "diffuse_radiation_wm2": [50.0] * len(keep),
        },
        index=idx[keep],
    )
    out = tmp_path / "leap_gap.epw"
    meta = build_amy_epw(df, out, lat=43.07, lon=-89.40, location_name="Madison_Leap")
    assert out.is_file()
    assert meta["rows"] >= 48
    text = out.read_text(encoding="utf-8")
    assert "2024" in text
    assert "2," in text  # February


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
    assert "6," in text and "15," in text

    out2 = tmp_path / "out.idf"
    meta2 = apply_hourly_outputs(out1, out2)
    text2 = out2.read_text(encoding="utf-8")
    assert "Fan Electricity Rate" in text2
    out3 = tmp_path / "out2.idf"
    meta3 = apply_hourly_outputs(out2, out3)
    assert meta3["added"] == []


def _diurnal(n: int = 96, phase: int = 0) -> list[float]:
    """Synthetic diurnal sine wave (hours), optional phase shift in hours."""
    out = []
    for i in range(n):
        out.append(50.0 + 20.0 * math.sin(2 * math.pi * (i + phase) / 24.0))
    return out


def test_detect_hour_shift_unshifted():
    obs = _diurnal(96, 0)
    sim = _diurnal(96, 0)
    r = detect_hour_shift(obs, sim, max_lag=3)
    assert r["best_lag_hours"] == 0
    assert r["warning"] is None
    assert r["corr_at_0"] == pytest.approx(1.0, abs=1e-3)


def test_detect_hour_shift_one_hour():
    obs = _diurnal(96, 0)
    sim = _diurnal(96, 1)  # sim is 1 hour ahead of obs pattern
    r = detect_hour_shift(obs, sim, max_lag=3)
    assert r["best_lag_hours"] != 0
    assert r["warning"] is not None
    assert abs(r["best_lag_hours"]) == 1


def test_nmbe_cvrmse_degrades_under_hour_shift():
    obs = _diurnal(168, 0)
    aligned = _diurnal(168, 0)
    shifted = _diurnal(168, 1)
    good = nmbe_cvrmse(obs, aligned)
    bad = nmbe_cvrmse(obs, shifted)
    assert good["cvrmse_pct"] == pytest.approx(0.0, abs=1e-6)
    assert bad["cvrmse_pct"] > good["cvrmse_pct"]
    assert bad["cvrmse_pct"] > 5.0  # meaningful degradation on diurnal signal


def test_weather_suitability_modes():
    amy = weather_suitability(source="amy")
    assert amy["mode"] == ACTUAL_YEAR_CALIBRATION

    chicago = weather_suitability(
        epw_path=DEFAULT_MADISON_EPW,
        epw_note="Chicago O'Hare TMY3 bundled with OpenFDD WattLab.",
        city_id="chicago",
    )
    assert chicago["mode"] == TYPICAL_YEAR_SCREENING

    madison = weather_suitability(
        epw_path=DEFAULT_MADISON_EPW,
        epw_note=DEFAULT_EPW_NOTE,
        city_id="madison",
    )
    assert madison["mode"] == SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY


def test_split_bills_holdout():
    bills = [{"month": m, "kwh": 1000.0 + m * 10} for m in range(1, 13)]
    cal, val, meta = split_bills_for_holdout(bills, validation_months=3)
    assert meta["applied"] is True
    assert [b["month"] for b in val] == [10, 11, 12]
    assert len(cal) == 9

    cal2, val2, meta2 = split_bills_for_holdout(bills[:4], validation_months=2)
    assert meta2["applied"] is False
    assert val2 == []


def test_resolve_calibration_status():
    assert (
        resolve_calibration_status(
            weather_mode=SUBSTITUTE_CLIMATE_CONCEPTUAL_ONLY,
            has_bills=True,
            bills_pass_fail="pass",
            validation_applied=True,
            validation_pass_fail="pass",
        )
        == STATUS_CONCEPTUAL_ONLY
    )
    assert (
        resolve_calibration_status(
            weather_mode=ACTUAL_YEAR_CALIBRATION,
            has_bills=False,
            bills_pass_fail="bills_recommended",
            validation_applied=False,
            validation_pass_fail=None,
        )
        == STATUS_CONCEPTUAL_ONLY
    )
    assert (
        resolve_calibration_status(
            weather_mode=ACTUAL_YEAR_CALIBRATION,
            has_bills=True,
            bills_pass_fail="pass",
            validation_applied=True,
            validation_pass_fail="pass",
        )
        == STATUS_VALIDATED
    )
    assert (
        resolve_calibration_status(
            weather_mode=ACTUAL_YEAR_CALIBRATION,
            has_bills=True,
            bills_pass_fail="pass",
            validation_applied=True,
            validation_pass_fail="fail",
        )
        == STATUS_FAILED_VALIDATION
    )
    assert (
        resolve_calibration_status(
            weather_mode=ACTUAL_YEAR_CALIBRATION,
            has_bills=True,
            bills_pass_fail="pass",
            validation_applied=False,
            validation_pass_fail=None,
        )
        == STATUS_CALIBRATED_NOT_VALIDATED
    )


def test_run_manifest_write(tmp_path: Path):
    idf = tmp_path / "a.idf"
    epw = tmp_path / "a.epw"
    idf.write_text("!- idf\n", encoding="utf-8")
    epw.write_text("LOCATION,X\n", encoding="utf-8")
    run_dir = tmp_path / "run"
    m = build_run_manifest(
        run_id="test1",
        run_dir=run_dir,
        idf_path=idf,
        epw_path=epw,
        patches=[{"name": "fan_avail_continuous"}],
        weather_suitability={"mode": TYPICAL_YEAR_SCREENING, "reason": "test"},
        status="SUCCESS",
    )
    path = write_run_manifest(run_dir, m)
    assert path.is_file()
    assert m["model_sha256"]
    assert m["weather_sha256"]
    assert m["energyplus_version"]
    assert m["docker_image"]
