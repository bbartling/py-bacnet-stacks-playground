"""Author an evidence-bounded, runnable Building 59 screening seed.

The generated IDF is intentionally labelled ``OFFICE_SCREENING_SEED_UNCALIBRATED``.
It is useful for exercising the EnergyPlus pipeline and for sensitivity-screening
work after a reviewer accepts its assumptions.  It is not the as-built Building
59 model and must not be promoted to a calibration or DSM baseline.

Only a few published quantities are treated as source facts here: two monitored
office floors totaling 4,650 m2, four RTU service groups, and the reported
per-RTU 20,000 cfm supply flow, 5,000 cfm minimum outdoor air, 30 ton cooling,
20 hp supply fan, and 7.5 hp return fan.  Geometry, constructions, windows,
internal loads, schedules, and equipment performance are visibly bounded
screening assumptions.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import ClassVar, Iterable, Literal, Sequence

CLAIM_LABEL = "OFFICE_SCREENING_SEED_UNCALIBRATED"
ENERGYPLUS_VERSION = "26.1"
DEFAULT_SIMULATION_YEAR = 2020
FLOOR_LENGTH_M = 93.0
FLOOR_DEPTH_M = 25.0
OFFICE_FLOORS = (3, 4)
RTU_GROUPS = (1, 2, 3, 4)
SEGMENTS = (
    ("SOUTH_PERIMETER", 0.0, 5.0),
    ("CORE", 5.0, 20.0),
    ("NORTH_PERIMETER", 20.0, 25.0),
)
PLENUM_HEIGHT_M = 0.6
OCCUPIED_HEIGHT_M = 3.4

CFM_TO_M3_S = 0.00047194745
TON_TO_W = 3516.85284
DX_MIN_AIRFLOW_PER_CAPACITY_M3_S_W = 4.027e-5
DX_MAX_AIRFLOW_PER_CAPACITY_M3_S_W = 6.041e-5


@dataclass(frozen=True)
class PublishedRTURatings:
    """Immutable source evidence; these are not all direct simulation inputs."""

    supply_flow_cfm: float = 20_000.0
    minimum_outdoor_air_cfm: float = 5_000.0
    cooling_tons: float = 30.0
    supply_fan_motor_hp: float = 20.0
    return_fan_motor_hp: float = 7.5

    @property
    def supply_flow_m3_s(self) -> float:
        return self.supply_flow_cfm * CFM_TO_M3_S

    @property
    def minimum_outdoor_air_m3_s(self) -> float:
        return self.minimum_outdoor_air_cfm * CFM_TO_M3_S

    @property
    def cooling_capacity_w(self) -> float:
        return self.cooling_tons * TON_TO_W


PUBLISHED_RTU_RATINGS = PublishedRTURatings()

# Backward-compatible, explicitly published values.  The packaged-DX proxy
# uses a separate coil airflow below because 20,000 cfm / 30 ton is outside the
# EnergyPlus TwoSpeedDX rated airflow-per-capacity domain.  The reported
# 20,000 cfm is retained as the fan upper rating, not silently forced through
# the proxy coil.
RTU_SUPPLY_FLOW_M3_S = PUBLISHED_RTU_RATINGS.supply_flow_m3_s
RTU_MINIMUM_OA_M3_S = PUBLISHED_RTU_RATINGS.minimum_outdoor_air_m3_s
RTU_COOLING_CAPACITY_W = PUBLISHED_RTU_RATINGS.cooling_capacity_w
RTU_SUPPLY_FAN_HP = PUBLISHED_RTU_RATINGS.supply_fan_motor_hp
RTU_RETURN_FAN_HP = PUBLISHED_RTU_RATINGS.return_fan_motor_hp


@dataclass(frozen=True)
class B59CalibrationParameters:
    """Bounded screening/calibration inputs; geometry and scope are excluded.

    Bounds are engineering priors, not confidence intervals.  A value can be
    called calibrated only after the repository's evidence, identifiability,
    and holdout gates pass.
    """

    people_area_per_person_m2: float = 20.0
    lighting_w_m2: float = 8.0
    equipment_w_m2: float = 10.0
    wall_thermal_resistance_m2_k_w: float = 2.5
    roof_thermal_resistance_m2_k_w: float = 5.3
    glazing_u_w_m2_k: float = 2.0
    glazing_shgc: float = 0.35
    infiltration_m3_s_m2: float = 0.0003
    measured_south_lighting_fraction: float = 0.50
    weekday_occupancy_start_hour: float = 8.0
    weekday_occupancy_end_hour: float = 18.0
    weekday_hvac_start_hour: float = 5.0
    weekday_hvac_end_hour: float = 22.0
    hvac_availability_mode: Literal["weekday_window", "continuous"] = "weekday_window"
    occupancy_calendar_mode: Literal["generic", "pandemic_2020"] = "pandemic_2020"
    post_march17_people_multiplier: float = 0.25
    post_march17_lighting_multiplier: float = 0.561 / 2.048
    post_march17_equipment_multiplier: float = 2.207 / 9.054
    # Compact schedule fractions. Defaults preserve historical screening (0.05).
    # Measured 2018 weekday/weekend medians support higher MEL standby/weekend
    # and ~0.17 lighting weekend scale (see config/b59_schedule_priors.json).
    people_standby_fraction: float = 0.05
    people_weekend_fraction: float = 0.05
    lights_standby_fraction: float = 0.05
    lights_weekend_fraction: float = 0.05
    mel_standby_fraction: float = 0.05
    mel_weekend_fraction: float = 0.05
    occupied_heating_setpoint_c: float = 21.0
    occupied_cooling_setpoint_c: float = 24.0
    unoccupied_heating_setpoint_c: float = 15.6
    unoccupied_cooling_setpoint_c: float = 29.4
    supply_fan_pressure_pa: float = 1100.0
    supply_fan_total_efficiency: float = 0.70
    return_fan_pressure_pa: float = 415.0
    return_fan_total_efficiency: float = 0.70
    cooling_cop: float = 3.0
    cooling_capacity_w: float = RTU_COOLING_CAPACITY_W
    cooling_shr: float = 0.75
    coil_airflow_m3_s: float = 12_000.0 * CFM_TO_M3_S
    minimum_outdoor_air_m3_s: float = RTU_MINIMUM_OA_M3_S
    # PackagedVAV cooling supply-air setpoint. Historical screening used a
    # hard-coded 14.4 C (57.9 F); measured RTU SAT SP medians are ~18.7–20 C.
    supply_air_temperature_setpoint_c: float = 14.4

    BOUNDS: ClassVar[dict[str, tuple[float, float, str]]] = {
        "people_area_per_person_m2": (10.0, 35.0, "m2/person"),
        # Lower floor opened for evidence-backed dial-in toward measured lig_S /
        # MEL annual kWh (screening champion over-predicted both end uses).
        "lighting_w_m2": (2.5, 14.0, "W/m2"),
        "equipment_w_m2": (4.0, 20.0, "W/m2"),
        "wall_thermal_resistance_m2_k_w": (1.5, 5.0, "m2-K/W"),
        "roof_thermal_resistance_m2_k_w": (3.5, 8.0, "m2-K/W"),
        "glazing_u_w_m2_k": (1.2, 3.5, "W/m2-K"),
        "glazing_shgc": (0.20, 0.55, "fraction"),
        "infiltration_m3_s_m2": (0.0001, 0.0010, "m3/s-m2"),
        "measured_south_lighting_fraction": (0.25, 0.75, "fraction"),
        "weekday_occupancy_start_hour": (6.0, 10.0, "hour"),
        "weekday_occupancy_end_hour": (15.0, 21.0, "hour"),
        "weekday_hvac_start_hour": (4.0, 8.0, "hour"),
        "weekday_hvac_end_hour": (17.0, 23.0, "hour"),
        "post_march17_people_multiplier": (0.10, 0.50, "fraction"),
        "post_march17_lighting_multiplier": (0.20, 0.40, "fraction"),
        "post_march17_equipment_multiplier": (0.15, 0.40, "fraction"),
        "people_standby_fraction": (0.0, 0.20, "fraction"),
        "people_weekend_fraction": (0.0, 0.20, "fraction"),
        "lights_standby_fraction": (0.02, 0.30, "fraction"),
        "lights_weekend_fraction": (0.05, 0.30, "fraction"),
        "mel_standby_fraction": (0.05, 0.55, "fraction"),
        "mel_weekend_fraction": (0.05, 0.80, "fraction"),
        "occupied_heating_setpoint_c": (19.0, 22.0, "C"),
        "occupied_cooling_setpoint_c": (23.0, 27.0, "C"),
        "unoccupied_heating_setpoint_c": (12.0, 18.0, "C"),
        "unoccupied_cooling_setpoint_c": (27.0, 32.0, "C"),
        "supply_fan_pressure_pa": (600.0, 1500.0, "Pa"),
        "supply_fan_total_efficiency": (0.55, 0.82, "fraction"),
        "return_fan_pressure_pa": (200.0, 700.0, "Pa"),
        "return_fan_total_efficiency": (0.55, 0.82, "fraction"),
        "cooling_cop": (2.5, 4.5, "W/W"),
        "cooling_capacity_w": (0.90 * RTU_COOLING_CAPACITY_W, 1.50 * RTU_COOLING_CAPACITY_W, "W"),
        "cooling_shr": (0.65, 0.85, "fraction"),
        "coil_airflow_m3_s": (10_500.0 * CFM_TO_M3_S, 13_500.0 * CFM_TO_M3_S, "m3/s"),
        "minimum_outdoor_air_m3_s": (0.75 * RTU_MINIMUM_OA_M3_S, 1.10 * RTU_MINIMUM_OA_M3_S, "m3/s"),
        "supply_air_temperature_setpoint_c": (12.0, 22.0, "C"),
    }
    HVAC_AVAILABILITY_MODES: ClassVar[tuple[str, ...]] = ("weekday_window", "continuous")
    OCCUPANCY_CALENDAR_MODES: ClassVar[tuple[str, ...]] = ("generic", "pandemic_2020")

    def __post_init__(self) -> None:
        for name, (lower, upper, units) in self.BOUNDS.items():
            value = getattr(self, name)
            if not math.isfinite(value) or not lower <= value <= upper:
                raise ValueError(f"{name}={value!r} is outside [{lower}, {upper}] {units}")
        if self.weekday_hvac_start_hour >= self.weekday_hvac_end_hour:
            raise ValueError("weekday HVAC start must precede end")
        if self.weekday_occupancy_start_hour >= self.weekday_occupancy_end_hour:
            raise ValueError("weekday occupancy start must precede end")
        if self.weekday_hvac_start_hour > self.weekday_occupancy_start_hour:
            raise ValueError("weekday HVAC must start no later than occupancy")
        if self.weekday_hvac_end_hour <= self.weekday_occupancy_end_hour:
            raise ValueError("weekday HVAC must end after occupancy")
        for name in (
            "weekday_occupancy_start_hour",
            "weekday_occupancy_end_hour",
            "weekday_hvac_start_hour",
            "weekday_hvac_end_hour",
        ):
            if not math.isclose(getattr(self, name) * 4.0, round(getattr(self, name) * 4.0)):
                raise ValueError(f"{name} must align to the 15-minute EnergyPlus timestep")
        if self.hvac_availability_mode not in self.HVAC_AVAILABILITY_MODES:
            raise ValueError("hvac_availability_mode must be one of " + ", ".join(self.HVAC_AVAILABILITY_MODES))
        if self.occupancy_calendar_mode not in self.OCCUPANCY_CALENDAR_MODES:
            raise ValueError("occupancy_calendar_mode must be one of " + ", ".join(self.OCCUPANCY_CALENDAR_MODES))
        if self.occupied_heating_setpoint_c >= self.occupied_cooling_setpoint_c:
            raise ValueError("occupied heating setpoint must be below cooling setpoint")
        airflow_per_capacity = self.coil_airflow_m3_s / self.cooling_capacity_w
        if not (DX_MIN_AIRFLOW_PER_CAPACITY_M3_S_W <= airflow_per_capacity <= DX_MAX_AIRFLOW_PER_CAPACITY_M3_S_W):
            raise ValueError(
                "coil_airflow_m3_s / cooling_capacity_w is outside the EnergyPlus TwoSpeedDX rated performance domain"
            )

    def manifest(self) -> dict[str, dict[str, object]]:
        manifest: dict[str, dict[str, object]] = {
            name: {"value": getattr(self, name), "lower": lower, "upper": upper, "units": units}
            for name, (lower, upper, units) in self.BOUNDS.items()
        }
        manifest["hvac_availability_mode"] = {
            "value": self.hvac_availability_mode,
            "choices": list(self.HVAC_AVAILABILITY_MODES),
            "kind": "discrete_hypothesis",
        }
        manifest["occupancy_calendar_mode"] = {
            "value": self.occupancy_calendar_mode,
            "choices": list(self.OCCUPANCY_CALENDAR_MODES),
            "kind": "discrete_hypothesis",
        }
        return manifest


DEFAULT_CALIBRATION_PARAMETERS = B59CalibrationParameters()
OutputProfile = Literal["lean", "diagnostic"]
METER_LIGHTING_SOUTH = "B59:MeterBound:LightingSouth"
METER_LIGHTING_NORTH_UNMETERED = "B59:Unmetered:LightingNorth"
METER_MELS = "B59:MeterBound:MELsSouthPlusNorth"
METER_MODEL_HVAC = "B59:MappedRTU:FansPlusCooling"
METER_TERMINAL_HEAT_UNRESOLVED = "B59:Unresolved:ElectricTerminalReheat"
METER_PARTIAL_TARGET_PROXY = "B59:ScopeAudit:PartialMeterBoundProxy"

UNMATCHED_TOPOLOGY = (
    "The rectangular 93 m by 25 m footprint, orientation, zoning, windows, and constructions are screening assumptions.",
    "Each RTU service group is represented by six aggregate occupied zones, not the documented 57-zone/50-UFT map.",
    "Segmented supply plenums approximate UFAD delivery; stratification, diffuser induction, leakage, and raised-floor details are not resolved.",
    "PackagedVAV TwoSpeedDX is air-cooled; the documented water-cooled DX condenser loop and shared HPC cooling towers are not represented.",
    "Electric terminal reheat is an all-electric load proxy, not the documented hydronic UFT and heat-pump plant.",
    "The four template air loops use identical schedules and curves but do not reproduce the documented common fan-speed controller.",
    "The published 20,000 cfm fan rating exceeds the packaged-DX airflow domain at 30 tons; proxy coil airflow is bounded at 10,500-13,500 cfm and the exact candidate value is recorded separately.",
    "The weekday schedule and all internal-load, envelope, glazing, infiltration, thermostat, COP, and fan-pressure values require data binding.",
    "No NERSC floor, mechanical floor, shared heat rejection, tariff, actual-year weather, or historical control-regime transition is modeled.",
)


@dataclass(frozen=True)
class ZoneSpec:
    """One occupied aggregate zone and its dedicated UFAD plenum segment."""

    floor: int
    rtu_group: int
    segment: str
    x0: float
    x1: float
    y0: float
    y1: float
    plenum_z0: float
    occupied_z0: float
    occupied_z1: float

    @property
    def name(self) -> str:
        return f"F{self.floor}_RTU{self.rtu_group}_{self.segment}"

    @property
    def plenum_name(self) -> str:
        return f"{self.name}_UFAD_PLENUM"

    @property
    def area_m2(self) -> float:
        return (self.x1 - self.x0) * (self.y1 - self.y0)

    @property
    def rtu_name(self) -> str:
        return f"B59_RTU_{self.rtu_group}"


def screening_zone_specs() -> tuple[ZoneSpec, ...]:
    """Return the deterministic two-floor/four-service-group zone layout."""

    group_width = FLOOR_LENGTH_M / len(RTU_GROUPS)
    zones: list[ZoneSpec] = []
    for floor_index, floor in enumerate(OFFICE_FLOORS):
        floor_base = floor_index * (PLENUM_HEIGHT_M + OCCUPIED_HEIGHT_M)
        for rtu_group in RTU_GROUPS:
            x0 = (rtu_group - 1) * group_width
            x1 = rtu_group * group_width
            for segment, y0, y1 in SEGMENTS:
                zones.append(
                    ZoneSpec(
                        floor=floor,
                        rtu_group=rtu_group,
                        segment=segment,
                        x0=x0,
                        x1=x1,
                        y0=y0,
                        y1=y1,
                        plenum_z0=floor_base,
                        occupied_z0=floor_base + PLENUM_HEIGHT_M,
                        occupied_z1=floor_base + PLENUM_HEIGHT_M + OCCUPIED_HEIGHT_M,
                    )
                )
    return tuple(zones)


def screening_seed_summary(
    parameters: B59CalibrationParameters = DEFAULT_CALIBRATION_PARAMETERS,
    *,
    simulation_year: int = DEFAULT_SIMULATION_YEAR,
) -> dict[str, object]:
    """Return machine-checkable scope and claim-boundary metadata."""

    _validate_simulation_year(simulation_year)
    zones = screening_zone_specs()
    return {
        "schema": "vibe23.b59_screening_seed.v1",
        "claim_label": CLAIM_LABEL,
        "energyplus_version": ENERGYPLUS_VERSION,
        "simulation_year": simulation_year,
        "modeled_scope": "two monitored office floors only",
        "office_floor_count": len(OFFICE_FLOORS),
        "office_floor_area_each_m2": FLOOR_LENGTH_M * FLOOR_DEPTH_M,
        "office_floor_area_total_m2": sum(zone.area_m2 for zone in zones),
        "rtu_service_group_count": len(RTU_GROUPS),
        "occupied_zone_count": len(zones),
        "ufad_plenum_zone_count": len(zones),
        "segments_per_rtu_per_floor": [name for name, _, _ in SEGMENTS],
        "rtu_published_seed_values": {
            "supply_flow_cfm": PUBLISHED_RTU_RATINGS.supply_flow_cfm,
            "supply_flow_m3_s": RTU_SUPPLY_FLOW_M3_S,
            "minimum_outdoor_air_cfm": PUBLISHED_RTU_RATINGS.minimum_outdoor_air_cfm,
            "minimum_outdoor_air_m3_s": RTU_MINIMUM_OA_M3_S,
            "cooling_tons": PUBLISHED_RTU_RATINGS.cooling_tons,
            "cooling_capacity_w": RTU_COOLING_CAPACITY_W,
            "supply_fan_motor_hp": RTU_SUPPLY_FAN_HP,
            "return_fan_motor_hp": RTU_RETURN_FAN_HP,
        },
        "rtu_simulation_proxy": {
            "coil_airflow_m3_s": parameters.coil_airflow_m3_s,
            "coil_airflow_cfm": parameters.coil_airflow_m3_s / CFM_TO_M3_S,
            "cooling_capacity_w": parameters.cooling_capacity_w,
            "cooling_shr": parameters.cooling_shr,
            "minimum_outdoor_air_m3_s": parameters.minimum_outdoor_air_m3_s,
            "supply_fan_pressure_pa": parameters.supply_fan_pressure_pa,
            "supply_fan_total_efficiency": parameters.supply_fan_total_efficiency,
            "return_fan_pressure_pa": parameters.return_fan_pressure_pa,
            "return_fan_total_efficiency": parameters.return_fan_total_efficiency,
            "rationale": (
                "Packaged TwoSpeedDX uses a bounded nominal coil airflow near 400 cfm/ton; "
                "the published 20,000 cfm remains an immutable fan-system rating because "
                "forcing 667 cfm/ton through the proxy coil violates its performance domain. "
                "Fan pressures and efficiencies remain calibratable proxies because published "
                "motor hp does not establish coincident shaft power or system pressure rise."
            ),
        },
        "calibration_parameters": parameters.manifest(),
        "immutable_geometry_scope": {
            "floor_length_m": FLOOR_LENGTH_M,
            "floor_depth_m": FLOOR_DEPTH_M,
            "office_floors": list(OFFICE_FLOORS),
            "rtu_groups": list(RTU_GROUPS),
            "segments": [name for name, _, _ in SEGMENTS],
        },
        "meter_scope": {
            "measured_target_formula": "mels_S + mels_N + lig_S + hvac_S + hvac_N",
            "facility_total_comparison_allowed": False,
            "guideline14_claim_eligible": False,
            "model_output_mapping": {
                "mels_S_plus_mels_N": METER_MELS,
                "lig_S_proxy": METER_LIGHTING_SOUTH,
                "lig_N_unmetered_heat_gain": METER_LIGHTING_NORTH_UNMETERED,
                "mapped_rtu_fans_plus_cooling": METER_MODEL_HVAC,
                "unresolved_terminal_heat": METER_TERMINAL_HEAT_UNRESOLVED,
                "partial_target_proxy": METER_PARTIAL_TARGET_PROXY,
            },
            "dispositions": {
                "north_lighting": (
                    "Retained as a separately metered simulation heat gain but excluded from "
                    "the measured-target proxy because lig_N is absent."
                ),
                "elevators": (
                    "The measured HVAC panels include elevators; this seed has no elevator load. "
                    "Subtract measured elevator energy or add a bound elevator model before a claim."
                ),
                "terminal_heat": (
                    "Electric VAV terminal reheat is reported separately and excluded from the "
                    "target proxy; the documented UFT/heat-pump topology is hydronic and the "
                    "ASHP meter is separate."
                ),
                "ashp_wshp": (
                    "ASHP/WSHP electricity may be separately metered and its inclusion in the "
                    "target is unresolved; fail the claim until panel mapping is proven."
                ),
            },
        },
        "unmatched_topology": list(UNMATCHED_TOPOLOGY),
        "zone_specs": [asdict(zone) | {"name": zone.name, "area_m2": zone.area_m2} for zone in zones],
    }


def _fmt(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.8g}"
    return str(value)


def _validate_simulation_year(simulation_year: int) -> None:
    if isinstance(simulation_year, bool) or not isinstance(simulation_year, int):
        raise TypeError("simulation_year must be an integer")
    if not 1900 <= simulation_year <= 2100:
        raise ValueError("simulation_year must be between 1900 and 2100")


def _object(object_type: str, fields: Sequence[object]) -> str:
    lines = [f"{object_type},"]
    for index, field in enumerate(fields):
        terminator = ";" if index == len(fields) - 1 else ","
        lines.append(f"  {_fmt(field)}{terminator}")
    return "\n".join(lines)


def _vertices(values: Iterable[tuple[float, float, float]]) -> list[object]:
    points = list(values)
    fields: list[object] = [len(points)]
    for x, y, z in points:
        fields.extend((x, y, z))
    return fields


def _surface(
    *,
    name: str,
    surface_type: str,
    construction: str,
    zone: str,
    boundary: str,
    vertices: Sequence[tuple[float, float, float]],
) -> str:
    outside = boundary == "Outdoors"
    return _object(
        "BuildingSurface:Detailed",
        [
            name,
            surface_type,
            construction,
            zone,
            "",
            boundary,
            "",
            "SunExposed" if outside else "NoSun",
            "WindExposed" if outside else "NoWind",
            "autocalculate",
            *_vertices(vertices),
        ],
    )


def _box_surfaces(zone: ZoneSpec, *, plenum: bool) -> list[str]:
    name = zone.plenum_name if plenum else zone.name
    z0 = zone.plenum_z0 if plenum else zone.occupied_z0
    z1 = zone.occupied_z0 if plenum else zone.occupied_z1
    x0, x1, y0, y1 = zone.x0, zone.x1, zone.y0, zone.y1
    walls = {
        "SOUTH": ((x0, y0, z1), (x0, y0, z0), (x1, y0, z0), (x1, y0, z1)),
        "EAST": ((x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)),
        "NORTH": ((x1, y1, z1), (x1, y1, z0), (x0, y1, z0), (x0, y1, z1)),
        "WEST": ((x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1)),
    }
    boundaries = {
        "SOUTH": y0 == 0.0,
        "EAST": x1 == FLOOR_LENGTH_M,
        "NORTH": y1 == FLOOR_DEPTH_M,
        "WEST": x0 == 0.0,
    }
    result: list[str] = []
    for direction, points in walls.items():
        outside = boundaries[direction]
        result.append(
            _surface(
                name=f"{name}_{direction}_WALL",
                surface_type="Wall",
                construction="SCREENING_EXTERIOR_WALL" if outside else "SCREENING_INTERIOR",
                zone=name,
                boundary="Outdoors" if outside else "Adiabatic",
                vertices=points,
            )
        )
    result.append(
        _surface(
            name=f"{name}_FLOOR",
            surface_type="Floor",
            construction="SCREENING_FLOOR",
            zone=name,
            boundary="Adiabatic",
            vertices=((x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)),
        )
    )
    is_roof = not plenum and zone.floor == max(OFFICE_FLOORS)
    result.append(
        _surface(
            name=f"{name}_CEILING",
            surface_type="Roof" if is_roof else "Ceiling",
            construction="SCREENING_ROOF" if is_roof else "SCREENING_INTERIOR",
            zone=name,
            boundary="Outdoors" if is_roof else "Adiabatic",
            vertices=((x0, y1, z1), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1)),
        )
    )
    return result


def _window(zone: ZoneSpec, direction: str) -> str:
    """Create a 40%-of-wall-area screening window on one exterior wall."""

    z0 = zone.occupied_z0 + 0.85
    z1 = zone.occupied_z1 - 0.85
    if direction in {"SOUTH", "NORTH"}:
        inset = 0.1 * (zone.x1 - zone.x0)
        lo, hi = zone.x0 + inset, zone.x1 - inset
        if direction == "SOUTH":
            points = ((lo, zone.y0, z1), (lo, zone.y0, z0), (hi, zone.y0, z0), (hi, zone.y0, z1))
        else:
            points = ((hi, zone.y1, z1), (hi, zone.y1, z0), (lo, zone.y1, z0), (lo, zone.y1, z1))
    else:
        inset = 0.1 * (zone.y1 - zone.y0)
        lo, hi = zone.y0 + inset, zone.y1 - inset
        if direction == "EAST":
            points = ((zone.x1, lo, z1), (zone.x1, lo, z0), (zone.x1, hi, z0), (zone.x1, hi, z1))
        else:
            points = ((zone.x0, hi, z1), (zone.x0, hi, z0), (zone.x0, lo, z0), (zone.x0, lo, z1))
    return _object(
        "FenestrationSurface:Detailed",
        [
            f"{zone.name}_{direction}_WINDOW",
            "Window",
            "SCREENING_WINDOW",
            f"{zone.name}_{direction}_WALL",
            "",
            "autocalculate",
            "",
            1,
            *_vertices(points),
        ],
    )


def _schedule_time(hour: float) -> str:
    total_minutes = round(hour * 60)
    return f"Until: {total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _schedules(parameters: B59CalibrationParameters) -> list[str]:
    occupancy_start = _schedule_time(parameters.weekday_occupancy_start_hour)
    occupancy_end = _schedule_time(parameters.weekday_occupancy_end_hour)
    hvac_start = _schedule_time(parameters.weekday_hvac_start_hour)
    hvac_end = _schedule_time(parameters.weekday_hvac_end_hour)

    def load_schedule(
        name: str,
        post_multiplier: float,
        *,
        standby: float,
        weekend: float,
        shoulder: float = 0.25,
    ) -> str:
        def period(through: str, multiplier: float) -> list[object]:
            return [
                through,
                "For: SummerDesignDay WinterDesignDay",
                "Until: 24:00",
                standby,
                "For: Weekdays",
                occupancy_start,
                standby * multiplier,
                occupancy_end,
                1.0 * multiplier,
                hvac_end,
                shoulder * multiplier,
                "Until: 24:00",
                standby * multiplier,
                "For: Weekends Holidays",
                "Until: 24:00",
                weekend * multiplier,
                "For: AllOtherDays",
                "Until: 24:00",
                weekend * multiplier,
            ]

        fields: list[object] = [name, "FRACTION"]
        if parameters.occupancy_calendar_mode == "pandemic_2020":
            fields.extend(period("Through: 3/17", 1.0))
            fields.extend(period("Through: 12/31", post_multiplier))
        else:
            fields.extend(period("Through: 12/31", 1.0))
        return _object("Schedule:Compact", fields)

    if parameters.hvac_availability_mode == "continuous":
        hvac_availability = _object("Schedule:Constant", ["SCREENING_HVAC_AVAILABILITY", "FRACTION", 1])
    else:
        hvac_availability = _object(
            "Schedule:Compact",
            [
                "SCREENING_HVAC_AVAILABILITY",
                "FRACTION",
                "Through: 12/31",
                "For: SummerDesignDay WinterDesignDay",
                "Until: 24:00",
                1,
                "For: Weekdays",
                hvac_start,
                0,
                hvac_end,
                1,
                "Until: 24:00",
                0,
                "For: AllOtherDays",
                "Until: 24:00",
                0,
            ],
        )

    return [
        _object("ScheduleTypeLimits", ["FRACTION", 0, 1, "Continuous"]),
        _object("ScheduleTypeLimits", ["TEMPERATURE", -60, 200, "Continuous", "Temperature"]),
        _object("ScheduleTypeLimits", ["ANY_NUMBER"]),
        _object("Schedule:Constant", ["SCREENING_ACTIVITY", "ANY_NUMBER", 120]),
        _object("Schedule:Constant", ["SCREENING_ALWAYS_ON", "FRACTION", 1]),
        load_schedule(
            "SCREENING_PEOPLE_FRACTION",
            parameters.post_march17_people_multiplier,
            standby=parameters.people_standby_fraction,
            weekend=parameters.people_weekend_fraction,
            shoulder=0.10,
        ),
        load_schedule(
            "SCREENING_LIGHTS_FRACTION",
            parameters.post_march17_lighting_multiplier,
            standby=parameters.lights_standby_fraction,
            weekend=parameters.lights_weekend_fraction,
        ),
        load_schedule(
            "SCREENING_MEL_FRACTION",
            parameters.post_march17_equipment_multiplier,
            standby=parameters.mel_standby_fraction,
            weekend=parameters.mel_weekend_fraction,
            shoulder=0.55,
        ),
        hvac_availability,
        _object(
            "Schedule:Compact",
            [
                "SCREENING_HEATING_SETPOINT",
                "TEMPERATURE",
                "Through: 12/31",
                "For: WinterDesignDay SummerDesignDay",
                "Until: 24:00",
                parameters.occupied_heating_setpoint_c,
                "For: Weekdays",
                hvac_start,
                parameters.unoccupied_heating_setpoint_c,
                hvac_end,
                parameters.occupied_heating_setpoint_c,
                "Until: 24:00",
                parameters.unoccupied_heating_setpoint_c,
                "For: AllOtherDays",
                "Until: 24:00",
                parameters.unoccupied_heating_setpoint_c,
            ],
        ),
        _object(
            "Schedule:Compact",
            [
                "SCREENING_COOLING_SETPOINT",
                "TEMPERATURE",
                "Through: 12/31",
                "For: WinterDesignDay SummerDesignDay",
                "Until: 24:00",
                parameters.occupied_cooling_setpoint_c,
                "For: Weekdays",
                hvac_start,
                parameters.unoccupied_cooling_setpoint_c,
                hvac_end,
                parameters.occupied_cooling_setpoint_c,
                "Until: 24:00",
                parameters.unoccupied_cooling_setpoint_c,
                "For: AllOtherDays",
                "Until: 24:00",
                parameters.unoccupied_cooling_setpoint_c,
            ],
        ),
    ]


def _design_days() -> list[str]:
    common_tail: list[object] = [
        "",
        "",
        "",
        "",
        101301,
        2.2,
        150,
        "No",
        "No",
        "No",
        "ASHRAEClearSky",
        "",
        "",
        "",
        "",
    ]
    return [
        _object(
            "SizingPeriod:DesignDay",
            [
                "SAN_FRANCISCO_SCREENING_HEATING_99_6",
                1,
                21,
                "WinterDesignDay",
                3.8,
                0.0,
                "DefaultMultipliers",
                "",
                "Wetbulb",
                3.8,
                *common_tail,
                0.0,
            ],
        ),
        _object(
            "SizingPeriod:DesignDay",
            [
                "SAN_FRANCISCO_SCREENING_COOLING_1",
                7,
                21,
                "SummerDesignDay",
                27.2,
                8.1,
                "DefaultMultipliers",
                "",
                "Wetbulb",
                18.3,
                "",
                "",
                "",
                "",
                101301,
                4.4,
                290,
                "No",
                "No",
                "No",
                "ASHRAEClearSky",
                "",
                "",
                "",
                "",
                1.0,
            ],
        ),
    ]


def _materials_and_constructions(parameters: B59CalibrationParameters) -> list[str]:
    return [
        _object(
            "Material:NoMass",
            ["SCREENING_WALL_R", "MediumSmooth", parameters.wall_thermal_resistance_m2_k_w, 0.9, 0.6, 0.6],
        ),
        _object(
            "Material:NoMass",
            ["SCREENING_ROOF_R", "MediumRough", parameters.roof_thermal_resistance_m2_k_w, 0.9, 0.6, 0.6],
        ),
        _object("Material", ["SCREENING_CONCRETE", "MediumRough", 0.15, 1.4, 2200, 900, 0.9, 0.65, 0.65]),
        _object("Material", ["SCREENING_GYPSUM", "Smooth", 0.025, 0.16, 800, 1090, 0.9, 0.5, 0.5]),
        _object(
            "WindowMaterial:SimpleGlazingSystem",
            ["SCREENING_SIMPLE_GLAZING", parameters.glazing_u_w_m2_k, parameters.glazing_shgc, 0.6],
        ),
        _object("Construction", ["SCREENING_EXTERIOR_WALL", "SCREENING_WALL_R"]),
        _object("Construction", ["SCREENING_ROOF", "SCREENING_ROOF_R"]),
        _object("Construction", ["SCREENING_FLOOR", "SCREENING_CONCRETE"]),
        _object("Construction", ["SCREENING_INTERIOR", "SCREENING_GYPSUM"]),
        _object("Construction", ["SCREENING_WINDOW", "SCREENING_SIMPLE_GLAZING"]),
    ]


def _zone_objects(zones: Sequence[ZoneSpec]) -> list[str]:
    result: list[str] = []
    for zone in zones:
        result.append(
            _object(
                "Zone",
                [
                    zone.plenum_name,
                    0,
                    0,
                    0,
                    0,
                    1,
                    1,
                    PLENUM_HEIGHT_M,
                    "autocalculate",
                    "autocalculate",
                    "",
                    "",
                    "No",
                ],
            )
        )
        result.append(
            _object(
                "Zone",
                [
                    zone.name,
                    0,
                    0,
                    0,
                    0,
                    1,
                    1,
                    OCCUPIED_HEIGHT_M,
                    "autocalculate",
                    "autocalculate",
                    "",
                    "",
                    "Yes",
                ],
            )
        )
    result.append(_object("ZoneList", ["B59_SCREENING_OCCUPIED_ZONES", *(zone.name for zone in zones)]))
    return result


def _geometry(zones: Sequence[ZoneSpec]) -> list[str]:
    result: list[str] = []
    for zone in zones:
        result.extend(_box_surfaces(zone, plenum=True))
        result.extend(_box_surfaces(zone, plenum=False))
        if zone.y0 == 0.0:
            result.append(_window(zone, "SOUTH"))
        if zone.y1 == FLOOR_DEPTH_M:
            result.append(_window(zone, "NORTH"))
        if zone.x0 == 0.0:
            result.append(_window(zone, "WEST"))
        if zone.x1 == FLOOR_LENGTH_M:
            result.append(_window(zone, "EAST"))
    return result


def _south_lighting_name(zone: ZoneSpec) -> str:
    return f"B59_LIGHTS_METERED_SOUTH_PROXY_{zone.name}"


def _north_lighting_name(zone: ZoneSpec) -> str:
    return f"B59_LIGHTS_UNMETERED_NORTH_PROXY_{zone.name}"


def _internal_loads(zones: Sequence[ZoneSpec], parameters: B59CalibrationParameters) -> list[str]:
    result = [
        _object(
            "People",
            [
                "B59_SCREENING_PEOPLE",
                "B59_SCREENING_OCCUPIED_ZONES",
                "SCREENING_PEOPLE_FRACTION",
                "Area/Person",
                "",
                "",
                parameters.people_area_per_person_m2,
                0.3,
                "autocalculate",
                "SCREENING_ACTIVITY",
                "",
                "No",
            ],
        ),
        _object(
            "ElectricEquipment",
            [
                "B59_SCREENING_MEL",
                "B59_SCREENING_OCCUPIED_ZONES",
                "SCREENING_MEL_FRACTION",
                "Watts/Area",
                "",
                parameters.equipment_w_m2,
                "",
                0,
                0.5,
                0,
                "OfficeMEL",
            ],
        ),
        _object(
            "ZoneInfiltration:DesignFlowRate",
            [
                "B59_SCREENING_INFILTRATION",
                "B59_SCREENING_OCCUPIED_ZONES",
                "SCREENING_ALWAYS_ON",
                "Flow/Area",
                "",
                parameters.infiltration_m3_s_m2,
                "",
                "",
                1,
                0,
                0,
                0,
            ],
        ),
    ]
    lighting_splits = (
        (
            _south_lighting_name,
            parameters.measured_south_lighting_fraction,
            "MeteredSouthPanelProxy",
        ),
        (
            _north_lighting_name,
            1.0 - parameters.measured_south_lighting_fraction,
            "UnmeteredNorthPanelProxy",
        ),
    )
    for zone in zones:
        for name_factory, fraction, end_use in lighting_splits:
            result.append(
                _object(
                    "Lights",
                    [
                        name_factory(zone),
                        zone.name,
                        "SCREENING_LIGHTS_FRACTION",
                        "Watts/Area",
                        "",
                        parameters.lighting_w_m2 * fraction,
                        "",
                        0,
                        0.42,
                        0.18,
                        1.0,
                        end_use,
                    ],
                )
            )
    return result


def _thermostat_and_terminals(zones: Sequence[ZoneSpec], parameters: B59CalibrationParameters) -> list[str]:
    result = [
        _object(
            "HVACTemplate:Thermostat",
            ["B59_SCREENING_THERMOSTAT", "SCREENING_HEATING_SETPOINT", "", "SCREENING_COOLING_SETPOINT", ""],
        )
    ]
    group_area = FLOOR_LENGTH_M * FLOOR_DEPTH_M * len(OFFICE_FLOORS) / len(RTU_GROUPS)
    for zone in zones:
        max_flow = parameters.coil_airflow_m3_s * zone.area_m2 / group_area
        result.append(
            _object(
                "HVACTemplate:Zone:VAV",
                [
                    zone.name,
                    zone.rtu_name,
                    "B59_SCREENING_THERMOSTAT",
                    max_flow,
                    "",
                    "",
                    "Constant",
                    0.2,
                    "",
                    "",
                    "Flow/Area",
                    0,
                    parameters.minimum_outdoor_air_m3_s / group_area,
                    0,
                    "Electric",
                    "SCREENING_HVAC_AVAILABILITY",
                    "Reverse",
                    "",
                    "",
                    35,
                    "",
                    zone.plenum_name,
                    "",
                    "None",
                    "",
                    "autosize",
                    "SystemSupplyAirTemperature",
                    "",
                    "",
                    "SupplyAirTemperature",
                    35,
                    "",
                ],
            )
        )
    return result


def _rtu_templates(parameters: B59CalibrationParameters) -> list[str]:
    result: list[str] = []
    for group in RTU_GROUPS:
        result.append(
            _object(
                "HVACTemplate:System:PackagedVAV",
                [
                    f"B59_RTU_{group}",
                    "SCREENING_HVAC_AVAILABILITY",
                    parameters.coil_airflow_m3_s,
                    0,
                    "DrawThrough",
                    parameters.supply_fan_total_efficiency,
                    parameters.supply_fan_pressure_pa,
                    0.9,
                    1,
                    "TwoSpeedDX",
                    "SCREENING_HVAC_AVAILABILITY",
                    "",
                    parameters.supply_air_temperature_setpoint_c,
                    parameters.cooling_capacity_w,
                    parameters.cooling_shr,
                    parameters.cooling_cop,
                    "None",
                    "",
                    "",
                    10,
                    0,
                    "",
                    "",
                    parameters.coil_airflow_m3_s,
                    parameters.minimum_outdoor_air_m3_s,
                    "FixedMinimum",
                    "SCREENING_HVAC_AVAILABILITY",
                    "DifferentialDryBulb",
                    "NoLockout",
                    21,
                    "",
                    "",
                    4,
                    "",
                    "",
                    "VariableSpeedMotorPressureReset",
                    "StayOff",
                    "",
                    "None",
                    0.7,
                    0.65,
                    "None",
                    "None",
                    "None",
                    "",
                    60,
                    "None",
                    "",
                    0.000001,
                    0,
                    "",
                    30,
                    "NonCoincident",
                    "Yes",
                    parameters.return_fan_total_efficiency,
                    parameters.return_fan_pressure_pa,
                    0.9,
                    1,
                    "VariableSpeedMotorPressureReset",
                ],
            )
        )
    return result


def _meter_scope_objects(zones: Sequence[ZoneSpec]) -> list[str]:
    south_light_pairs: list[object] = []
    north_light_pairs: list[object] = []
    for zone in zones:
        south_light_pairs.extend((_south_lighting_name(zone), "Lights Electricity Energy"))
        north_light_pairs.extend((_north_lighting_name(zone), "Lights Electricity Energy"))
    return [
        _object("Meter:Custom", [METER_LIGHTING_SOUTH, "Electricity", *south_light_pairs]),
        _object(
            "Meter:Custom",
            [METER_LIGHTING_NORTH_UNMETERED, "Electricity", *north_light_pairs],
        ),
        _object("Meter:Custom", [METER_MELS, "Electricity", "", "InteriorEquipment:Electricity"]),
        _object(
            "Meter:Custom",
            [METER_MODEL_HVAC, "Electricity", "", "Fans:Electricity", "", "Cooling:Electricity"],
        ),
        _object(
            "Meter:Custom",
            [METER_TERMINAL_HEAT_UNRESOLVED, "Electricity", "", "Heating:Electricity"],
        ),
        _object(
            "Meter:Custom",
            [
                METER_PARTIAL_TARGET_PROXY,
                "Electricity",
                "",
                "InteriorEquipment:Electricity",
                *south_light_pairs,
                "",
                "Fans:Electricity",
                "",
                "Cooling:Electricity",
            ],
        ),
    ]


def _outputs(profile: OutputProfile) -> list[str]:
    if profile not in {"lean", "diagnostic"}:
        raise ValueError(f"unsupported output profile: {profile!r}")
    meters = (
        "Electricity:Facility",
        "Electricity:HVAC",
        "InteriorLights:Electricity",
        "InteriorEquipment:Electricity",
        "Fans:Electricity",
        "Cooling:Electricity",
        "Heating:Electricity",
        METER_LIGHTING_SOUTH,
        METER_LIGHTING_NORTH_UNMETERED,
        METER_MELS,
        METER_MODEL_HVAC,
        METER_TERMINAL_HEAT_UNRESOLVED,
        METER_PARTIAL_TARGET_PROXY,
    )
    variables = (
        "Zone Air Temperature",
        "Zone Thermostat Heating Setpoint Temperature",
        "Zone Thermostat Cooling Setpoint Temperature",
        "Zone Air System Sensible Heating Rate",
        "Zone Air System Sensible Cooling Rate",
        "System Node Temperature",
        "System Node Mass Flow Rate",
        "Air System Outdoor Air Mass Flow Rate",
        "Fan Electricity Rate",
        "Cooling Coil Electricity Rate",
        "Heating Coil Electricity Rate",
    )
    frequencies = ("Hourly",) if profile == "lean" else ("Hourly", "Monthly")
    result = [_object("Output:Meter", [meter, frequency]) for meter in meters for frequency in frequencies]
    if profile == "lean":
        return result
    result.extend(_object("Output:Variable", ["*", variable, "Hourly"]) for variable in variables)
    result.extend(
        [
            _object("Output:Table:SummaryReports", ["AllSummary"]),
            _object("OutputControl:Table:Style", ["CommaAndHTML"]),
            _object("Output:SQLite", ["SimpleAndTabular"]),
        ]
    )
    return result


def build_b59_screening_seed_idf(
    parameters: B59CalibrationParameters = DEFAULT_CALIBRATION_PARAMETERS,
    *,
    output_profile: OutputProfile = "lean",
    simulation_year: int = DEFAULT_SIMULATION_YEAR,
) -> str:
    """Return a deterministic EnergyPlus 26.1 IDF screening seed."""

    _validate_simulation_year(simulation_year)
    zones = screening_zone_specs()
    comments = [
        "! -----------------------------------------------------------------------------",
        f"! CLAIM LABEL: {CLAIM_LABEL}",
        "! SCOPE: two monitored office floors, 4,650 m2 total.",
        "! THIS IS A RUNNABLE SCREENING SEED, NOT AN AS-BUILT OR CALIBRATED MODEL.",
        "! No result from this file authorizes a Guideline-14, DSM, savings, or tariff claim.",
        "!",
        (
            "! PUBLISHED RTU RATING (evidence, not direct coil input): "
            f"{_fmt(RTU_SUPPLY_FLOW_M3_S)} m3/s (20,000 cfm) supply, "
            f"{_fmt(RTU_MINIMUM_OA_M3_S)} m3/s (5,000 cfm) minimum OA, "
            f"{_fmt(RTU_COOLING_CAPACITY_W)} W (30 ton), 20 hp supply motor, "
            "7.5 hp return motor."
        ),
        (
            "! SIMULATION PROXY: TwoSpeedDX coil flow "
            f"{_fmt(parameters.coil_airflow_m3_s)} m3/s "
            f"({parameters.coil_airflow_m3_s / CFM_TO_M3_S:.0f} cfm) at "
            f"{_fmt(parameters.cooling_capacity_w)} W; this stays near the supported "
            "400 cfm/ton coil domain. Fan pressures/efficiencies are bounded proxies; "
            "published motor hp is not silently converted to coincident shaft power."
        ),
        f"! OUTPUT PROFILE: {output_profile}.",
        f"! SIMULATION CALENDAR YEAR: {simulation_year}; explicit so leap-day weather is retained.",
        (
            "! METER SCOPE: facility total is prohibited as a calibration target; use the "
            "partial meter-bound proxy only after resolving elevator and ASHP/WSHP dispositions; "
            "electric terminal reheat is separately reported and excluded."
        ),
        "!",
        "! UNMATCHED / UNRESOLVED TOPOLOGY:",
        *(f"! - {item}" for item in UNMATCHED_TOPOLOGY),
        "! -----------------------------------------------------------------------------",
    ]
    objects: list[str] = [
        _object("Version", [ENERGYPLUS_VERSION]),
        _object("Building", [CLAIM_LABEL, 0, "City", 0.04, 0.4, "FullExterior", 100, 6]),
        _object("Timestep", [4]),
        _object(
            "ShadowCalculation",
            ["PolygonClipping", "Periodic", 20, 15000, "SutherlandHodgman", 512, "SimpleSkyDiffuseModeling"],
        ),
        _object("SimulationControl", ["Yes", "Yes", "No", "No", "Yes", "No", 1]),
        _object(
            "RunPeriod",
            [
                "SCREENING_YEAR",
                1,
                1,
                simulation_year,
                12,
                31,
                simulation_year,
                "",
                "Yes",
                "Yes",
                "No",
                "Yes",
                "Yes",
                "No",
                "Hour24",
            ],
        ),
        _object("GlobalGeometryRules", ["UpperLeftCorner", "Counterclockwise", "World", "Relative", "Relative"]),
        _object("Sizing:Parameters", [1.0, 1.0]),
    ]
    objects.extend(_design_days())
    objects.extend(_schedules(parameters))
    objects.extend(_materials_and_constructions(parameters))
    objects.extend(_zone_objects(zones))
    objects.extend(_geometry(zones))
    objects.extend(_internal_loads(zones, parameters))
    objects.extend(_thermostat_and_terminals(zones, parameters))
    objects.extend(_rtu_templates(parameters))
    objects.extend(_meter_scope_objects(zones))
    objects.extend(_outputs(output_profile))
    return "\n".join(comments) + "\n\n" + "\n\n".join(objects) + "\n"


def write_b59_screening_seed_idf(
    destination: Path,
    parameters: B59CalibrationParameters = DEFAULT_CALIBRATION_PARAMETERS,
    *,
    output_profile: OutputProfile = "lean",
    simulation_year: int = DEFAULT_SIMULATION_YEAR,
) -> Path:
    """Write the deterministic screening seed without implying model promotion."""

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        build_b59_screening_seed_idf(
            parameters,
            output_profile=output_profile,
            simulation_year=simulation_year,
        ),
        encoding="utf-8",
        newline="\n",
    )
    return destination
