"""Parameter registry for existing-building calibration search.

Every knob the search may turn is declared up front as a
:class:`~wattlab.existing_building.models.ParameterSpec` with hard bounds,
a ``tuneable`` flag, the EnergyPlus object/field it maps onto, and its
dependencies. The search layer refuses to touch anything not registered.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from wattlab.existing_building.models import ParameterSpec


class ParameterRegistry:
    """Ordered, name-unique collection of parameter specs."""

    def __init__(self, specs: Iterable[ParameterSpec] = ()) -> None:
        self._specs: dict[str, ParameterSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: ParameterSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"parameter {spec.name!r} is already registered")
        self._specs[spec.name] = spec

    def __contains__(self, name: str) -> bool:
        return name in self._specs

    def __len__(self) -> int:
        return len(self._specs)

    def __iter__(self):
        return iter(self._specs.values())

    def get(self, name: str) -> ParameterSpec:
        try:
            return self._specs[name]
        except KeyError:
            raise KeyError(
                f"unknown parameter {name!r}; registered: {sorted(self._specs)}"
            ) from None

    @property
    def names(self) -> list[str]:
        return list(self._specs)

    def tuneable(self) -> list[ParameterSpec]:
        return [s for s in self._specs.values() if s.tuneable]

    def defaults(self) -> dict[str, float]:
        return {s.name: s.default for s in self._specs.values()}

    def bounds(self) -> dict[str, tuple[float, float]]:
        return {s.name: (s.minimum, s.maximum) for s in self._specs.values()}

    def validate_dependencies(self) -> None:
        """Every ``depends_on`` entry must itself be registered."""
        for spec in self._specs.values():
            unknown = [d for d in spec.depends_on if d not in self._specs]
            if unknown:
                raise ValueError(
                    f"parameter {spec.name!r} depends on unregistered "
                    f"parameters: {', '.join(unknown)}"
                )

    def validate_values(self, values: Mapping[str, float]) -> dict[str, float]:
        """Reject unknown names, non-tuneable overrides, and out-of-bounds values."""
        out: dict[str, float] = {}
        for name, value in values.items():
            spec = self.get(name)
            if not spec.tuneable and value != spec.default:
                raise ValueError(
                    f"parameter {name!r} is not tuneable; it is pinned to "
                    f"{spec.default}"
                )
            if not (spec.minimum <= value <= spec.maximum):
                raise ValueError(
                    f"parameter {name!r} value {value} is outside bounds "
                    f"[{spec.minimum}, {spec.maximum}]"
                )
            out[name] = float(value)
        return out


def default_parameter_registry() -> ParameterRegistry:
    """Baseline tuneable-parameter set for an office-like existing building.

    Bounds are deliberately generous screening bounds, not design values;
    the objective's physical-plausibility penalties tighten them per case.
    """
    return ParameterRegistry(
        [
            ParameterSpec(
                name="lighting_power_density_w_ft2",
                description="Installed interior lighting power density",
                units="W/ft2",
                default=0.9,
                minimum=0.3,
                maximum=2.5,
                energyplus_target="Lights.Watts per Zone Floor Area",
            ),
            ParameterSpec(
                name="equipment_power_density_w_ft2",
                description="Plug/process equipment power density",
                units="W/ft2",
                default=1.0,
                minimum=0.2,
                maximum=4.0,
                energyplus_target="ElectricEquipment.Watts per Zone Floor Area",
            ),
            ParameterSpec(
                name="occupant_density_ft2_person",
                description="Floor area per occupant",
                units="ft2/person",
                default=200.0,
                minimum=80.0,
                maximum=600.0,
                energyplus_target="People.Zone Floor Area per Person",
            ),
            ParameterSpec(
                name="infiltration_ach",
                description="Envelope infiltration air-change rate",
                units="1/h",
                default=0.4,
                minimum=0.05,
                maximum=1.5,
                energyplus_target="ZoneInfiltration:DesignFlowRate.Air Changes per Hour",
            ),
            ParameterSpec(
                name="cooling_cop",
                description="Cooling plant coefficient of performance",
                units="W/W",
                default=3.2,
                minimum=2.0,
                maximum=6.5,
                energyplus_target="Coil:Cooling:DX.Gross Rated COP",
            ),
            ParameterSpec(
                name="heating_efficiency",
                description="Heating plant thermal efficiency",
                units="fraction",
                default=0.8,
                minimum=0.55,
                maximum=0.99,
                energyplus_target="Boiler:HotWater.Nominal Thermal Efficiency",
            ),
            ParameterSpec(
                name="fan_static_pressure_pa",
                description="Supply fan total static pressure",
                units="Pa",
                default=750.0,
                minimum=250.0,
                maximum=1800.0,
                energyplus_target="Fan:VariableVolume.Pressure Rise",
            ),
            ParameterSpec(
                name="outdoor_air_fraction",
                description="Minimum outdoor-air fraction of supply flow",
                units="fraction",
                default=0.15,
                minimum=0.0,
                maximum=0.6,
                energyplus_target="Controller:OutdoorAir.Minimum Outdoor Air Flow Rate",
            ),
            ParameterSpec(
                name="weekday_operating_hours",
                description="Weekday HVAC/occupancy operating hours",
                units="h/day",
                default=10.0,
                minimum=6.0,
                maximum=24.0,
                energyplus_target="Schedule:Compact (availability + occupancy)",
                depends_on=["occupant_density_ft2_person"],
            ),
            ParameterSpec(
                name="floor_area_ft2",
                description="Gross conditioned floor area (evidence, not a knob)",
                units="ft2",
                default=42000.0,
                minimum=1000.0,
                maximum=2_000_000.0,
                tuneable=False,
                energyplus_target="Building geometry (fixed by drawings)",
            ),
        ]
    )
