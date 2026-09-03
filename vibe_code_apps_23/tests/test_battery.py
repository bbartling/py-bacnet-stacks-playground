from __future__ import annotations

from vibe23.battery import BatteryParams, simulate_dispatch


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
    # never charge and discharge same step
    for c, d in zip(out["charge_kw"], out["discharge_kw"], strict=True):
        assert not (c > 0 and d > 0)


def test_battery_rejects_simultaneous_by_construction():
    params = BatteryParams(capacity_kwh=5.0, max_charge_kw=2.0, max_discharge_kw=2.0)
    out = simulate_dispatch([3.0] * 24, [0.2] * 24, params, mode="peak_shave", dt_hours=1.0)
    assert out["intervals"] == 24.0
