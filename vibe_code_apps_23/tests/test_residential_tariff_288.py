from __future__ import annotations

from vibe23.residential.tariffs import expand_hourly_rates, summer_tou_hourly, winter_tou_hourly
from vibe23.tariff import BillingState, FixtureTariffProvider, billing_cost


def test_summer_tou_expands_to_288():
    tariff = summer_tou_hourly()
    assert tariff.intervals_per_day == 288
    assert tariff.dt_hours == 1 / 12
    # 16:00 band is $0.55
    assert tariff.energy_rates_per_kwh[16 * 12] == 0.55


def test_winter_tou_morning_peak():
    tariff = winter_tou_hourly()
    assert tariff.energy_rates_per_kwh[7 * 12] == 0.35


def test_billing_cost_288():
    tariff = summer_tou_hourly()
    bill = billing_cost([1.0] * 288, tariff=tariff, opening_state=BillingState())
    assert bill["energy_kwh"] == 24.0
    assert bill["total_cost_usd"] > 0


def test_fixture_tariff_provider():
    provider = FixtureTariffProvider(summer_tou_hourly())
    assert provider.describe()["intervals"] == 288
    assert expand_hourly_rates([(0, 24, 0.1)])[0] == 0.1
