"""Default 60-minute recovery must move DualSP before occupancy start."""
from eplus_gym.six_zone_daily_controller import SixZoneDailyParams, build_zone_series_f


def test_default_incumbent_recovery_ramps_before_occupancy():
    p = SixZoneDailyParams()
    series = build_zone_series_f(p, "1F_A")
    start = p.occupancy_start_step
    assert series[start] == 70.0
    assert series[start - 1] > 65.0
    assert series[start - 1] <= 70.0
    assert series[start - 4] > 65.0
    assert max(abs(series[i] - series[i - 1]) for i in range(1, start + 1)) <= 1.25 + 1e-9
