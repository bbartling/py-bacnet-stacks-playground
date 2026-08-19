"""Phase 6: tariff mode catalog + 96×15min price forecast vectors."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Sequence

import numpy as np

from eplus_gym.tariff_contract import TariffContract

SCHEMA = "vibe22.mega.tariff_modes.v1"
INTERVALS_PER_DAY = 96
HOURS_PER_DAY = 24

TariffMode = Literal[
    "flat_illustrative",
    "tou_typical_illustrative",
    "tou_winter_peak_illustrative",
    "tou_evening_peak_illustrative",
    "custom_hourly",
    "verified_tariff",
]

REQUIRED_MODES: tuple[TariffMode, ...] = (
    "flat_illustrative",
    "tou_typical_illustrative",
    "tou_winter_peak_illustrative",
    "tou_evening_peak_illustrative",
    "custom_hourly",
    "verified_tariff",
)


@dataclass
class TariffModeSpec:
    mode: TariffMode
    energy_rate_per_kwh: float
    demand_rate_per_kw: float
    label: str
    verified: bool = False
    hourly_energy_rates: list[float] | None = None

    def hourly_prices(self) -> np.ndarray:
        if self.hourly_energy_rates is not None:
            if len(self.hourly_energy_rates) != HOURS_PER_DAY:
                raise ValueError(f"custom_hourly requires {HOURS_PER_DAY} values")
            return np.asarray(self.hourly_energy_rates, dtype=np.float64)
        if self.mode == "flat_illustrative":
            return np.full(HOURS_PER_DAY, self.energy_rate_per_kwh)
        if self.mode == "tou_typical_illustrative":
            # Peak 14–20 local
            rates = np.full(HOURS_PER_DAY, self.energy_rate_per_kwh * 0.7)
            rates[14:20] = self.energy_rate_per_kwh * 1.3
            return rates
        if self.mode == "tou_winter_peak_illustrative":
            rates = np.full(HOURS_PER_DAY, self.energy_rate_per_kwh * 0.8)
            rates[6:10] = self.energy_rate_per_kwh * 1.4
            return rates
        if self.mode == "tou_evening_peak_illustrative":
            rates = np.full(HOURS_PER_DAY, self.energy_rate_per_kwh * 0.75)
            rates[16:21] = self.energy_rate_per_kwh * 1.5
            return rates
        raise ValueError(f"unsupported mode {self.mode!r}")

    def quarter_hour_prices(self) -> np.ndarray:
        hourly = self.hourly_prices()
        return np.repeat(hourly, 4)

    def to_contract(self, *, existing_billing_peak_kw: float = 0.0) -> TariffContract:
        if self.mode == "verified_tariff":
            if not self.verified:
                raise ValueError("verified_tariff requires verified=True (fail closed)")
            return TariffContract(
                money_mode="VERIFIED_TARIFF",
                energy_rate_per_kwh=self.energy_rate_per_kwh,
                demand_rate_per_kw=self.demand_rate_per_kw,
                existing_billing_peak_kw=existing_billing_peak_kw,
                label=self.label,
                verified=True,
            )
        return TariffContract.illustrative(
            energy_rate_per_kwh=self.energy_rate_per_kwh,
            demand_rate_per_kw=self.demand_rate_per_kw,
            existing_billing_peak_kw=existing_billing_peak_kw,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "energy_rate_per_kwh": self.energy_rate_per_kwh,
            "demand_rate_per_kw": self.demand_rate_per_kw,
            "label": self.label,
            "verified": self.verified,
        }


def default_tariff_catalog() -> dict[TariffMode, TariffModeSpec]:
    base_e = 0.11
    base_d = 12.0
    return {
        "flat_illustrative": TariffModeSpec("flat_illustrative", base_e, base_d, "Flat illustrative"),
        "tou_typical_illustrative": TariffModeSpec(
            "tou_typical_illustrative", base_e, base_d, "TOU typical illustrative"
        ),
        "tou_winter_peak_illustrative": TariffModeSpec(
            "tou_winter_peak_illustrative", base_e, base_d, "TOU winter peak illustrative"
        ),
        "tou_evening_peak_illustrative": TariffModeSpec(
            "tou_evening_peak_illustrative", base_e, base_d, "TOU evening peak illustrative"
        ),
        "custom_hourly": TariffModeSpec(
            "custom_hourly",
            base_e,
            base_d,
            "Custom hourly illustrative",
            hourly_energy_rates=[base_e * (1.2 if 14 <= h < 20 else 0.85) for h in range(HOURS_PER_DAY)],
        ),
        "verified_tariff": TariffModeSpec(
            "verified_tariff", base_e, base_d, "Verified tariff placeholder", verified=False
        ),
    }


def tariff_mode_mask(mode: TariffMode) -> np.ndarray:
    """One-hot over REQUIRED_MODES for observation contract."""
    vec = np.zeros(len(REQUIRED_MODES), dtype=np.float32)
    vec[REQUIRED_MODES.index(mode)] = 1.0
    return vec


def build_tariff_forecast_vectors(
    mode: TariffMode,
    *,
    catalog: dict[TariffMode, TariffModeSpec] | None = None,
) -> dict[str, Any]:
    cat = catalog or default_tariff_catalog()
    spec = cat[mode]
    hourly = spec.hourly_prices()
    qtr = spec.quarter_hour_prices()
    return {
        "tariff_mode": mode,
        "next_24h_energy_rates": hourly.tolist(),
        "next_96x15min_energy_rates": qtr.tolist(),
        "tariff_mode_mask": tariff_mode_mask(mode).tolist(),
        "demand_rate_per_kw": spec.demand_rate_per_kw,
    }
