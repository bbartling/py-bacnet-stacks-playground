"""Validated input contracts for the school deep-retrofit rehearsal.

Pydantic v2 models that reject malformed weather requests, utility bill data,
and retrofit scenarios *before* any files are written or simulations run:

- ``WeatherRequest``     — Open-Meteo archive request bound for the AMY EPW flow.
- ``WeatherDatasetMeta`` — provenance metadata for a downloaded weather dataset.
- ``UtilityBillRecord``  — one monthly bill with fuel/unit pairing rules.
- ``UtilityDataset``     — exactly 12 consecutive months of single-fuel bills.
- ``RetrofitScenario``   — measure bundle with explicit conceptual-surrogate flag.
"""

from __future__ import annotations

import re
from calendar import isleap
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Open-Meteo archive hourly variables the AMY EPW builder needs
# (dry bulb, dew point, RH, pressure, GHI/DNI/DHI, wind — see wattlab/weather/epw.py).
EPW_REQUIRED_VARIABLES: frozenset[str] = frozenset(
    {
        "temperature_2m",
        "dew_point_2m",
        "relative_humidity_2m",
        "surface_pressure",
        "shortwave_radiation",
        "direct_normal_irradiance",
        "diffuse_radiation",
        "wind_speed_10m",
        "wind_direction_10m",
    }
)

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

FuelKind = Literal["electricity", "gas"]
UnitKind = Literal["kwh", "mcf", "therm"]

_FUEL_UNITS: dict[str, set[str]] = {
    "electricity": {"kwh"},
    "gas": {"mcf", "therm"},
}


def _check_date_order(start: date, end: date) -> None:
    if start > end:
        raise ValueError(
            f"start_date {start.isoformat()} must be on or before "
            f"end_date {end.isoformat()}"
        )


def _require_utc(value: str) -> str:
    if value != "UTC":
        raise ValueError(
            f"timezone must be 'UTC' for the EPW flow (got {value!r}); "
            "archive observations are validated in UTC, then shifted to "
            "local standard time before EPW rows are written"
        )
    return value


def _validate_epw_variables(variables: list[str]) -> list[str]:
    deduplicated = list(dict.fromkeys(variables))
    missing = EPW_REQUIRED_VARIABLES - set(deduplicated)
    if missing:
        raise ValueError(
            "variables insufficient for EPW generation; missing: "
            + ", ".join(sorted(missing))
        )
    return deduplicated


class WeatherRequest(BaseModel):
    """Request for actual-year hourly weather feeding the AMY EPW flow."""

    model_config = ConfigDict(extra="forbid")

    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start_date: date
    end_date: date
    timezone: str = "UTC"
    variables: list[str] = Field(
        default_factory=lambda: sorted(EPW_REQUIRED_VARIABLES)
    )
    # When True, a response covering fewer hours than the requested span is
    # accepted (e.g. an in-progress year); annual EPW builds still reject it.
    allow_partial: bool = False

    @field_validator("timezone")
    @classmethod
    def _timezone_must_be_utc(cls, v: str) -> str:
        return _require_utc(v)

    @field_validator("variables")
    @classmethod
    def _variables_cover_epw(cls, v: list[str]) -> list[str]:
        return _validate_epw_variables(v)

    @model_validator(mode="after")
    def _date_order(self) -> "WeatherRequest":
        _check_date_order(self.start_date, self.end_date)
        return self


class WeatherDatasetMeta(BaseModel):
    """Provenance metadata for a downloaded/cached weather dataset."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(min_length=1)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    start_date: date
    end_date: date
    timezone: str = "UTC"
    variables: list[str]
    rows: int = Field(gt=0)
    sha256: str
    cached_path: str | None = None
    downloaded_at_utc: datetime | None = None

    @field_validator("timezone")
    @classmethod
    def _timezone_must_be_utc(cls, v: str) -> str:
        return _require_utc(v)

    @field_validator("variables")
    @classmethod
    def _variables_cover_epw(cls, v: list[str]) -> list[str]:
        return _validate_epw_variables(v)

    @field_validator("sha256")
    @classmethod
    def _sha256_hex(cls, v: str) -> str:
        if not _SHA256_RE.match(v):
            raise ValueError(
                "sha256 must be 64 lowercase hex characters "
                f"(got {len(v)} chars)"
            )
        return v

    @model_validator(mode="after")
    def _date_order(self) -> "WeatherDatasetMeta":
        _check_date_order(self.start_date, self.end_date)
        if (
            self.start_date == date(self.start_date.year, 1, 1)
            and self.end_date == date(self.start_date.year, 12, 31)
        ):
            expected_rows = 8784 if isleap(self.start_date.year) else 8760
            if self.rows != expected_rows:
                raise ValueError(
                    f"full calendar year {self.start_date.year} requires "
                    f"exactly {expected_rows} hourly rows (got {self.rows})"
                )
        return self


class UtilityBillRecord(BaseModel):
    """One monthly utility bill for a single fuel."""

    model_config = ConfigDict(extra="forbid")

    month: str
    fuel: FuelKind
    unit: UnitKind
    usage: float = Field(ge=0)
    cost_usd: float | None = Field(default=None, ge=0)
    demand_kw: float | None = Field(default=None, ge=0)

    @field_validator("month")
    @classmethod
    def _month_format(cls, v: str) -> str:
        if not _MONTH_RE.match(v):
            raise ValueError(
                f"month must be 'YYYY-MM' with MM in 01..12 (got {v!r})"
            )
        return v

    @model_validator(mode="after")
    def _fuel_unit_pair(self) -> "UtilityBillRecord":
        allowed = _FUEL_UNITS[self.fuel]
        if self.unit not in allowed:
            raise ValueError(
                f"unit {self.unit!r} invalid for fuel {self.fuel!r}; "
                f"allowed: {sorted(allowed)}"
            )
        return self


def _month_index(month: str) -> int:
    year, mon = month.split("-")
    return int(year) * 12 + int(mon)


class UtilityDataset(BaseModel):
    """Exactly 12 consecutive months of bills for one fuel and one building."""

    model_config = ConfigDict(extra="forbid")

    bills: list[UtilityBillRecord]
    floor_area_sqft: float = Field(gt=0)
    provenance: Literal["actual", "synthetic_rehearsal"]

    @model_validator(mode="after")
    def _bills_are_12_consecutive_single_fuel(self) -> "UtilityDataset":
        if len(self.bills) != 12:
            raise ValueError(
                f"UtilityDataset requires exactly 12 monthly bills "
                f"(got {len(self.bills)})"
            )
        fuels = {b.fuel for b in self.bills}
        if len(fuels) > 1:
            raise ValueError(
                f"all bills must share one fuel (got {sorted(fuels)}); "
                "use one UtilityDataset per fuel"
            )
        units = {b.unit for b in self.bills}
        if len(units) > 1:
            raise ValueError(
                f"all bills must share one unit (got {sorted(units)}); "
                "convert bills to a consistent unit before validation"
            )
        months = [b.month for b in self.bills]
        dupes = sorted({m for m in months if months.count(m) > 1})
        if dupes:
            raise ValueError(f"duplicate bill months: {', '.join(dupes)}")
        idx = sorted(_month_index(m) for m in months)
        if idx[-1] - idx[0] != 11:
            present = set(idx)
            gap_names = [
                f"{(g - 1) // 12:04d}-{(g - 1) % 12 + 1:02d}"
                for g in range(idx[0], idx[-1])
                if g not in present
            ]
            raise ValueError(
                "bill months must be consecutive; missing: "
                + ", ".join(gap_names[:12])
            )
        return self


class RetrofitScenario(BaseModel):
    """A named bundle of retrofit measures for multi-year analysis."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    measure_ids: list[str] = Field(min_length=1)
    scenario_kind: Literal["hydronic_renewal", "electrification"]
    analysis_years: int = Field(default=30, ge=1, le=40)
    # No default on purpose: callers must state whether equipment swaps are
    # EnergyPlus simulation surrogates rather than construction-ready designs.
    conceptual_surrogate: bool

    @field_validator("name")
    @classmethod
    def _name_nonblank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("name must not be blank")
        return stripped

    @field_validator("measure_ids")
    @classmethod
    def _measures_nonblank_unique(cls, v: list[str]) -> list[str]:
        stripped = [m.strip() for m in v]
        if any(not m for m in stripped):
            raise ValueError("measure_ids must not contain blank entries")
        if len(set(stripped)) != len(stripped):
            dupes = sorted({m for m in stripped if stripped.count(m) > 1})
            raise ValueError(
                f"measure_ids must be unique; duplicates: {', '.join(dupes)}"
            )
        return stripped
