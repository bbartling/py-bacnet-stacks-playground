"""Post-ExpandObjects W2A / plant field mutator (live knobs only).

Every knob must change a concrete expanded IDF object field. Dead IdealLoads /
pre-expand capacity levers are refused.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass, fields
from typing import Any

# Baseline when Rated Heating Capacity is autosize (≈2.7 MMBtu/h / 9 zones).
DEFAULT_HTG_COIL_CAPACITY_W = 87_900.0
# Baseline when Rated Power is autosize — derived from head via affinity-ish placeholder.
DEFAULT_PUMP_POWER_W = 2_500.0

DEAD_KNOBS = frozenset(
    {
        "heating_capacity_mmbtu_h",
        "oa_occupied_frac",
        "cap",
        "IdealLoads",
        "ideal_loads_capacity",
    }
)

LIVE_KNOB_NAMES = frozenset(
    {
        "htg_coil_capacity_mult",
        "htg_coil_cop_mult",
        "clg_coil_cop_mult",
        "fan_delta_p_mult",
        "fan_eff_mult",
        "pump_power_mult",
        "loop_setpoint_c",
        "oa_frac_scale",
        "optimum_start_h",
        "setback_heat_sp_c",
        "oa_shoulder_scale",
        "fan_avail_use_sch_hvac",
        "people_density_mult",
        "equip_w_area_mult",
        "lights_w_area_mult",
        "summer_sch_scale",
        "summer_include_hvac",
    }
)

# Default expanded setback / shoulder values (post schedule repair).
DEFAULT_SETBACK_HEAT_SP_C = 18.33


@dataclass(frozen=True)
class W2APlantKnobs:
    htg_coil_capacity_mult: float = 1.0
    htg_coil_cop_mult: float = 1.0
    clg_coil_cop_mult: float = 1.0  # Rated Cooling COP (base 3.5)
    fan_delta_p_mult: float = 1.0
    fan_eff_mult: float = 1.0
    pump_power_mult: float = 1.0
    loop_setpoint_c: float | None = None  # None → leave HVACTemplate-Always 34
    oa_frac_scale: float = 1.0
    optimum_start_h: float = 0.0
    # Creative structural knobs (expanded schedules / fan avail)
    setback_heat_sp_c: float | None = None  # None → leave 18.33 setbacks
    oa_shoulder_scale: float = 1.0  # scale 0<OA frac<1 shoulders only
    fan_avail_use_sch_hvac: bool = False  # Fan:OnOff avail → SCH_HVAC (off weekends)
    # Internal gains (research-report people/plug/lighting dials)
    people_density_mult: float = 1.0  # scale People per Floor Area
    equip_w_area_mult: float = 1.0  # scale ElectricEquipment W/area (skip FanProxy)
    lights_w_area_mult: float = 1.0  # scale Lights W/area
    # School-out Jun–Jul only (Aug treated as in-session). None = year-round Through:12/31.
    summer_sch_scale: float | None = None  # e.g. 0.25 ≈ summer-school fraction of design
    summer_include_hvac: bool = False  # True also shortens SCH_HVAC Jun–Jul

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def refuse_dead_knobs(knobs: dict[str, Any]) -> None:
    bad = sorted(set(knobs) & DEAD_KNOBS)
    unknown = sorted(set(knobs) - LIVE_KNOB_NAMES - {"trial_id", "label"})
    if bad:
        raise ValueError(f"dead W2A knobs refused (do not affect expanded plant): {bad}")
    if unknown:
        raise ValueError(f"unknown W2A knobs: {unknown}")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _replace_field_by_comment(
    block: str,
    *,
    comment_substr: str,
    new_value: str,
    object_type: str,
    object_name: str,
    ledger: list[dict[str, Any]],
) -> str:
    lines = block.splitlines(keepends=True)
    out: list[str] = []
    changed = False
    for line in lines:
        if (not changed) and comment_substr.lower() in line.lower() and "!" in line:
            m = re.match(r"^(\s*)([^,;]+)([,;])(.*)$", line)
            if m:
                old = m.group(2).strip()
                if old != new_value:
                    ledger.append(
                        {
                            "object_type": object_type,
                            "object_name": object_name,
                            "field_comment": comment_substr,
                            "old": old,
                            "new": new_value,
                        }
                    )
                    line = f"{m.group(1)}{new_value}{m.group(3)}{m.group(4)}\n" if line.endswith("\n") else f"{m.group(1)}{new_value}{m.group(3)}{m.group(4)}"
                    if not line.endswith("\n") and block.endswith("\n"):
                        line += "\n"
                changed = True
        out.append(line)
    return "".join(out)


def _object_name(block: str) -> str:
    lines = [ln for ln in block.splitlines() if ln.strip()]
    if len(lines) < 2:
        return ""
    # second field is Name
    m = re.match(r"^\s*([^,;]+)", lines[1])
    return m.group(1).strip() if m else ""


def _iter_objects(text: str, object_type: str) -> list[tuple[int, int, str]]:
    """Return (start, end, block) spans for objects of the given type."""
    pat = re.compile(rf"(?mi)^({re.escape(object_type)})\s*,.*?;", re.S)
    return [(m.start(), m.end(), m.group(0)) for m in pat.finditer(text)]


def _scale_or_set_numeric(old: str, mult: float, *, autosize_baseline: float) -> str:
    s = old.strip()
    if s.lower() == "autosize" or s == "":
        return f"{autosize_baseline * mult:.6g}"
    try:
        return f"{float(s) * mult:.6g}"
    except ValueError:
        return f"{autosize_baseline * mult:.6g}"


def _mutate_coils(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    spans = _iter_objects(text, "Coil:Heating:WaterToAirHeatPump:EquationFit")
    if not spans:
        return text
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        new_block = block
        # Always materialize capacity so autosize→numeric is a live change even at mult=1.
        m = re.search(
            r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Rated Heating Capacity.*)$",
            new_block,
        )
        if m:
            old = m.group(2).strip()
            new_v = _scale_or_set_numeric(
                old if old.lower() != "autosize" else "autosize",
                knobs.htg_coil_capacity_mult,
                autosize_baseline=DEFAULT_HTG_COIL_CAPACITY_W,
            )
            # When old was numeric, scale from that; when autosize, baseline*mult
            if old.lower() != "autosize":
                try:
                    new_v = f"{float(old) * knobs.htg_coil_capacity_mult:.6g}"
                except ValueError:
                    pass
            else:
                new_v = f"{DEFAULT_HTG_COIL_CAPACITY_W * knobs.htg_coil_capacity_mult:.6g}"
            if old != new_v:
                ledger.append(
                    {
                        "object_type": "Coil:Heating:WaterToAirHeatPump:EquationFit",
                        "object_name": name,
                        "field_comment": "Rated Heating Capacity",
                        "old": old,
                        "new": new_v,
                    }
                )
                new_block = (
                    new_block[: m.start()]
                    + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                    + new_block[m.end() :]
                )
        if knobs.htg_coil_cop_mult != 1.0:
            m = re.search(
                r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Rated Heating Coefficient of Performance.*)$",
                new_block,
            )
            if m:
                old = m.group(2).strip()
                try:
                    new_v = f"{float(old) * knobs.htg_coil_cop_mult:.6g}"
                except ValueError:
                    new_v = f"{4.2 * knobs.htg_coil_cop_mult:.6g}"
                if old != new_v:
                    ledger.append(
                        {
                            "object_type": "Coil:Heating:WaterToAirHeatPump:EquationFit",
                            "object_name": name,
                            "field_comment": "Rated Heating COP",
                            "old": old,
                            "new": new_v,
                        }
                    )
                    new_block = (
                        new_block[: m.start()]
                        + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                        + new_block[m.end() :]
                    )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mutate_cooling_cop(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    """Scale Rated Cooling COP on equation-fit WAHP cooling coils (base 3.5)."""
    if knobs.clg_coil_cop_mult == 1.0:
        return text
    spans = _iter_objects(text, "Coil:Cooling:WaterToAirHeatPump:EquationFit")
    if not spans:
        return text
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        new_block = block
        m = re.search(
            r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Rated Cooling Coefficient of Performance.*)$",
            new_block,
        )
        if m:
            old = m.group(2).strip()
            try:
                new_v = f"{float(old) * knobs.clg_coil_cop_mult:.6g}"
            except ValueError:
                new_v = f"{3.5 * knobs.clg_coil_cop_mult:.6g}"
            if old != new_v:
                ledger.append(
                    {
                        "object_type": "Coil:Cooling:WaterToAirHeatPump:EquationFit",
                        "object_name": name,
                        "field_comment": "Rated Cooling COP",
                        "old": old,
                        "new": new_v,
                    }
                )
                new_block = (
                    new_block[: m.start()]
                    + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                    + new_block[m.end() :]
                )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


# Default: people / plugs / lights / kitchen only.
# SCH_HVAC optional — hard HVAC cut over-corrected Aug bills (~−60% in first pass).
_SUMMER_SCH_NAMES_CORE = (
    "SCH_Occ_Class",
    "SCH_Occ_Library",
    "SCH_Occ_Cafe",
    "SCH_Occ_Gym",
    "SCH_Lights",
    "SCH_Lights_Gym",
    "SCH_Equip",
    "SCH_Kitchen",
)
_SUMMER_SCH_NAMES_WITH_HVAC = _SUMMER_SCH_NAMES_CORE + ("SCH_HVAC",)
_SUMMER_SCH_NAMES = _SUMMER_SCH_NAMES_CORE  # back-compat alias


def _summer_low_body(name: str, scale: float) -> str:
    """Jun–Aug body: Mon–Thu summer-school hours; Fri/weekend essentially off."""
    s = max(0.02, min(1.0, float(scale)))
    if name == "SCH_HVAC":
        return (
            "    For: Weekends Holidays Friday,\n"
            "    Until: 24:00,\n"
            "    0.0,\n"
            "    For: Monday Tuesday Wednesday Thursday,\n"
            "    Until: 07:00,\n"
            "    0.0,\n"
            "    Until: 07:30,\n"
            "    0.25,\n"
            "    Until: 13:30,\n"
            "    1.0,\n"
            "    Until: 24:00,\n"
            "    0.0,\n"
            "    For: AllOtherDays,\n"
            "    Until: 24:00,\n"
            "    0.0;\n"
        )
    # Occ / lights / equip / kitchen — short occupied window, scaled peak
    return (
        "    For: Weekends Holidays Friday,\n"
        "    Until: 24:00,\n"
        "    0.02,\n"
        "    For: Monday Tuesday Wednesday Thursday,\n"
        "    Until: 07:30,\n"
        "    0.02,\n"
        "    Until: 08:00,\n"
        "    0.10,\n"
        "    Until: 13:00,\n"
        f"    {s:.4g},\n"
        "    Until: 24:00,\n"
        "    0.02,\n"
        "    For: AllOtherDays,\n"
        "    Until: 24:00,\n"
        "    0.0;\n"
    )


def _mutate_summer_schedules(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    """Split year-round Through:12/31 into school-year + Jun–Jul summer-out + Aug–Dec.

    August is treated as in-session (early occupancy / staff prep). Summer-out is
    Through: 7/31 only. Research summer school: Mon–Thu ~8:00–13:00 contact.
    """
    if knobs.summer_sch_scale is None:
        return text
    scale = float(knobs.summer_sch_scale)
    names = (
        _SUMMER_SCH_NAMES_WITH_HVAC
        if knobs.summer_include_hvac
        else _SUMMER_SCH_NAMES_CORE
    )
    for sch_name in names:
        pat = re.compile(
            rf"(?ms)^(Schedule:Compact,\s*\n\s*{re.escape(sch_name)}\s*,.*?;)\s*",
            re.I,
        )
        m = pat.search(text)
        if not m:
            continue
        block = m.group(1)
        tm = re.search(r"(?im)^(\s*Through:\s*12/31\s*,.*)$", block)
        if not tm:
            continue
        head = block[: tm.start()]
        body = block[tm.end() :]  # For/Until… ending with ;
        body_mid = body.rstrip()
        if body_mid.endswith(";"):
            body_mid = body_mid[:-1].rstrip() + ","
        summer_mid = _summer_low_body(sch_name, scale).rstrip()
        if summer_mid.endswith(";"):
            summer_mid = summer_mid[:-1] + ","
        fall = body.lstrip() if body.lstrip().startswith("For") else body
        if not fall.rstrip().endswith(";"):
            fall = fall.rstrip().rstrip(",") + ";"
        # Jan–May school · Jun–Jul summer-out · Aug–Dec school (Aug in-session)
        new_block = (
            f"{head}"
            f"    Through: 5/31,\n"
            f"{body_mid}\n"
            f"    Through: 7/31,\n"
            f"{summer_mid}\n"
            f"    Through: 12/31,\n"
            f"{fall}\n"
        )
        text = text[: m.start()] + new_block + text[m.end() :]
        ledger.append(
            {
                "object_type": "Schedule:Compact",
                "object_name": sch_name,
                "field_comment": "summer Through:7/31 school-out (Aug in-session)",
                "old": "Through: 12/31 (year-round)",
                "new": f"Through: 5/31 + 7/31@{scale:g} + 12/31 (Aug school)",
            }
        )
    return text


def _mutate_fans(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    if knobs.fan_delta_p_mult == 1.0 and knobs.fan_eff_mult == 1.0:
        return text
    spans = _iter_objects(text, "Fan:OnOff")
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        new_block = block
        if knobs.fan_eff_mult != 1.0:
            m = re.search(
                r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Fan Efficiency.*)$",
                new_block,
            )
            if m:
                old = m.group(2).strip()
                try:
                    new_v = f"{min(0.95, float(old) * knobs.fan_eff_mult):.6g}"
                except ValueError:
                    new_v = f"{min(0.95, 0.7 * knobs.fan_eff_mult):.6g}"
                if old != new_v:
                    ledger.append(
                        {
                            "object_type": "Fan:OnOff",
                            "object_name": name,
                            "field_comment": "Fan Efficiency",
                            "old": old,
                            "new": new_v,
                        }
                    )
                    new_block = (
                        new_block[: m.start()]
                        + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                        + new_block[m.end() :]
                    )
        if knobs.fan_delta_p_mult != 1.0:
            m = re.search(
                r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Pressure Rise.*)$",
                new_block,
            )
            if m:
                old = m.group(2).strip()
                try:
                    new_v = f"{float(old) * knobs.fan_delta_p_mult:.6g}"
                except ValueError:
                    new_v = f"{75.0 * knobs.fan_delta_p_mult:.6g}"
                if old != new_v:
                    ledger.append(
                        {
                            "object_type": "Fan:OnOff",
                            "object_name": name,
                            "field_comment": "Pressure Rise",
                            "old": old,
                            "new": new_v,
                        }
                    )
                    new_block = (
                        new_block[: m.start()]
                        + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                        + new_block[m.end() :]
                    )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mutate_pumps(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    """Scale Rated Pump Head only; leave Rated Power as autosize so E+ efficiency stays physical."""
    if knobs.pump_power_mult == 1.0:
        return text
    spans = _iter_objects(text, "Pump:ConstantSpeed")
    if not spans:
        spans = _iter_objects(text, "Pump:VariableSpeed")
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        obj_type = block.split(",", 1)[0].strip()
        new_block = block
        m = re.search(
            r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Rated Pump Head.*)$",
            new_block,
        )
        if m:
            old = m.group(2).strip()
            try:
                new_v = f"{float(old) * knobs.pump_power_mult:.6g}"
            except ValueError:
                new_v = old
            if old != new_v:
                ledger.append(
                    {
                        "object_type": obj_type,
                        "object_name": name,
                        "field_comment": "Rated Pump Head",
                        "old": old,
                        "new": new_v,
                    }
                )
                new_block = (
                    new_block[: m.start()]
                    + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                    + new_block[m.end() :]
                )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mutate_loop_setpoint(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    if knobs.loop_setpoint_c is None:
        return text
    target = f"{float(knobs.loop_setpoint_c):.6g}"
    # HVACTemplate-Always 34 is the mixed-loop high setpoint schedule
    pat = re.compile(
        r"(?mi)^(Schedule:Compact,\s*\n\s*HVACTemplate-Always 34\s*,.*?;)",
        re.S,
    )
    m = pat.search(text)
    if not m:
        return text
    block = m.group(1)
    name = "HVACTemplate-Always 34"
    # Replace numeric Until values that are the constant 34
    new_lines: list[str] = []
    for line in block.splitlines(keepends=True):
        mm = re.match(r"^(\s*)(34(?:\.0+)?)([,;])(.*)$", line)
        if mm and "Through" not in line and "For" not in line and "Until" not in line:
            old = mm.group(2)
            if old != target:
                ledger.append(
                    {
                        "object_type": "Schedule:Compact",
                        "object_name": name,
                        "field_comment": "loop high setpoint value",
                        "old": old,
                        "new": target,
                    }
                )
                line = f"{mm.group(1)}{target}{mm.group(3)}{mm.group(4)}"
                if not line.endswith("\n"):
                    line += "\n"
        new_lines.append(line)
    return text[: m.start()] + "".join(new_lines) + text[m.end() :]


def _mutate_oa_frac(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    if knobs.oa_frac_scale == 1.0:
        return text
    pat = re.compile(r"(?mi)^(Schedule:Compact,\s*\n\s*SCH_OA\s*,.*?;)", re.S)
    m = pat.search(text)
    if not m:
        return text
    block = m.group(1)
    new_lines: list[str] = []
    for line in block.splitlines(keepends=True):
        mm = re.match(r"^(\s*)([0-9]*\.?[0-9]+)([,;])(.*)$", line)
        if mm and "Through" not in line and "For" not in line and "Until" not in line:
            old = mm.group(2)
            try:
                val = float(old)
            except ValueError:
                new_lines.append(line)
                continue
            if val > 0.0:
                new_v = f"{min(1.0, val * knobs.oa_frac_scale):.6g}"
                if new_v != old:
                    ledger.append(
                        {
                            "object_type": "Schedule:Compact",
                            "object_name": "SCH_OA",
                            "field_comment": "occupied OA fraction",
                            "old": old,
                            "new": new_v,
                        }
                    )
                    line = f"{mm.group(1)}{new_v}{mm.group(3)}{mm.group(4)}"
                    if not line.endswith("\n"):
                        line += "\n"
        new_lines.append(line)
    return text[: m.start()] + "".join(new_lines) + text[m.end() :]


def _snap_15min(hours: float) -> float:
    """Snap decimal hours to 15-min legal EnergyPlus Until times."""
    total_min = int(round(hours * 60.0 / 15.0) * 15)
    return total_min / 60.0


def _fmt_until(hours: float) -> str:
    h = int(math.floor(hours)) % 24
    m = int(round((hours - math.floor(hours)) * 60.0))
    if m == 60:
        h = (h + 1) % 24
        m = 0
    if h == 0 and m == 0 and hours >= 24:
        return "24:00"
    if hours >= 24.0 - 1e-9:
        return "24:00"
    return f"{h:02d}:{m:02d}"


def _mutate_optimum_start(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    if not knobs.optimum_start_h or abs(knobs.optimum_start_h) < 1e-9:
        return text
    advance = _snap_15min(float(knobs.optimum_start_h))
    if advance <= 0:
        return text
    pat = re.compile(r"(?mi)^(Schedule:Compact,\s*\n\s*SCH_HtgSP\s*,.*?;)", re.S)
    m = pat.search(text)
    if not m:
        return text
    block = m.group(1)
    # Shift weekday morning Until times earlier by advance (15-min legal)
    new_lines: list[str] = []
    for line in block.splitlines(keepends=True):
        mm = re.search(r"Until:\s*(\d{1,2}):(\d{2})", line, re.I)
        if mm:
            hh, mi = int(mm.group(1)), int(mm.group(2))
            if hh == 24:
                hours = 24.0
            else:
                hours = hh + mi / 60.0
            # Morning band only: 05:00–08:00 → pull earlier for optimum start
            if 5.0 <= hours <= 8.0:
                new_h = max(0.0, hours - advance)
                new_h = _snap_15min(new_h)
                old_s = mm.group(0)
                new_s = f"Until: {_fmt_until(new_h)}"
                if old_s != new_s:
                    ledger.append(
                        {
                            "object_type": "Schedule:Compact",
                            "object_name": "SCH_HtgSP",
                            "field_comment": "optimum_start Until shift",
                            "old": old_s,
                            "new": new_s,
                        }
                    )
                    line = line.replace(old_s, new_s, 1)
        new_lines.append(line)
    return text[: m.start()] + "".join(new_lines) + text[m.end() :]


def _mutate_setback_heat_sp(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    """Replace SCH_HtgSP setback values (≈18.33°C) with a deeper setback."""
    if knobs.setback_heat_sp_c is None:
        return text
    target = f"{float(knobs.setback_heat_sp_c):.6g}"
    pat = re.compile(r"(?mi)^(Schedule:Compact,\s*\n\s*SCH_HtgSP\s*,.*?;)", re.S)
    m = pat.search(text)
    if not m:
        return text
    block = m.group(1)
    new_lines: list[str] = []
    for line in block.splitlines(keepends=True):
        mm = re.match(r"^(\s*)([0-9]*\.?[0-9]+)([,;])(.*)$", line)
        if not mm or "Through" in line or "For" in line or "Until" in line:
            new_lines.append(line)
            continue
        old = mm.group(2)
        try:
            val = float(old)
        except ValueError:
            new_lines.append(line)
            continue
        # Setback band only — leave occupied ~21.11 alone
        if abs(val - DEFAULT_SETBACK_HEAT_SP_C) < 0.05:
            if old != target:
                ledger.append(
                    {
                        "object_type": "Schedule:Compact",
                        "object_name": "SCH_HtgSP",
                        "field_comment": "setback heating SP",
                        "old": old,
                        "new": target,
                    }
                )
                line = f"{mm.group(1)}{target}{mm.group(3)}{mm.group(4)}"
                if not line.endswith("\n"):
                    line += "\n"
        new_lines.append(line)
    return text[: m.start()] + "".join(new_lines) + text[m.end() :]


def _mutate_oa_shoulder(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    """Scale SCH_OA shoulder fractions (0 < frac < 1); leave 0/1 alone."""
    if knobs.oa_shoulder_scale == 1.0:
        return text
    pat = re.compile(r"(?mi)^(Schedule:Compact,\s*\n\s*SCH_OA\s*,.*?;)", re.S)
    m = pat.search(text)
    if not m:
        return text
    block = m.group(1)
    new_lines: list[str] = []
    for line in block.splitlines(keepends=True):
        mm = re.match(r"^(\s*)([0-9]*\.?[0-9]+)([,;])(.*)$", line)
        if mm and "Through" not in line and "For" not in line and "Until" not in line:
            old = mm.group(2)
            try:
                val = float(old)
            except ValueError:
                new_lines.append(line)
                continue
            if 0.0 < val < 1.0:
                new_v = f"{min(1.0, max(0.0, val * knobs.oa_shoulder_scale)):.6g}"
                if new_v != old:
                    ledger.append(
                        {
                            "object_type": "Schedule:Compact",
                            "object_name": "SCH_OA",
                            "field_comment": "shoulder OA fraction",
                            "old": old,
                            "new": new_v,
                        }
                    )
                    line = f"{mm.group(1)}{new_v}{mm.group(3)}{mm.group(4)}"
                    if not line.endswith("\n"):
                        line += "\n"
        new_lines.append(line)
    return text[: m.start()] + "".join(new_lines) + text[m.end() :]


def _scale_w_per_area_field(
    block: str,
    *,
    object_type: str,
    object_name: str,
    mult: float,
    comment_substr: str,
    ledger: list[dict[str, Any]],
) -> str:
    m = re.search(
        rf"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*{re.escape(comment_substr)}.*)$",
        block,
    )
    if not m:
        return block
    old = m.group(2).strip()
    try:
        new_v = f"{float(old) * mult:.6g}"
    except ValueError:
        return block
    if old == new_v:
        return block
    ledger.append(
        {
            "object_type": object_type,
            "object_name": object_name,
            "field_comment": comment_substr,
            "old": old,
            "new": new_v,
        }
    )
    return (
        block[: m.start()]
        + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
        + block[m.end() :]
    )


def _mutate_people_density(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    if knobs.people_density_mult == 1.0:
        return text
    spans = _iter_objects(text, "People")
    if not spans:
        spans = _iter_objects(text, "PEOPLE")
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        new_block = _scale_w_per_area_field(
            block,
            object_type="People",
            object_name=name,
            mult=knobs.people_density_mult,
            comment_substr="People per Floor Area",
            ledger=ledger,
        )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mutate_equip_w_area(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    """Scale plug/process ElectricEquipment only — never FanProxy (HVAC proxy)."""
    if knobs.equip_w_area_mult == 1.0:
        return text
    spans = _iter_objects(text, "ElectricEquipment")
    if not spans:
        spans = _iter_objects(text, "ELECTRICEQUIPMENT")
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        if "fanproxy" in name.lower():
            pieces.append(block)
            last = end
            continue
        new_block = _scale_w_per_area_field(
            block,
            object_type="ElectricEquipment",
            object_name=name,
            mult=knobs.equip_w_area_mult,
            comment_substr="Watts per Floor Area",
            ledger=ledger,
        )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mutate_lights_w_area(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    if knobs.lights_w_area_mult == 1.0:
        return text
    spans = _iter_objects(text, "Lights")
    if not spans:
        spans = _iter_objects(text, "LIGHTS")
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        new_block = _scale_w_per_area_field(
            block,
            object_type="Lights",
            object_name=name,
            mult=knobs.lights_w_area_mult,
            comment_substr="Watts per Floor Area",
            ledger=ledger,
        )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def _mutate_fan_avail_sch_hvac(text: str, knobs: W2APlantKnobs, ledger: list[dict[str, Any]]) -> str:
    """Point Fan:OnOff availability at SCH_HVAC so weekends/overnight can idle."""
    if not knobs.fan_avail_use_sch_hvac:
        return text
    spans = _iter_objects(text, "Fan:OnOff")
    pieces: list[str] = []
    last = 0
    for start, end, block in spans:
        pieces.append(text[last:start])
        name = _object_name(block)
        new_block = block
        m = re.search(
            r"(?im)^(\s*)([^,;]+)([,;])(.*!-?\s*Availability Schedule Name.*)$",
            new_block,
        )
        if m:
            old = m.group(2).strip()
            new_v = "SCH_HVAC"
            if old != new_v:
                ledger.append(
                    {
                        "object_type": "Fan:OnOff",
                        "object_name": name,
                        "field_comment": "Availability Schedule Name",
                        "old": old,
                        "new": new_v,
                    }
                )
                new_block = (
                    new_block[: m.start()]
                    + f"{m.group(1)}{new_v}{m.group(3)}{m.group(4)}"
                    + new_block[m.end() :]
                )
        pieces.append(new_block)
        last = end
    pieces.append(text[last:])
    return "".join(pieces)


def apply_w2a_plant_knobs(expanded_idf_text: str, knobs: W2APlantKnobs | dict[str, Any]) -> dict[str, Any]:
    """Mutate expanded IDF text; return text, sha256, fields_changed, knobs."""
    if isinstance(knobs, dict):
        refuse_dead_knobs(knobs)
        known = {f.name for f in fields(W2APlantKnobs)}
        knobs = W2APlantKnobs(**{k: v for k, v in knobs.items() if k in known})
    text = expanded_idf_text
    ledger: list[dict[str, Any]] = []
    text = _mutate_coils(text, knobs, ledger)
    text = _mutate_cooling_cop(text, knobs, ledger)
    text = _mutate_fans(text, knobs, ledger)
    text = _mutate_pumps(text, knobs, ledger)
    text = _mutate_loop_setpoint(text, knobs, ledger)
    text = _mutate_oa_frac(text, knobs, ledger)
    text = _mutate_oa_shoulder(text, knobs, ledger)
    text = _mutate_setback_heat_sp(text, knobs, ledger)
    text = _mutate_optimum_start(text, knobs, ledger)
    text = _mutate_fan_avail_sch_hvac(text, knobs, ledger)
    text = _mutate_people_density(text, knobs, ledger)
    text = _mutate_equip_w_area(text, knobs, ledger)
    text = _mutate_lights_w_area(text, knobs, ledger)
    text = _mutate_summer_schedules(text, knobs, ledger)
    return {
        "text": text,
        "expanded_idf_sha256": sha256_text(text),
        "fields_changed": ledger,
        "knobs": knobs.as_dict(),
        "n_fields_changed": len(ledger),
    }


def detect_duplicate_models(
    trials: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fail-closed uniqueness: different knobs must not share expanded SHA / empty ledger."""
    by_sha: dict[str, list[str]] = {}
    collisions: list[dict[str, Any]] = []
    empty_ledger: list[str] = []
    for t in trials:
        tid = str(t.get("trial_id") or t.get("id") or "?")
        sha = t.get("expanded_idf_sha256")
        fields_changed = t.get("fields_changed") or []
        if not fields_changed:
            empty_ledger.append(tid)
        if sha:
            by_sha.setdefault(str(sha), []).append(tid)
    for sha, ids in by_sha.items():
        if len(ids) > 1:
            # Only a collision if knobs differ
            knob_sets = []
            for t in trials:
                if str(t.get("trial_id") or t.get("id")) in ids:
                    knob_sets.append(t.get("knobs"))
            if len({json_dumps_stable(k) for k in knob_sets}) > 1:
                collisions.append({"expanded_idf_sha256": sha, "trial_ids": ids})
    unique = len(by_sha)
    fail = bool(collisions) or bool(empty_ledger)
    return {
        "attempted_runs": len(trials),
        "unique_models": unique,
        "duplicate_collisions": collisions,
        "empty_fields_changed": empty_ledger,
        "uniqueness_ok": not fail,
        "fail_closed": fail,
    }


def json_dumps_stable(obj: Any) -> str:
    import json

    return json.dumps(obj, sort_keys=True, default=str)


def plant_plausibility_check(expanded_idf_text: str) -> dict[str, Any]:
    """Expanded IDF must contain W2A coils + loop pump; no IdealLoads; strip cap 0."""
    t = expanded_idf_text
    has_coil = bool(re.search(r"(?mi)^Coil:Heating:WaterToAirHeatPump:EquationFit\s*,", t))
    has_pump = bool(re.search(r"(?mi)^Pump:(ConstantSpeed|VariableSpeed)\s*,", t))
    has_ideal = bool(re.search(r"(?mi)^ZoneHVAC:IdealLoadsAirSystem\s*,", t))
    # Supplemental strip capacity should remain 0 where present
    strip_ok = True
    for m in re.finditer(r"(?im)^(\s*)([^,;]+)([,;])(.*Supplemental Heating Coil Capacity.*)$", t):
        if m.group(2).strip() not in ("0", "0.0"):
            strip_ok = False
            break
    has_ewt = "Rated Entering Water Temperature" in t or "Entering Water" in t
    ok = has_coil and has_pump and (not has_ideal) and strip_ok
    return {
        "ok": ok,
        "has_w2a_heating_coil": has_coil,
        "has_loop_pump": has_pump,
        "has_ideal_loads": has_ideal,
        "supplemental_strip_capacity_zero": strip_ok,
        "ewt_or_loop_objects_present": has_ewt,
    }
