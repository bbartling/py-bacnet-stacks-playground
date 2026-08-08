"""Apply eplus_school_calendar_v1 schedule/OA/capacity/ground repairs to IdealLoads IDF."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from eplus_native.idf_inspect import NINE_ZONES
from eplus_native.idf_stage import upsert_schedule_compact

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_CAL = _ROOT / "contracts" / "eplus_school_calendar_v1.json"

# Approximate floor areas (ft2) for capacity allocation — same order as seed defaults.
ZONE_AREA_FT2 = {
    "1F_Library_IMC": 4000.0,
    "1F_Cafe_Kitchen": 6600.0,
    "1F_Gym": 7500.0,
    "1F_Area_A": 12000.0,
    "1F_Area_B": 8000.0,
    "1F_Area_C": 8800.0,
    "1F_Area_D": 8000.0,
    "2F_Area_A": 10000.0,
    "2F_Area_B": 10000.0,
}

MMBTU_H_TO_W = 293071.070172222  # W per MMBtu/h


def load_calendar_contract(path: Path | str | None = None) -> dict[str, Any]:
    p = Path(path) if path else _DEFAULT_CAL
    return json.loads(p.read_text(encoding="utf-8"))


def _f_to_c(f: float) -> float:
    return (float(f) - 32.0) * 5.0 / 9.0


def _compact(name: str, sch_type: str, fields: list[str]) -> str:
    """Build Schedule:Compact from alternating Through/For/Until/value tokens."""
    lines = [
        "SCHEDULE:COMPACT,",
        f"    {name},                !- Name",
        f"    {sch_type},              !- Schedule Type Limits Name",
    ]
    for i, tok in enumerate(fields):
        end = ";" if i == len(fields) - 1 else ","
        lines.append(f"    {tok}{end}                    !- Field {i + 1}")
    return "\n".join(lines) + "\n"


def _school_fraction_fields(*, occupied_value: float, unoccupied_value: float = 0.0) -> list[str]:
    """Bell-aligned fraction schedule (local civil; E+ uses weather-file/LST)."""
    occ = f"{occupied_value}"
    un = f"{unoccupied_value}"
    return [
        "Through: 12/31",
        "For: Weekends Holidays",
        "Until: 24:00",
        un,
        "For: Thursday",
        "Until: 05:30",
        un,
        "Until: 07:30",
        f"{max(occupied_value * 0.25, unoccupied_value)}",
        "Until: 13:30",
        occ,
        "Until: 18:00",
        f"{max(occupied_value * 0.15, unoccupied_value)}",
        "Until: 24:00",
        un,
        "For: Monday Tuesday Wednesday Friday",
        "Until: 05:30",
        un,
        "Until: 07:30",
        f"{max(occupied_value * 0.25, unoccupied_value)}",
        "Until: 14:40",
        occ,
        "Until: 18:00",
        f"{max(occupied_value * 0.15, unoccupied_value)}",
        "Until: 24:00",
        un,
        "For: AllOtherDays",
        "Until: 24:00",
        un,
    ]


def _heat_avail_fields() -> list[str]:
    """Heating can run overnight/weekend to hold unoccupied SP (not OA/fan)."""
    return [
        "Through: 12/31",
        "For: AllDays",
        "Until: 24:00",
        "1.0",
    ]


def _sys_avail_fields() -> list[str]:
    """System availability always on so IdealLoads can meet heating SP; OA gated separately."""
    return _heat_avail_fields()


def _cool_avail_fields() -> list[str]:
    return _school_fraction_fields(occupied_value=1.0, unoccupied_value=0.0)


def _upsert_run_period_holidays(text: str, contract: dict[str, Any]) -> str:
    """Inject RunPeriodControl:SpecialDays for assumed holidays + winter break."""
    hb = contract.get("holidays_and_breaks_local") or {}
    dates: list[str] = []
    dates.extend(hb.get("assumed_holidays") or [])
    br = hb.get("winter_break_inclusive") or []
    if len(br) == 2:
        # expand inclusive range as SpecialDays single-day entries (ASSUMED)
        import datetime as dt

        a = dt.date.fromisoformat(br[0])
        b = dt.date.fromisoformat(br[1])
        cur = a
        while cur <= b:
            dates.append(cur.isoformat())
            cur += dt.timedelta(days=1)
    # unique preserve
    seen: set[str] = set()
    uniq: list[str] = []
    for d in dates:
        if d not in seen:
            seen.add(d)
            uniq.append(d)

    blocks = []
    for i, iso in enumerate(uniq):
        y, m, day = iso.split("-")
        blocks.append(
            "RunPeriodControl:SpecialDays,\n"
            f"    Holiday_{i:03d},             !- Name\n"
            f"    {int(m)}/{int(day)},                  !- Start Date\n"
            "    1,                        !- Duration\n"
            "    Holiday;                  !- Special Day Type\n"
        )
    blob = "\n".join(blocks)
    # remove prior Holiday_* injections
    text = re.sub(
        r"RunPeriodControl:SpecialDays,\s*\n\s*Holiday_\d+.*?Special Day Type\s*\n",
        "",
        text,
        flags=re.I | re.S,
    )
    # insert before first ScheduleTypeLimits or after Timestep
    if re.search(r"Timestep,", text, re.I):
        return re.sub(
            r"(Timestep,.*?;\s*\n)",
            r"\1\n" + blob + "\n",
            text,
            count=1,
            flags=re.I | re.S,
        )
    return text + "\n" + blob


def _upsert_ground_temps(text: str, temps_c: list[float]) -> str:
    assert len(temps_c) == 12
    fields = ",\n".join(f"    {t}" for t in temps_c[:-1])
    last = f"    {temps_c[-1]}"
    block = (
        "Site:GroundTemperature:BuildingSurface,\n"
        f"{fields},\n"
        f"{last};\n"
    )
    text = re.sub(
        r"Site:GroundTemperature:BuildingSurface,.*?;",
        "",
        text,
        flags=re.I | re.S,
    )
    # SITE:LOCATION may end mid-line with `; !- comment`
    m = re.search(r"SITE:LOCATION,.*?;[^\n]*\n", text, re.I | re.S)
    if m:
        return text[: m.end()] + "\n" + block + "\n" + text[m.end() :]
    return text + "\n" + block


def _patch_oa_schedule_name(text: str, schedule_name: str = "SCH_OA") -> str:
    """Append Outdoor Air Schedule Name to each DesignSpecification:OutdoorAir."""

    def repl(m: re.Match[str]) -> str:
        body = m.group(1).rstrip()
        # If already has a non-numeric 7th schedule-like field, leave
        parts = [p.strip() for p in body.split(",")]
        # Ensure we end with schedule field before semicolon
        # Existing blocks end with ACH field then ;
        if len(parts) >= 6:
            # replace trailing ACH-only terminator by adding schedule
            # body currently like: Name, Method, perPerson, perArea, perZone, ACH
            head = ",\n    ".join(p.split("!")[0].strip() for p in parts[:6])
            return (
                "DESIGNSPECIFICATION:OUTDOORAIR,\n"
                f"    {head},\n"
                f"    {schedule_name};              !- Outdoor Air Schedule Name\n"
            )
        return m.group(0)

    return re.sub(
        r"DESIGNSPECIFICATION:OUTDOORAIR,\s*(.*?);",
        repl,
        text,
        flags=re.I | re.S,
    )


def _allocate_heating_capacity_w(total_mmbtu_h: float) -> dict[str, float]:
    total_w = float(total_mmbtu_h) * MMBTU_H_TO_W
    areas = {z: ZONE_AREA_FT2[z] for z in NINE_ZONES}
    s = sum(areas.values())
    return {z: total_w * (a / s) for z, a in areas.items()}


def _patch_ideal_loads(
    text: str,
    *,
    heat_cap_w_by_zone: dict[str, float] | None,
    sys_avail: str,
    heat_avail: str,
    cool_avail: str,
) -> str:
    """Rewrite IdealLoads availability + optional capacity limits."""

    def repl_one(m: re.Match[str]) -> str:
        block = m.group(0)
        name_m = re.search(r"ZONEHVAC:IDEALLOADSAIRSYSTEM,\s*\n\s*([^,]+)\s*,", block, re.I)
        if not name_m:
            return block
        obj = name_m.group(1).strip()
        zone = obj.replace("_Ideal", "")
        # Availability schedule (first schedule field after name/nodes is harder; patch by comment)
        block = re.sub(
            r"(Availability Schedule Name\s*\n)",
            r"\1",
            block,
            count=1,
        )
        block = re.sub(
            r"^(\s*)([^,]+)(,\s*!- Availability Schedule Name)",
            rf"\g<1>{sys_avail}\3",
            block,
            count=1,
            flags=re.M,
        )
        block = re.sub(
            r"^(\s*)([^,]+)(,\s*!- Heating Availability Schedule Name)",
            rf"\g<1>{heat_avail}\3",
            block,
            count=1,
            flags=re.M,
        )
        block = re.sub(
            r"^(\s*)([^,]+)(,\s*!- Cooling Availability Schedule Name)",
            rf"\g<1>{cool_avail}\3",
            block,
            count=1,
            flags=re.M,
        )
        if heat_cap_w_by_zone is not None and zone in heat_cap_w_by_zone:
            cap = heat_cap_w_by_zone[zone]
            block = re.sub(
                r"^(\s*)NoLimit(,\s*!- Heating Limit)",
                r"\g<1>LimitCapacity\2",
                block,
                count=1,
                flags=re.M | re.I,
            )
            block = re.sub(
                r"^(\s*)([^,]*)(,\s*!- Maximum Sensible Heating Capacity)",
                rf"\g<1>{cap:.3f}\3",
                block,
                count=1,
                flags=re.M,
            )
        return block

    return re.sub(
        r"ZONEHVAC:IDEALLOADSAIRSYSTEM,.*?;",
        repl_one,
        text,
        flags=re.I | re.S,
    )


def _patch_htg_setpoints(text: str, contract: dict[str, Any]) -> str:
    sp = contract.get("setpoints_f") or {}
    occ_c = _f_to_c(float(sp.get("occupied_heating_f", 70.0)))
    unocc_c = _f_to_c(float(sp.get("unoccupied_heating_f", 65.0)))
    body = _compact(
        "SCH_HtgSP",
        "Temperature",
        [
            "Through: 12/31",
            "For: SummerDesignDay",
            "Until: 24:00",
            f"{unocc_c:.2f}",
            "For: WinterDesignDay",
            "Until: 24:00",
            f"{occ_c:.2f}",
            "For: Weekends Holidays",
            "Until: 24:00",
            f"{unocc_c:.2f}",
            "For: Thursday",
            "Until: 06:45",
            f"{unocc_c:.2f}",
            "Until: 13:30",
            f"{occ_c:.2f}",
            "Until: 24:00",
            f"{unocc_c:.2f}",
            "For: AllOtherDays",
            "Until: 06:45",
            f"{unocc_c:.2f}",
            "Until: 15:30",
            f"{occ_c:.2f}",
            "Until: 24:00",
            f"{unocc_c:.2f}",
        ],
    )
    return upsert_schedule_compact(text, "SCH_HtgSP", body)


def apply_schedule_calendar_repair(
    idf_text: str,
    *,
    contract: dict[str, Any] | None = None,
    heating_capacity_mmbtu_h: float | None = None,
    optimum_start_hours: float | None = None,
) -> str:
    """Return repaired IDF text. Does not force SCH_HVAC always-on for OA/fan."""
    cal = contract or load_calendar_contract()
    text = idf_text

    # Core schedules
    text = upsert_schedule_compact(
        text, "SCH_SysAvail", _compact("SCH_SysAvail", "Fraction", _sys_avail_fields())
    )
    text = upsert_schedule_compact(
        text, "SCH_HeatAvail", _compact("SCH_HeatAvail", "Fraction", _heat_avail_fields())
    )
    text = upsert_schedule_compact(
        text, "SCH_CoolAvail", _compact("SCH_CoolAvail", "Fraction", _cool_avail_fields())
    )
    oa_fields = _school_fraction_fields(occupied_value=1.0, unoccupied_value=0.0)
    if optimum_start_hours:
        # sensitivity: shift morning OA/occ earlier by lead hours (coarse)
        lead = max(0.0, float(optimum_start_hours))
        start = 5.5 - lead
        start_s = f"{int(start):02d}:{int(round((start % 1) * 60)):02d}"
        oa_fields = [
            "Through: 12/31",
            "For: Weekends Holidays",
            "Until: 24:00",
            "0.0",
            "For: AllOtherDays",
            f"Until: {start_s}",
            "0.0",
            "Until: 18:00",
            "1.0",
            "Until: 24:00",
            "0.0",
        ]
    text = upsert_schedule_compact(text, "SCH_OA", _compact("SCH_OA", "Fraction", oa_fields))
    text = upsert_schedule_compact(
        text,
        "SCH_FanProxy",
        _compact("SCH_FanProxy", "Fraction", _school_fraction_fields(occupied_value=1.0)),
    )
    text = upsert_schedule_compact(
        text,
        "SCH_Occ",
        _compact("SCH_Occ", "Fraction", _school_fraction_fields(occupied_value=0.95, unoccupied_value=0.05)),
    )

    # Keep legacy SCH_HVAC as OA/fan-shaped (occupied only) for any leftover refs
    text = upsert_schedule_compact(
        text,
        "SCH_HVAC",
        _compact("SCH_HVAC", "Fraction", _school_fraction_fields(occupied_value=1.0, unoccupied_value=0.0)),
    )

    text = _patch_htg_setpoints(text, cal)
    text = _upsert_run_period_holidays(text, cal)
    gt = (cal.get("ground_temperature_building_surface_c") or {}).get("jan_dec_c")
    if gt:
        text = _upsert_ground_temps(text, list(gt))
    text = _patch_oa_schedule_name(text, "SCH_OA")

    caps = None
    if heating_capacity_mmbtu_h is not None:
        caps = _allocate_heating_capacity_w(float(heating_capacity_mmbtu_h))
    text = _patch_ideal_loads(
        text,
        heat_cap_w_by_zone=caps,
        sys_avail="SCH_SysAvail",
        heat_avail="SCH_HeatAvail",
        cool_avail="SCH_CoolAvail",
    )

    # Alias building name for repo honesty when present
    text = re.sub(
        r"(Building,\s*\n\s*)([^,]+)(\s*,)",
        r"\1Lakeside_ES\3",
        text,
        count=1,
        flags=re.I,
    )
    return text


def repair_idf_file(
    src: Path | str,
    dst: Path | str,
    *,
    heating_capacity_mmbtu_h: float | None = None,
    optimum_start_hours: float | None = None,
    contract_path: Path | str | None = None,
) -> Path:
    cal = load_calendar_contract(contract_path)
    text = Path(src).read_text(encoding="utf-8", errors="replace")
    out = apply_schedule_calendar_repair(
        text,
        contract=cal,
        heating_capacity_mmbtu_h=heating_capacity_mmbtu_h,
        optimum_start_hours=optimum_start_hours,
    )
    dst_p = Path(dst)
    dst_p.parent.mkdir(parents=True, exist_ok=True)
    dst_p.write_text(out, encoding="utf-8", newline="\n")
    return dst_p
