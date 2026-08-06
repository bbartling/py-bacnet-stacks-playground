"""Stage-repair utility champion IDF for zero-severe DSM eligibility."""
from __future__ import annotations

import re
from pathlib import Path

# BAS Areas used by heating DSM (6 zones)
DSM_ZONES = (
    "1F_Area_A",
    "1F_Area_B",
    "1F_Area_C",
    "1F_Area_D",
    "2F_Area_A",
    "2F_Area_B",
)


def _replace_building_warmup(text: str, max_days: int = 50, min_days: int = 6) -> str:
    """Bump Building warmup days (first Building object)."""
    lines = text.splitlines()
    out = []
    in_building = False
    field_i = 0
    for line in lines:
        if re.match(r"^\s*Building\s*,", line, re.I):
            in_building = True
            field_i = 0
            out.append(line)
            continue
        if in_building:
            # fields after name: north axis, terrain, loads tol, temp tol, solar, max warmup, min warmup
            if "!" in line or re.match(r"^\s*[0-9.]", line) or line.strip().endswith(";"):
                # count numeric/comma fields roughly via comments
                if "Maximum Number of Warmup Days" in line:
                    m = re.match(r"^(\s*)([0-9.]+)(.*)$", line)
                    if m:
                        line = f"{m.group(1)}{max_days}{m.group(3)}"
                elif "Minimum Number of Warmup Days" in line:
                    m = re.match(r"^(\s*)([0-9.]+)(.*)$", line)
                    if m:
                        line = f"{m.group(1)}{min_days}{m.group(3)}"
            if line.strip().endswith(";"):
                in_building = False
        out.append(line)
    return "\n".join(out)


def _patch_setpoint_schedule_for_design_days(text: str, sch_name: str, htg: bool) -> str:
    """Ensure DesignDay / AllOtherDays have non-zero setpoints (fixes 0°C sizing)."""
    # Replace entire Schedule:Compact block for sch_name
    if htg:
        # 18.33 C unocc / 20 C occ — design days use occupied-like heating
        body = f"""SCHEDULE:COMPACT,
    {sch_name},                !- Name
    Temperature,              !- Schedule Type Limits Name
    Through: 12/31,           !- Field 1
    For: SummerDesignDay,     !- Field 2
    Until: 24:00,             !- Field 3
    18.33,                    !- Field 4
    For: WinterDesignDay,     !- Field 5
    Until: 24:00,             !- Field 6
    20.00,                    !- Field 7
    For: Weekends Holidays,    !- Field 8
    Until: 24:00,             !- Field 9
    18.33,                    !- Field 10
    For: Thursday,            !- Field 11
    Until: 06:45,             !- Field 12
    18.33,                    !- Field 13
    Until: 14:00,             !- Field 14
    20.00,                    !- Field 15
    Until: 24:00,             !- Field 16
    18.33,                    !- Field 17
    For: AllOtherDays,        !- Field 18
    Until: 06:45,             !- Field 19
    18.33,                    !- Field 20
    Until: 15:30,             !- Field 21
    20.00,                    !- Field 22
    Until: 24:00,             !- Field 23
    18.33;                    !- Field 24
"""
    else:
        body = f"""SCHEDULE:COMPACT,
    {sch_name},                !- Name
    Temperature,              !- Schedule Type Limits Name
    Through: 12/31,           !- Field 1
    For: SummerDesignDay,     !- Field 2
    Until: 24:00,             !- Field 3
    23.33,                    !- Field 4
    For: WinterDesignDay,     !- Field 5
    Until: 24:00,             !- Field 6
    29.44,                    !- Field 7
    For: Weekends Holidays,    !- Field 8
    Until: 24:00,             !- Field 9
    29.44,                    !- Field 10
    For: Thursday,            !- Field 11
    Until: 06:45,             !- Field 12
    29.44,                    !- Field 13
    Until: 14:00,             !- Field 14
    23.33,                    !- Field 15
    Until: 24:00,             !- Field 16
    29.44,                    !- Field 17
    For: AllOtherDays,        !- Field 18
    Until: 06:45,             !- Field 19
    29.44,                    !- Field 20
    Until: 15:30,             !- Field 21
    23.33,                    !- Field 22
    Until: 24:00,             !- Field 23
    29.44;                    !- Field 24
"""
    pat = re.compile(
        rf"SCHEDULE:COMPACT,\s*\n\s*{re.escape(sch_name)}\s*,.*?;",
        re.I | re.S,
    )
    if not pat.search(text):
        raise ValueError(f"could not find Schedule:Compact {sch_name}")
    return pat.sub(body.rstrip(), text, count=1)


def _ensure_timestep_outputs(text: str) -> str:
    """Ensure Timestep meters + zone MAT + IdealLoads energy for DSM extraction."""
    # Upgrade existing Hourly Electricity meter and add Timestep counterparts
    block = """
!- === DSM native timestep outputs (IdealLoads + COP proxy) ===
OUTPUT:METER,
    Electricity:Facility,     !- Key Name
    Timestep;                 !- Reporting Frequency

OUTPUT:METER,
    DistrictHeatingWater:Facility,    !- Key Name
    Timestep;                 !- Reporting Frequency

OUTPUT:METER,
    DistrictCooling:Facility,    !- Key Name
    Timestep;                 !- Reporting Frequency

OUTPUT:METER,
    Electricity:Facility,     !- Key Name
    Hourly;                   !- Reporting Frequency

OUTPUT:METER,
    DistrictHeatingWater:Facility,    !- Key Name
    Hourly;                   !- Reporting Frequency

OUTPUT:METER,
    DistrictCooling:Facility,    !- Key Name
    Hourly;                   !- Reporting Frequency

OUTPUT:VARIABLE,
    *,                        !- Key Value
    Zone Mean Air Temperature,    !- Variable Name
    Timestep;                 !- Reporting Frequency

OUTPUT:VARIABLE,
    *,                        !- Key Value
    Zone Ideal Loads Supply Air Sensible Heating Energy,    !- Variable Name
    Timestep;                 !- Reporting Frequency

OUTPUT:VARIABLE,
    *,                        !- Key Value
    Zone Ideal Loads Supply Air Sensible Cooling Energy,    !- Variable Name
    Timestep;                 !- Reporting Frequency
"""
    # Remove duplicate trailing meter/variable block markers if re-patched
    if "DSM native timestep outputs" in text:
        text = re.sub(
            r"!- === DSM native timestep outputs.*?Zone Ideal Loads Supply Air Sensible Cooling Energy,.*?;\s*\n",
            "",
            text,
            flags=re.I | re.S,
        )
    return text.rstrip() + "\n" + block


def stage_repair_idf(source_idf: Path | str, dest_idf: Path | str) -> Path:
    """Copy champion IDF to staged path and apply severe-error repairs."""
    src = Path(source_idf)
    dst = Path(dest_idf)
    dst.parent.mkdir(parents=True, exist_ok=True)
    text = src.read_text(encoding="utf-8")
    text = _replace_building_warmup(text, max_days=50, min_days=6)
    text = _patch_setpoint_schedule_for_design_days(text, "SCH_HtgSP", htg=True)
    text = _patch_setpoint_schedule_for_design_days(text, "SCH_ClgSP", htg=False)
    text = _ensure_timestep_outputs(text)
    # Align schedule Until fields to 15-min timestep (avoid UNTIL:14:40 warnings)
    text = text.replace("Until: 14:40,", "Until: 14:45,")
    text = text.replace("Until: 06:45,", "Until: 06:45,")  # 06:45 ok for 15-min? 45 is multiple of 15
    dst.write_text(text, encoding="utf-8")
    return dst


def htg_schedule_name(zone: str) -> str:
    return f"SCH_HtgSP_{zone}"


def avail_schedule_name(zone: str) -> str:
    return f"SCH_Avail_{zone}"


def format_schedule_compact(
    name: str,
    *,
    schedule_type: str,
    blocks: list[tuple[int, int, float]],
) -> str:
    """Build Schedule:Compact from (until_hour, until_minute, value) blocks covering 24h.

    ``until`` is exclusive end-of-interval clock on the day (minute 0..59).
    Last block must end at 24:00.
    """
    if not blocks:
        raise ValueError("empty schedule blocks")
    lines = [
        "SCHEDULE:COMPACT,",
        f"    {name},                !- Name",
        f"    {schedule_type},              !- Schedule Type Limits Name",
        "    Through: 12/31,           !- Field 1",
        "    For: AllDays,             !- Field 2",
    ]
    fi = 3
    for i, (uh, um, val) in enumerate(blocks):
        until = f"{uh:02d}:{um:02d}" if not (uh == 24 and um == 0) else "24:00"
        if uh == 24:
            until = "24:00"
        end = ";" if i == len(blocks) - 1 else ","
        lines.append(f"    Until: {until},             !- Field {fi}")
        fi += 1
        lines.append(f"    {val:.4g}{end}                    !- Field {fi}")
        fi += 1
    return "\n".join(lines) + "\n"


def rewire_dualsetpoint_heating(text: str, zone: str, htg_sch: str) -> str:
    """Point ``{zone}_DualSP`` heating schedule at ``htg_sch``; cooling unchanged."""
    dual = f"{zone}_DualSP"
    # Match the DualSetpoint *object* whose Name field is dual (not ZoneControl refs).
    pat = re.compile(
        rf"(THERMOSTATSETPOINT:DUALSETPOINT,\s*\r?\n\s*{re.escape(dual)}\s*,[^\r\n]*\r?\n\s*)([^,!\r\n]+)",
        re.I,
    )

    def _sub(m: re.Match) -> str:
        return f"{m.group(1)}{htg_sch}"

    new, n = pat.subn(_sub, text, count=1)
    if n != 1:
        raise ValueError(f"could not rewire DualSetpoint heating for {dual}")
    return new


def rewire_ideal_loads_availability(text: str, zone: str, avail_sch: str) -> str:
    """Set IdealLoads availability + heating availability for ``{zone}_Ideal``."""
    ideal = f"{zone}_Ideal"
    obj_pat = re.compile(
        rf"ZONEHVAC:IDEALLOADSAIRSYSTEM,\s*\r?\n\s*{re.escape(ideal)}\s*,.*?;",
        re.I | re.S,
    )
    om = obj_pat.search(text)
    if not om:
        raise ValueError(f"IdealLoads {ideal} not found")
    block = om.group(0)
    lines = block.splitlines()
    out_lines = []
    for line in lines:
        if "Heating Availability Schedule Name" in line:
            mm = re.match(r"^(\s*)([^,!]+)(.*)$", line)
            if mm:
                line = f"{mm.group(1)}{avail_sch}{mm.group(3)}"
        elif "!- Availability Schedule Name" in line and "Heating" not in line and "Cooling" not in line:
            mm = re.match(r"^(\s*)([^,!]+)(.*)$", line)
            if mm:
                line = f"{mm.group(1)}{avail_sch}{mm.group(3)}"
        out_lines.append(line)
    # Preserve original newline style roughly via join with \n (E+ accepts)
    return text[: om.start()] + "\n".join(out_lines) + text[om.end() :]


def upsert_schedule_compact(text: str, name: str, body: str) -> str:
    """Replace existing Schedule:Compact ``name`` or append if missing."""
    pat = re.compile(
        rf"SCHEDULE:COMPACT,\s*\r?\n\s*{re.escape(name)}\s*,.*?;",
        re.I | re.S,
    )
    if pat.search(text):
        return pat.sub(body.rstrip(), text, count=1)
    return text.rstrip() + "\n\n" + body


def ensure_per_area_dsm_schedules(
    text: str,
    *,
    htg_blocks_by_zone: dict[str, list[tuple[int, int, float]]],
    avail_blocks_by_zone: dict[str, list[tuple[int, int, float]]] | None = None,
    zones: tuple[str, ...] = DSM_ZONES,
) -> str:
    """Create per-area heating (+ optional avail) schedules and rewire 6 DSM zones.

    Program zones (Library/Cafe/Gym) keep baseline ``SCH_HtgSP`` / ``SCH_HVAC``.
    """
    text = _ensure_timestep_outputs(text)
    for z in zones:
        hname = htg_schedule_name(z)
        body = format_schedule_compact(
            hname,
            schedule_type="Temperature",
            blocks=htg_blocks_by_zone[z],
        )
        text = upsert_schedule_compact(text, hname, body)
        text = rewire_dualsetpoint_heating(text, z, hname)
        if avail_blocks_by_zone is not None:
            aname = avail_schedule_name(z)
            abody = format_schedule_compact(
                aname,
                schedule_type="Fraction",
                blocks=avail_blocks_by_zone[z],
            )
            text = upsert_schedule_compact(text, aname, abody)
            text = rewire_ideal_loads_availability(text, z, aname)
    return text


def patch_run_period(
    text: str,
    *,
    begin_month: int,
    begin_day: int,
    end_month: int,
    end_day: int,
    begin_year: int | None = None,
    end_year: int | None = None,
    name: str = "DSM_WINDOW",
) -> str:
    """Replace first RunPeriod object dates (keeps other fields)."""
    lines = text.splitlines()
    out = []
    in_rp = False
    for line in lines:
        if re.match(r"^\s*RunPeriod\s*,", line, re.I):
            in_rp = True
            out.append(line)
            continue
        if in_rp:
            if "!- Name" in line:
                m = re.match(r"^(\s*)([^,!]+)(.*)$", line)
                if m:
                    line = f"{m.group(1)}{name}{m.group(3)}"
            elif "Begin Month" in line:
                m = re.match(r"^(\s*)([0-9]+)(.*)$", line)
                if m:
                    line = f"{m.group(1)}{begin_month}{m.group(3)}"
            elif "Begin Day of Month" in line:
                m = re.match(r"^(\s*)([0-9]+)(.*)$", line)
                if m:
                    line = f"{m.group(1)}{begin_day}{m.group(3)}"
            elif "Begin Year" in line and begin_year is not None:
                m = re.match(r"^(\s*)([0-9]+)(.*)$", line)
                if m:
                    line = f"{m.group(1)}{begin_year}{m.group(3)}"
            elif "End Month" in line:
                m = re.match(r"^(\s*)([0-9]+)(.*)$", line)
                if m:
                    line = f"{m.group(1)}{end_month}{m.group(3)}"
            elif "End Day of Month" in line:
                m = re.match(r"^(\s*)([0-9]+)(.*)$", line)
                if m:
                    line = f"{m.group(1)}{end_day}{m.group(3)}"
            elif "End Year" in line and end_year is not None:
                m = re.match(r"^(\s*)([0-9]+)(.*)$", line)
                if m:
                    line = f"{m.group(1)}{end_year}{m.group(3)}"
            if ";" in line.split("!")[0]:
                in_rp = False
        out.append(line)
    return "\n".join(out)
