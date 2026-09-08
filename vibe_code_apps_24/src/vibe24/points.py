"""Residential RTU point catalog for the live twin."""
from __future__ import annotations

from .bus import PointDef, PointKind


def residential_rtu_points() -> list[PointDef]:
    return [
        PointDef("ZONE-T", PointKind.SENSOR, "Zone air temperature", "degreesFahrenheit", 72.0),
        PointDef("OA-T", PointKind.SENSOR, "Outdoor air temperature", "degreesFahrenheit", 85.0),
        PointDef("RTU-KW", PointKind.SENSOR, "RTU electric power", "kilowatts", 0.0),
        PointDef("FAN-S", PointKind.SENSOR, "Supply fan status (1=on)", "", 0.0, binary=True),
        PointDef("MODE", PointKind.SENSOR, "0=off 1=heat 2=cool 3=fan", "", 0.0),
        PointDef("HEAT-SP", PointKind.COMMANDABLE, "Heating setpoint", "degreesFahrenheit", 71.0),
        PointDef("COOL-SP", PointKind.COMMANDABLE, "Cooling setpoint", "degreesFahrenheit", 73.0),
        PointDef("UNIT-ENABLE", PointKind.COMMANDABLE, "Unit enable (1=on)", "", 1.0, binary=True),
        PointDef("OCC-OVRD", PointKind.COMMANDABLE, "Occupancy override (1=occ)", "", 1.0, binary=True),
    ]
