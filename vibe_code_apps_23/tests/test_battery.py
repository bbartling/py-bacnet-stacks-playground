from __future__ import annotations

import pytest

from vibe23.battery import BatteryParams, simulate_dispatch
from vibe23.comfort import degree_hours_abs_delta, net_welfare_usd
from vibe23.dispatch import cyclic_lp_dispatch


def test_battery_price_arbitrage_and_soc_bounds():
    params = BatteryParams(
        capacity_kwh=10.0,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        initial_soc=0.5,
    )
    prices = [0.1] * 144 + [0.5] * 144
    load = [2.0] * 288
    out = simulate_dispatch(load, prices, params, mode="price_arbitrage")
    assert len(out["purchased_kw"]) == 288
    assert all(0.1 <= s <= 0.95 for s in out["soc"])
    for c, d in zip(out["charge_kw"], out["discharge_kw"], strict=True):
        assert not (c > 0 and d > 0)
    assert float(out["purchased_peak_kw"]) <= float(out["house_peak_kw"]) + 1e-9


def test_peak_shave_recharges_on_valley():
    params = BatteryParams(capacity_kwh=5.0, max_charge_kw=2.0, max_discharge_kw=2.0, initial_soc=0.5)
    # Distinct peak and valley so median recharge can fire under house-peak cap.
    load = [1.0] * 12 + [4.0] * 12
    out = simulate_dispatch(load, [0.2] * 24, params, mode="peak_shave", dt_hours=1.0)
    assert out["intervals"] == 24.0
    assert sum(out["charge_kw"]) > 0.0
    assert sum(out["discharge_kw"]) > 0.0
    assert float(out["purchased_peak_kw"]) <= float(out["house_peak_kw"]) + 1e-9


def test_cyclic_lp_feasible_and_peak_capped():
    params = BatteryParams(capacity_kwh=13.5, max_charge_kw=5.0, max_discharge_kw=5.0, initial_soc=0.5)
    prices = [0.08] * 96 + [0.55] * 96 + [0.14] * 96
    load = [1.5] * 288
    no_batt_bill = sum(p * k * (1 / 12) for p, k in zip(prices, load, strict=True))
    lp = cyclic_lp_dispatch(load, prices, params)
    assert float(lp["bill_usd"]) <= no_batt_bill + 1e-6
    assert float(lp["purchased_peak_kw"]) <= float(lp["house_peak_kw"]) + 1e-6
    assert abs(float(lp["initial_soc_opt"]) - float(lp["soc"][0])) < 1e-9
    # Greedy may beat LP on *day* bill by ending at high SOC (non-cyclic free lunch).
    greedy = simulate_dispatch(load, prices, params, mode="price_arbitrage")
    assert float(greedy["purchased_peak_kw"]) <= float(greedy["house_peak_kw"]) + 1e-9


def test_restore_final_soc_closes_the_day_at_initial():
    params = BatteryParams(
        capacity_kwh=13.5,
        max_charge_kw=5.0,
        max_discharge_kw=5.0,
        soc_min=0.1,
        soc_max=0.95,
        initial_soc=0.5,
    )
    # Cheap morning then an expensive tail, so greedy ends the day drained.
    prices = [0.08] * 192 + [0.55] * 96
    load = [2.0] * 288

    free = simulate_dispatch(load, prices, params, mode="price_arbitrage")
    assert abs(float(free["final_soc"]) - params.initial_soc) > 1e-2, (
        "expected greedy to end away from initial SOC on this price shape"
    )
    assert free["soc_restored"] is False

    fair = simulate_dispatch(load, prices, params, mode="price_arbitrage", restore_final_soc=True)
    assert fair["soc_restored"] is True
    assert abs(float(fair["final_soc"]) - params.initial_soc) < 1e-3
    # Restoration must not break the physical invariants the greedy loop enforces.
    assert all(params.soc_min - 1e-9 <= s <= params.soc_max + 1e-9 for s in fair["soc"])
    for c, d in zip(fair["charge_kw"], fair["discharge_kw"], strict=True):
        assert not (c > 1e-9 and d > 1e-9)
    assert all(p >= -1e-9 for p in fair["purchased_kw"])
    assert float(fair["purchased_peak_kw"]) <= float(fair["house_peak_kw"]) + 1e-9


def test_restore_final_soc_removes_the_drain_discount():
    """Ending drained is a free lunch; restoring SOC must not make the bill cheaper."""
    params = BatteryParams(capacity_kwh=13.5, max_charge_kw=5.0, max_discharge_kw=5.0, initial_soc=0.5)
    prices = [0.08] * 96 + [0.20] * 96 + [0.55] * 96
    load = [2.5] * 288

    def bill(out) -> float:
        return sum(p * k * (1 / 12) for p, k in zip(prices, out["purchased_kw"], strict=True))

    free = simulate_dispatch(load, prices, params, mode="price_arbitrage")
    fair = simulate_dispatch(load, prices, params, mode="price_arbitrage", restore_final_soc=True)
    assert float(fair["final_soc"]) > float(free["final_soc"])
    assert bill(fair) >= bill(free) - 1e-9


def test_restore_final_soc_sheds_a_surplus():
    """A day that ends over-charged is closed back down, not just topped up."""
    params = BatteryParams(capacity_kwh=10.0, max_charge_kw=4.0, max_discharge_kw=4.0, initial_soc=0.5)
    prices = [0.55] * 96 + [0.08] * 192  # expensive first, cheap tail → greedy ends high
    # Load must fall in the cheap tail, or the house-peak cap leaves no charging headroom.
    load = [4.0] * 96 + [1.0] * 192

    free = simulate_dispatch(load, prices, params, mode="price_arbitrage")
    assert float(free["final_soc"]) > params.initial_soc + 1e-2

    fair = simulate_dispatch(load, prices, params, mode="price_arbitrage", restore_final_soc=True)
    assert fair["soc_restored"] is True
    assert abs(float(fair["final_soc"]) - params.initial_soc) < 1e-3
    assert all(params.soc_min - 1e-9 <= s <= params.soc_max + 1e-9 for s in fair["soc"])


def test_net_welfare_can_go_negative():
    dh = degree_hours_abs_delta([74.0] * 12, [72.0] * 12, dt_hours=1.0)
    assert dh == pytest.approx(24.0)
    welfare = net_welfare_usd(bill_savings_usd=0.50, degree_hours=dh, wtp_usd_per_f_h=0.10)
    assert welfare["comfort_cost_usd"] == pytest.approx(2.4)
    assert welfare["net_welfare_usd"] < 0
