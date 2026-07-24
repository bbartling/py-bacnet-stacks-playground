#!/usr/bin/env python3
"""Patch VAV-reheat DOE-style IDFs: SAT / envelope / HW (any building).

Generalized knobs for gas G14 chase after ``wattlab geo-idf`` + ``wattlab dial-loads``.
Not Liberty-hardcoded — schedule/window names match DOE Large Office / RefBldg patterns.

Supports:
  - flat SAT (°C) or seasonal winter/summer SAT (dump AHUs often ~55°F / ~48°F)
  - window U/SHGC (``NonRes Fixed Assembly Window`` simple glazing)
  - infiltration multiplier on Flow Rate per Exterior Surface Area
  - optional HW loop schedule setpoint (°C); live HWS often ~152–167°F
  - optional insulation conductivity multiplier (1.0 = leave alone)

Raises if critical patches land 0 hits (silent no-ops caused false r7).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def _replace_sat_flat(text: str, sat_c: float) -> tuple[str, int]:
    text2, n = re.subn(
        r"(Seasonal-Reset-Supply-Air-Temp-Sch,.*?Until: 24:00,[^\n]*\n\s*)([0-9.]+)(;)",
        lambda m: f"{m.group(1)}{sat_c}{m.group(3)}",
        text,
        count=1,
        flags=re.S,
    )
    return text2, n


def _replace_sat_seasonal(
    text: str, *, winter_c: float, summer_c: float
) -> tuple[str, int]:
    """Winter (Nov–Mar) warmer SAT; Apr–Oct colder for more VAV reheat."""
    block = (
        "Schedule:Compact,\n"
        "    Seasonal-Reset-Supply-Air-Temp-Sch,    !- Name\n"
        "    Temperature,              !- Schedule Type Limits Name\n"
        "    Through: 3/31,            !- Field 1\n"
        "    For: AllDays,             !- Field 2\n"
        "    Until: 24:00,             !- Field 3\n"
        f"    {winter_c},                     !- Field 4\n"
        "    Through: 10/31,           !- Field 5\n"
        "    For: AllDays,             !- Field 6\n"
        "    Until: 24:00,             !- Field 7\n"
        f"    {summer_c},                     !- Field 8\n"
        "    Through: 12/31,           !- Field 9\n"
        "    For: AllDays,             !- Field 10\n"
        "    Until: 24:00,             !- Field 11\n"
        f"    {winter_c};                     !- Field 12\n"
    )
    # Value line is often "12.8;                     !- Field 4"
    text2, n = re.subn(
        r"Schedule:Compact,\n    Seasonal-Reset-Supply-Air-Temp-Sch,.*?\n\s*[0-9.]+;[^\n]*\n",
        block,
        text,
        count=1,
        flags=re.S,
    )
    return text2, n


def _replace_window(text: str, window_u: float, window_shgc: float) -> tuple[str, int]:
    text2, n = re.subn(
        r"(WindowMaterial:SimpleGlazingSystem,\s*\n\s*NonRes Fixed Assembly Window,[^\n]*\n\s*)"
        r"[0-9.]+(,[^\n]*\n\s*)[0-9.]+;",
        lambda m: f"{m.group(1)}{window_u}{m.group(2)}{window_shgc};",
        text,
        count=1,
    )
    return text2, n


def patch(
    src: Path,
    dst: Path,
    *,
    sat_c: float | None,
    sat_winter_c: float | None,
    sat_summer_c: float | None,
    window_u: float,
    window_shgc: float,
    infil_mult_on_current: float,
    hw_loop_c: float | None,
    insulation_cond_mult: float,
    oa_per_person_mult: float = 1.0,
    winter_oa_earlier: bool = False,
    require_hits: bool = True,
) -> dict:
    text = src.read_text(encoding="utf-8", errors="replace")
    meta: dict = {"src": str(src), "dst": str(dst)}

    if sat_winter_c is not None and sat_summer_c is not None:
        text, n = _replace_sat_seasonal(
            text, winter_c=sat_winter_c, summer_c=sat_summer_c
        )
        meta["sat_mode"] = "seasonal"
        meta["sat_winter_c"] = sat_winter_c
        meta["sat_summer_c"] = sat_summer_c
        meta["sat_patches"] = n
    else:
        assert sat_c is not None
        text, n = _replace_sat_flat(text, sat_c)
        meta["sat_mode"] = "flat"
        meta["sat_c"] = sat_c
        meta["sat_patches"] = n

    text, n = _replace_window(text, window_u, window_shgc)
    meta["window_u"] = window_u
    meta["window_shgc"] = window_shgc
    meta["window_patches"] = n

    text2, n = re.subn(
        r"([0-9.eE+-]+)(\s*,\s*!- Flow Rate per Exterior Surface Area)",
        lambda m: f"{float(m.group(1)) * infil_mult_on_current:.6e}{m.group(2)}",
        text,
    )
    meta["infil_mult"] = infil_mult_on_current
    meta["infil_patches"] = n
    text = text2

    if hw_loop_c is not None:
        # DOE variants: value on next line, or same-line "Until: 24:00,82.2;"
        text2, n = re.subn(
            r"(HW-Loop-Temp-Schedule,.*?Until: 24:00,[^\n]*\n\s*)([0-9.]+)(;)",
            lambda m: f"{m.group(1)}{hw_loop_c}{m.group(3)}",
            text,
            count=1,
            flags=re.S,
        )
        if n == 0:
            text2, n = re.subn(
                r"(HW-Loop-Temp-Schedule,.*?Until: 24:00,)([0-9.]+)(;)",
                lambda m: f"{m.group(1)}{hw_loop_c}{m.group(3)}",
                text,
                count=1,
                flags=re.S,
            )
        meta["hw_loop_c"] = hw_loop_c
        meta["hw_patches"] = n
        text = text2

    # Outdoor air (DesignSpecification:OutdoorAir Flow/Person) — slight bump;
    # winter heating feels this most when min-OA schedule is on.
    if abs(oa_per_person_mult - 1.0) > 1e-9:
        text2, n = re.subn(
            r"([0-9.]+)(;\s*!- Outdoor Air Flow per Person)",
            lambda m: f"{float(m.group(1)) * oa_per_person_mult:.6g}{m.group(2)}",
            text,
        )
        meta["oa_per_person_mult"] = oa_per_person_mult
        meta["oa_patches"] = n
        text = text2
    else:
        meta["oa_per_person_mult"] = 1.0
        meta["oa_patches"] = 0

    # Winter-only: open min-OA damper one hour earlier on weekdays (more cold OA hours).
    if winter_oa_earlier:
        text2, n = re.subn(
            r"(MinOA_MotorizedDamper_Sched,.*?For: Weekdays SummerDesignDay,\s*\n\s*Until: )07:00,",
            r"\g<1>06:00,",
            text,
            count=1,
            flags=re.S,
        )
        # Prefer a true winter/summer split of the MinOA schedule when possible.
        winter_block = """Schedule:Compact,
    MinOA_MotorizedDamper_Sched,    !- Name
    Fraction,                 !- Schedule Type Limits Name
    Through: 3/31,            !- Field 1
    For: Weekdays SummerDesignDay,    !- Field 2
    Until: 06:00,             !- Field 3
    0.0,                      !- Field 4
    Until: 22:00,             !- Field 5
    1.0,                      !- Field 6
    Until: 24:00,             !- Field 7
    0.0,                      !- Field 8
    For: Saturday WinterDesignDay,    !- Field 9
    Until: 06:00,             !- Field 10
    0.0,                      !- Field 11
    Until: 18:00,             !- Field 12
    1.0,                      !- Field 13
    Until: 24:00,             !- Field 14
    0.0,                      !- Field 15
    For: AllOtherDays,        !- Field 16
    Until: 24:00,             !- Field 17
    0.0,                      !- Field 18
    Through: 10/31,           !- Field 19
    For: Weekdays SummerDesignDay,    !- Field 20
    Until: 07:00,             !- Field 21
    0.0,                      !- Field 22
    Until: 22:00,             !- Field 23
    1.0,                      !- Field 24
    Until: 24:00,             !- Field 25
    0.0,                      !- Field 26
    For: Saturday WinterDesignDay,    !- Field 27
    Until: 07:00,             !- Field 28
    0.0,                      !- Field 29
    Until: 18:00,             !- Field 30
    1.0,                      !- Field 31
    Until: 24:00,             !- Field 32
    0.0,                      !- Field 33
    For: AllOtherDays,        !- Field 34
    Until: 24:00,             !- Field 35
    0.0,                      !- Field 36
    Through: 12/31,           !- Field 37
    For: Weekdays SummerDesignDay,    !- Field 38
    Until: 06:00,             !- Field 39
    0.0,                      !- Field 40
    Until: 22:00,             !- Field 41
    1.0,                      !- Field 42
    Until: 24:00,             !- Field 43
    0.0,                      !- Field 44
    For: Saturday WinterDesignDay,    !- Field 45
    Until: 06:00,             !- Field 46
    0.0,                      !- Field 47
    Until: 18:00,             !- Field 48
    1.0,                      !- Field 49
    Until: 24:00,             !- Field 50
    0.0,                      !- Field 51
    For: AllOtherDays,        !- Field 52
    Until: 24:00,             !- Field 53
    0.0;                      !- Field 54
"""
        text3, n2 = re.subn(
            r"Schedule:Compact,\n\s*MinOA_MotorizedDamper_Sched,.*?;",
            winter_block.rstrip("\n") + "\n",
            text,
            count=1,
            flags=re.S,
        )
        if n2:
            text = text3
            meta["winter_oa_schedule_patches"] = n2
            meta["winter_oa_earlier"] = True
        else:
            text = text2
            meta["winter_oa_schedule_patches"] = n
            meta["winter_oa_earlier"] = bool(n)
    else:
        meta["winter_oa_earlier"] = False
        meta["winter_oa_schedule_patches"] = 0

    meta["insulation_cond_mult"] = insulation_cond_mult
    if abs(insulation_cond_mult - 1.0) > 1e-9:
        # Only touch the numeric field on a line that already has "!- Conductivity".
        lines = text.splitlines(keepends=True)
        n = 0
        i = 0
        while i < len(lines):
            if lines[i].lstrip().startswith("Material,"):
                name_line = lines[i + 1] if i + 1 < len(lines) else ""
                name = name_line.strip().split(",")[0].strip()
                if any(k.lower() in name.lower() for k in ("batt", "insul", "rigid", "polyiso")):
                    for j in range(i + 2, min(i + 12, len(lines))):
                        if "!- Conductivity" in lines[j]:
                            m = re.match(
                                r"^(\s*)([0-9.]+)(,\s*!-\s*Conductivity[^\n]*\n?)$",
                                lines[j],
                            )
                            if m:
                                new_v = float(m.group(2)) * insulation_cond_mult
                                nl = "\n" if lines[j].endswith("\n") and not m.group(3).endswith("\n") else ""
                                lines[j] = f"{m.group(1)}{new_v}{m.group(3)}{nl}"
                                n += 1
                            break
            i += 1
        text = "".join(lines)
        meta["insulation_cond_patches"] = n
    else:
        meta["insulation_cond_patches"] = 0

    if require_hits:
        bad = []
        if meta.get("sat_patches", 0) < 1:
            bad.append("sat")
        if meta.get("window_patches", 0) < 1:
            bad.append("window")
        if infil_mult_on_current != 1.0 and meta.get("infil_patches", 0) < 1:
            bad.append("infil")
        if hw_loop_c is not None and meta.get("hw_patches", 0) < 1:
            bad.append("hw")
        if abs(oa_per_person_mult - 1.0) > 1e-9 and meta.get("oa_patches", 0) < 1:
            bad.append("oa")
        if bad:
            raise RuntimeError(f"patch hits missing for: {bad}; meta={meta}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text)
    return meta


def main() -> None:
    p = argparse.ArgumentParser(
        description="Patch VAV reheat + envelope knobs on a DOE-style IDF (any building)."
    )
    p.add_argument("--src", required=True)
    p.add_argument("--dst", required=True)
    p.add_argument("--sat-c", type=float, default=None)
    p.add_argument("--sat-winter-c", type=float, default=None)
    p.add_argument("--sat-summer-c", type=float, default=None)
    p.add_argument("--window-u", type=float, default=4.0)
    p.add_argument("--window-shgc", type=float, default=0.45)
    p.add_argument("--infil-mult", type=float, default=1.1)
    p.add_argument("--hw-c", type=float, default=None)
    p.add_argument("--insulation-cond-mult", type=float, default=1.0)
    p.add_argument("--oa-per-person-mult", type=float, default=1.0)
    p.add_argument(
        "--winter-oa-earlier",
        action="store_true",
        help="Seasonal MinOA schedule: open 1h earlier Nov–Mar (slight cold-OA bump)",
    )
    p.add_argument("--allow-miss", action="store_true")
    p.add_argument("--meta-out")
    args = p.parse_args()
    if args.sat_winter_c is None and args.sat_c is None:
        args.sat_c = 12.8
    meta = patch(
        Path(args.src),
        Path(args.dst),
        sat_c=args.sat_c,
        sat_winter_c=args.sat_winter_c,
        sat_summer_c=args.sat_summer_c,
        window_u=args.window_u,
        window_shgc=args.window_shgc,
        infil_mult_on_current=args.infil_mult,
        hw_loop_c=args.hw_c,
        insulation_cond_mult=args.insulation_cond_mult,
        oa_per_person_mult=args.oa_per_person_mult,
        winter_oa_earlier=args.winter_oa_earlier,
        require_hits=not args.allow_miss,
    )
    print(json.dumps(meta, indent=2))
    if args.meta_out:
        Path(args.meta_out).write_text(json.dumps(meta, indent=2) + "\n")


if __name__ == "__main__":
    main()
