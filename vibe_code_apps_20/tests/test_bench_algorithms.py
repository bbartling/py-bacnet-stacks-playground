"""wattlab.bench — absorbed hvac-bench proxy calculators + metrics."""

from wattlab.bench.algorithms import fan_affinity, schedule_reduction
from wattlab.bench.benchmark import calibration_metrics


def test_affinity_saves_energy():
    out = fan_affinity(
        {
            "design_kw": 10,
            "baseline_speed_fraction": 1.0,
            "proposed_speed_fraction": 0.8,
            "hours": 1000,
        }
    )
    assert round(out["savings_kwh"], 1) == 4880.0


def test_schedule():
    out = schedule_reduction(
        {
            "equipment_kw": 10,
            "baseline_annual_hours": 2000,
            "proposed_annual_hours": 1500,
        }
    )
    assert out["savings_kwh"] == 5000


def test_metrics_perfect():
    out = calibration_metrics([1, 2, 3], [1, 2, 3])
    assert out["cvrmse_percent"] == 0
    assert out["nmbe_percent"] == 0
