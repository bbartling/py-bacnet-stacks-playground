"""Tests for shared simulation contract helpers."""

from ml.simulation_contract import (
    ANNUAL_REPLAY_STUB,
    FUTURE_OBJECTIVE_DOC,
    UNSUPPORTED_CONTROL_SCHEDULE,
    incremental_demand,
)


def test_incremental_demand_zero_when_below_existing():
    new_p, inc_kw, inc_cost = incremental_demand(100.0, 80.0, 12.0)
    assert new_p == 100.0
    assert inc_kw == 0.0
    assert inc_cost == 0.0


def test_incremental_demand_charges_only_delta():
    new_p, inc_kw, inc_cost = incremental_demand(100.0, 120.0, 12.0)
    assert new_p == 120.0
    assert inc_kw == 20.0
    assert inc_cost == 240.0


def test_contract_constants_documented():
    assert UNSUPPORTED_CONTROL_SCHEDULE == "UNSUPPORTED_CONTROL_SCHEDULE"
    assert "HEURISTIC" in ANNUAL_REPLAY_STUB
    assert "comfort" in FUTURE_OBJECTIVE_DOC.lower()
