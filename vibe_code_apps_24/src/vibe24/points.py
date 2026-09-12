"""Residential RTU point catalog for the live twin."""
from __future__ import annotations

from .bus import PointDef, PointKind
from .thermostat import DEFAULT_DEADBAND_F, DEFAULT_ZONE_SP_F, effective_heat_cool


def residential_rtu_points() -> list[PointDef]:
    heat0, cool0 = effective_heat_cool(DEFAULT_ZONE_SP_F, DEFAULT_DEADBAND_F)
    return [
        PointDef("ZONE-T", PointKind.SENSOR, "Zone air temperature", "degreesFahrenheit", 72.0),
        PointDef("OA-T", PointKind.SENSOR, "Outdoor air temperature", "degreesFahrenheit", 85.0),
        PointDef("RTU-KW", PointKind.SENSOR, "RTU electric power", "kilowatts", 0.0),
        PointDef("FAN-S", PointKind.SENSOR, "Supply fan status (1=on)", "", 0.0, binary=True),
        PointDef("MODE", PointKind.SENSOR, "0=off 1=heat 2=cool 3=fan", "", 0.0),
        # Real-thermostat style: one SP + deadband → derived heat/cool (read-only).
        PointDef(
            "ZONE-SP",
            PointKind.COMMANDABLE,
            "Zone setpoint (center)",
            "degreesFahrenheit",
            DEFAULT_ZONE_SP_F,
        ),
        PointDef(
            "DEADBAND",
            PointKind.COMMANDABLE,
            "Thermostat deadband width (F)",
            "degreesFahrenheit",
            DEFAULT_DEADBAND_F,
        ),
        PointDef(
            "HEAT-EFF",
            PointKind.SENSOR,
            "Effective heating setpoint (ZONE-SP - DEADBAND/2)",
            "degreesFahrenheit",
            heat0,
        ),
        PointDef(
            "COOL-EFF",
            PointKind.SENSOR,
            "Effective cooling setpoint (ZONE-SP + DEADBAND/2)",
            "degreesFahrenheit",
            cool0,
        ),
        PointDef("UNIT-ENABLE", PointKind.COMMANDABLE, "Unit enable (1=on)", "", 1.0, binary=True),
        PointDef("OCC-OVRD", PointKind.COMMANDABLE, "Occupancy override (1=occ)", "", 1.0, binary=True),
    ]
