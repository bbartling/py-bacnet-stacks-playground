"""Adapt a DOE Large Office (or similar) IDF to site-scale massing.

Generalized from the Liberty B100 geometry campaign: mid-floor multipliers,
XY scale to target conditioned area, fenestration height strip for WWR target,
optional Site:Location + SHGC patches. No Liberty hardcodes — all via CLI args.

Typical:

    wattlab geo-idf \\
      --src uploads/prototypes/RefBldgLargeOfficeNew2004_Chicago.idf \\
      --dst uploads/prototypes/geo_site.idf \\
      --target-area-ft2 140000 --stories 6 --wwr 0.60 \\
      --lat 42.33 --lon -83.05 --site-name Detroit_MI
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

# DOE Large Office mid-band zones (bot/mid/top massing). Override with --mid-zones.
DEFAULT_MID_ZONES = (
    "Core_mid",
    "MidFloor_Plenum",
    "Perimeter_mid_ZN_1",
    "Perimeter_mid_ZN_2",
    "Perimeter_mid_ZN_3",
    "Perimeter_mid_ZN_4",
)

# Stock DOE Large Office New2004 conditioned floorplate ≈ 38,476 ft² (one story).
DEFAULT_FLOORPLATE_FT2 = 38476.0

VERT_RE = re.compile(
    r"^(\s*)(-?[0-9.]+),(-?[0-9.]+),(-?[0-9.]+)[;,]?\s*(!- X,Y,Z ==> Vertex.*)$"
)


def set_zone_multiplier(idf: str, zone_name: str, mult: int) -> str:
    start = idf.find(f"  Zone,\n    {zone_name},")
    if start < 0:
        # tolerate alternate spacing
        start = idf.find(f"Zone,\n    {zone_name},")
    if start < 0:
        raise ValueError(f"missing zone {zone_name}")
    end = idf.find(";", start)
    block = idf[start : end + 1]
    new_block, n = re.subn(
        r"([0-9.]+)(,\s+!- Multiplier)", rf"{mult}\2", block, count=1
    )
    if n != 1:
        raise ValueError(f"multiplier patch failed for {zone_name}")
    return idf[:start] + new_block + idf[end + 1 :]


def scale_origins(idf: str, scale: float) -> str:
    out: list[str] = []
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
    if not m:
        return line
    comment = m.group(5)
    nl = "\n" if line.endswith("\n") else ""
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


def process_geometry(
    idf: str,
    *,
    xy_scale: float,
    wwr_target: float,
) -> tuple[str, int, int]:
    """Scale surfaces, then fenestration height strip toward ``wwr_target``."""
    lines = idf.splitlines(True)
    out: list[str] = []
    i = 0
    nb = nf = 0
    walls: dict[str, tuple[float, float]] = {}
    while i < len(lines):
        if lines[i].startswith("  BuildingSurface:Detailed,"):
            block, i = take_object(lines, i)
            nb += scale_block_verts(block, xy_scale)
            name = block[1].split(",")[0].strip()
            surf_type = block[2].split(",")[0].strip()
            if surf_type == "Wall":
                zr = wall_z_range(block)
                if zr:
                    walls[name] = zr
            out.extend(block)
            continue
        out.append(lines[i])
        i += 1

    lines = "".join(out).splitlines(True)
    out = []
    i = 0
    while i < len(lines):
        if lines[i].startswith("  FenestrationSurface:Detailed,"):
            block, i = take_object(lines, i)
            parent = block[4].split(",")[0].strip()
            zr = walls.get(parent)
            if zr:
                wz0, wz1 = zr
                wall_h = wz1 - wz0
                target_h = min(wwr_target * wall_h, wall_h * 0.92)
                sill = wz0 + 0.04 * wall_h
                head = sill + target_h
                if head > wz1 - 0.02 * wall_h:
                    head = wz1 - 0.02 * wall_h
                    sill = head - target_h
                zs = []
                for line in block:
                    m = VERT_RE.match(line.rstrip("\n"))
                    if m:
                        zs.append(float(m.group(4)))
                if zs:
                    zmin, zmax = min(zs), max(zs)

                    def zx(
                        z: float,
                        zmin: float = zmin,
                        zmax: float = zmax,
                        sill: float = sill,
                        head: float = head,
                    ) -> float:
                        if abs(zmax - zmin) < 1e-9:
                            return sill
                        if abs(z - zmax) < 1e-9:
                            return head
                        if abs(z - zmin) < 1e-9:
                            return sill
                        frac = (z - zmin) / (zmax - zmin)
                        return sill + frac * (head - sill)

                    nf += scale_block_verts(block, xy_scale, zx)
                else:
                    nf += scale_block_verts(block, xy_scale)
            else:
                nf += scale_block_verts(block, xy_scale)
            out.extend(block)
            continue
        out.append(lines[i])
        i += 1
    return "".join(out), nb, nf


def build_site_scale_idf(
    src: Path,
    dst: Path,
    *,
    target_area_ft2: float,
    stories: int = 6,
    floorplate_ft2: float = DEFAULT_FLOORPLATE_FT2,
    wwr: float = 0.60,
    mid_zones: list[str] | None = None,
    lat: float | None = None,
    lon: float | None = None,
    elevation_m: float = 190.0,
    tz_hr: float = -5.0,
    site_name: str | None = None,
    building_name: str | None = None,
    shgc: float | None = 0.45,
    enable_weather_run: bool = True,
    header_note: str | None = None,
) -> dict[str, Any]:
    """Build a site-scale IDF; write ``dst``; return provenance meta."""
    if stories < 2:
        raise ValueError("stories must be >= 2 for bot/mid/top massing")
    mid_mult = max(1, int(stories) - 2)
    xy_scale = math.sqrt(float(target_area_ft2) / (float(floorplate_ft2) * float(stories)))
    zones = list(mid_zones) if mid_zones else list(DEFAULT_MID_ZONES)

    text = Path(src).read_text(encoding="utf-8", errors="replace")
    for z in zones:
        try:
            text = set_zone_multiplier(text, z, mid_mult)
        except ValueError:
            # Skip missing zones (prototype variants)
            continue

    text = scale_origins(text, xy_scale)
    text, nb, nf = process_geometry(text, xy_scale=xy_scale, wwr_target=float(wwr))

    n_shgc = 0
    if shgc is not None:
        text2, n_shgc = re.subn(
            r"(WindowMaterial:SimpleGlazingSystem,[^\n]*\n"
            r"\s+[^\n]*!- Name\n"
            r"\s+[0-9.]+,\s+!- U-Factor[^\n]*\n"
            r"\s+)[0-9.]+;",
            rf"\g<1>{float(shgc)};",
            text,
            count=1,
            flags=re.M,
        )
        if n_shgc:
            text = text2
        else:
            # DOE Large Office NonRes Fixed Assembly Window pattern
            text2, n_shgc = re.subn(
                r"(NonRes Fixed Assembly Window,  !- Name\n"
                r"    [0-9.]+,                 !- U-Factor \{W/m2-K\}\n"
                r"    )[0-9.]+;",
                rf"\g<1>{float(shgc)};",
                text,
                count=1,
            )
            if n_shgc:
                text = text2

    if enable_weather_run:
        text = text.replace(
            "NO,                      !- Run Simulation for Weather File Run Periods",
            "YES,                     !- Run Simulation for Weather File Run Periods",
            1,
        )

    if lat is not None and lon is not None:
        name = site_name or f"Site_{lat}_{lon}"
        text = re.sub(
            r"  Site:Location,\n    [^;]+;",
            f"""  Site:Location,
    {name},  !- Name
    {float(lat):.4f},                   !- Latitude {{deg}}
    {float(lon):.4f},                  !- Longitude {{deg}}
    {float(tz_hr):.2f},                   !- Time Zone {{hr}}
    {float(elevation_m):.2f};                  !- Elevation {{m}}""",
            text,
            count=1,
            flags=re.M,
        )

    if building_name:
        text = re.sub(
            r"(  Building,\n    )[^,]+,",
            rf"\g<1>{building_name},",
            text,
            count=1,
        )

    note = header_note or (
        f"! Site-scale geo-idf: stories={stories} mid×{mid_mult}, "
        f"target={target_area_ft2:g} ft², WWR~{wwr}, xy_scale={xy_scale:.4f}\n!\n"
    )
    if not text.lstrip().startswith("!"):
        text = note + text
    else:
        text = note + text

    if "Output:Meter,Electricity:Facility,Monthly" not in text:
        text += (
            "\n  Output:Meter,Electricity:Facility,Monthly;\n"
            "  Output:Meter,NaturalGas:Facility,Monthly;\n"
        )

    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")

    return {
        "source": str(src),
        "idf": str(dst),
        "xy_scale": round(xy_scale, 6),
        "mid_multiplier": mid_mult,
        "stories_above_grade": int(stories),
        "target_area_ft2": float(target_area_ft2),
        "floorplate_ft2": float(floorplate_ft2),
        "wwr_target": float(wwr),
        "building_verts_scaled": nb,
        "fen_verts_scaled": nf,
        "shgc_patched": int(n_shgc),
        "chiller_electric_mentions": text.count("Chiller:Electric"),
        "cooling_tower_mentions": text.count("CoolingTower"),
        "area_scale_hint": 1.0,
        "note": "Use custom_idf + prototype_area_scale=1 for Twin/G14; do not 5Zone×scale.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wattlab geo-idf",
        description="Adapt DOE Large Office IDF to site-scale massing (any building).",
    )
    p.add_argument("--src", required=True, help="Source prototype IDF (e.g. DOE Large Office)")
    p.add_argument("--dst", required=True, help="Output site-scale IDF path")
    p.add_argument("--target-area-ft2", type=float, required=True)
    p.add_argument("--stories", type=int, default=6)
    p.add_argument(
        "--floorplate-ft2",
        type=float,
        default=DEFAULT_FLOORPLATE_FT2,
        help="Source conditioned floorplate ft² (DOE Large Office ≈ 38476)",
    )
    p.add_argument("--wwr", type=float, default=0.60)
    p.add_argument("--lat", type=float, default=None)
    p.add_argument("--lon", type=float, default=None)
    p.add_argument("--tz", type=float, default=-5.0)
    p.add_argument("--elevation-m", type=float, default=190.0)
    p.add_argument("--site-name", default=None)
    p.add_argument("--building-name", default=None)
    p.add_argument("--shgc", type=float, default=0.45)
    p.add_argument("--no-shgc", action="store_true")
    p.add_argument("--meta-out", default=None, help="Write provenance JSON")
    args = p.parse_args(argv)

    meta = build_site_scale_idf(
        Path(args.src),
        Path(args.dst),
        target_area_ft2=args.target_area_ft2,
        stories=args.stories,
        floorplate_ft2=args.floorplate_ft2,
        wwr=args.wwr,
        lat=args.lat,
        lon=args.lon,
        elevation_m=args.elevation_m,
        tz_hr=args.tz,
        site_name=args.site_name,
        building_name=args.building_name,
        shgc=None if args.no_shgc else args.shgc,
    )
    print(json.dumps(meta, indent=2))
    if args.meta_out:
        Path(args.meta_out).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
