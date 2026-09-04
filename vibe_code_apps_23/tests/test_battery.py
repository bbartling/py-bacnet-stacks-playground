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


def test_net_welfare_can_go_negative():
    dh = degree_hours_abs_delta([74.0] * 12, [72.0] * 12, dt_hours=1.0)
    assert dh == pytest.approx(24.0)
    welfare = net_welfare_usd(bill_savings_usd=0.50, degree_hours=dh, wtp_usd_per_f_h=0.10)
    assert welfare["comfort_cost_usd"] == pytest.approx(2.4)
    assert welfare["net_welfare_usd"] < 0
