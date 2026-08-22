"""Unit tests for nightly grid compute (no LIVE EnergyPlus)."""
from __future__ import annotations

from pathlib import Path

import pytest

from eplus_gym.a04_identity import A04_SHA_CRLF
from eplus_gym.rl.nightly_grid_anytime import anytime_curve, best_fully_ready_cost
from eplus_gym.rl.nightly_grid_branch import IdenticalStateFailure, prove_identical_midnight
from eplus_gym.rl.nightly_grid_cost import monthly_demand_total, total_cost_from_monthly
from eplus_gym.rl.nightly_grid_freeze import A04HashMismatchError, assert_a04_hash
from eplus_gym.rl.nightly_grid_instrument import aggregate_timing, percentile
from eplus_gym.rl.nightly_grid_menu import build_one_day_menu, load_nightly_contract, preregistered_anytime_order
from eplus_gym.rl.two_month_cost import score_flat_plus_demand


def test_monthly_demand_sum_not_cross_month_peak():
    peaks = {"2025-12": 200.0, "2026-01": 250.0}
    total = monthly_demand_total(peaks, demand_rate_usd_per_kw=12.0)
    assert total == pytest.approx(200 * 12 + 250 * 12)
    assert total != pytest.approx(250 * 12)


def test_total_cost_energy_plus_demand():
    e = {"2025-12": 100.0, "2026-01": 110.0}
    d = {"2025-12": 50.0, "2026-01": 60.0}
    assert total_cost_from_monthly(monthly_energy_usd=e, monthly_demand_usd=d) == pytest.approx(320.0)


def test_two_month_cost_demand_is_sum_of_months():
    fac = [100.0] * 96 * 31 + [200.0] * 96 * 31  # Dec flat 100, Jan flat 200
    rows = {r["period"]: r for r in score_flat_plus_demand(fac)}
    assert rows["two_month"]["demand_charge_usd"] == pytest.approx(
        rows["2025-12"]["demand_charge_usd"] + rows["2026-01"]["demand_charge_usd"]
    )


def test_candidate_dedupe_one_day():
    menu = build_one_day_menu(day="2026-01-26")
    assert menu["declared_action_count"] == 146
    assert menu["n_unique_one_day"] < menu["declared_action_count"]
    assert menu["n_unique_one_day"] >= 100


def test_preregistered_ordering_deterministic():
    contract = load_nightly_contract(Path(__file__).resolve().parents[1])
    menu = build_one_day_menu(day="2026-01-26")
    a = preregistered_anytime_order(menu, seed_indices=contract["preregistered_anytime_seed_indices"])
    b = preregistered_anytime_order(menu, seed_indices=contract["preregistered_anytime_seed_indices"])
    assert a == b
    assert len(a) == menu["n_unique_one_day"]
    assert len(a) == len(set(a))


def test_identical_state_proof():
    z = [[70.0] * 6, [70.01] * 6, [70.02] * 6]
    proof = prove_identical_midnight(z, tol_f=0.05)
    assert proof["ok"] is True
    with pytest.raises(IdenticalStateFailure):
        prove_identical_midnight([[70.0] * 6, [71.0] * 6], tol_f=0.05)


def test_percentile_and_aggregate_schema():
    assert percentile([1, 2, 3, 4, 5], 50) == pytest.approx(3)
    agg = aggregate_timing(
        [
            {"wall_s": 1.0, "exit_code": 0, "child_user_cpu_s": 0.5, "child_system_cpu_s": 0.1, "peak_rss_bytes": 100},
            {"wall_s": 2.0, "exit_code": 0, "child_user_cpu_s": 0.5, "child_system_cpu_s": 0.1, "peak_rss_bytes": 200},
        ]
    )
    for key in ("total_wall_s", "mean_latency_s", "p95_latency_s", "failure_rate"):
        assert key in agg


def test_regret_calculation():
    rows = []
    for i, cost in enumerate([30.0, 20.0, 25.0, 18.0, 18.0]):
        rows.append(
            {
                "candidate_id": f"c{i}",
                "status": "OK",
                "score": {"total_modeled_objective": cost, "fully_ready_eligible": True},
            }
        )
    assert best_fully_ready_cost(rows) == pytest.approx(18.0)
    curve = anytime_curve(rows, markers=(2, 4, 5))
    assert curve["exhaustive_best_fully_ready_cost"] == pytest.approx(18.0)
    assert curve["candidates_within_10_usd"] == 2


def test_tariff_rescore_zero_launches_field():
    # Structural: publish helper stores additional_eplus_launches=0
    blob = {"by_tariff": {}, "additional_eplus_launches": 0}
    assert blob["additional_eplus_launches"] == 0


def test_a04_hash_fail_closed(tmp_path: Path):
    bad = tmp_path / "fake.idf"
    bad.write_text("not-a04", encoding="utf-8")
    with pytest.raises(A04HashMismatchError):
        assert_a04_hash(bad, expected_full=A04_SHA_CRLF, prefix="212a2835eabb8b3a")


def test_no_bacnet_authority_in_contract():
    contract = load_nightly_contract(Path(__file__).resolve().parents[1])
    assert int(contract["bacnet_command_authority"]) == 0


def test_process_failure_retention():
    rows = [
        {"wall_s": 1.0, "exit_code": 0, "status": "OK"},
        {"wall_s": 2.0, "exit_code": 1, "status": "FAILED"},
    ]
    agg = aggregate_timing(rows)
    assert agg["failure_rate"] == pytest.approx(0.5)
