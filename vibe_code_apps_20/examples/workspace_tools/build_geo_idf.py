#!/usr/bin/env python3
"""Adapt DOE RefBldgLargeOfficeNew2004 → Liberty B100 site-scale IDF."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

ROOT = Path("/home/ben/wattlab_workspace")
SRC = ROOT / "uploads/prototypes/RefBldgLargeOfficeNew2004_Chicago.idf"
DST = ROOT / "uploads/prototypes/geo_b100_6fl_wwr60_wc.idf"
ART = ROOT / ".artifacts/geo_b100_6fl_glass"

FLOORPLATE_FT2 = 38476.0
TARGET_AREA = 140000.0
XY_SCALE = math.sqrt(TARGET_AREA / (FLOORPLATE_FT2 * 6))
WWR_BOOST = 0.60 / 0.38  # 38% → 60%

VERT_RE = re.compile(
    r"^(\s*)(-?[0-9.]+),(-?[0-9.]+),(-?[0-9.]+)[;,]?\s*(!- X,Y,Z ==> Vertex.*)$"
)


def set_zone_multiplier(idf: str, zone_name: str, mult: int) -> str:
    start = idf.find(f"  Zone,\n    {zone_name},")
    if start < 0:
        raise SystemExit(f"missing zone {zone_name}")
    end = idf.find(";", start)
    block = idf[start : end + 1]
    new_block, n = re.subn(
        r"([0-9.]+)(,\s+!- Multiplier)", rf"{mult}\2", block, count=1
    )
    if n != 1:
        raise SystemExit(f"multiplier patch failed for {zone_name}")
    return idf[:start] + new_block + idf[end + 1 :]


def scale_origins(idf: str, scale: float) -> str:
    out = []
    for line in idf.splitlines(True):
        if "!- X Origin" in line or "!- Y Origin" in line:
            m = re.match(
                r"(\s*)(-?[0-9.eE+]+)(,.*!- [XY] Origin.*)", line.rstrip("\n")
            )
            if m:
                line = f"{m.group(1)}{float(m.group(2)) * scale:.4f}{m.group(3)}\n"
        out.append(line)
    return "".join(out)


def rewrite_vert_line(line: str, x: float, y: float, z: float) -> str:
    m = VERT_RE.match(line.rstrip("\n"))
    assert m
    comment = m.group(5)
    nl = "\n" if line.endswith("\n") else ""
    # Last vertex in object ends with ';' before comment
    if ";" in line.split("!")[0]:
        return f"{m.group(1)}{x:.4f},{y:.4f},{z:.4f};  {comment}{nl}"
    return f"{m.group(1)}{x:.4f},{y:.4f},{z:.4f},  {comment}{nl}"


def scale_block_verts(block: list[str], scale_xy: float, z_xform=None) -> int:
    n = 0
    for j, line in enumerate(block):
        m = VERT_RE.match(line.rstrip("\n"))
        if not m:
            continue
        x = float(m.group(2)) * scale_xy
        y = float(m.group(3)) * scale_xy
        z = float(m.group(4))
        if z_xform is not None:
            z = z_xform(z)
        block[j] = rewrite_vert_line(line, x, y, z)
        n += 1
    return n


def take_object(lines: list[str], i: int) -> tuple[list[str], int]:
    block = [lines[i]]
    i += 1
    while i < len(lines):
        block.append(lines[i])
        # object ends when a line contains ';' (vertex last line or lone ;)
        if ";" in lines[i]:
            i += 1
            break
        i += 1
    return block, i


def wall_z_range(wall_block: list[str]) -> tuple[float, float] | None:
    zs = []
    for line in wall_block:
        m = VERT_RE.match(line.rstrip("\n"))
        if m:
            zs.append(float(m.group(4)))
    if not zs:
        return None
    return min(zs), max(zs)


def process_geometry(idf: str) -> tuple[str, int, int]:
    """Scale surfaces first, then fenestration to 60% of parent wall height (curtain strip)."""
    lines = idf.splitlines(True)
    # Pass 1: scale all building surfaces; index walls by name
    out: list[str] = []
    i = 0
    nb = nf = 0
    walls: dict[str, tuple[float, float]] = {}
    while i < len(lines):
        if lines[i].startswith("  BuildingSurface:Detailed,"):
            block, i = take_object(lines, i)
            nb += scale_block_verts(block, XY_SCALE)
            # name is first field after type line
            name = block[1].split(",")[0].strip()
            # only exterior walls (Surface Type Wall + Outdoors) matter for WWR
            surf_type = block[2].split(",")[0].strip()
            if surf_type == "Wall":
                zr = wall_z_range(block)
                if zr:
                    walls[name] = zr
            out.extend(block)
            continue
        out.append(lines[i])
        i += 1

    # Pass 2: fenestration on scaled text
    lines = "".join(out).splitlines(True)
    out = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("  FenestrationSurface:Detailed,"):
            block, i = take_object(lines, i)
            parent = block[4].split(",")[0].strip()  # Building Surface Name
            zr = walls.get(parent)
            if zr:
                wz0, wz1 = zr
                wall_h = wz1 - wz0
                # strip window: WWR≈height fraction for full-width curtain glass
                target_h = min(0.60 * wall_h, wall_h * 0.92)
                sill = wz0 + 0.04 * wall_h
                head = sill + target_h
                if head > wz1 - 0.02 * wall_h:
                    head = wz1 - 0.02 * wall_h
                    sill = head - target_h

                def zx(z: float, zs=None, sill=sill, head=head) -> float:
                    # map original low→sill, high→head (after we know orig zs)
                    return z  # placeholder replaced below

                zs = []
                for line in block:
                    m = VERT_RE.match(line.rstrip("\n"))
                    if m:
                        zs.append(float(m.group(4)))
                if zs:
                    zmin, zmax = min(zs), max(zs)

                    def zx(z: float, zmin=zmin, zmax=zmax, sill=sill, head=head) -> float:
                        if abs(zmax - zmin) < 1e-9:
                            return sill
                        # low verts → sill, high → head
                        if abs(z - zmax) < 1e-9:
                            return head
                        if abs(z - zmin) < 1e-9:
                            return sill
                        frac = (z - zmin) / (zmax - zmin)
                        return sill + frac * (head - sill)

                    nf += scale_block_verts(block, XY_SCALE, zx)
                else:
                    nf += scale_block_verts(block, XY_SCALE)
            else:
                nf += scale_block_verts(block, XY_SCALE)
            out.extend(block)
            continue
        out.append(lines[i])
        i += 1
    return "".join(out), nb, nf


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    text = SRC.read_text(encoding="utf-8", errors="replace")

    for z in [
        "Core_mid",
        "MidFloor_Plenum",
        "Perimeter_mid_ZN_1",
        "Perimeter_mid_ZN_2",
        "Perimeter_mid_ZN_3",
        "Perimeter_mid_ZN_4",
    ]:
        text = set_zone_multiplier(text, z, 4)

    text = scale_origins(text, XY_SCALE)
    text, nb, nf = process_geometry(text)

    # SHGC last field (no VT in this object)
    text, n_shgc = re.subn(
        r"(NonRes Fixed Assembly Window,  !- Name\n"
        r"    3\.23646,                 !- U-Factor \{W/m2-K\}\n"
        r"    )0\.39;",
        r"\g<1>0.45;",
        text,
        count=1,
    )

    text = text.replace(
        "NO,                      !- Run Simulation for Weather File Run Periods",
        "YES,                     !- Run Simulation for Weather File Run Periods",
        1,
    )
    text = re.sub(
        r"  Site:Location,\n    [^;]+;",
        """  Site:Location,
    Detroit_MI_Liberty_B100,  !- Name
    42.33,                   !- Latitude {deg}
    -83.05,                  !- Longitude {deg}
    -5.00,                   !- Time Zone {hr}
    190.00;                  !- Elevation {m}""",
        text,
        count=1,
        flags=re.M,
    )
    text = text.replace(
        "Ref Bldg Large Office New2004_v1.3_5.0",
        "Liberty_B100_6fl_WWR60_WC",
        1,
    )
    text = (
        "! Liberty B100 site-scale: DOE LargeOffice, 6fl mid×4, XY scale, "
        "WWR~0.60, water-cooled chillers\n!\n"
        + text
    )
    if "Output:Meter,Electricity:Facility,Monthly" not in text:
        text += (
            "\n  Output:Meter,Electricity:Facility,Monthly;\n"
            "  Output:Meter,NaturalGas:Facility,Monthly;\n"
        )

    DST.write_text(text)
    meta = {
        "source": str(SRC),
        "idf": str(DST),
        "xy_scale": XY_SCALE,
        "mid_multiplier": 4,
        "stories_above_grade": 6,
        "target_area_ft2": TARGET_AREA,
        "wwr_target": 0.60,
        "wwr_boost": WWR_BOOST,
        "plant": "water_cooled_chiller",
        "building_verts_scaled": nb,
        "fen_verts_scaled": nf,
        "shgc_patched": n_shgc,
        "chiller_electric_mentions": text.count("Chiller:Electric"),
        "cooling_tower_mentions": text.count("CoolingTower"),
    }
    (ART / "geo_build_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))
    # spot checks
    sample = DST.read_text()
    idx = sample.find("Perimeter_bot_ZN_1_Wall_South_Window")
    print("--- fen sample ---")
    print(sample[idx : idx + 450])
    print("--- glazing ---")
    print(re.search(r"WindowMaterial:SimpleGlazingSystem,.*?;", sample, re.S).group(0))


if __name__ == "__main__":
    main()
