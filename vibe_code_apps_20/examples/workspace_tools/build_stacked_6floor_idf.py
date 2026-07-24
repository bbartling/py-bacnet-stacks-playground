#!/usr/bin/env python3
"""Build a 6-story stacked single-zone-per-floor office IDF (HVACTemplate VAV + WC plant).

Screening twin: one big zone per floor, floors connected via interzone ceilings/floors.
E+ 26.1-compatible: BuildingSurface:Detailed includes blank Space Name; AutoCalculate VF.

    python build_stacked_6floor_idf.py \\
      --dst uploads/prototypes/geo_b100_6stack.idf \\
      --building-name B100 --target-area-ft2 140000 --wwr 0.60
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

FT2_TO_M2 = 0.09290304
FT_TO_M = 0.3048


def _rect(lx: float, ly: float, z0: float, z1: float) -> dict[str, list[tuple[float, float, float]]]:
    """Wall/floor/roof quads; UpperLeft CounterClockWise Relative."""
    return {
        "floor": [(0, ly, z0), (0, 0, z0), (lx, 0, z0), (lx, ly, z0)],
        "roof": [(0, ly, z1), (lx, ly, z1), (lx, 0, z1), (0, 0, z1)],
        "wall_s": [(0, 0, z1), (lx, 0, z1), (lx, 0, z0), (0, 0, z0)],
        "wall_e": [(lx, 0, z1), (lx, ly, z1), (lx, ly, z0), (lx, 0, z0)],
        "wall_n": [(lx, ly, z1), (0, ly, z1), (0, ly, z0), (lx, ly, z0)],
        "wall_w": [(0, ly, z1), (0, 0, z1), (0, 0, z0), (0, ly, z0)],
    }


def _verts(vs: list[tuple[float, float, float]]) -> str:
    lines = []
    for i, (x, y, z) in enumerate(vs):
        end = ";" if i == len(vs) - 1 else ","
        lines.append(f"    {x:.4f},{y:.4f},{z:.4f}{end}  !- X,Y,Z ==> Vertex {i+1}")
    return "\n".join(lines)


def _surf(
    name: str,
    stype: str,
    constr: str,
    zone: str,
    obc: str,
    obc_obj: str,
    sun: str,
    wind: str,
    verts: list[tuple[float, float, float]],
) -> str:
    # E+ 26.1: blank Space Name after Zone Name. Empty OBC Object must be a single blank field
    # (never ",," — that shifts vertices).
    obc_obj_field = obc_obj if obc_obj else ""
    return f"""
  BuildingSurface:Detailed,
    {name},                  !- Name
    {stype},                 !- Surface Type
    {constr},                !- Construction Name
    {zone},                  !- Zone Name
    ,                        !- Space Name
    {obc},                   !- Outside Boundary Condition
    {obc_obj_field},                        !- Outside Boundary Condition Object
    {sun},                   !- Sun Exposure
    {wind},                  !- Wind Exposure
    AutoCalculate,           !- View Factor to Ground
    4,                       !- Number of Vertices
{_verts(verts)}
"""


def _window_on_wall(
    name: str,
    wall_name: str,
    wall_vs: list[tuple[float, float, float]],
    wwr: float,
) -> str:
    (x0, y0, z1), (x1, y1, _z1b), (_x2, _y2, z0), (_x3, _y3, _z0b) = wall_vs
    hx, hy = x1 - x0, y1 - y0
    hlen = math.hypot(hx, hy)
    height = z1 - z0
    wall_area = hlen * height
    win_area = wall_area * wwr
    aspect = height / hlen if hlen else 1.0
    win_w = math.sqrt(win_area / aspect) if aspect else 0.0
    win_h = win_area / win_w if win_w else 0.0
    win_w = min(win_w, hlen * 0.95)
    win_h = min(win_h, height * 0.95)
    mx = (hlen - win_w) / 2.0
    mz = (height - win_h) / 2.0
    ux, uy = (hx / hlen, hy / hlen) if hlen else (1.0, 0.0)
    w_ul = (x0 + ux * mx, y0 + uy * mx, z1 - mz)
    w_ur = (x0 + ux * (mx + win_w), y0 + uy * (mx + win_w), z1 - mz)
    w_lr = (x0 + ux * (mx + win_w), y0 + uy * (mx + win_w), z0 + mz)
    w_ll = (x0 + ux * mx, y0 + uy * mx, z0 + mz)
    return f"""
  FenestrationSurface:Detailed,
    {name},                  !- Name
    Window,                  !- Surface Type
    Exterior Window,         !- Construction Name
    {wall_name},             !- Building Surface Name
    ,                        !- Outside Boundary Condition Object
    AutoCalculate,           !- View Factor to Ground
    ,                        !- Frame and Divider Name
    1.0,                     !- Multiplier
    4,                       !- Number of Vertices
{_verts([w_ul, w_ur, w_lr, w_ll])}
"""


def build_idf(
    *,
    building_name: str,
    target_area_ft2: float,
    stories: int,
    floor_to_floor_ft: float,
    wwr: float,
    window_u: float,
    window_shgc: float,
    lights_w_m2: float,
    equip_w_m2: float,
    people_m2_per_person: float,
    infil_ach: float,
    lat: float,
    lon: float,
    tz: float,
    elevation_m: float,
) -> str:
    area_m2 = target_area_ft2 * FT2_TO_M2
    floor_m2 = area_m2 / stories
    ly = math.sqrt(floor_m2 / 1.5)
    lx = floor_m2 / ly
    h = floor_to_floor_ft * FT_TO_M
    people_per_m2 = 1.0 / people_m2_per_person

    parts: list[str] = []
    parts.append(f"""!- Stacked {stories}-floor single-zone office (screening)
!- Building: {building_name}
!- Area: {target_area_ft2:.0f} ft2 ({area_m2:.0f} m2), {stories} stories, WWR={wwr}
!- HVAC: HVACTemplate VAV + water-cooled chiller + boiler (autosize)
!- Each floor = 1 zone; floors connected with interzone ceiling/floor pairs

  Version,26.1;

  Building,
    {building_name},         !- Name
    0.0,                     !- North Axis {{deg}}
    City,                    !- Terrain
    0.04,                    !- Loads Convergence Tolerance Value
    0.4,                     !- Temperature Convergence Tolerance Value {{deltaC}}
    FullExterior,            !- Solar Distribution
    25,                      !- Maximum Number of Warmup Days
    6;                       !- Minimum Number of Warmup Days

  Timestep,4;

  SurfaceConvectionAlgorithm:Inside,TARP;
  SurfaceConvectionAlgorithm:Outside,DOE-2;
  HeatBalanceAlgorithm,ConductionTransferFunction;

  GlobalGeometryRules,
    UpperLeftCorner,         !- Starting Vertex Position
    CounterClockWise,        !- Vertex Entry Direction
    Relative;                !- Coordinate System

  Site:Location,
    Detroit_MI,              !- Name
    {lat},                   !- Latitude {{deg}}
    {lon},                   !- Longitude {{deg}}
    {tz},                    !- Time Zone {{hr}}
    {elevation_m};           !- Elevation {{m}}

  SimulationControl,
    Yes,                     !- Do Zone Sizing Calculation
    Yes,                     !- Do System Sizing Calculation
    Yes,                     !- Do Plant Sizing Calculation
    No,                      !- Run Simulation for Sizing Periods
    Yes,                     !- Run Simulation for Weather File Run Periods
    No,                      !- Do HVAC Sizing Simulation for Sizing Periods
    1;                       !- Maximum Number of HVAC Sizing Simulation Passes

  SizingPeriod:DesignDay,
    Detroit Heating 99%,     !- Name
    1, 21, WinterDesignDay,
    -17.0, 0.0, , , Wetbulb, -17.0, , , , , 99500, 4.9, 270,
    No, No, No, ASHRAEClearSky, , , , , 0.0;

  SizingPeriod:DesignDay,
    Detroit Cooling 1%,      !- Name
    7, 21, SummerDesignDay,
    32.0, 10.5, , , Wetbulb, 23.0, , , , , 99500, 5.2, 230,
    No, No, No, ASHRAEClearSky, , , , , 1.0;

  RunPeriod,
    Annual,                  !- Name
    1,                       !- Begin Month
    1,                       !- Begin Day of Month
    ,                        !- Begin Year
    12,                      !- End Month
    31,                      !- End Day of Month
    ,                        !- End Year
    Sunday,                  !- Day of Week for Start Day
    Yes, Yes, No, Yes, Yes;

  ScheduleTypeLimits, Any Number;
  ScheduleTypeLimits, Fraction, 0.0, 1.0, CONTINUOUS;
  ScheduleTypeLimits, Temperature, -60, 200, CONTINUOUS, Temperature;
  ScheduleTypeLimits, Control Type, 0, 4, DISCRETE;
  ScheduleTypeLimits, On/Off, 0, 1, DISCRETE;

  Schedule:Compact,
    Always On, Fraction,
    Through: 12/31, For: AllDays, Until: 24:00, 1.0;

  Schedule:Compact,
    Activity level, Any Number,
    Through: 12/31, For: AllDays, Until: 24:00, 120;

  Schedule:Compact,
    FanAvailSched, On/Off,
    Through: 12/31,
    For: Weekdays SummerDesignDay,
    Until: 6:00, 0.0, Until: 22:00, 1.0, Until: 24:00, 0.0,
    For: Saturday,
    Until: 6:00, 0.0, Until: 18:00, 1.0, Until: 24:00, 0.0,
    For: AllOtherDays,
    Until: 24:00, 0.0;

  Schedule:Compact,
    Min OA Sched, Fraction,
    Through: 12/31,
    For: Weekdays SummerDesignDay,
    Until: 6:00, 0.0, Until: 22:00, 1.0, Until: 24:00, 0.0,
    For: Saturday,
    Until: 6:00, 0.0, Until: 18:00, 1.0, Until: 24:00, 0.0,
    For: AllOtherDays,
    Until: 24:00, 0.0;

  Schedule:Compact,
    BLDG_OCC_SCH, Fraction,
    Through: 12/31,
    For: Weekdays SummerDesignDay,
    Until: 6:00, 0.0, Until: 7:00, 0.1, Until: 8:00, 0.2, Until: 12:00, 0.95,
    Until: 13:00, 0.5, Until: 17:00, 0.95, Until: 18:00, 0.3, Until: 22:00, 0.1, Until: 24:00, 0.05,
    For: Saturday,
    Until: 6:00, 0.0, Until: 8:00, 0.1, Until: 12:00, 0.3, Until: 17:00, 0.1, Until: 24:00, 0.0,
    For: AllOtherDays, Until: 24:00, 0.0;

  Schedule:Compact,
    BLDG_LIGHT_SCH, Fraction,
    Through: 12/31,
    For: Weekdays SummerDesignDay,
    Until: 6:00, 0.05, Until: 7:00, 0.1, Until: 17:00, 0.9, Until: 22:00, 0.3, Until: 24:00, 0.05,
    For: Saturday,
    Until: 6:00, 0.05, Until: 8:00, 0.1, Until: 17:00, 0.3, Until: 24:00, 0.05,
    For: AllOtherDays, Until: 24:00, 0.05;

  Schedule:Compact,
    BLDG_EQUIP_SCH, Fraction,
    Through: 12/31,
    For: Weekdays SummerDesignDay,
    Until: 6:00, 0.4, Until: 7:00, 0.4, Until: 8:00, 0.4, Until: 12:00, 0.9,
    Until: 13:00, 0.8, Until: 17:00, 0.9, Until: 18:00, 0.5, Until: 24:00, 0.4,
    For: Saturday,
    Until: 6:00, 0.3, Until: 18:00, 0.4, Until: 24:00, 0.3,
    For: AllOtherDays, Until: 24:00, 0.3;

  Schedule:Compact,
    BLDG_INFIL_SCH, Fraction,
    Through: 12/31,
    For: Weekdays SummerDesignDay,
    Until: 6:00, 1.0, Until: 22:00, 0.25, Until: 24:00, 1.0,
    For: Saturday,
    Until: 6:00, 1.0, Until: 18:00, 0.25, Until: 24:00, 1.0,
    For: AllOtherDays, Until: 24:00, 1.0;

  Schedule:Compact,
    Htg-SetP-Sch, Temperature,
    Through: 12/31,
    For: Weekdays SummerDesignDay,
    Until: 6:00, 15.6, Until: 22:00, 21.0, Until: 24:00, 15.6,
    For: Saturday,
    Until: 6:00, 15.6, Until: 18:00, 21.0, Until: 24:00, 15.6,
    For: AllOtherDays, Until: 24:00, 15.6;

  Schedule:Compact,
    Clg-SetP-Sch, Temperature,
    Through: 12/31,
    For: Weekdays SummerDesignDay,
    Until: 6:00, 30.0, Until: 22:00, 24.0, Until: 24:00, 30.0,
    For: Saturday,
    Until: 6:00, 30.0, Until: 18:00, 24.0, Until: 24:00, 30.0,
    For: AllOtherDays, Until: 24:00, 30.0;

  Material,
    Concrete Floor, MediumRough, 0.15, 1.4, 2100, 800, 0.9, 0.7, 0.7;
  Material,
    Wall Insulation, MediumRough, 0.08, 0.04, 40, 800, 0.9, 0.7, 0.7;
  Material,
    Gypsum, Smooth, 0.0127, 0.16, 800, 1000, 0.9, 0.7, 0.7;
  Material,
    Roof Insulation, MediumRough, 0.12, 0.04, 40, 800, 0.9, 0.7, 0.7;
  Material,
    Stucco, MediumRough, 0.025, 0.7, 1800, 800, 0.9, 0.7, 0.7;

  Construction,
    Ext Wall, Stucco, Wall Insulation, Gypsum;
  Construction,
    Ext Roof, Roof Insulation, Concrete Floor;
  Construction,
    Ext Floor, Concrete Floor;
  Construction,
    Int Floor, Concrete Floor;

  WindowMaterial:SimpleGlazingSystem,
    Exterior Window Glass, {window_u}, {window_shgc};
  Construction,
    Exterior Window, Exterior Window Glass;

  Sizing:Parameters, 1.2, 1.2;
""")

    zone_names = [f"Floor_{i}" for i in range(1, stories + 1)]

    for i, zname in enumerate(zone_names):
        z0 = i * h
        z1 = (i + 1) * h
        geo = _rect(lx, ly, z0, z1)
        parts.append(f"""
  Zone,
    {zname}, 0, 0, 0, 0, 1, 1, autocalculate, autocalculate, autocalculate, , , Yes;
""")
        if i == 0:
            parts.append(
                _surf(f"{zname}_Floor", "Floor", "Ext Floor", zname, "Ground", "", "NoSun", "NoWind", geo["floor"])
            )
        else:
            below = zone_names[i - 1]
            parts.append(
                _surf(
                    f"{zname}_Floor",
                    "Floor",
                    "Int Floor",
                    zname,
                    "Surface",
                    f"{below}_Ceiling",
                    "NoSun",
                    "NoWind",
                    geo["floor"],
                )
            )

        if i == stories - 1:
            parts.append(
                _surf(f"{zname}_Roof", "Roof", "Ext Roof", zname, "Outdoors", "", "SunExposed", "WindExposed", geo["roof"])
            )
        else:
            above = zone_names[i + 1]
            parts.append(
                _surf(
                    f"{zname}_Ceiling",
                    "Ceiling",
                    "Int Floor",
                    zname,
                    "Surface",
                    f"{above}_Floor",
                    "NoSun",
                    "NoWind",
                    geo["roof"],
                )
            )

        for key, sname in (
            ("wall_s", f"{zname}_Wall_S"),
            ("wall_e", f"{zname}_Wall_E"),
            ("wall_n", f"{zname}_Wall_N"),
            ("wall_w", f"{zname}_Wall_W"),
        ):
            parts.append(
                _surf(sname, "Wall", "Ext Wall", zname, "Outdoors", "", "SunExposed", "WindExposed", geo[key])
            )
            parts.append(_window_on_wall(f"{sname}_Win", sname, geo[key], wwr))

        parts.append(f"""
  People, {zname}_People, {zname}, BLDG_OCC_SCH, People/Area, , {people_per_m2:.6f}, , 0.3, , Activity level;
  Lights, {zname}_Lights, {zname}, BLDG_LIGHT_SCH, Watts/Area, , {lights_w_m2}, , 0.2, 0.2, 0.2, 1, General;
  ElectricEquipment, {zname}_Equip, {zname}, BLDG_EQUIP_SCH, Watts/Area, , {equip_w_m2}, , 0, 0.5, 0, General;
  ZoneInfiltration:DesignFlowRate, {zname}_Infil, {zname}, BLDG_INFIL_SCH, AirChanges/Hour, , , , {infil_ach}, 1, 0, 0, 0;
""")

    parts.append("""
  HVACTemplate:Thermostat,
    All Zones,               !- Name
    Htg-SetP-Sch,            !- Heating Setpoint Schedule Name
    ,                        !- Constant Heating Setpoint {C}
    Clg-SetP-Sch,            !- Cooling Setpoint Schedule Name
    ;                        !- Constant Cooling Setpoint {C}
""")
    for zname in zone_names:
        parts.append(f"""
  HVACTemplate:Zone:VAV,
    {zname},                 !- Zone Name
    VAV Sys 1,               !- Template VAV System Name
    All Zones,               !- Template Thermostat Name
    autosize,                !- Supply Air Maximum Flow Rate {{m3/s}}
    ,                        !- Zone Heating Air Flow Rate {{m3/s}}
    ,                        !- Zone Ventilation Air Flow Rate {{m3/s}}
    Constant,                !- Zone Minimum Air Flow Input Method
    0.3,                     !- Constant Minimum Air Flow Fraction
    ,                        !- Fixed Minimum Air Flow Rate {{m3/s}}
    ,                        !- Minimum Air Flow Fraction Schedule Name
    flow/person,             !- Outdoor Air Method
    0.00944,                 !- Outdoor Air Flow Rate per Person {{m3/s}}
    0.0,                     !- Outdoor Air Flow Rate per Zone Floor Area {{m3/s-m2}}
    0.0,                     !- Outdoor Air Flow Rate per Zone {{m3/s}}
    HotWater,                !- Reheat Coil Type
    ,                        !- Reheat Coil Availability Schedule Name
    Reverse,                 !- Damper Heating Action
    ,                        !- Maximum Flow per Zone Floor Area During Reheat {{m3/s-m2}}
    ,                        !- Maximum Flow Fraction During Reheat
    ,                        !- Maximum Reheat Air Temperature {{C}}
    ,                        !- Design Specification Outdoor Air Object Name for Control
    ,                        !- Supply Plenum Name
    ,                        !- Return Plenum Name
    None,                    !- Baseboard Heating Type
    ,                        !- Baseboard Heating Availability Schedule Name
    autosize,                !- Baseboard Heating Capacity {{W}}
    SystemSupplyAirTemperature,  !- Zone Cooling Design Supply Air Temperature Input Method
    ,                        !- Zone Cooling Design Supply Air Temperature {{C}}
    ,                        !- Zone Cooling Design Supply Air Temperature Difference {{deltaC}}
    SupplyAirTemperature,    !- Zone Heating Design Supply Air Temperature Input Method
    50.0,                    !- Zone Heating Design Supply Air Temperature {{C}}
    ;                        !- Zone Heating Design Supply Air Temperature Difference {{deltaC}}
""")

    parts.append(f"""
  HVACTemplate:System:VAV,
    VAV Sys 1,               !- Name
    FanAvailSched,           !- System Availability Schedule Name
    autosize,                !- Supply Fan Maximum Flow Rate {{m3/s}}
    autosize,                !- Supply Fan Minimum Flow Rate {{m3/s}}
    0.7,                     !- Supply Fan Total Efficiency
    600,                     !- Supply Fan Delta Pressure {{Pa}}
    0.9,                     !- Supply Fan Motor Efficiency
    1,                       !- Supply Fan Motor in Air Stream Fraction
    ChilledWater,            !- Cooling Coil Type
    ,                        !- Cooling Coil Availability Schedule Name
    ,                        !- Cooling Coil Setpoint Schedule Name
    12.8,                    !- Cooling Coil Design Setpoint {{C}}
    HotWater,                !- Heating Coil Type
    ,                        !- Heating Coil Availability Schedule Name
    ,                        !- Heating Coil Setpoint Schedule Name
    10.0,                    !- Heating Coil Design Setpoint {{C}}
    0.8,                     !- Gas Heating Coil Efficiency
    0.0,                     !- Gas Heating Coil Parasitic Electric Load {{W}}
    None,                    !- Preheat Coil Type
    ,                        !- Preheat Coil Availability Schedule Name
    ,                        !- Preheat Coil Setpoint Schedule Name
    ,                        !- Preheat Coil Design Setpoint {{C}}
    0.8,                     !- Gas Preheat Coil Efficiency
    0.0,                     !- Gas Preheat Coil Parasitic Electric Load {{W}}
    autosize,                !- Maximum Outdoor Air Flow Rate {{m3/s}}
    autosize,                !- Minimum Outdoor Air Flow Rate {{m3/s}}
    FixedMinimum,            !- Minimum Outdoor Air Control Type
    Min OA Sched,            !- Minimum Outdoor Air Schedule Name
    DifferentialDryBulb,     !- Economizer Type
    NoLockout,               !- Economizer Lockout
    19,                      !- Economizer Upper Temperature Limit {{C}}
    4,                       !- Economizer Lower Temperature Limit {{C}}
    ,                        !- Economizer Upper Enthalpy Limit {{J/kg}}
    ,                        !- Economizer Maximum Limit Dewpoint Temperature {{C}}
    ,                        !- Supply Plenum Name
    ,                        !- Return Plenum Name
    DrawThrough,             !- Supply Fan Placement
    InletVaneDampers,        !- Supply Fan Part-Load Power Coefficients
    CycleOnAny,              !- Night Cycle Control
    {zone_names[0]},                        !- Night Cycle Control Zone Name
    None,                    !- Heat Recovery Type
    0.70,                    !- Sensible Heat Recovery Effectiveness
    0.65,                    !- Latent Heat Recovery Effectiveness
    None,                    !- Cooling Coil Setpoint Reset Type
    None,                    !- Heating Coil Setpoint Reset Type
    None,                    !- Dehumidification Control Type
    ,                        !- Dehumidification Control Zone Name
    60.0,                    !- Dehumidification Setpoint {{percent}}
    None,                    !- Humidifier Type
    ,                        !- Humidifier Availability Schedule Name
    0.000001,                !- Humidifier Rated Capacity {{m3/s}}
    2690.0,                  !- Humidifier Rated Electric Power {{W}}
    ,                        !- Humidifier Control Zone Name
    30.0,                    !- Humidifier Setpoint {{percent}}
    NonCoincident,           !- Sizing Option
    ,                        !- Return Fan
    ,                        !- Return Fan Total Efficiency
    ,                        !- Return Fan Delta Pressure {{Pa}}
    ,                        !- Return Fan Motor Efficiency
    ,                        !- Return Fan Motor in Air Stream Fraction
    ;                        !- Return Fan Part-Load Power Coefficients

  HVACTemplate:Plant:ChilledWaterLoop,
    Chilled Water Loop,      !- Name
    ,                        !- Pump Schedule Name
    INTERMITTENT,            !- Pump Control Type
    Default,                 !- Chiller Plant Operation Scheme Type
    ,                        !- Chiller Plant Equipment Operation Schemes Name
    ,                        !- Chilled Water Setpoint Schedule Name
    7.22,                    !- Chilled Water Design Setpoint {{C}}
    ConstantPrimaryNoSecondary,  !- Chilled Water Pump Configuration
    179352,                  !- Primary Chilled Water Pump Rated Head {{Pa}}
    179352,                  !- Secondary Chilled Water Pump Rated Head {{Pa}}
    Default,                 !- Condenser Plant Operation Scheme Type
    ,                        !- Condenser Equipment Operation Schemes Name
    ,                        !- Condenser Water Temperature Control Type
    ,                        !- Condenser Water Setpoint Schedule Name
    29.4,                    !- Condenser Water Design Setpoint {{C}}
    179352,                  !- Condenser Water Pump Rated Head {{Pa}}
    None,                    !- Chilled Water Setpoint Reset Type
    12.2,                    !- Chilled Water Setpoint at Outdoor Dry-Bulb Low {{C}}
    15.6,                    !- Chilled Water Reset Outdoor Dry-Bulb Low {{C}}
    6.7,                     !- Chilled Water Setpoint at Outdoor Dry-Bulb High {{C}}
    26.7,                    !- Chilled Water Reset Outdoor Dry-Bulb High {{C}}
    ,                        !- Chilled Water Primary Pump Type
    ,                        !- Chilled Water Secondary Pump Type
    ,                        !- Condenser Water Pump Type
    ,                        !- Chilled Water Supply Side Bypass Pipe
    ,                        !- Chilled Water Demand Side Bypass Pipe
    ,                        !- Condenser Water Supply Side Bypass Pipe
    ,                        !- Condenser Water Demand Side Bypass Pipe
    ,                        !- Fluid Type
    ,                        !- Loop Design Delta Temperature {{deltaC}}
    7.22;                    !- Minimum Outdoor Dry Bulb Temperature {{C}}

  HVACTemplate:Plant:Chiller,
    Main Chiller,            !- Name
    ElectricReciprocatingChiller,  !- Chiller Type
    autosize,                !- Capacity {{W}}
    3.2,                     !- Nominal COP {{W/W}}
    WaterCooled,             !- Condenser Type
    1,                       !- Priority
    ;                        !- Sizing Factor

  HVACTemplate:Plant:Tower,
    Main Tower,              !- Name
    SingleSpeed,             !- Tower Type
    autosize,                !- High Speed Nominal Capacity {{W}}
    autosize,                !- High Speed Fan Power {{W}}
    autosize,                !- Low Speed Nominal Capacity {{W}}
    autosize,                !- Low Speed Fan Power {{W}}
    autosize,                !- Free Convection Capacity {{W}}
    1,                       !- Priority
    ;                        !- Sizing Factor

  HVACTemplate:Plant:HotWaterLoop,
    Hot Water Loop,          !- Name
    ,                        !- Pump Schedule Name
    INTERMITTENT,            !- Pump Control Type
    Default,                 !- Hot Water Plant Operation Scheme Type
    ,                        !- Hot Water Plant Equipment Operation Schemes Name
    ,                        !- Hot Water Setpoint Schedule Name
    82,                      !- Hot Water Design Setpoint {{C}}
    ConstantFlow,            !- Hot Water Pump Configuration
    179352,                  !- Hot Water Pump Rated Head {{Pa}}
    OutdoorAirTemperatureReset,  !- Hot Water Setpoint Reset Type
    82.2,                    !- Hot Water Setpoint at Outdoor Dry-Bulb Low {{C}}
    -6.7,                    !- Hot Water Reset Outdoor Dry-Bulb Low {{C}}
    65.6,                    !- Hot Water Setpoint at Outdoor Dry-Bulb High {{C}}
    10;                      !- Hot Water Reset Outdoor Dry-Bulb High {{C}}

  HVACTemplate:Plant:Boiler,
    Main Boiler,             !- Name
    HotWaterBoiler,          !- Boiler Type
    autosize,                !- Capacity {{W}}
    0.8,                     !- Efficiency
    NaturalGas,              !- Fuel Type
    1,                       !- Priority
    ;                        !- Sizing Factor

  Output:Variable,*,Site Outdoor Air Drybulb Temperature,hourly;
  Output:Variable,*,Zone Mean Air Temperature,Hourly;
  Output:Meter,Electricity:Facility,Monthly;
  Output:Meter,NaturalGas:Facility,Monthly;
  Output:Meter,Electricity:Facility,RunPeriod;
  Output:Meter,NaturalGas:Facility,RunPeriod;
  Output:Table:SummaryReports, AllSummary;
""")
    return "\n".join(parts)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dst", required=True)
    p.add_argument("--building-name", required=True)
    p.add_argument("--target-area-ft2", type=float, default=140_000.0)
    p.add_argument("--stories", type=int, default=6)
    p.add_argument("--floor-to-floor-ft", type=float, default=13.0)
    p.add_argument("--wwr", type=float, default=0.60)
    p.add_argument("--window-u", type=float, default=3.24)
    p.add_argument("--window-shgc", type=float, default=0.40)
    p.add_argument("--lights-w-m2", type=float, default=10.76)
    p.add_argument("--equip-w-m2", type=float, default=8.0)
    p.add_argument("--people-m2-per", type=float, default=18.58)
    p.add_argument("--infil-ach", type=float, default=0.35)
    p.add_argument("--lat", type=float, default=42.3314)
    p.add_argument("--lon", type=float, default=-83.0458)
    p.add_argument("--tz", type=float, default=-5.0)
    p.add_argument("--elevation-m", type=float, default=183.0)
    p.add_argument("--meta-out")
    args = p.parse_args()

    text = build_idf(
        building_name=args.building_name,
        target_area_ft2=args.target_area_ft2,
        stories=args.stories,
        floor_to_floor_ft=args.floor_to_floor_ft,
        wwr=args.wwr,
        window_u=args.window_u,
        window_shgc=args.window_shgc,
        lights_w_m2=args.lights_w_m2,
        equip_w_m2=args.equip_w_m2,
        people_m2_per_person=args.people_m2_per,
        infil_ach=args.infil_ach,
        lat=args.lat,
        lon=args.lon,
        tz=args.tz,
        elevation_m=args.elevation_m,
    )
    dst = Path(args.dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text)
    meta = {
        "dst": str(dst),
        "building_name": args.building_name,
        "target_area_ft2": args.target_area_ft2,
        "stories": args.stories,
        "zones": args.stories,
        "wwr": args.wwr,
        "hvac": "HVACTemplate VAV + WC chiller + HW boiler",
        "note": "6 stacked single-zone floors; interzone floor/ceiling; separate IDF per tower",
    }
    print(json.dumps(meta, indent=2))
    if args.meta_out:
        Path(args.meta_out).write_text(json.dumps(meta, indent=2) + "\n")


if __name__ == "__main__":
    main()
