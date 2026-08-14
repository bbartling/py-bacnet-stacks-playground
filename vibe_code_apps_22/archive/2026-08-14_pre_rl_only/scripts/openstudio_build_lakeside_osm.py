#!/usr/bin/env python
"""Build a polished Lakeside Elementary School OpenStudio model (.osm).

9 thermal zones (6 BAS Areas + Gym + Cafe_Kitchen + Library_IMC), IdealLoads
+ Semco ERV proxy, utility-GL14 knobs (infil x1.2, lights x0.8 from util_103).

Run with OpenStudio's embedded interpreter (not system Python):

  .\\scripts\\run_os_py.ps1 .\\scripts\\openstudio_build_lakeside_osm.py
"""
from __future__ import annotations


import sys
from pathlib import Path as _PathForLakeside

_APP = _PathForLakeside(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
from lakeside.paths import (  # noqa: E402
    BUILDING_LABEL,
    CAMPUS_ID,
    REGION_LABEL,
    app_root,
    clean_data_building_dir,
    eplus_dir,
    packages_dir,
    reports_dir,
    site_root,
    utilities_dir,
)
from lakeside.paths import BUILDING_ID as _LAKESIDE_BUILDING_ID  # noqa: E402
from lakeside.paths import SITE_REF as _LAKESIDE_SITE_REF  # noqa: E402
import json
import math
import sys
from pathlib import Path

import openstudio

ROOT = site_root()
OUT_DIR = ROOT / "eplus" / "models"
OUT_OSM = OUT_DIR / "lakeside_9zone_openstudio.osm"
OUT_IDF = OUT_DIR / "lakeside_9zone_openstudio.idf"
OUT_META = OUT_DIR / "lakeside_9zone_openstudio_meta.json"
from eplus_gym_app.weather_files import resolve_amy_epw  # noqa: E402

AMY = resolve_amy_epw(ROOT) or (ROOT / "eplus" / "weather" / "madison_amy_202508_202607.epw")
TARGETS = ROOT / "eplus" / "assumptions" / "bas_calibration_targets.json"
FAN_CSV = ROOT / "reports" / "zone_avg_fan_run_hours_monthly.csv"

FT2_TO_M2 = 0.092903
WFT2 = 10.7639
STACK_H_M = 13.0 * 0.3048
CLASS_CLEAR_M = 10.0 * 0.3048

# util_103 (utility G14 pass)
LIGHTS_MULT = 0.8
INFIL_MULT = 1.2
INFIL_BASE = 0.000610  # m3/s-m2 exterior

WWR = {"N": 0.30, "S": 0.35, "E": 0.325, "W": 0.325}
WINDOW_U = 0.35 * 5.678263
WINDOW_SHGC = 0.34
WINDOW_VT = 0.52

AREA_ZONES = [
    ("1F_Area_A", 15, 1),
    ("1F_Area_B", 10, 1),
    ("1F_Area_C", 11, 1),
    ("1F_Area_D", 10, 1),
    ("2F_Area_A", 11, 2),
    ("2F_Area_B", 10, 2),
]
PROGRAM_ZONES = [
    ("1F_Library_IMC", 4000.0, 12.0, "library", "1F_Area_A"),
    ("1F_Cafe_Kitchen", 6600.0, 14.0, "cafe", "1F_Area_C"),
    ("1F_Gym", 7500.0, 24.0, "gym", "1F_Area_D"),
]
GROSS = 91210.0
FLOOR1_GROSS = 54700.0
FLOOR2_GROSS = 36500.0
COND = 89400.0
HP_1F = sum(z[1] for z in AREA_ZONES if z[2] == 1)
HP_2F = sum(z[1] for z in AREA_ZONES if z[2] == 2)


def f2c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def ft2_m2(ft2: float) -> float:
    return ft2 * FT2_TO_M2


def zone_lw(area_m2: float, aspect: float = 2.2) -> tuple[float, float]:
    w = math.sqrt(area_m2 / aspect)
    return aspect * w, w


def load_sp() -> tuple[float, float]:
    ho, hu = 68.0, 65.0
    if TARGETS.is_file():
        zt = json.loads(TARGETS.read_text(encoding="utf-8")).get("zone_temp") or {}
        ho = float(zt.get("bas_heat_setpoint_occ_f") or ho)
        hu = float(zt.get("recommended_heat_setback_unocc_f") or hu)
    return ho, hu


def fan_wm2() -> dict[str, float]:
    out = {z[0]: 2.0 for z in AREA_ZONES}
    if not FAN_CSV.is_file():
        return out
    try:
        import csv

        rows = list(csv.DictReader(FAN_CSV.open(encoding="utf-8")))
        # winter-weighted mean hours → crude W/m2 proxy (same spirit as eplus seed)
        by = {}
        for r in rows:
            zid = r.get("zone_id") or r.get("equip_id") or ""
            # zone_avg file uses zone_id like 1F_Area_A
            h = float(r.get("avg_fan_run_hours") or r.get("fan_run_hours") or 0)
            by.setdefault(zid, []).append(h)
        for zid, hrs in by.items():
            if zid in out and hrs:
                # map ~80h/mo winter → ~3 W/m2-ish; clamp
                avg = sum(hrs) / len(hrs)
                out[zid] = max(1.0, min(6.0, avg / 30.0))
    except Exception as e:
        print("fan proxy fallback:", e)
    return out


def zone_specs() -> list[dict]:
    f1 = COND * (FLOOR1_GROSS / GROSS)
    f2 = COND * (FLOOR2_GROSS / GROSS)
    program_total = sum(p[1] for p in PROGRAM_ZONES)
    classroom_1f = f1 - program_total
    specs = []
    for zid, ft2, clear_ft, kind, _src in PROGRAM_ZONES:
        specs.append(
            {
                "id": zid,
                "floor": 1,
                "n_hp": 0,
                "kind": kind,
                "area_ft2": ft2,
                "height_m": clear_ft * 0.3048,
                "aspect": 1.4 if kind == "gym" else 1.8,
            }
        )
    for zid, n_hp, floor in AREA_ZONES:
        if floor != 1:
            continue
        specs.append(
            {
                "id": zid,
                "floor": 1,
                "n_hp": n_hp,
                "kind": "classroom",
                "area_ft2": classroom_1f * (n_hp / HP_1F),
                "height_m": CLASS_CLEAR_M,
                "aspect": 2.2,
            }
        )
    for zid, n_hp, floor in AREA_ZONES:
        if floor != 2:
            continue
        specs.append(
            {
                "id": zid,
                "floor": 2,
                "n_hp": n_hp,
                "kind": "classroom",
                "area_ft2": f2 * (n_hp / HP_2F),
                "height_m": CLASS_CLEAR_M,
                "aspect": 2.2,
            }
        )
    return specs


def space_loads(kind: str) -> dict:
    # deep-research-ish LPD/EPD W/ft2 → W/m2, then lights mult applied later
    base = {
        "classroom": {"people_m2": 0.25, "lpd_wft2": 0.9, "epd_wft2": 0.75, "oa_p": 0.0025, "oa_a": 0.0003},
        "library": {"people_m2": 0.20, "lpd_wft2": 1.0, "epd_wft2": 0.8, "oa_p": 0.0025, "oa_a": 0.0003},
        "cafe": {"people_m2": 0.35, "lpd_wft2": 0.8, "epd_wft2": 1.0, "kitchen_wft2": 2.5, "oa_p": 0.0035, "oa_a": 0.0006},
        "gym": {"people_m2": 0.30, "lpd_wft2": 0.9, "epd_wft2": 0.5, "oa_p": 0.0030, "oa_a": 0.0004},
    }[kind]
    return base


def always_on(m, name: str, val: float = 1.0):
    s = openstudio.model.ScheduleConstant(m)
    s.setName(name)
    s.setValue(val)
    return s


def ruleset_day(m, name: str, hourly: list[float]):
    """Create ScheduleRuleset with one default day (24 hourly values)."""
    sch = openstudio.model.ScheduleRuleset(m)
    sch.setName(name)
    day = sch.defaultDaySchedule()
    day.setName(f"{name}_Default")
    for h, v in enumerate(hourly):
        day.addValue(openstudio.Time(0, h + 1, 0), float(v))
    return sch


def k12_occ_hourly() -> list[float]:
    # HE 0..23 local-ish school profile
    out = [0.0] * 24
    for h in range(7, 16):
        out[h] = 0.95 if 8 <= h <= 14 else 0.6
    return out


def k12_hvac_hourly() -> list[float]:
    out = [0.0] * 24
    for h in range(5, 18):
        out[h] = 1.0
    return out


def make_constructions(m):
    # Simple opaque layers (SI)
    def mat(name, thick, k, rho=800, cp=1000):
        x = openstudio.model.StandardOpaqueMaterial(m)
        x.setName(name)
        x.setThickness(thick)
        x.setConductivity(k)
        x.setDensity(rho)
        x.setSpecificHeat(cp)
        return x

    conc = mat("Mat_Conc", 0.1, 1.4, 2200, 900)
    ins = mat("Mat_Insul", 0.08, 0.04, 40, 1000)  # ~R-20 SI-ish
    gyp = mat("Mat_Gyp", 0.012, 0.16, 800, 1000)
    deck = mat("Mat_RoofDeck", 0.02, 45, 7800, 500)
    rins = mat("Mat_RoofIns", 0.12, 0.04, 40, 1000)

    wall = openstudio.model.Construction(m)
    wall.setName("ExtWall")
    wall.insertLayer(0, conc)
    wall.insertLayer(1, ins)
    wall.insertLayer(2, gyp)

    roof = openstudio.model.Construction(m)
    roof.setName("ExtRoof")
    roof.insertLayer(0, deck)
    roof.insertLayer(1, rins)
    roof.insertLayer(2, gyp)

    floor = openstudio.model.Construction(m)
    floor.setName("ExtFloor")
    floor.insertLayer(0, ins)
    floor.insertLayer(1, conc)

    glz = openstudio.model.SimpleGlazing(m)
    glz.setName("SimpleGlazing")
    glz.setUFactor(WINDOW_U)
    glz.setSolarHeatGainCoefficient(WINDOW_SHGC)
    glz.setVisibleTransmittance(WINDOW_VT)
    win = openstudio.model.Construction(m)
    win.setName("ExtWindow")
    win.insertLayer(0, glz)

    ext = openstudio.model.DefaultSurfaceConstructions(m)
    ext.setName("Lakeside_ExtSurfaces")
    ext.setWallConstruction(wall)
    ext.setRoofCeilingConstruction(roof)
    ext.setFloorConstruction(floor)

    sub = openstudio.model.DefaultSubSurfaceConstructions(m)
    sub.setName("Lakeside_ExtSubSurfaces")
    sub.setFixedWindowConstruction(win)

    gnd = openstudio.model.DefaultSurfaceConstructions(m)
    gnd.setName("Lakeside_GroundSurfaces")
    gnd.setFloorConstruction(floor)

    cs = openstudio.model.DefaultConstructionSet(m)
    cs.setName("Lakeside_DefaultConstructions")
    cs.setDefaultExteriorSurfaceConstructions(ext)
    cs.setDefaultExteriorSubSurfaceConstructions(sub)
    cs.setDefaultGroundContactSurfaceConstructions(gnd)
    return cs


def add_wwr(space, wwr_by_face: dict):
    for surf in space.surfaces():
        if surf.surfaceType() != "Wall" or surf.outsideBoundaryCondition() != "Outdoors":
            continue
        # outward normal ≈ face orientation
        n = surf.outwardNormal()
        nx, ny = n.x(), n.y()
        if abs(ny) >= abs(nx):
            face = "N" if ny > 0 else "S"
        else:
            face = "E" if nx > 0 else "W"
        target = wwr_by_face.get(face, 0.32)
        ok = surf.setWindowToWallRatio(target)
        if not ok:
            # older API returns bool; newer may return Optional
            try:
                surf.setWindowToWallRatio(target, 0.9)  # sill height m fraction alternate
            except Exception:
                pass


def build() -> openstudio.model.Model:
    m = openstudio.model.Model()

    bldg = m.getBuilding()
    bldg.setName("Lakeside Elementary School")
    bldg.setStandardsBuildingType("PrimarySchool")
    bldg.setNominalFloortoFloorHeight(STACK_H_M)

    site = m.getSite()
    site.setName("southern Wisconsin")
    site.setLatitude(43.16521)
    site.setLongitude(-89.25408)
    site.setTimeZone(-6.0)
    site.setElevation(280.0)

    if AMY.is_file():
        epw = openstudio.EpwFile(openstudio.path(str(AMY)))
        openstudio.model.WeatherFile.setWeatherFile(m, epw)

    year = m.getYearDescription()
    year.setCalendarYear(2025)

    run = m.getRunPeriod()
    run.setName("AMY_LAKESIDE")
    run.setBeginMonth(8)
    run.setBeginDayOfMonth(1)
    run.setEndMonth(7)
    run.setEndDayOfMonth(2)  # match EPW DATA PERIODS end
    run.setUseWeatherFileHolidays(False)
    run.setUseWeatherFileDaylightSavings(False)
    run.setUseWeatherFileRainInd(True)
    run.setUseWeatherFileSnowInd(True)
    run.setApplyWeekendHolidayRule(False)
    run.setUseWeatherFileRainInd(True)

    # Design days (EPW has DESIGN CONDITIONS,0)
    dd_w = openstudio.model.DesignDay(m)
    dd_w.setName("Madison Winter")
    dd_w.setDayType("WinterDesignDay")
    dd_w.setMonth(1)
    dd_w.setDayOfMonth(21)
    dd_w.setMaximumDryBulbTemperature(-17.8)
    dd_w.setDailyDryBulbTemperatureRange(0.0)
    dd_w.setHumidityIndicatingConditionsAtMaximumDryBulb(-17.8)
    dd_w.setHumidityIndicatingType("Wetbulb")
    dd_w.setBarometricPressure(99000)
    dd_w.setWindSpeed(3.5)
    dd_w.setWindDirection(270)
    dd_w.setSolarModelIndicator("ASHRAEClearSky")
    dd_w.setSkyClearness(0.0)

    dd_s = openstudio.model.DesignDay(m)
    dd_s.setName("Madison Summer")
    dd_s.setDayType("SummerDesignDay")
    dd_s.setMonth(7)
    dd_s.setDayOfMonth(21)
    dd_s.setMaximumDryBulbTemperature(33.0)
    dd_s.setDailyDryBulbTemperatureRange(10.0)
    dd_s.setHumidityIndicatingConditionsAtMaximumDryBulb(23.0)
    dd_s.setHumidityIndicatingType("Wetbulb")
    dd_s.setBarometricPressure(99000)
    dd_s.setWindSpeed(4.0)
    dd_s.setWindDirection(230)
    dd_s.setSolarModelIndicator("ASHRAEClearSky")
    dd_s.setSkyClearness(1.0)

    ts = m.getTimestep()
    ts.setNumberOfTimestepsPerHour(4)

    sim = m.getSimulationControl()
    sim.setDoZoneSizingCalculation(True)
    sim.setDoSystemSizingCalculation(True)
    sim.setRunSimulationforSizingPeriods(True)
    sim.setRunSimulationforWeatherFileRunPeriods(True)

    cs = make_constructions(m)
    bldg.setDefaultConstructionSet(cs)

    story1 = openstudio.model.BuildingStory(m)
    story1.setName("First Floor")
    story1.setNominalZCoordinate(0.0)
    story1.setNominalFloortoFloorHeight(STACK_H_M)
    story2 = openstudio.model.BuildingStory(m)
    story2.setName("Second Floor")
    story2.setNominalZCoordinate(STACK_H_M)
    story2.setNominalFloortoFloorHeight(STACK_H_M)

    # Space types
    stypes = {}
    for kind in ("classroom", "library", "cafe", "gym"):
        st = openstudio.model.SpaceType(m)
        st.setName(f"ST_{kind}")
        st.setStandardsSpaceType(kind.title() if kind != "cafe" else "Cafeteria")
        stypes[kind] = st

    always = always_on(m, "SCH_AlwaysOn", 1.0)
    infil_sch = always_on(m, "SCH_Infil", 1.0)
    occ_sch = ruleset_day(m, "SCH_Occ_K12", k12_occ_hourly())
    light_sch = ruleset_day(m, "SCH_Lights_K12", k12_occ_hourly())
    equip_sch = ruleset_day(m, "SCH_Equip_K12", [max(0.2, v) for v in k12_occ_hourly()])
    hvac_sch = ruleset_day(m, "SCH_HVAC_K12", k12_hvac_hourly())
    kitchen_sch = ruleset_day(
        m,
        "SCH_Kitchen",
        [1.0 if 6 <= h <= 13 else 0.1 for h in range(24)],
    )
    act_sch = always_on(m, "SCH_Activity", 120.0)  # W/person

    ho_f, hu_f = load_sp()
    co_f, cu_f = 74.0, 85.0
    # heating SP: occ hours use ho, else hu — approximate with dual constant via ruleset
    htg_hr = [f2c(ho_f) if 7 <= h < 16 else f2c(hu_f) for h in range(24)]
    clg_hr = [f2c(co_f) if 7 <= h < 16 else f2c(cu_f) for h in range(24)]
    htg_sch = ruleset_day(m, "SCH_HtgSP", htg_hr)
    clg_sch = ruleset_day(m, "SCH_ClgSP", clg_hr)

    fans = fan_wm2()
    specs = zone_specs()

    x_prog = 0.0
    y_prog = 80.0
    x_c = {1: 0.0, 2: 0.0}

    for spec in specs:
        zid = spec["id"]
        kind = spec["kind"]
        area_m2 = ft2_m2(spec["area_ft2"])
        L, W = zone_lw(area_m2, spec["aspect"])
        H = spec["height_m"]
        floor = spec["floor"]

        if kind in ("gym", "cafe", "library"):
            x0, y0, z0 = x_prog, y_prog, 0.0
            x_prog += L + 3.0
        else:
            z0 = (floor - 1) * STACK_H_M
            x0 = x_c[floor]
            y0 = 0.0
            x_c[floor] += L + 2.0

        pts = openstudio.Point3dVector()
        # Clockwise when viewed from above so floor outward normal points down
        for x, y in ((x0, y0), (x0, y0 + W), (x0 + L, y0 + W), (x0 + L, y0)):
            pts.append(openstudio.Point3d(x, y, z0))

        space_opt = openstudio.model.Space.fromFloorPrint(pts, H, m)
        if not space_opt.is_initialized():
            raise RuntimeError(f"fromFloorPrint failed for {zid}")
        space = space_opt.get()
        space.setName(zid)
        space.setBuildingStory(story1 if floor == 1 else story2)
        space.setSpaceType(stypes[kind])
        space.setDefaultConstructionSet(cs)

        zone = openstudio.model.ThermalZone(m)
        zone.setName(zid)
        space.setThermalZone(zone)

        add_wwr(space, WWR)

        loads = space_loads(kind)

        # People
        pd = openstudio.model.PeopleDefinition(m)
        pd.setName(f"{zid}_PeopleDef")
        pd.setPeopleperSpaceFloorArea(loads["people_m2"])
        people = openstudio.model.People(pd)
        people.setName(f"{zid}_People")
        people.setSpace(space)
        people.setNumberofPeopleSchedule(occ_sch)
        people.setActivityLevelSchedule(act_sch)

        # Lights (util_103 lights x0.8)
        ld = openstudio.model.LightsDefinition(m)
        ld.setName(f"{zid}_LightsDef")
        ld.setWattsperSpaceFloorArea(loads["lpd_wft2"] * WFT2 * LIGHTS_MULT)
        lights = openstudio.model.Lights(ld)
        lights.setName(f"{zid}_Lights")
        lights.setSpace(space)
        lights.setSchedule(light_sch)

        # Plug loads
        ed = openstudio.model.ElectricEquipmentDefinition(m)
        ed.setName(f"{zid}_EquipDef")
        ed.setWattsperSpaceFloorArea(loads["epd_wft2"] * WFT2)
        eq = openstudio.model.ElectricEquipment(ed)
        eq.setName(f"{zid}_Equip")
        eq.setSpace(space)
        eq.setSchedule(equip_sch)

        if kind == "cafe" and loads.get("kitchen_wft2"):
            kd = openstudio.model.ElectricEquipmentDefinition(m)
            kd.setName(f"{zid}_KitchenDef")
            kd.setWattsperSpaceFloorArea(loads["kitchen_wft2"] * WFT2)
            kq = openstudio.model.ElectricEquipment(kd)
            kq.setName(f"{zid}_Kitchen")
            kq.setSpace(space)
            kq.setSchedule(kitchen_sch)

        # Fan proxy as electric equipment
        fan_w = fans.get(zid, 2.0)
        fd = openstudio.model.ElectricEquipmentDefinition(m)
        fd.setName(f"{zid}_FanProxyDef")
        fd.setWattsperSpaceFloorArea(fan_w)
        fq = openstudio.model.ElectricEquipment(fd)
        fq.setName(f"{zid}_FanProxy")
        fq.setSpace(space)
        fq.setSchedule(hvac_sch)

        # Infiltration (util_103 infil x1.2)
        inf = openstudio.model.SpaceInfiltrationDesignFlowRate(m)
        inf.setName(f"{zid}_Infil")
        inf.setSpace(space)
        inf.setSchedule(infil_sch)
        inf.setFlowperExteriorSurfaceArea(INFIL_BASE * INFIL_MULT)

        # Thermostat + IdealLoads
        tstat = openstudio.model.ThermostatSetpointDualSetpoint(m)
        tstat.setName(f"{zid}_DualSP")
        tstat.setHeatingSetpointTemperatureSchedule(htg_sch)
        tstat.setCoolingSetpointTemperatureSchedule(clg_sch)
        zone.setThermostatSetpointDualSetpoint(tstat)

        il = openstudio.model.ZoneHVACIdealLoadsAirSystem(m)
        il.setName(f"{zid}_Ideal")
        il.setAvailabilitySchedule(hvac_sch)
        il.setHeatingAvailabilitySchedule(hvac_sch)
        il.setCoolingAvailabilitySchedule(hvac_sch)
        il.setMaximumHeatingSupplyAirTemperature(50.0)
        il.setMinimumCoolingSupplyAirTemperature(13.0)
        il.setHeatRecoveryType("Enthalpy")
        il.setSensibleHeatRecoveryEffectiveness(0.70)
        il.setLatentHeatRecoveryEffectiveness(0.55)
        il.addToThermalZone(zone)

        # OA design
        dsoa = openstudio.model.DesignSpecificationOutdoorAir(m)
        dsoa.setName(f"{zid}_OA")
        dsoa.setOutdoorAirMethod("Sum")
        dsoa.setOutdoorAirFlowperPerson(loads["oa_p"])
        dsoa.setOutdoorAirFlowperFloorArea(loads["oa_a"])
        space.setDesignSpecificationOutdoorAir(dsoa)

    # Output meters (E+ 25.x IdealLoads heat fuel → DistrictHeatingWater)
    for var in (
        "Electricity:Facility",
        "DistrictHeatingWater:Facility",
        "DistrictCooling:Facility",
        "InteriorLights:Electricity",
        "InteriorEquipment:Electricity",
    ):
        om = openstudio.model.OutputMeter(m)
        om.setName(var)
        om.setReportingFrequency("Monthly")

    return m


def patch_idf_runperiod(idf_text: str) -> str:
    """Ensure RunPeriod spans AMY years 2025-08-01 .. 2026-07-02."""
    import re

    def repl(m: re.Match) -> str:
        block = m.group(0)
        if re.search(r"Begin Year", block, re.I):
            return block
        lines = block.splitlines()
        out = []
        inserted_begin = False
        inserted_end = False
        for line in lines:
            out.append(line)
            if (not inserted_begin) and "Begin Day of Month" in line:
                out.append("    2025,                     !- Begin Year")
                inserted_begin = True
            elif inserted_begin and (not inserted_end) and "End Day of Month" in line:
                out.append("    2026,                     !- End Year")
                inserted_end = True
        return "\n".join(out)

    return re.sub(r"(?is)RunPeriod,.*?;", repl, idf_text, count=1)


def main() -> int:
    print("Building Lakeside OpenStudio model...")
    print("OpenStudio", openstudio.openStudioVersion(), "EnergyPlus", openstudio.energyPlusVersion())
    m = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    osm_path = openstudio.path(str(OUT_OSM))
    m.save(osm_path, True)
    print("wrote", OUT_OSM)

    ft = openstudio.energyplus.ForwardTranslator()
    ws = ft.translateModel(m)
    idf_path = openstudio.path(str(OUT_IDF))
    ws.save(idf_path, True)

    raw = OUT_IDF.read_text(encoding="utf-8", errors="replace")
    patched = patch_idf_runperiod(raw)
    # Align end day with EPW
    patched = patched.replace(
        "    7,                        !- End Month\n    3,",
        "    7,                        !- End Month\n    2,",
    )
    # E+ 25.2 meter rename (OS may still emit legacy DistrictHeating:Facility)
    patched = patched.replace("DistrictHeating:Facility", "DistrictHeatingWater:Facility")
    OUT_IDF.write_text(patched, encoding="utf-8")
    print("wrote", OUT_IDF, "(runperiod patched for AMY years)")

    meta = {
        "osm": str(OUT_OSM),
        "idf": str(OUT_IDF),
        "openstudio_version": openstudio.openStudioVersion(),
        "energyplus_version_sdk": openstudio.energyPlusVersion(),
        "n_spaces": len(list(m.getSpaces())),
        "n_zones": len(list(m.getThermalZones())),
        "n_surfaces": len(list(m.getSurfaces())),
        "knobs": {"lights_mult": LIGHTS_MULT, "infil_mult": INFIL_MULT, "source": "util_103"},
        "hvac": "ZoneHVACIdealLoadsAirSystem + enthalpy HR (Semco proxy)",
        "honesty": (
            "IdealLoads + COP proxy for site electric — not a full GSHP/GLHE plant. "
            "Geometry is rectangular program massing, not CAD. "
            "No Docker; native OpenStudio 3.11 SDK."
        ),
        "zones": [s["id"] for s in zone_specs()],
    }
    OUT_META.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
