"""Phase 6: tariff mode catalog + 96×15min price forecast vectors."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Sequence

import numpy as np

from eplus_gym.tariff_contract import TariffContract

SCHEMA = "vibe22.mega.tariff_modes.v1"
INTERVALS_PER_DAY = 96
HOURS_PER_DAY = 24

ILLUSTRATIVE_TARIFF_BANNER = "ILLUSTRATIVE TARIFF — NOT VERIFIED UTILITY PRICING"

TariffMode = Literal[
    "flat_illustrative",
    "tou_typical_illustrative",
    "tou_winter_peak_illustrative",
    "tou_evening_peak_illustrative",
    "custom_hourly",
    "verified_tariff",
    "FLAT_PLUS_DEMAND",
    "ILLUSTRATIVE_TOU_PLUS_DEMAND",
]

# Obs one-hot stays on the legacy six modes so N_OBS_V4 is stable.
REQUIRED_MODES: tuple[str, ...] = (
    "flat_illustrative",
    "tou_typical_illustrative",
    "tou_winter_peak_illustrative",
    "tou_evening_peak_illustrative",
    "custom_hourly",
    "verified_tariff",
)

# Experiment IDs → catalog keys (demand already included on both).
EXPERIMENT_ALIASES: dict[str, str] = {
    "FLAT_PLUS_DEMAND": "flat_illustrative",
    "ILLUSTRATIVE_TOU_PLUS_DEMAND": "tou_evening_peak_illustrative",
}

EXPERIMENT_LABELS: dict[str, str] = {
    "FLAT_PLUS_DEMAND": "PRIMARY FLAT_PLUS_DEMAND",
    "ILLUSTRATIVE_TOU_PLUS_DEMAND": "SECONDARY ILLUSTRATIVE_TOU_PLUS_DEMAND",
}


def resolve_tariff_mode(mode: str) -> str:
    m = str(mode)
    return EXPERIMENT_ALIASES.get(m, m)


def experiment_id_for_mode(mode: str) -> str:
    m = str(mode)
    if m in EXPERIMENT_ALIASES:
        return m
    if m == "flat_illustrative":
        return "FLAT_PLUS_DEMAND"
    if m == "tou_evening_peak_illustrative":
        return "ILLUSTRATIVE_TOU_PLUS_DEMAND"
    return m


def tariff_banner(mode: str) -> str | None:
    resolved = resolve_tariff_mode(mode)
    if str(mode) == "ILLUSTRATIVE_TOU_PLUS_DEMAND" or resolved.startswith("tou_"):
        return ILLUSTRATIVE_TARIFF_BANNER
    if str(mode) in {"FLAT_PLUS_DEMAND", "flat_illustrative"}:
        return "ILLUSTRATIVE FLAT + DEMAND — NOT VERIFIED UTILITY PRICING"
    return None


@dataclass
class TariffModeSpec:
    mode: str
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
        key = resolve_tariff_mode(self.mode)
        if key == "flat_illustrative" or self.mode == "FLAT_PLUS_DEMAND":
            return np.full(HOURS_PER_DAY, self.energy_rate_per_kwh)
        if key == "tou_typical_illustrative":
            rates = np.full(HOURS_PER_DAY, self.energy_rate_per_kwh * 0.7)
            rates[14:20] = self.energy_rate_per_kwh * 1.3
            return rates
        if key == "tou_winter_peak_illustrative":
            rates = np.full(HOURS_PER_DAY, self.energy_rate_per_kwh * 0.8)
            rates[6:10] = self.energy_rate_per_kwh * 1.4
            return rates
        if key == "tou_evening_peak_illustrative" or self.mode == "ILLUSTRATIVE_TOU_PLUS_DEMAND":
            rates = np.full(HOURS_PER_DAY, self.energy_rate_per_kwh * 0.75)
            rates[16:21] = self.energy_rate_per_kwh * 1.5
            return rates
        raise ValueError(f"unsupported mode {self.mode!r}")

    def quarter_hour_prices(self) -> np.ndarray:
        hourly = self.hourly_prices()
        return np.repeat(hourly, 4)

    def to_contract(self, *, existing_billing_peak_kw: float = 0.0) -> TariffContract:
        key = resolve_tariff_mode(self.mode)
        if key == "verified_tariff":
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
            "experiment_id": experiment_id_for_mode(self.mode),
            "banner": tariff_banner(self.mode),
        }


def default_tariff_catalog() -> dict[str, TariffModeSpec]:
    base_e = 0.11
    base_d = 12.0
    cat: dict[str, TariffModeSpec] = {
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
    # Named experiments (PRIMARY / SECONDARY) — same economics as aliases.
    cat["FLAT_PLUS_DEMAND"] = TariffModeSpec(
        "FLAT_PLUS_DEMAND", base_e, base_d, EXPERIMENT_LABELS["FLAT_PLUS_DEMAND"]
    )
    cat["ILLUSTRATIVE_TOU_PLUS_DEMAND"] = TariffModeSpec(
        "ILLUSTRATIVE_TOU_PLUS_DEMAND",
        base_e,
        base_d,
        EXPERIMENT_LABELS["ILLUSTRATIVE_TOU_PLUS_DEMAND"],
    )
    return cat


def tariff_mode_mask(mode: str) -> np.ndarray:
    """One-hot over REQUIRED_MODES for observation contract (aliases resolved)."""
    key = resolve_tariff_mode(mode)
    vec = np.zeros(len(REQUIRED_MODES), dtype=np.float32)
    if key not in REQUIRED_MODES:
        raise KeyError(f"tariff mode {mode!r} (resolved {key!r}) not in REQUIRED_MODES")
    vec[REQUIRED_MODES.index(key)] = 1.0
    return vec


def build_tariff_forecast_vectors(
    mode: str,
    *,
    catalog: dict[str, TariffModeSpec] | None = None,
) -> dict[str, Any]:
    cat = catalog or default_tariff_catalog()
    if mode not in cat:
        key = resolve_tariff_mode(mode)
        if key not in cat:
            raise KeyError(mode)
        mode = key
    spec = cat[mode]
    hourly = spec.hourly_prices()
    qtr = spec.quarter_hour_prices()
    return {
        "tariff_mode": mode,
        "experiment_id": experiment_id_for_mode(mode),
        "banner": tariff_banner(mode),
        "next_24h_energy_rates": hourly.tolist(),
        "next_96x15min_energy_rates": qtr.tolist(),
        "tariff_mode_mask": tariff_mode_mask(mode).tolist(),
        "demand_rate_per_kw": spec.demand_rate_per_kw,
    }
