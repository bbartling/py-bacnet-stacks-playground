"""Synthetic series vs Open-FDD hunting_fault_mask."""

from open_fdd.rules.pid_hunting import PidHuntingParams, hunting_fault_mask

from vibe25.synth import COLUMN, POLL_SECONDS, healthy_cooling_valve, hunting_cooling_valve


def test_hunting_trips_default_pid_hunt_1():
    df = hunting_cooling_valve()
    fault, metrics = hunting_fault_mask(
        df[COLUMN],
        params=PidHuntingParams(),
        poll_seconds=POLL_SECONDS,
    )
    assert bool(fault.any())
    assert float(metrics.loc[fault, "total_variation_1h"].max()) >= 500.0
    assert float(metrics.loc[fault, "output_span_1h"].max()) >= 20.0
    assert float(metrics.loc[fault, "equivalent_cycles_1h"].max()) >= 2.5
    assert float(metrics.loc[fault, "reversals_1h"].max()) >= 4.0


def test_healthy_does_not_trip_default_pid_hunt_1():
    df = healthy_cooling_valve()
    fault, metrics = hunting_fault_mask(
        df[COLUMN],
        params=PidHuntingParams(),
        poll_seconds=POLL_SECONDS,
    )
    assert not bool(fault.any())
    assert float(metrics["total_variation_1h"].fillna(0).max()) < 500.0
