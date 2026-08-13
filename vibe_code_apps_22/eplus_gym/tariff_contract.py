"""Tariff contract for EnergyPlus DSM optimization screening."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Literal, Optional

MoneyMode = Literal["PHYSICAL_ONLY", "VERIFIED_TARIFF", "ILLUSTRATIVE"]

CONTRACT_VERSION = "eplus_gym_tariff_v1"

# LaTeX (KaTeX) for Streamlit st.latex — billing-floor incremental demand.
LATEX_TOTAL_COST = r"C = C_{\mathrm{energy}} + C_{\mathrm{demand}}^{\mathrm{inc}}"
LATEX_ENERGY = (
    r"C_{\mathrm{energy}} = \sum_{t=1}^{96} P_t\,\Delta t\, r_{\mathrm{energy}}(t)"
    r"\quad(\Delta t = 0.25\,\mathrm{h})"
)
LATEX_DEMAND = (
    r"P^{\mathrm{new}} = \max\!\big(P^{\mathrm{MTD}},\, P^{\mathrm{day}}\big),"
    r"\quad"
    r"\Delta P = \max\!\big(0,\, P^{\mathrm{new}} - P^{\mathrm{MTD}}\big),"
    r"\quad "
    r"C_{\mathrm{demand}}^{\mathrm{inc}} = \Delta P\, r_{\mathrm{demand}}"
)
LATEX_SAVINGS = (
    r"\Delta C = C^{\mathrm{baseline}} - C^{\mathrm{candidate}}"
    r"\quad\text{(verified \$ only when money\_mode ≠ PHYSICAL\_ONLY)}"
)
LATEX_PHYSICAL = (
    r"\text{PHYSICAL\_ONLY: rank by }(\Delta E,\,\Delta P^{\mathrm{peak}},\,"
    r"\text{comfort DH})\text{ — illustrative \$ never selects the winner}"
)


@dataclass
class TariffContract:
    """Versioned tariff. Default money_mode is PHYSICAL_ONLY."""

    contract_version: str = CONTRACT_VERSION
    money_mode: MoneyMode = "PHYSICAL_ONLY"
    energy_rate_per_kwh: float = 0.0
    demand_rate_per_kw: float = 0.0
    existing_billing_peak_kw: float = 0.0
    contract_demand_kw: float | None = None
    ratchet_fraction: float | None = None
    tou_energy_rates: Dict[str, float] = field(default_factory=dict)
    label: str = "PHYSICAL_ONLY screening"
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def physical_only(
        cls,
        *,
        existing_billing_peak_kw: float = 0.0,
    ) -> "TariffContract":
        return cls(
            money_mode="PHYSICAL_ONLY",
            energy_rate_per_kwh=0.0,
            demand_rate_per_kw=0.0,
            existing_billing_peak_kw=float(existing_billing_peak_kw),
            label="PHYSICAL_ONLY — no verified tariff",
            verified=False,
        )

    @classmethod
    def illustrative(
        cls,
        *,
        energy_rate_per_kwh: float,
        demand_rate_per_kw: float,
        existing_billing_peak_kw: float = 0.0,
    ) -> "TariffContract":
        return cls(
            money_mode="ILLUSTRATIVE",
            energy_rate_per_kwh=float(energy_rate_per_kwh),
            demand_rate_per_kw=float(demand_rate_per_kw),
            existing_billing_peak_kw=float(existing_billing_peak_kw),
            label="ILLUSTRATIVE — cannot select operational winner",
            verified=False,
        )

    @classmethod
    def from_dict(cls, raw: Dict[str, Any] | None) -> "TariffContract":
        if not raw:
            return cls.physical_only()
        mode = str(raw.get("money_mode") or "PHYSICAL_ONLY").upper()
        if mode not in {"PHYSICAL_ONLY", "VERIFIED_TARIFF", "ILLUSTRATIVE"}:
            mode = "PHYSICAL_ONLY"
        return cls(
            contract_version=str(raw.get("contract_version") or CONTRACT_VERSION),
            money_mode=mode,  # type: ignore[arg-type]
            energy_rate_per_kwh=float(raw.get("energy_rate_per_kwh") or 0.0),
            demand_rate_per_kw=float(raw.get("demand_rate_per_kw") or 0.0),
            existing_billing_peak_kw=float(raw.get("existing_billing_peak_kw") or 0.0),
            contract_demand_kw=(
                float(raw["contract_demand_kw"])
                if raw.get("contract_demand_kw") is not None
                else None
            ),
            ratchet_fraction=(
                float(raw["ratchet_fraction"])
                if raw.get("ratchet_fraction") is not None
                else None
            ),
            tou_energy_rates=dict(raw.get("tou_energy_rates") or {}),
            label=str(raw.get("label") or mode),
            verified=bool(raw.get("verified", mode == "VERIFIED_TARIFF")),
        )


def latex_cost_equations() -> Dict[str, str]:
    """KaTeX strings for Streamlit Optimize Tomorrow UI."""
    return {
        "total": LATEX_TOTAL_COST,
        "energy": LATEX_ENERGY,
        "demand": LATEX_DEMAND,
        "savings": LATEX_SAVINGS,
        "physical_only": LATEX_PHYSICAL,
    }
