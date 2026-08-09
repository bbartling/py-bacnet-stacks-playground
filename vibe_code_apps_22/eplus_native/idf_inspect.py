"""Parse IdealLoads / schedule / zone facts from Lakeside champion IDF text."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


NINE_ZONES = (
    "1F_Library_IMC",
    "1F_Cafe_Kitchen",
    "1F_Gym",
    "1F_Area_A",
    "1F_Area_B",
    "1F_Area_C",
    "1F_Area_D",
    "2F_Area_A",
    "2F_Area_B",
)

BAS_SIX = (
    "1F_Area_A",
    "1F_Area_B",
    "1F_Area_C",
    "1F_Area_D",
    "2F_Area_A",
    "2F_Area_B",
)

PROGRAM_ZONES = ("1F_Library_IMC", "1F_Cafe_Kitchen", "1F_Gym")


@dataclass
class ScheduleCompact:
    name: str
    schedule_type: str
    body: str

    def weekend_holiday_fraction_is_zero(self) -> bool:
        """True if For: Weekends Holidays block forces Until:24:00 → 0.0."""
        m = re.search(
            r"For:\s*Weekends\s+Holidays\b.*?"
            r"Until:\s*24:00\b[^\n]*\n\s*([0-9.]+)",
            self.body,
            re.I | re.S,
        )
        if not m:
            return False
        return abs(float(m.group(1))) < 1e-12

    def overnight_weekday_before_0530_is_zero(self) -> bool:
        m = re.search(
            r"For:\s*Monday\s+Tuesday\s+Wednesday\s+Friday\b.*?"
            r"Until:\s*05:30\b[^\n]*\n\s*([0-9.]+)",
            self.body,
            re.I | re.S,
        )
        if not m:
            m = re.search(
                r"For:\s*Thursday\b.*?"
                r"Until:\s*05:30\b[^\n]*\n\s*([0-9.]+)",
                self.body,
                re.I | re.S,
            )
        if not m:
            return False
        return abs(float(m.group(1))) < 1e-12


@dataclass
class IdealLoadsFacts:
    name: str
    availability: str
    heating_limit: str
    cooling_limit: str
    heating_availability: str
    cooling_availability: str
    max_sensible_heating_capacity: str | None = None


@dataclass
class IdfDefectFacts:
    path: str
    zones: list[str] = field(default_factory=list)
    sch_hvac: ScheduleCompact | None = None
    ideal_loads: list[IdealLoadsFacts] = field(default_factory=list)
    has_ground_temp_building_surface: bool = False
    has_runperiod_control_daylight_saving: bool = False
    outdoor_air_specs_with_schedule: int = 0
    outdoor_air_specs_total: int = 0


def _extract_schedule_compact(text: str, name: str) -> ScheduleCompact | None:
    pat = re.compile(
        rf"SCHEDULE:COMPACT,\s*\n\s*{re.escape(name)}\s*,[^\n]*\n\s*([^,\n]+)[^\n]*\n(.*?;)",
        re.I | re.S,
    )
    m = pat.search(text)
    if not m:
        return None
    return ScheduleCompact(
        name=name,
        schedule_type=m.group(1).strip(),
        body=m.group(0),
    )


def _field_value(block: str, comment: str) -> str | None:
    """Return the IDF field value on the line whose ``!-`` comment equals ``comment``."""
    for line in block.splitlines():
        if "!-" not in line:
            continue
        left, _, right = line.partition("!-")
        if right.strip() != comment:
            continue
        return left.strip().rstrip(",").strip()
    return None


def _parse_ideal_loads(text: str) -> list[IdealLoadsFacts]:
    out: list[IdealLoadsFacts] = []
    for m in re.finditer(r"ZONEHVAC:IDEALLOADSAIRSYSTEM,(.*?);", text, re.I | re.S):
        block = m.group(0)
        name = _field_value(block, "Name")
        if not name:
            continue
        out.append(
            IdealLoadsFacts(
                name=name,
                availability=_field_value(block, "Availability Schedule Name") or "",
                heating_limit=_field_value(block, "Heating Limit") or "",
                max_sensible_heating_capacity=_field_value(
                    block, "Maximum Sensible Heating Capacity"
                ),
                cooling_limit=_field_value(block, "Cooling Limit") or "",
                heating_availability=_field_value(block, "Heating Availability Schedule Name")
                or "",
                cooling_availability=_field_value(block, "Cooling Availability Schedule Name")
                or "",
            )
        )
    return out


def _zone_names(text: str) -> list[str]:
    names: list[str] = []
    for m in re.finditer(r"^ZONE,\s*\n\s*([^,]+)\s*,", text, re.I | re.M):
        names.append(m.group(1).strip())
    return names


def inspect_idf(path: Path | str) -> IdfDefectFacts:
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    oa_total = len(re.findall(r"^DESIGNSPECIFICATION:OUTDOORAIR,", text, re.I | re.M))
    # Outdoor Air Schedule Name is field 7 in DesignSpecification:OutdoorAir (often blank/0)
    oa_with_sch = 0
    for block in re.finditer(
        r"DESIGNSPECIFICATION:OUTDOORAIR,\s*(.*?);",
        text,
        re.I | re.S,
    ):
        fields = [f.strip() for f in block.group(1).split(",")]
        # name + 6 numeric/method fields; schedule is often absent → trailing 0
        if len(fields) >= 7:
            sch = fields[6].split("!")[0].strip()
            if sch and sch not in {"0", ""}:
                oa_with_sch += 1
    return IdfDefectFacts(
        path=str(p.resolve()),
        zones=_zone_names(text),
        sch_hvac=_extract_schedule_compact(text, "SCH_HVAC"),
        ideal_loads=_parse_ideal_loads(text),
        has_ground_temp_building_surface=bool(
            re.search(r"Site:GroundTemperature:BuildingSurface", text, re.I)
        ),
        has_runperiod_control_daylight_saving=bool(
            re.search(r"RunPeriodControl:DaylightSavingTime", text, re.I)
        ),
        outdoor_air_specs_with_schedule=oa_with_sch,
        outdoor_air_specs_total=oa_total,
    )


def champion_idf_candidates() -> list[Path]:
    """Prefer site freeze/champion; fall back to repo pinned twin."""
    out: list[Path] = []
    import os

    site = os.environ.get("LAKESIDE_SITE_ROOT")
    if site:
        freeze_root = Path(site) / "eplus" / "campaigns"
        if freeze_root.is_dir():
            freezes = sorted(freeze_root.glob("freeze_pre_schedule_plant_*/champion_B_equip_mult_mid_model.idf"))
            out.extend(freezes[-1:])
        champ = (
            Path(site)
            / "eplus"
            / "campaigns"
            / "bounded_exec_20260807"
            / "trials"
            / "B_equip_mult_mid"
            / "model.idf"
        )
        if champ.is_file():
            out.append(champ)
    root = Path(__file__).resolve().parents[1]
    pinned = root / "models" / "eplus" / "lakeside_6zone_gshp_best.idf"
    if pinned.is_file():
        out.append(pinned)
    # unique preserve order
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in out:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq
