"""Strict models and loader for the canonical ECM registry."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal[
    "PRODUCTION_PROXY_AND_ENERGYPLUS",
    "PRODUCTION_PROXY_ONLY",
    "CONCEPTUAL_ENERGYPLUS_PROXY",
    "RESEARCH",
    "NEEDS_IMPLEMENTATION",
    "NOT_APPLICABLE",
]
Risk = Literal["low", "medium", "high"]
Confidence = Literal["low", "medium", "high"]

PRODUCTION_STATUSES: frozenset[str] = frozenset(
    {
        "PRODUCTION_PROXY_AND_ENERGYPLUS",
        "PRODUCTION_PROXY_ONLY",
        "CONCEPTUAL_ENERGYPLUS_PROXY",
    }
)
CATALOG_PATH = Path(__file__).resolve().parents[1] / "measures" / "catalog.yaml"


class ECMEntry(BaseModel):
    """One validated energy conservation measure definition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ecm_id: str = Field(pattern=r"^ECM-[A-Z0-9-]+$")
    display_name: str = Field(min_length=1)
    short_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    equipment_types: list[str] = Field(min_length=1)
    system_families: list[str] = Field(min_length=1)
    retrofit_classes: list[str] = Field(min_length=1)
    description: str = Field(min_length=1)
    engineering_rationale: str = Field(min_length=1)
    required_inputs: list[str]
    optional_inputs: list[str]
    proxy_calculator: str | None
    energyplus_patch: str | None
    conceptual_surrogate: bool
    unit_contract: dict[str, str] = Field(min_length=1)
    applicability_checks: list[str] = Field(min_length=1)
    incompatibilities: list[str]
    dependencies: list[str]
    default_cost_model: dict[str, str | float] = Field(min_length=1)
    default_measure_life: int = Field(gt=0)
    default_maintenance_cost: float = Field(ge=0)
    comfort_risk: Risk
    iaq_risk: Risk
    humidity_risk: Risk
    implementation_complexity: Risk
    confidence: Confidence
    public_sources: list[str] = Field(min_length=1)
    status: Status

    @model_validator(mode="after")
    def _status_contract(self) -> "ECMEntry":
        if (
            self.status == "PRODUCTION_PROXY_AND_ENERGYPLUS"
            and (not self.proxy_calculator or not self.energyplus_patch)
        ):
            raise ValueError(
                "PRODUCTION_PROXY_AND_ENERGYPLUS requires calculator and patch"
            )
        if self.status == "PRODUCTION_PROXY_ONLY" and not self.proxy_calculator:
            raise ValueError("PRODUCTION_PROXY_ONLY requires proxy_calculator")
        if (
            self.status == "CONCEPTUAL_ENERGYPLUS_PROXY"
            and (not self.energyplus_patch or not self.conceptual_surrogate)
        ):
            raise ValueError(
                "CONCEPTUAL_ENERGYPLUS_PROXY requires a patch and conceptual_surrogate"
            )
        return self


class ECMCatalog:
    """Immutable indexed view over validated ECM entries."""

    def __init__(self, entries: list[ECMEntry]) -> None:
        index: dict[str, ECMEntry] = {}
        for entry in entries:
            if entry.ecm_id in index:
                raise ValueError(f"Duplicate ECM id: {entry.ecm_id}")
            index[entry.ecm_id] = entry
        for entry in entries:
            for referenced in entry.dependencies + entry.incompatibilities:
                if referenced not in index:
                    raise ValueError(
                        f"{entry.ecm_id} references unknown ECM {referenced}"
                    )
                if referenced == entry.ecm_id:
                    raise ValueError(f"{entry.ecm_id} cannot reference itself")
        self._entries = tuple(entries)
        self._index = index

    def list(self, *, category: str | None = None) -> list[ECMEntry]:
        return [
            entry
            for entry in self._entries
            if category is None or entry.category == category
        ]

    def get(self, ecm_id: str) -> ECMEntry:
        try:
            return self._index[ecm_id]
        except KeyError as exc:
            raise KeyError(f"Unknown ECM: {ecm_id}") from exc


def _read_catalog(path: Path) -> ECMCatalog:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"ecms"}:
        raise ValueError("ECM catalog root must contain only 'ecms'")
    rows = raw["ecms"]
    if not isinstance(rows, list):
        raise ValueError("ECM catalog 'ecms' must be a list")
    return ECMCatalog([ECMEntry.model_validate(row) for row in rows])


@lru_cache(maxsize=1)
def _default_catalog() -> ECMCatalog:
    return _read_catalog(CATALOG_PATH)


def load_catalog(path: str | Path | None = None) -> ECMCatalog:
    """Load and validate the default or an explicitly supplied catalog."""

    return _default_catalog() if path is None else _read_catalog(Path(path))


def list_ecms(*, category: str | None = None) -> list[ECMEntry]:
    return load_catalog().list(category=category)


def get_ecm(ecm_id: str) -> ECMEntry:
    return load_catalog().get(ecm_id)
