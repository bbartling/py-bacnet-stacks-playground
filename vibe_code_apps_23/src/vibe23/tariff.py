"""Tariff evidence and interval-price contracts for Vibe 23 DSM research.

Illustrative/candidate tariffs may be ranked for educational demos but must
stay labeled. Only VERIFIED evidence authorizes operational monetary selection.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Sequence

INTERVALS_PER_DAY = 96  # legacy 15-min default; residential DSM uses 288 (5-min)
INTERVALS_5MIN = 288
TARIFF_SCHEMA = "vibe23.tariff.v1"


class TariffEvidence(str, Enum):
    """How directly a tariff is evidenced for the modeled building/account."""

    VERIFIED = "VERIFIED"
    CANDIDATE = "CANDIDATE"
    ILLUSTRATIVE = "ILLUSTRATIVE"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _finite_nonnegative(value: float, name: str) -> float:
    value = float(value)
    if value != value or value in (float("inf"), float("-inf")) or value < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return value


@dataclass(frozen=True)
class BillingState:
    """Opening billing state for one decision day; never mutate it while scoring."""

    month_to_date_peak_kw: float = 0.0
    ratchet_kw: float = 0.0
    contract_kw: float = 0.0

    def __post_init__(self) -> None:
        for name in ("month_to_date_peak_kw", "ratchet_kw", "contract_kw"):
            _finite_nonnegative(getattr(self, name), name)

    @property
    def billing_floor_kw(self) -> float:
        return max(self.month_to_date_peak_kw, self.ratchet_kw, self.contract_kw)

    def fingerprint(self) -> str:
        return _sha256(asdict(self))


@dataclass(frozen=True)
class TariffScenario:
    """A versioned interval research tariff (96×15-min or 288×5-min typical).

    ``VERIFIED`` needs both the tariff source and an account/building-period
    binding.  Illustrative money can be ranked for educational demos but must
    stay labeled ``ILLUSTRATIVE``.
    """

    tariff_id: str
    evidence: TariffEvidence
    energy_rates_per_kwh: tuple[float, ...]
    demand_rate_per_kw: float = 0.0
    source_reference: str | None = None
    source_sha256: str | None = None
    account_period_binding: str | None = None
    effective_period: str | None = None
    notes: str | None = None
    schema: str = TARIFF_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != TARIFF_SCHEMA:
            raise ValueError(f"schema must be {TARIFF_SCHEMA}")
        if not isinstance(self.evidence, TariffEvidence):
            raise ValueError("evidence must be a TariffEvidence value")
        if not self.tariff_id.strip():
            raise ValueError("tariff_id is required")
        if len(self.energy_rates_per_kwh) < 1:
            raise ValueError("energy_rates_per_kwh must not be empty")
        for rate in self.energy_rates_per_kwh:
            _finite_nonnegative(rate, "energy rate")
        _finite_nonnegative(self.demand_rate_per_kw, "demand_rate_per_kw")
        if self.source_sha256 and not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise ValueError("source_sha256 must be a lowercase SHA-256")
        if self.evidence is TariffEvidence.VERIFIED:
            if (
                not self.source_reference
                or not self.source_sha256
                or not self.account_period_binding
                or not self.effective_period
            ):
                raise ValueError(
                    "VERIFIED tariff requires source_reference, source_sha256, account_period_binding, "
                    "and effective_period"
                )

    @property
    def intervals_per_day(self) -> int:
        return len(self.energy_rates_per_kwh)

    @property
    def dt_hours(self) -> float:
        return 24.0 / float(self.intervals_per_day)

    @property
    def monetary_selection_authorized(self) -> bool:
        return self.evidence is TariffEvidence.VERIFIED

    @property
    def money_label(self) -> str:
        if self.evidence is TariffEvidence.VERIFIED:
            return "VERIFIED BUILDING/ACCOUNT TARIFF"
        if self.evidence is TariffEvidence.CANDIDATE:
            return "CANDIDATE TARIFF — UNBOUND TO BUILDING ACCOUNT"
        return "ILLUSTRATIVE TARIFF — SCENARIO ONLY"

    @property
    def selection_label(self) -> str:
        if self.monetary_selection_authorized:
            return "MONETARY_RANKING_ALLOWED"
        return "PHYSICAL_RANKING_REQUIRED; MONEY_IS_SCENARIO_ONLY"

    def fingerprint(self) -> str:
        body = asdict(self)
        body["evidence"] = self.evidence.value
        body["energy_rates_per_kwh"] = list(self.energy_rates_per_kwh)
        return _sha256(body)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence"] = self.evidence.value
        result["energy_rates_per_kwh"] = list(self.energy_rates_per_kwh)
        result["money_label"] = self.money_label
        result["selection_label"] = self.selection_label
        result["tariff_sha256"] = self.fingerprint()
        return result

    @classmethod
    def flat(
        cls,
        *,
        tariff_id: str,
        evidence: TariffEvidence,
        energy_rate_per_kwh: float,
        demand_rate_per_kw: float = 0.0,
        intervals_per_day: int = INTERVALS_PER_DAY,
        **provenance: Any,
    ) -> "TariffScenario":
        if intervals_per_day < 1:
            raise ValueError("intervals_per_day must be positive")
        return cls(
            tariff_id=tariff_id,
            evidence=evidence,
            energy_rates_per_kwh=tuple(float(energy_rate_per_kwh) for _ in range(intervals_per_day)),
            demand_rate_per_kw=float(demand_rate_per_kw),
            **provenance,
        )


def load_tariff(payload_or_path: Mapping[str, Any] | Path | str) -> TariffScenario:
    """Load a tariff JSON payload and retain the evidence classification.

    The loader intentionally accepts no implicit default tariff.  An author
    must explicitly choose verified, candidate, or illustrative evidence.
    """

    if isinstance(payload_or_path, (Path, str)):
        path = Path(payload_or_path)
        raw = json.loads(path.read_text(encoding="utf-8"))
    else:
        raw = dict(payload_or_path)
    if "evidence" not in raw:
        raise ValueError("tariff evidence is required; refuse an unlabeled tariff")
    try:
        evidence = TariffEvidence(str(raw["evidence"]).upper())
    except ValueError as exc:
        raise ValueError("evidence must be VERIFIED, CANDIDATE, or ILLUSTRATIVE") from exc
    rates = raw.get("energy_rates_per_kwh")
    if rates is None and raw.get("energy_rate_per_kwh") is not None:
        n = int(raw.get("intervals_per_day") or INTERVALS_PER_DAY)
        rates = [raw["energy_rate_per_kwh"]] * n
    if not isinstance(rates, Sequence) or isinstance(rates, (str, bytes)):
        raise ValueError("energy_rates_per_kwh (or flat energy_rate_per_kwh) is required")
    return TariffScenario(
        tariff_id=str(raw.get("tariff_id") or "").strip(),
        evidence=evidence,
        energy_rates_per_kwh=tuple(float(v) for v in rates),
        demand_rate_per_kw=float(raw.get("demand_rate_per_kw") or 0.0),
        source_reference=raw.get("source_reference"),
        source_sha256=raw.get("source_sha256"),
        account_period_binding=raw.get("account_period_binding"),
        effective_period=raw.get("effective_period"),
        notes=raw.get("notes"),
        schema=str(raw.get("schema") or TARIFF_SCHEMA),
    )


def billing_cost(
    facility_kw: Sequence[float],
    *,
    tariff: TariffScenario,
    opening_state: BillingState,
    dt_hours: float | None = None,
) -> dict[str, Any]:
    """Calculate daily energy plus incremental-demand cost from a fixed opening state."""

    if len(facility_kw) != tariff.intervals_per_day:
        raise ValueError(f"facility_kw must have {tariff.intervals_per_day} values")
    dt_hours = float(tariff.dt_hours if dt_hours is None else dt_hours)
    if not math.isfinite(dt_hours) or dt_hours <= 0.0:
        raise ValueError("dt_hours must be finite and positive")
    values = tuple(_finite_nonnegative(v, "facility kW") for v in facility_kw)
    energy_kwh = sum(v * dt_hours for v in values)
    energy_cost = sum(
        kw * dt_hours * rate for kw, rate in zip(values, tariff.energy_rates_per_kwh, strict=True)
    )
    day_peak_kw = max(values)
    old_floor_kw = opening_state.billing_floor_kw
    new_floor_kw = max(old_floor_kw, day_peak_kw)
    demand_increment_kw = new_floor_kw - old_floor_kw
    demand_cost = demand_increment_kw * tariff.demand_rate_per_kw
    return {
        "energy_kwh": float(energy_kwh),
        "energy_cost_usd": float(energy_cost),
        "day_peak_kw": float(day_peak_kw),
        "opening_billing_floor_kw": float(old_floor_kw),
        "new_billing_floor_kw": float(new_floor_kw),
        "incremental_demand_kw": float(demand_increment_kw),
        "demand_cost_usd": float(demand_cost),
        "total_cost_usd": float(energy_cost + demand_cost),
        "tariff_evidence": tariff.evidence.value,
        "tariff_label": tariff.money_label,
        "tariff_sha256": tariff.fingerprint(),
        "billing_state_sha256": opening_state.fingerprint(),
    }


class TariffProvider(ABC):
    """Interface for fixture or future utility-rate API adapters."""

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def scenario(self) -> TariffScenario:
        raise NotImplementedError


class FixtureTariffProvider(TariffProvider):
    """Deterministic tariff loaded from JSON or an in-memory scenario."""

    def __init__(self, payload_or_path: Mapping[str, Any] | Path | str | TariffScenario) -> None:
        if isinstance(payload_or_path, TariffScenario):
            self._scenario = payload_or_path
            self._source = "in-memory"
        else:
            self._scenario = load_tariff(payload_or_path)
            self._source = str(payload_or_path)

    def describe(self) -> dict[str, Any]:
        return {
            "provider": "FixtureTariffProvider",
            "source": self._source,
            "tariff_id": self._scenario.tariff_id,
            "evidence": self._scenario.evidence.value,
            "intervals": self._scenario.intervals_per_day,
            "claim": "API_RATE_NOT_REQUIRED_FOR_DEMO",
        }

    def scenario(self) -> TariffScenario:
        return self._scenario


class FutureApiTariffProvider(TariffProvider):
    """Stub for a future live utility-rate API (not required for acceptance)."""

    def describe(self) -> dict[str, Any]:
        return {
            "provider": "FutureApiTariffProvider",
            "status": "NOT_IMPLEMENTED",
            "claim": "API_RATE_NOT_REQUIRED_FOR_DEMO",
        }

    def scenario(self) -> TariffScenario:
        raise NotImplementedError("Live utility-rate API is not required for the residential demo")
