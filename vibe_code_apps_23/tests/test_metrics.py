import pytest

from vibe23.metrics import cvrmse, nmbe, score_calibration


def test_perfect_fit_passes_monthly():
    measured = [100.0, 120.0, 110.0, 130.0]
    simulated = measured.copy()
    score = score_calibration(measured, simulated, "monthly")
    assert score.nmbe_pct == pytest.approx(0.0)
    assert score.cvrmse_pct == pytest.approx(0.0)
    assert score.passes is True


def test_bias_sign_is_measured_minus_simulated():
    measured = [100.0, 100.0, 100.0]
    simulated = [90.0, 90.0, 90.0]
    assert nmbe(measured, simulated) > 0


def test_bad_fit_fails_monthly():
    score = score_calibration([100.0, 100.0, 100.0], [70.0, 70.0, 70.0], "monthly")
    assert cvrmse([100.0, 100.0, 100.0], [70.0, 70.0, 70.0]) > 15
    assert score.passes is False


def test_cvrmse_is_nonnegative_for_signed_series():
    value = cvrmse([-10.0, -10.0], [10.0, -30.0])
    assert value > 0.0
    assert score_calibration([-10.0, -10.0], [10.0, -30.0], "monthly").passes is False
