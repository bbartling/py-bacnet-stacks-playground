import pandas as pd
import pytest

from vibe23.calibration import (
    align_series,
    calibration_claim_status,
    calibration_scorecard,
    end_use_check,
    peak_check,
    zone_temperature_check,
)


def _series(values, start="2019-01-01", freq="1h"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq=freq))


def test_alignment_never_interpolates_missing_data():
    measured = _series([1.0, 1.0, 1.0])
    simulated = pd.Series(
        [1.0, 1.0], index=pd.to_datetime(["2019-01-01 00:00", "2019-01-01 02:00"])
    )
    aligned = align_series(measured, simulated, interval="1h", aggregation="mean")
    assert aligned.paired_rows == 2
    assert list(aligned.paired.index.hour) == [0, 2]


def test_alignment_rejects_naive_aware_mix():
    measured = _series([1.0, 1.0])
    simulated = pd.Series([1.0, 1.0], index=pd.date_range("2019-01-01", periods=2, freq="1h", tz="UTC"))
    with pytest.raises(ValueError, match="both be naive"):
        align_series(measured, simulated, interval="1h", aggregation="mean")


def test_calibration_status_requires_full_year_and_provenance():
    monthly = align_series(_series([100.0] * 12, freq="MS"), _series([100.0] * 12, freq="MS"), interval="MS", aggregation="sum")
    scorecard = calibration_scorecard(monthly_alignment=monthly, hourly_alignment=None, provenance_complete=True)
    assert scorecard["claim_status"] == "MONTHLY_CALIBRATED"
    assert calibration_claim_status(monthly=None, hourly=None, provenance_complete=False) == "CALIBRATION_BOOTSTRAP"


def test_peak_end_use_and_zone_checks_are_separate():
    measured = _series([10.0, 20.0, 10.0])
    simulated = _series([10.0, 18.0, 10.0])
    assert peak_check(measured, simulated)["passes"] is True
    assert end_use_check({"fans": measured}, {"fans": simulated})["checks"]["fans"]["available"] is True
    zones = zone_temperature_check({"core": _series([22.0, 22.5, 23.0])}, {"core": _series([22.2, 22.6, 23.1])})
    assert zones["passes"] is True


def test_hourly_gl14_does_not_bypass_physics_gates():
    monthly = align_series(
        _series([100.0] * 12, freq="MS"),
        _series([100.0] * 12, freq="MS"),
        interval="MS",
        aggregation="sum",
    )
    hourly = align_series(_series([100.0] * 24), _series([100.0] * 24), interval="1h", aggregation="mean")
    pending = calibration_scorecard(
        monthly_alignment=monthly,
        hourly_alignment=hourly,
        provenance_complete=True,
    )
    assert pending["claim_status"] == "MONTHLY_CALIBRATED"
    assert pending["physics_gates_passed"] is False

    passed = {"available": True, "passes": True}
    complete = calibration_scorecard(
        monthly_alignment=monthly,
        hourly_alignment=hourly,
        provenance_complete=True,
        peak=passed,
        end_uses=passed,
        zones=passed,
        controls=passed,
        transients=passed,
    )
    assert complete["claim_status"] == "HOURLY_CALIBRATED"


def test_peak_check_rejects_zero_measured_peak():
    with pytest.raises(ValueError, match="positive"):
        peak_check(_series([0.0, 0.0]), _series([0.0, 0.0]))
