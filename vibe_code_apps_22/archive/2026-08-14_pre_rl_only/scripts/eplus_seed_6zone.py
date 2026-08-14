#!/usr/bin/env python
"""Build Lakeside 9-zone IdealLoads IDF (6 BAS Areas + Gym + Cafe/Kitchen + Library/IMC).

Massing / zoning (deep-research-report.md + BAS Areas):
- 2 stories, 54,700 / 36,500 ft2 gross split → conditioned carve
- Classroom Areas: 10 ft clear; Library 12 ft; Cafe/Kitchen 14 ft; Gym 24 ft
- Program ft2 peeled from 1F Areas A/C/D; 2F remains academic wing

BAS dial-ins:
- Occupied SP 68/74 F (HP graphics); unocc heat ~65 F from Jan zn_t analytics
- Fan proxy W/m2 from zone_avg_fan_run_hours_monthly.csv (thermal_zone_analytics)
- Lunch / gym / kitchen schedules from deep-research operating hours
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
APP = app_root()
import json
import math
import os
import sys
from pathlib import Path

ROOT = site_root()
OUT = ROOT / "eplus" / "models" / "lakeside_6zone_gshp_v0.idf"  # campaign seed path
OUT9 = ROOT / "eplus" / "models" / "lakeside_9zone_gshp_v0.idf"
LATEST = ROOT / "eplus" / "models" / "lakeside_6zone_gshp_latest.idf"
TARGETS = ROOT / "eplus" / "assumptions" / "bas_calibration_targets.json"
LEDGER = ROOT / "eplus" / "assumptions" / "ledger.json"
ANSWERS = ROOT / "eplus" / "assumptions" / "answers.json"
FAN_CSV = ROOT / "reports" / "zone_avg_fan_run_hours_monthly.csv"
IDD = Path(r"C:\EnergyPlusV26-1-0\Energy+.idd")

MCP_VENV = ROOT.parent / "EnergyPlus-MCP" / "energyplus-mcp-server" / ".venv" / "Lib" / "site-packages"
if MCP_VENV.is_dir():
    sys.path.insert(0, str(MCP_VENV))

from eppy.modeleditor import IDF  # noqa: E402

# BAS Area pods (HP counts for fan proxy / 2F split). Program zones have n_hp=0.
AREA_ZONES = [
    ("1F_Area_A", 15, 1),
    ("1F_Area_B", 10, 1),
    ("1F_Area_C", 11, 1),
    ("1F_Area_D", 10, 1),
    ("2F_Area_A", 11, 2),
    ("2F_Area_B", 10, 2),
]
# Carved from 1F Areas (deep-research program + BAS IMC in Area A)
PROGRAM_ZONES = [
    # id, ft2, clear_ft, kind, carve_from_area
    ("1F_Library_IMC", 4000.0, 12.0, "library", "1F_Area_A"),
    ("1F_Cafe_Kitchen", 6600.0, 14.0, "cafe", "1F_Area_C"),  # 4800 cafe + 1800 kitchen
    ("1F_Gym", 7500.0, 24.0, "gym", "1F_Area_D"),
]
GROSS_FT2 = 91210.0
COND_FT2 = 89400.0
FLOOR1_GROSS_FT2 = 54700.0
FLOOR2_GROSS_FT2 = 36500.0
# Academic wing floor-to-floor for stacking 2F over classroom 1F
STACK_H_M = 13.0 * 0.3048
CLASS_CLEAR_FT = 10.0
HP_1F = sum(z[1] for z in AREA_ZONES if z[2] == 1)
HP_2F = sum(z[1] for z in AREA_ZONES if z[2] == 2)
HEAT_COP, COOL_COP = 3.5, 4.5

WWR_BY_FACE = {
    "N": float(os.environ.get("EPLUS_WWR_N", "0.30")),
    "S": float(os.environ.get("EPLUS_WWR_S", "0.35")),
    "E": float(os.environ.get("EPLUS_WWR_E", "0.325")),
    "W": float(os.environ.get("EPLUS_WWR_W", "0.325")),
}
DEFAULT_WWR = float(os.environ.get("EPLUS_SEED_WWR", "0.32"))
WINDOW_U_IP = float(os.environ.get("EPLUS_SEED_WINDOW_U_IP", "0.35"))
WINDOW_U = float(os.environ.get("EPLUS_SEED_WINDOW_U", str(WINDOW_U_IP * 5.678263)))
WINDOW_SHGC = float(os.environ.get("EPLUS_SEED_WINDOW_SHGC", "0.34"))
WINDOW_VT = float(os.environ.get("EPLUS_SEED_WINDOW_VT", "0.52"))

# deep-research LPD W/ft2 → W/m2; EPD W/ft2 → W/m2
FT2_TO_M2 = 0.092903
WFT2 = 10.7639  # W/m2 per W/ft2


def f2c(f: float) -> float:
    return (f - 32.0) * 5.0 / 9.0


def ft2_to_m2(ft2: float) -> float:
    return ft2 * FT2_TO_M2


def load_sp():
    ho, hu = 68.0, 65.0
    if TARGETS.is_file():
        zt = json.loads(TARGETS.read_text(encoding="utf-8")).get("zone_temp") or {}
        ho = float(zt.get("bas_heat_setpoint_occ_f") or zt.get("recommended_heat_setpoint_occ_f") or ho)
        hu = float(zt.get("recommended_heat_setback_unocc_f") or hu)
    return ho, hu


def fan_wm2_by_area() -> dict[str, float]:
    """Map BAS Area → fan proxy W/m2 from monthly avg fan run hours (plots/analytics source)."""
    out = {z[0]: 2.0 for z in AREA_ZONES}
    # Prefer live CSV used by zone_avg_fan_run_hours_by_month.png
    if FAN_CSV.is_file():
        import pandas as pd

        df = pd.read_csv(FAN_CSV)
        # Use winter-weighted mean (Nov–Feb) when available — matches heating-dominated runtime
        winter = df[df["month"].astype(str).str.match(r".*-(11|12|01|02)$")]
        use = winter if len(winter) else df
        for zid, g in use.groupby("zone_id"):
            mean_h = float(g["avg_fan_run_hours"].mean())
            # Scale ~2 W/m2 at 40 h/mo; clamp 0.5–4.0 (program zones get fixed below)
            out[str(zid)] = max(0.5, min(4.0, 2.0 * (mean_h / 40.0)))
        return out
    if TARGETS.is_file():
        fr = (json.loads(TARGETS.read_text(encoding="utf-8")).get("fan_runtime") or {}).get("by_zone") or {}
        vals = [v.get("avg_fan_run_hours") or 0 for v in fr.values()]
        mean = sum(vals) / len(vals) if vals else 40.0
        for z, _, _ in AREA_ZONES:
            hrs = (fr.get(z) or {}).get("avg_fan_run_hours") or mean
            out[z] = max(0.5, min(4.0, 2.0 * (hrs / max(mean, 1.0))))
    return out


def conditioned_by_floor_ft2() -> tuple[float, float]:
    f1 = COND_FT2 * (FLOOR1_GROSS_FT2 / GROSS_FT2)
    f2 = COND_FT2 * (FLOOR2_GROSS_FT2 / GROSS_FT2)
    return f1, f2


def build_zone_specs() -> list[dict]:
    """Return list of zone dicts with area_ft2, height_m, kind, floor, n_hp."""
    f1, f2 = conditioned_by_floor_ft2()
    carve = {p[4]: p[1] for p in PROGRAM_ZONES}
    program_total = sum(carve.values())
    classroom_1f = f1 - program_total
    if classroom_1f < 5000:
        raise RuntimeError(f"1F classroom remainder too small: {classroom_1f}")

    specs: list[dict] = []
    # Program zones first (geometry placed beside academic wing)
    for zid, ft2, clear_ft, kind, _src in PROGRAM_ZONES:
        specs.append({
            "id": zid, "floor": 1, "n_hp": 0, "kind": kind,
            "area_ft2": ft2, "height_m": clear_ft * 0.3048,
            "aspect": 1.4 if kind == "gym" else 1.8,
        })

    # 1F Areas — HP-share of remaining classroom area
    for zid, n_hp, floor in AREA_ZONES:
        if floor != 1:
            continue
        ft2 = classroom_1f * (n_hp / HP_1F)
        specs.append({
            "id": zid, "floor": 1, "n_hp": n_hp, "kind": "classroom",
            "area_ft2": ft2, "height_m": CLASS_CLEAR_FT * 0.3048, "aspect": 2.2,
        })
    # 2F Areas — full 2F conditioned
    for zid, n_hp, floor in AREA_ZONES:
        if floor != 2:
            continue
        ft2 = f2 * (n_hp / HP_2F)
        specs.append({
            "id": zid, "floor": 2, "n_hp": n_hp, "kind": "classroom",
            "area_ft2": ft2, "height_m": CLASS_CLEAR_FT * 0.3048, "aspect": 2.2,
        })
    return specs


def space_loads(kind: str) -> dict:
    """People/m2 design, LPD W/m2, EPD W/m2, OA cfm→SI, schedules, activity W."""
    # OA: deep-research table (cfm/person, cfm/ft2) → m3/s-person, m3/s-m2
    def oa(cfm_p, cfm_ft2):
        return cfm_p * 0.000471947, cfm_ft2 * 0.000471947 / FT2_TO_M2

    if kind == "classroom":
        # ~25 p / 900 ft2 active rooms, diluted for flex → ~0.045 /m2
        return {
            "people_m2": 0.045, "lpd": 0.80 * WFT2, "epd": 0.60 * WFT2,
            "oa_p": oa(10, 0.12)[0], "oa_a": oa(10, 0.12)[1],
            "occ_sch": "SCH_Occ_Class", "light_sch": "SCH_Lights", "equip_sch": "SCH_Equip",
            "activity": 120.0, "fan_wm2_default": 2.0,
        }
    if kind == "library":
        return {
            "people_m2": 0.012, "lpd": 0.90 * WFT2, "epd": 1.00 * WFT2,
            "oa_p": oa(5, 0.12)[0], "oa_a": oa(5, 0.12)[1],
            "occ_sch": "SCH_Occ_Library", "light_sch": "SCH_Lights", "equip_sch": "SCH_Equip",
            "activity": 120.0, "fan_wm2_default": 1.5,
        }
    if kind == "cafe":
        # Peak lunch ~130 people / 6600 ft2 ≈ 0.021 /ft2 → 0.23 /m2 at peak; design people/area mid
        return {
            "people_m2": 0.18, "lpd": 0.80 * WFT2, "epd": 0.50 * WFT2,
            "oa_p": oa(7.5, 0.18)[0], "oa_a": oa(7.5, 0.18)[1],
            "occ_sch": "SCH_Occ_Cafe", "light_sch": "SCH_Lights", "equip_sch": "SCH_Equip",
            "activity": 130.0, "fan_wm2_default": 1.8,
            "kitchen_epd": 2.5 * WFT2,  # diversified kitchen process on SCH_Kitchen
        }
    if kind == "gym":
        return {
            "people_m2": 0.008, "lpd": 0.65 * WFT2, "epd": 0.30 * WFT2,
            "oa_p": oa(20, 0.18)[0], "oa_a": oa(20, 0.18)[1],
            "occ_sch": "SCH_Occ_Gym", "light_sch": "SCH_Lights_Gym", "equip_sch": "SCH_Equip",
            "activity": 250.0, "fan_wm2_default": 1.2,
        }
    raise KeyError(kind)


def zone_lw(area_m2: float, aspect: float):
    w = math.sqrt(area_m2 / aspect)
    return area_m2 / w, w


def _pt(bl, br, tl, u: float, v: float):
    return (
        bl[0] + u * (br[0] - bl[0]) + v * (tl[0] - bl[0]),
        bl[1] + u * (br[1] - bl[1]) + v * (tl[1] - bl[1]),
        bl[2] + u * (br[2] - bl[2]) + v * (tl[2] - bl[2]),
    )


def add_window(idf: IDF, name: str, wall_name: str, wall_verts, wwr: float):
    if wwr <= 0.01:
        return
    bl, br, tr, tl = wall_verts
    sill, head = 0.12, 0.88
    h_frac = head - sill
    w_frac = min(0.92, max(0.05, wwr / h_frac))
    u0 = (1.0 - w_frac) / 2.0
    u1 = u0 + w_frac
    verts = [
        _pt(bl, br, tl, u0, sill),
        _pt(bl, br, tl, u1, sill),
        _pt(bl, br, tl, u1, head),
        _pt(bl, br, tl, u0, head),
    ]
    f = idf.newidfobject("FENESTRATIONSURFACE:DETAILED")
    f.Name = name
    f.Surface_Type = "Window"
    f.Construction_Name = "ExtWindow"
    f.Building_Surface_Name = wall_name
    f.Number_of_Vertices = 4
    for i, (x, y, z) in enumerate(verts, 1):
        setattr(f, f"Vertex_{i}_Xcoordinate", x)
        setattr(f, f"Vertex_{i}_Ycoordinate", y)
        setattr(f, f"Vertex_{i}_Zcoordinate", z)


def add_box(idf, zname, x0, y0, z0, L, W, H, wwr_by_face):
    x1, y1, z1 = x0 + L, y0 + W, z0 + H

    def surf(name, typ, cons, outside, verts):
        s = idf.newidfobject("BUILDINGSURFACE:DETAILED")
        s.Name = name
        s.Surface_Type = typ
        s.Construction_Name = cons
        s.Zone_Name = zname
        s.Outside_Boundary_Condition = outside
        if outside == "Outdoors":
            s.Sun_Exposure = "SunExposed"
            s.Wind_Exposure = "WindExposed"
        else:
            s.Sun_Exposure = "NoSun"
            s.Wind_Exposure = "NoWind"
        s.Number_of_Vertices = 4
        for i, (x, y, z) in enumerate(verts, 1):
            setattr(s, f"Vertex_{i}_Xcoordinate", x)
            setattr(s, f"Vertex_{i}_Ycoordinate", y)
            setattr(s, f"Vertex_{i}_Zcoordinate", z)
        return verts

    surf(f"{zname}_Floor", "Floor", "ExtFloor", "Ground",
         [(x0, y0, z0), (x0, y1, z0), (x1, y1, z0), (x1, y0, z0)])
    surf(f"{zname}_Roof", "Roof", "ExtRoof", "Outdoors",
         [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)])
    s_verts = surf(f"{zname}_S", "Wall", "ExtWall", "Outdoors",
                   [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)])
    n_verts = surf(f"{zname}_N", "Wall", "ExtWall", "Outdoors",
                   [(x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1)])
    e_verts = surf(f"{zname}_E", "Wall", "ExtWall", "Outdoors",
                   [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)])
    w_verts = surf(f"{zname}_W", "Wall", "ExtWall", "Outdoors",
                   [(x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1)])
    for side, verts in (("S", s_verts), ("N", n_verts), ("E", e_verts), ("W", w_verts)):
        add_window(idf, f"{zname}_{side}_Win", f"{zname}_{side}", verts, wwr_by_face[side])


def build():
    IDF.setiddname(str(IDD))
    blank = ROOT / "eplus" / "models" / "_blank.idf"
    blank.parent.mkdir(parents=True, exist_ok=True)
    blank.write_text("  Version,26.1;\n", encoding="utf-8")
    idf = IDF(str(blank))
    while idf.idfobjects.get("VERSION"):
        idf.removeidfobject(idf.idfobjects["VERSION"][0])

    ho_f, hu_f = load_sp()
    ho, hu = f2c(ho_f), f2c(hu_f)
    co_f, cu_f = 74.0, 85.0
    co, cu = f2c(co_f), f2c(cu_f)
    fans = fan_wm2_by_area()
    wwr_by_face = dict(WWR_BY_FACE)
    specs = build_zone_specs()

    idf.newidfobject("VERSION", Version_Identifier="26.1")
    b = idf.newidfobject("BUILDING")
    b.Name = "Lakeside_ES"
    b.North_Axis = 0
    b.Terrain = "Suburbs"
    b.Loads_Convergence_Tolerance_Value = 0.04
    b.Temperature_Convergence_Tolerance_Value = 0.4
    b.Solar_Distribution = "FullInteriorAndExterior"
    b.Maximum_Number_of_Warmup_Days = 25
    b.Minimum_Number_of_Warmup_Days = 6

    idf.newidfobject("TIMESTEP", Number_of_Timesteps_per_Hour=4)
    idf.newidfobject("SURFACECONVECTIONALGORITHM:INSIDE", Algorithm="TARP")
    idf.newidfobject("SURFACECONVECTIONALGORITHM:OUTSIDE", Algorithm="DOE-2")
    idf.newidfobject("HEATBALANCEALGORITHM", Algorithm="ConductionTransferFunction")

    sc = idf.newidfobject("SIMULATIONCONTROL")
    sc.Do_Zone_Sizing_Calculation = "Yes"
    sc.Do_System_Sizing_Calculation = "Yes"
    sc.Do_Plant_Sizing_Calculation = "No"
    sc.Run_Simulation_for_Sizing_Periods = "Yes"
    sc.Run_Simulation_for_Weather_File_Run_Periods = "Yes"

    rp = idf.newidfobject("RUNPERIOD")
    rp.Name = "CalibrationWindow"
    rp.Begin_Month = 8
    rp.Begin_Day_of_Month = 1
    rp.Begin_Year = 2025
    rp.End_Month = 7
    rp.End_Day_of_Month = 2
    rp.End_Year = 2026
    rp.Day_of_Week_for_Start_Day = "Thursday"
    rp.Use_Weather_File_Holidays_and_Special_Days = "Yes"
    rp.Use_Weather_File_Daylight_Saving_Period = "Yes"
    rp.Apply_Weekend_Holiday_Rule = "No"
    rp.Use_Weather_File_Rain_Indicators = "Yes"
    rp.Use_Weather_File_Snow_Indicators = "Yes"

    loc = idf.newidfobject("SITE:LOCATION")
    loc.Name = "Sun_Prairie_WI"
    loc.Latitude = 43.16521
    loc.Longitude = -89.25408
    loc.Time_Zone = -6
    loc.Elevation = 261

    idf.newidfobject("SCHEDULETYPELIMITS", Name="Any Number")
    st = idf.newidfobject("SCHEDULETYPELIMITS", Name="Fraction")
    st.Lower_Limit_Value = 0
    st.Upper_Limit_Value = 1
    st.Numeric_Type = "CONTINUOUS"
    st = idf.newidfobject("SCHEDULETYPELIMITS", Name="Temperature")
    st.Lower_Limit_Value = -60
    st.Upper_Limit_Value = 200
    st.Numeric_Type = "CONTINUOUS"
    st = idf.newidfobject("SCHEDULETYPELIMITS", Name="Control Type")
    st.Lower_Limit_Value = 0
    st.Upper_Limit_Value = 4
    st.Numeric_Type = "DISCRETE"

    def add_sched(name, typ, pairs):
        obj = idf.newidfobject("SCHEDULE:COMPACT")
        obj.Name = name
        obj.Schedule_Type_Limits_Name = typ
        for i, val in enumerate(pairs, start=1):
            setattr(obj, f"Field_{i}", val)

    # --- Classroom / general (aligned with thermal_zone_analytics occupied window) ---
    add_sched("SCH_Occ_Class", "Fraction", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", "0.05",
        "For: Thursday", "Until: 07:00", "0.05", "Until: 07:30", "0.2",
        "Until: 08:00", "0.9", "Until: 13:30", "1.0", "Until: 15:00", "0.2",
        "Until: 18:00", "0.08", "Until: 24:00", "0.05",
        "For: Monday Tuesday Wednesday Friday", "Until: 07:00", "0.05", "Until: 07:30", "0.2",
        "Until: 08:00", "0.9", "Until: 14:40", "1.0", "Until: 15:30", "0.25",
        "Until: 18:00", "0.1", "Until: 24:00", "0.05",
    ])
    # Library — lower density, similar hours
    add_sched("SCH_Occ_Library", "Fraction", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", "0.02",
        "For: Thursday", "Until: 07:30", "0.05", "Until: 13:30", "0.55",
        "Until: 15:00", "0.15", "Until: 24:00", "0.02",
        "For: Monday Tuesday Wednesday Friday", "Until: 07:30", "0.05", "Until: 14:40", "0.55",
        "Until: 15:30", "0.15", "Until: 24:00", "0.02",
    ])
    # Cafe — lunch waves ~11:00–13:00 (deep-research grade lunch blocks)
    add_sched("SCH_Occ_Cafe", "Fraction", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", "0.02",
        "For: Thursday", "Until: 07:00", "0.05", "Until: 10:45", "0.08",
        "Until: 11:00", "0.25", "Until: 13:00", "0.95", "Until: 13:30", "0.2",
        "Until: 15:00", "0.05", "Until: 24:00", "0.02",
        "For: Monday Tuesday Wednesday Friday", "Until: 07:00", "0.05", "Until: 10:45", "0.08",
        "Until: 11:00", "0.25", "Until: 13:00", "0.95", "Until: 14:40", "0.15",
        "Until: 15:30", "0.05", "Until: 24:00", "0.02",
    ])
    # Gym — intermittent PE blocks during school day
    add_sched("SCH_Occ_Gym", "Fraction", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", "0.02",
        "For: Thursday", "Until: 08:00", "0.05", "Until: 09:00", "0.7",
        "Until: 10:00", "0.15", "Until: 11:00", "0.7", "Until: 12:00", "0.15",
        "Until: 13:00", "0.5", "Until: 13:30", "0.1", "Until: 24:00", "0.02",
        "For: Monday Tuesday Wednesday Friday", "Until: 08:00", "0.05", "Until: 09:00", "0.7",
        "Until: 10:00", "0.15", "Until: 11:00", "0.7", "Until: 12:00", "0.15",
        "Until: 13:00", "0.7", "Until: 14:00", "0.15", "Until: 14:40", "0.4",
        "Until: 15:30", "0.08", "Until: 24:00", "0.02",
    ])
    add_sched("SCH_Lights", "Fraction", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", "0.1",
        "For: Thursday", "Until: 06:45", "0.1", "Until: 07:30", "0.5",
        "Until: 13:30", "0.9", "Until: 18:00", "0.25", "Until: 24:00", "0.1",
        "For: Monday Tuesday Wednesday Friday", "Until: 06:45", "0.1", "Until: 07:30", "0.5",
        "Until: 15:00", "0.9", "Until: 18:00", "0.3", "Until: 24:00", "0.1",
    ])
    add_sched("SCH_Lights_Gym", "Fraction", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", "0.05",
        "For: Thursday", "Until: 07:30", "0.05", "Until: 13:30", "0.75",
        "Until: 15:00", "0.15", "Until: 24:00", "0.05",
        "For: Monday Tuesday Wednesday Friday", "Until: 07:30", "0.05", "Until: 15:00", "0.75",
        "Until: 18:00", "0.15", "Until: 24:00", "0.05",
    ])
    add_sched("SCH_Equip", "Fraction", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", "0.15",
        "For: Thursday", "Until: 07:00", "0.15", "Until: 13:30", "0.7",
        "Until: 18:00", "0.25", "Until: 24:00", "0.15",
        "For: Monday Tuesday Wednesday Friday", "Until: 07:00", "0.15", "Until: 15:00", "0.7",
        "Until: 18:00", "0.3", "Until: 24:00", "0.15",
    ])
    # Kitchen process — deep-research 6:00–13:30 school days
    add_sched("SCH_Kitchen", "Fraction", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", "0.05",
        "For: Thursday", "Until: 06:00", "0.05", "Until: 13:30", "0.85",
        "Until: 15:00", "0.15", "Until: 24:00", "0.05",
        "For: Monday Tuesday Wednesday Friday", "Until: 06:00", "0.05", "Until: 13:30", "0.85",
        "Until: 15:00", "0.2", "Until: 24:00", "0.05",
    ])
    add_sched("SCH_Infil", "Fraction", [
        "Through: 12/31", "For: AllDays", "Until: 07:00", "1.0",
        "Until: 15:30", "0.5", "Until: 24:00", "1.0",
    ])
    add_sched("SCH_HVAC", "Fraction", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", "0.0",
        "For: Thursday", "Until: 05:30", "0.0", "Until: 14:00", "1.0", "Until: 24:00", "0.0",
        "For: Monday Tuesday Wednesday Friday", "Until: 05:30", "0.0", "Until: 15:30", "1.0",
        "Until: 24:00", "0.0",
    ])
    add_sched("SCH_AlwaysOn", "Fraction", ["Through: 12/31", "For: AllDays", "Until: 24:00", "1.0"])
    add_sched("SCH_ControlType", "Control Type", ["Through: 12/31", "For: AllDays", "Until: 24:00", "4"])
    add_sched("SCH_HtgSP", "Temperature", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", f"{hu:.2f}",
        "For: Thursday", "Until: 06:45", f"{hu:.2f}", "Until: 14:00", f"{ho:.2f}",
        "Until: 24:00", f"{hu:.2f}",
        "For: Monday Tuesday Wednesday Friday", "Until: 06:45", f"{hu:.2f}",
        "Until: 15:30", f"{ho:.2f}", "Until: 24:00", f"{hu:.2f}",
    ])
    add_sched("SCH_ClgSP", "Temperature", [
        "Through: 12/31",
        "For: Weekends Holidays", "Until: 24:00", f"{cu:.2f}",
        "For: Thursday", "Until: 06:45", f"{cu:.2f}", "Until: 14:00", f"{co:.2f}",
        "Until: 24:00", f"{cu:.2f}",
        "For: Monday Tuesday Wednesday Friday", "Until: 06:45", f"{cu:.2f}",
        "Until: 15:30", f"{co:.2f}", "Until: 24:00", f"{cu:.2f}",
    ])
    add_sched("SCH_Activity", "Any Number", ["Through: 12/31", "For: AllDays", "Until: 24:00", "120"])
    add_sched("SCH_Activity_Gym", "Any Number", ["Through: 12/31", "For: AllDays", "Until: 24:00", "250"])
    add_sched("SCH_Activity_Cafe", "Any Number", ["Through: 12/31", "For: AllDays", "Until: 24:00", "130"])

    def mat(name, rough, thick, cond, dens, spech):
        m = idf.newidfobject("MATERIAL")
        m.Name = name
        m.Roughness = rough
        m.Thickness = thick
        m.Conductivity = cond
        m.Density = dens
        m.Specific_Heat = spech
        m.Thermal_Absorptance = 0.9
        m.Solar_Absorptance = 0.7
        m.Visible_Absorptance = 0.7

    mat("Mat_Conc", "MediumRough", 0.1, 1.4, 2100, 880)
    mat("Mat_Insul", "MediumRough", 0.10, 0.04, 30, 1200)
    mat("Mat_Gyp", "MediumSmooth", 0.012, 0.16, 800, 1090)
    mat("Mat_RoofIns", "MediumRough", 0.15, 0.04, 30, 1200)
    mat("Mat_RoofDeck", "MediumRough", 0.02, 0.14, 530, 900)

    sg = idf.newidfobject("WINDOWMATERIAL:SIMPLEGLAZINGSYSTEM")
    sg.Name = "SimpleGlazing"
    sg.UFactor = WINDOW_U
    sg.Solar_Heat_Gain_Coefficient = WINDOW_SHGC
    sg.Visible_Transmittance = WINDOW_VT

    for cname, layers in (
        ("ExtWall", ["Mat_Conc", "Mat_Insul", "Mat_Gyp"]),
        ("ExtRoof", ["Mat_RoofDeck", "Mat_RoofIns", "Mat_Gyp"]),
        ("ExtFloor", ["Mat_Insul", "Mat_Conc"]),
        ("ExtWindow", ["SimpleGlazing"]),
    ):
        c = idf.newidfobject("CONSTRUCTION", Name=cname)
        c.Outside_Layer = layers[0]
        for i, layer in enumerate(layers[1:], start=2):
            setattr(c, f"Layer_{i}", layer)

    g = idf.newidfobject("GLOBALGEOMETRYRULES")
    g.Starting_Vertex_Position = "UpperLeftCorner"
    g.Vertex_Entry_Direction = "CounterClockWise"
    g.Coordinate_System = "Relative"

    # Place program zones on y>0 strip; academic wing on y=0 stacked
    x_prog = 0.0
    x_c = {1: 0.0, 2: 0.0}
    y_prog = 80.0

    for spec in specs:
        zname = spec["id"]
        kind = spec["kind"]
        loads = space_loads(kind)
        area_m2 = ft2_to_m2(spec["area_ft2"])
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

        z = idf.newidfobject("ZONE")
        z.Name = zname
        z.Direction_of_Relative_North = 0
        z.X_Origin = 0
        z.Y_Origin = 0
        z.Z_Origin = 0
        z.Type = 1
        z.Multiplier = 1
        z.Ceiling_Height = "autocalculate"
        z.Volume = "autocalculate"
        z.Floor_Area = "autocalculate"

        add_box(idf, zname, x0, y0, z0, L, W, H, wwr_by_face)

        act_sch = {
            "classroom": "SCH_Activity",
            "library": "SCH_Activity",
            "cafe": "SCH_Activity_Cafe",
            "gym": "SCH_Activity_Gym",
        }[kind]

        p = idf.newidfobject("PEOPLE")
        p.Name = f"{zname}_People"
        p.Zone_or_ZoneList_or_Space_or_SpaceList_Name = zname
        p.Number_of_People_Schedule_Name = loads["occ_sch"]
        p.Number_of_People_Calculation_Method = "People/Area"
        p.People_per_Floor_Area = loads["people_m2"]
        p.Fraction_Radiant = 0.3
        p.Sensible_Heat_Fraction = "autocalculate"
        p.Activity_Level_Schedule_Name = act_sch

        li = idf.newidfobject("LIGHTS")
        li.Name = f"{zname}_Lights"
        li.Zone_or_ZoneList_or_Space_or_SpaceList_Name = zname
        li.Schedule_Name = loads["light_sch"]
        li.Design_Level_Calculation_Method = "Watts/Area"
        li.Watts_per_Floor_Area = loads["lpd"]
        li.Return_Air_Fraction = 0.0
        li.Fraction_Radiant = 0.2
        li.Fraction_Visible = 0.2
        li.Fraction_Replaceable = 1.0
        li.EndUse_Subcategory = "General"

        eq = idf.newidfobject("ELECTRICEQUIPMENT")
        eq.Name = f"{zname}_Equip"
        eq.Zone_or_ZoneList_or_Space_or_SpaceList_Name = zname
        eq.Schedule_Name = loads["equip_sch"]
        eq.Design_Level_Calculation_Method = "Watts/Area"
        eq.Watts_per_Floor_Area = loads["epd"]
        eq.Fraction_Latent = 0.0
        eq.Fraction_Radiant = 0.3
        eq.Fraction_Lost = 0.0
        eq.EndUse_Subcategory = "General"

        if kind == "cafe" and loads.get("kitchen_epd"):
            kq = idf.newidfobject("ELECTRICEQUIPMENT")
            kq.Name = f"{zname}_Kitchen"
            kq.Zone_or_ZoneList_or_Space_or_SpaceList_Name = zname
            kq.Schedule_Name = "SCH_Kitchen"
            kq.Design_Level_Calculation_Method = "Watts/Area"
            kq.Watts_per_Floor_Area = loads["kitchen_epd"]
            kq.Fraction_Latent = 0.1
            kq.Fraction_Radiant = 0.2
            kq.Fraction_Lost = 0.3
            kq.EndUse_Subcategory = "Kitchen"

        fan_w = fans.get(zname, loads["fan_wm2_default"])
        fq = idf.newidfobject("ELECTRICEQUIPMENT")
        fq.Name = f"{zname}_FanProxy"
        fq.Zone_or_ZoneList_or_Space_or_SpaceList_Name = zname
        fq.Schedule_Name = "SCH_HVAC"
        fq.Design_Level_Calculation_Method = "Watts/Area"
        fq.Watts_per_Floor_Area = fan_w
        fq.Fraction_Latent = 0.0
        fq.Fraction_Radiant = 0.0
        fq.Fraction_Lost = 0.0
        fq.EndUse_Subcategory = "Fans"

        inf = idf.newidfobject("ZONEINFILTRATION:DESIGNFLOWRATE")
        inf.Name = f"{zname}_Infil"
        inf.Zone_or_ZoneList_or_Space_or_SpaceList_Name = zname
        inf.Schedule_Name = "SCH_Infil"
        inf.Design_Flow_Rate_Calculation_Method = "Flow/ExteriorArea"
        inf.Flow_Rate_per_Exterior_Surface_Area = 0.000610
        inf.Constant_Term_Coefficient = 1
        inf.Temperature_Term_Coefficient = 0
        inf.Velocity_Term_Coefficient = 0
        inf.Velocity_Squared_Term_Coefficient = 0

        ts = idf.newidfobject("THERMOSTATSETPOINT:DUALSETPOINT")
        ts.Name = f"{zname}_DualSP"
        ts.Heating_Setpoint_Temperature_Schedule_Name = "SCH_HtgSP"
        ts.Cooling_Setpoint_Temperature_Schedule_Name = "SCH_ClgSP"

        zt = idf.newidfobject("ZONECONTROL:THERMOSTAT")
        zt.Name = f"{zname}_Tstat"
        zt.Zone_or_ZoneList_Name = zname
        zt.Control_Type_Schedule_Name = "SCH_ControlType"
        zt.Control_1_Object_Type = "ThermostatSetpoint:DualSetpoint"
        zt.Control_1_Name = f"{zname}_DualSP"

        el = idf.newidfobject("ZONEHVAC:EQUIPMENTLIST")
        el.Name = f"{zname}_EqList"
        el.Load_Distribution_Scheme = "SequentialLoad"
        el.Zone_Equipment_1_Object_Type = "ZoneHVAC:IdealLoadsAirSystem"
        el.Zone_Equipment_1_Name = f"{zname}_Ideal"
        el.Zone_Equipment_1_Cooling_Sequence = 1
        el.Zone_Equipment_1_Heating_or_NoLoad_Sequence = 1

        ec = idf.newidfobject("ZONEHVAC:EQUIPMENTCONNECTIONS")
        ec.Zone_Name = zname
        ec.Zone_Conditioning_Equipment_List_Name = f"{zname}_EqList"
        ec.Zone_Air_Inlet_Node_or_NodeList_Name = f"{zname}_InNode"
        ec.Zone_Air_Exhaust_Node_or_NodeList_Name = f"{zname}_ExNode"
        ec.Zone_Air_Node_Name = f"{zname}_ZoneNode"

        dsoa = idf.newidfobject("DESIGNSPECIFICATION:OUTDOORAIR")
        dsoa.Name = f"{zname}_OA"
        dsoa.Outdoor_Air_Method = "Sum"
        dsoa.Outdoor_Air_Flow_per_Person = loads["oa_p"]
        dsoa.Outdoor_Air_Flow_per_Zone_Floor_Area = loads["oa_a"]

        il = idf.newidfobject("ZONEHVAC:IDEALLOADSAIRSYSTEM")
        il.Name = f"{zname}_Ideal"
        il.Availability_Schedule_Name = "SCH_HVAC"
        il.Zone_Supply_Air_Node_Name = f"{zname}_InNode"
        il.Zone_Exhaust_Air_Node_Name = f"{zname}_ExNode"
        il.Maximum_Heating_Supply_Air_Temperature = 50
        il.Minimum_Cooling_Supply_Air_Temperature = 13
        il.Maximum_Heating_Supply_Air_Humidity_Ratio = 0.015
        il.Minimum_Cooling_Supply_Air_Humidity_Ratio = 0.009
        il.Heating_Limit = "NoLimit"
        il.Cooling_Limit = "NoLimit"
        il.Heating_Availability_Schedule_Name = "SCH_HVAC"
        il.Cooling_Availability_Schedule_Name = "SCH_HVAC"
        il.Dehumidification_Control_Type = "ConstantSupplyHumidityRatio"
        il.Humidification_Control_Type = "ConstantSupplyHumidityRatio"
        il.Design_Specification_Outdoor_Air_Object_Name = f"{zname}_OA"
        il.Heat_Recovery_Type = "Enthalpy"
        il.Sensible_Heat_Recovery_Effectiveness = 0.70
        il.Latent_Heat_Recovery_Effectiveness = 0.55

        sz = idf.newidfobject("SIZING:ZONE")
        sz.Zone_or_ZoneList_Name = zname
        sz.Zone_Cooling_Design_Supply_Air_Temperature_Input_Method = "SupplyAirTemperature"
        sz.Zone_Cooling_Design_Supply_Air_Temperature = 12.0
        sz.Zone_Heating_Design_Supply_Air_Temperature_Input_Method = "SupplyAirTemperature"
        sz.Zone_Heating_Design_Supply_Air_Temperature = 50.0
        sz.Zone_Cooling_Design_Supply_Air_Humidity_Ratio = 0.0085
        sz.Zone_Heating_Design_Supply_Air_Humidity_Ratio = 0.008
        sz.Cooling_Design_Air_Flow_Method = "DesignDay"
        sz.Heating_Design_Air_Flow_Method = "DesignDay"

    for nm, month, day, dtype, db, dr, wb, wind, sky in (
        ("Madison Winter", 1, 21, "WinterDesignDay", -17.8, 0.0, -17.8, 3.5, 0),
        ("Madison Summer", 7, 21, "SummerDesignDay", 33.0, 10.0, 23.0, 4.0, 1.0),
    ):
        dd = idf.newidfobject("SIZINGPERIOD:DESIGNDAY")
        dd.Name = nm
        dd.Month = month
        dd.Day_of_Month = day
        dd.Day_Type = dtype
        dd.Maximum_DryBulb_Temperature = db
        dd.Daily_DryBulb_Temperature_Range = dr
        dd.DryBulb_Temperature_Range_Modifier_Type = "DefaultMultipliers"
        dd.Humidity_Condition_Type = "Wetbulb"
        dd.Wetbulb_or_DewPoint_at_Maximum_DryBulb = wb
        dd.Barometric_Pressure = 101325
        dd.Wind_Speed = wind
        dd.Wind_Direction = 270
        dd.Rain_Indicator = "No"
        dd.Snow_Indicator = "No"
        dd.Daylight_Saving_Time_Indicator = "No"
        dd.Solar_Model_Indicator = "ASHRAEClearSky"
        dd.Sky_Clearness = sky

    idf.newidfobject("OUTPUT:VARIABLE", Key_Value="*", Variable_Name="Zone Mean Air Temperature", Reporting_Frequency="Hourly")
    idf.newidfobject("OUTPUT:VARIABLE", Key_Value="*", Variable_Name="Zone Ideal Loads Supply Air Sensible Heating Energy", Reporting_Frequency="Monthly")
    idf.newidfobject("OUTPUT:VARIABLE", Key_Value="*", Variable_Name="Zone Ideal Loads Supply Air Sensible Cooling Energy", Reporting_Frequency="Monthly")
    for meter, freq in (
        ("Electricity:Facility", "Hourly"),
        ("Electricity:Facility", "Monthly"),
        ("InteriorLights:Electricity", "Monthly"),
        ("InteriorEquipment:Electricity", "Monthly"),
        ("DistrictHeatingWater:Facility", "Monthly"),
        ("DistrictCooling:Facility", "Monthly"),
    ):
        idf.newidfobject("OUTPUT:METER", Key_Name=meter, Reporting_Frequency=freq)
    idf.newidfobject("OUTPUT:TABLE:SUMMARYREPORTS", Report_1_Name="AllSummary")
    oc = idf.newidfobject("OUTPUTCONTROL:TABLE:STYLE")
    oc.Column_Separator = "Comma"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    idf.saveas(str(OUT))
    idf.saveas(str(OUT9))
    idf.saveas(str(LATEST))

    f1, f2 = conditioned_by_floor_ft2()
    zone_roster = [
        {
            "id": s["id"], "kind": s["kind"], "floor": s["floor"],
            "area_ft2": round(s["area_ft2"], 1), "clear_height_ft": round(s["height_m"] / 0.3048, 1),
            "n_hp": s["n_hp"],
        }
        for s in specs
    ]
    envelope = {
        "n_zones": len(specs),
        "wwr_overall_target": DEFAULT_WWR,
        "wwr_by_face": wwr_by_face,
        "window_u_ip": WINDOW_U_IP,
        "window_u_si": WINDOW_U,
        "window_shgc": WINDOW_SHGC,
        "window_vt": WINDOW_VT,
        "floor1_gross_ft2": FLOOR1_GROSS_FT2,
        "floor2_gross_ft2": FLOOR2_GROSS_FT2,
        "floor1_cond_ft2": round(f1, 1),
        "floor2_cond_ft2": round(f2, 1),
        "program_carved_ft2": {
            p[0]: p[1] for p in PROGRAM_ZONES
        },
        "stack_floor_to_floor_ft": 13.0,
        "classroom_clear_ft": CLASS_CLEAR_FT,
        "sources": [
            "deep-research-report.md massing + program",
            "bas_screenshots overview Areas + IMC",
            "reports/zone_temp_monthly_occ_unocc.csv",
            "reports/zone_avg_fan_run_hours_monthly.csv",
            "plots/analytics/zone_temp_occ_unocc_by_month.png",
            "plots/analytics/zone_avg_fan_run_hours_by_month.png",
        ],
        "zones": zone_roster,
    }

    if ANSWERS.is_file():
        ans = json.loads(ANSWERS.read_text(encoding="utf-8"))
        ans["envelope"] = envelope
        ans["setpoints_f"] = {"heat_occ": ho_f, "heat_unocc": hu_f, "cool_occ": co_f, "cool_unocc": cu_f}
        ans["bas_graphics"] = {
            "heat_cool_sp_f": "68 / 74 occupied (HP screens); unocc heat from Jan zn_t ~65",
            "fan_proxy": "zone_avg_fan_run_hours_monthly winter-weighted → W/m2",
            "doas": "CS Semco enthalpy wheel IdealLoads ERV proxy",
            "areas": "6 BAS Areas + Gym + Cafe_Kitchen + Library_IMC",
        }
        ans["zoning"] = {
            "n_zones": len(specs),
            "bas_areas": 6,
            "program_zones": ["1F_Gym", "1F_Cafe_Kitchen", "1F_Library_IMC"],
            "massing": "54700/36500 ft2 1F/2F deep-research",
        }
        ANSWERS.write_text(json.dumps(ans, indent=2), encoding="utf-8")

    ledger = {
        "version": 1,
        "heat_cop_proxy": HEAT_COP,
        "cool_cop_proxy": COOL_COP,
        "envelope": envelope,
        "fan_proxy_wm2": fans,
        "iterations": [{
            "iter": 0,
            "idf": OUT.name,
            "hypothesis": "seed_9zone_program_peel_bas_validated",
            "notes": (
                "9 IdealLoads zones: 6 BAS Areas + Gym/Cafe_Kitchen/Library_IMC; "
                "clear heights 10/12/14/24; lunch/gym/kitchen schedules; "
                "SP 68/74; fan proxy from zone_avg_fan_run_hours_monthly."
            ),
            "setpoints_f": {"heat_occ": ho_f, "heat_unocc": hu_f, "cool_occ": co_f, "cool_unocc": cu_f},
        }],
    }
    LEDGER.write_text(json.dumps(ledger, indent=2), encoding="utf-8")

    total_ft2 = sum(s["area_ft2"] for s in specs)
    print(
        f"wrote {OUT} + {OUT9.name} ({OUT.stat().st_size} bytes) "
        f"n_zones={len(specs)} total_ft2={total_ft2:.0f} "
        f"SP={ho_f}/{hu_f}F cool={co_f}/{cu_f}F WWR={DEFAULT_WWR}"
    )
    for s in specs:
        print(f"  {s['id']:20} kind={s['kind']:10} {s['area_ft2']:8.0f} ft2  H={s['height_m']/0.3048:.0f} ft")
    return 0


if __name__ == "__main__":
    if not TARGETS.is_file():
        import subprocess
        subprocess.check_call([sys.executable, str(APP / "scripts" / "eplus_observed_targets.py")])
    raise SystemExit(build())
