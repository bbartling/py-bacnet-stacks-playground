"""Illustrative residential TOU tariffs expanded to 288 five-minute intervals."""
from __future__ import annotations

from typing import Sequence

from ..tariff import INTERVALS_5MIN, TariffEvidence, TariffScenario
from .constants import CLAIM_TARIFF, INTERVALS_PER_DAY

SUMMER_HOURLY = (
    (0, 6, 0.08),
    (6, 14, 0.16),
    (14, 16, 0.30),
    (16, 21, 0.55),
    (21, 24, 0.14),
)
WINTER_HOURLY = (
    (0, 6, 0.08),
    (6, 9, 0.35),
    (9, 16, 0.14),
    (16, 21, 0.40),
    (21, 24, 0.12),
)


def expand_hourly_rates(
    bands: Sequence[tuple[float, float, float]],
    *,
    intervals_per_day: int = INTERVALS_PER_DAY,
) -> tuple[float, ...]:
    if intervals_per_day % 24 != 0:
        raise ValueError("intervals_per_day must be divisible by 24")
    steps_per_hour = intervals_per_day // 24
    rates: list[float] = []
    for hour in range(24):
        rate = None
        for start, end, value in bands:
            if start <= hour < end:
                rate = float(value)
                break
        if rate is None:
            raise ValueError(f"no tariff band covers hour {hour}")
        rates.extend([rate] * steps_per_hour)
    if len(rates) != intervals_per_day:
        raise RuntimeError("expanded tariff length mismatch")
    return tuple(rates)


def summer_tou_hourly(*, intervals_per_day: int = INTERVALS_5MIN) -> TariffScenario:
    return TariffScenario(
        tariff_id="illustrative_summer_tou_weekday",
        evidence=TariffEvidence.ILLUSTRATIVE,
        energy_rates_per_kwh=expand_hourly_rates(SUMMER_HOURLY, intervals_per_day=intervals_per_day),
        demand_rate_per_kw=0.0,
        source_reference="vibe23 residential plan illustrative high-spread summer TOU",
        notes=CLAIM_TARIFF,
    )


def winter_tou_hourly(*, intervals_per_day: int = INTERVALS_5MIN) -> TariffScenario:
    return TariffScenario(
        tariff_id="illustrative_winter_tou_weekday",
        evidence=TariffEvidence.ILLUSTRATIVE,
        energy_rates_per_kwh=expand_hourly_rates(WINTER_HOURLY, intervals_per_day=intervals_per_day),
        demand_rate_per_kw=0.0,
        source_reference="vibe23 residential plan illustrative high-spread winter TOU",
        notes=CLAIM_TARIFF,
    )
