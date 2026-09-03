"""Pydantic contracts for studio IDF / EPW / tariff uploads."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _yes_no(value: str) -> bool:
    token = value.strip().split("!")[0].strip().rstrip(",;").lower()
    if token in {"yes", "y", "true", "1"}:
        return True
    if token in {"no", "n", "false", "0", ""}:
        return False
    raise ValueError(f"expected Yes/No, got {value!r}")


class SimulationControlFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_sizing: bool = False
    system_sizing: bool = False
    plant_sizing: bool = False
    hvac_sizing_simulation: bool = False

    @property
    def any_autosize_control(self) -> bool:
        return self.zone_sizing or self.system_sizing or self.plant_sizing or self.hvac_sizing_simulation


class CoilRating(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    object_type: str
    rated_w: float | None = None
    rated_cop: float | None = None
    autosized: bool = False


class EnvelopeMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    n_surfaces: int
    n_zones: int
    n_fenestration: int
    floor_m2: float
    floor_ft2: float
    wall_m2: float
    window_m2: float
    roof_m2: float
    wwr: float | None = None
    wwr_pct: float | None = None
    bbox_ft_dx: float | None = None
    bbox_ft_dy: float | None = None
    bbox_ft_dz: float | None = None


class IdfDashboard(BaseModel):
    """Energy-modeler snapshot of an uploaded or bundled IDF."""

    model_config = ConfigDict(extra="forbid")

    source_name: str
    version: str | None = None
    building_name: str | None = None
    timestep: int | None = None
    north_axis_deg: float | None = None
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    elevation_m: float | None = None
    zone_names: list[str] = Field(default_factory=list)
    equipment_types: list[str] = Field(default_factory=list)
    simulation_control: SimulationControlFlags
    envelope: EnvelopeMetrics
    coils: list[CoilRating] = Field(default_factory=list)
    autosized_field_count: int = 0
    hvac_autosize: bool = False
    cooling_capacity_w: float | None = None
    heating_capacity_w: float | None = None
    cooling_tons: float | None = None

    @property
    def cooling_capacity_ton(self) -> float | None:
        return self.cooling_tons


class OutdoorDay(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    month: int
    day: int
    drybulb_c: list[float]
    drybulb_f: list[float]
    location: str | None = None

    @field_validator("drybulb_c", "drybulb_f")
    @classmethod
    def _len_24(cls, values: list[float]) -> list[float]:
        if len(values) != 24:
            raise ValueError("outdoor day must have 24 hourly values")
        return values


class TariffUpload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_name: str
    intervals: int
    rates_usd_per_kwh: list[float]

    @field_validator("rates_usd_per_kwh")
    @classmethod
    def _positive_rates(cls, values: list[float]) -> list[float]:
        if len(values) not in {24, 96, 288}:
            raise ValueError("tariff must have 24, 96, or 288 interval rates")
        if any(v < 0 for v in values):
            raise ValueError("rates must be non-negative")
        return values
