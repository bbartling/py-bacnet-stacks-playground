#!/usr/bin/env python3
"""Apply DOE Commercial Reference Building vintage targets (climate 5A) to a Large-Office-form IDF.

Official Post-1980 / Pre-1980 IDF zips are often unavailable from energy.gov; DOE forms are
identical across vintages — only fabric / infiltration / LPD / plant efficiency change.
This patches a site-scale New2004-derived IDF to Post-1980 (90.1-1989) or Pre-1980
(Briggs et al.) **Chicago 5A** scorecard targets from the DOE Ref Bldg report.

Any building: pass --src / --dst / --vintage. Not Liberty-hardcoded.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

# IP → SI for U-factor
IP_U_TO_SI = 5.678263

# Chicago IL 5A from DOE Ref Bldg report Tables 19/21/24/25 (+ infil §5.3.2)
# Wall/roof U in IP Btu/h·ft²·°F; window U IP; SHGC dimensionless.
VINTAGE_5A = {
    "post1980": {
        "label": "DOE Post-1980 / ASHRAE 90.1-1989 climate 5A",
        "window_u_ip": 0.59,
        "window_shgc": 0.39,
        "mass_wall_u_ip": 0.100,
        "roof_u_ip": 0.053,  # IEAD / single roof U for existing stock
        "new_mass_wall_u_ip": 0.151,  # 90.1-2004 mass wall 5A (scale base)
        "new_roof_u_ip": 0.034,  # 90.1-2004 IEAD 5A
        "infil_vs_new": 1.5 / 0.4,  # existing vs new airtightness @ 75 Pa
        "lights_w_m2": 14.0,  # ~1.3 W/ft² office 90.1-1989 building-area proxy
        "boiler_eff": 0.75,
    },
    "pre1980": {
        "label": "DOE Pre-1980 (Briggs) climate 5A",
        "window_u_ip": 0.62,
        "window_shgc": 0.41,
        "mass_wall_u_ip": 0.156,
        "roof_u_ip": 0.072,
        "new_mass_wall_u_ip": 0.151,
        "new_roof_u_ip": 0.034,
        "infil_vs_new": 1.5 / 0.4,
        "lights_w_m2": 14.0,  # DOE assumed lighting updated to ≥1989
        "boiler_eff": 0.70,
    },
}


def _set_window(text: str, u_si: float, shgc: float) -> tuple[str, int]:
    text2, n = re.subn(
        r"(WindowMaterial:SimpleGlazingSystem,\s*\n\s*NonRes Fixed Assembly Window,[^\n]*\n\s*)"
        r"[0-9.]+(,[^\n]*\n\s*)[0-9.]+;",
        lambda m: f"{m.group(1)}{u_si:.5f}{m.group(2)}{shgc:.3f};",
        text,
        count=1,
    )
    return text2, n


def _scale_insulation_thickness(text: str, material_name: str, factor: float) -> tuple[str, int]:
    """Scale Thickness field on a named Material (line after name)."""
    lines = text.splitlines(keepends=True)
    n = 0
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("Material,"):
            name_line = lines[i + 1] if i + 1 < len(lines) else ""
            name = name_line.strip().split(",")[0].strip()
            if name == material_name:
                # Thickness is typically 2 lines after name (Roughness then Thickness)
                for j in range(i + 2, min(i + 6, len(lines))):
                    if "Thickness" in lines[j]:
                        m = re.match(r"^(\s*)([0-9.eE+-]+)(,\s*!-\s*Thickness[^\n]*\n?)$", lines[j])
                        if m:
                            new_t = float(m.group(2)) * factor
                            nl = "" if m.group(3).endswith("\n") else ("\n" if lines[j].endswith("\n") else "")
                            lines[j] = f"{m.group(1)}{new_t}{m.group(3)}{nl}"
                            n += 1
                        break
        i += 1
    return "".join(lines), n


def _mul_infil(text: str, mult: float) -> tuple[str, int]:
    text2, n = re.subn(
        r"([0-9.eE+-]+)(\s*,\s*!- Flow Rate per Exterior Surface Area)",
        lambda m: f"{float(m.group(1)) * mult:.6e}{m.group(2)}",
        text,
    )
    return text2, n


def _set_lights_w_m2(text: str, w_m2: float) -> tuple[str, int]:
    text2, n = re.subn(
        r"([0-9.]+)(,\s*!- Watts per Floor Area)",
        lambda m: f"{w_m2:.2f}{m.group(2)}",
        text,
    )
    return text2, n


def _set_boiler_eff(text: str, eff: float) -> tuple[str, int]:
    # First Nominal Thermal Efficiency under Boiler:HotWater
    text2, n = re.subn(
        r"(Boiler:HotWater,.*?Nominal Thermal Efficiency\n\s*)([0-9.]+)",
        lambda m: f"{m.group(1)}{eff:.3f}",
        text,
        count=1,
        flags=re.S,
    )
    if n == 0:
        text2, n = re.subn(
            r"(Boiler:HotWater,.*?\n\s*)([0-9.]+)(,\s*!- Nominal Thermal Efficiency)",
            lambda m: f"{m.group(1)}{eff:.3f}{m.group(3)}",
            text,
            count=1,
            flags=re.S,
        )
    return text2, n


def apply_vintage(
    src: Path,
    dst: Path,
    vintage: str,
    *,
    lights_w_m2: float | None = None,
    skip_lights: bool = False,
) -> dict:
    if vintage not in VINTAGE_5A:
        raise SystemExit(f"unknown vintage {vintage}; choose {list(VINTAGE_5A)}")
    cfg = VINTAGE_5A[vintage]
    text = src.read_text(encoding="utf-8", errors="replace")
    meta: dict = {
        "src": str(src),
        "dst": str(dst),
        "vintage": vintage,
        "label": cfg["label"],
        "climate": "5A_Chicago_proxy_for_Detroit",
        "note": "DOE Ref Bldg form identical across vintages; fabric/infil/LPD/boiler patched from 5A scorecard",
    }

    u_si = cfg["window_u_ip"] * IP_U_TO_SI
    text, n = _set_window(text, u_si, cfg["window_shgc"])
    meta["window_u_si"] = round(u_si, 5)
    meta["window_shgc"] = cfg["window_shgc"]
    meta["window_patches"] = n

    wall_factor = cfg["new_mass_wall_u_ip"] / cfg["mass_wall_u_ip"]
    text, n = _scale_insulation_thickness(text, "Mass NonRes Wall Insulation", wall_factor)
    meta["wall_thickness_factor"] = round(wall_factor, 4)
    meta["wall_patches"] = n

    roof_factor = cfg["new_roof_u_ip"] / cfg["roof_u_ip"]
    text, n = _scale_insulation_thickness(text, "IEAD NonRes Roof Insulation", roof_factor)
    meta["roof_thickness_factor"] = round(roof_factor, 4)
    meta["roof_patches"] = n

    text, n = _mul_infil(text, cfg["infil_vs_new"])
    meta["infil_mult"] = cfg["infil_vs_new"]
    meta["infil_patches"] = n

    if skip_lights:
        meta["lights_w_m2"] = None
        meta["lights_patches"] = 0
        meta["lights_note"] = "left unchanged (assume lighting retrofit)"
    else:
        lpd = cfg["lights_w_m2"] if lights_w_m2 is None else lights_w_m2
        text, n = _set_lights_w_m2(text, lpd)
        meta["lights_w_m2"] = lpd
        meta["lights_patches"] = n

    text, n = _set_boiler_eff(text, cfg["boiler_eff"])
    meta["boiler_eff"] = cfg["boiler_eff"]
    meta["boiler_patches"] = n

    bad = [
        k
        for k in ("window_patches", "wall_patches", "roof_patches", "infil_patches")
        if meta.get(k, 0) < 1
    ]
    if not skip_lights and meta.get("lights_patches", 0) < 1:
        bad.append("lights")
    if bad:
        raise RuntimeError(f"vintage patch misses: {bad}; meta={meta}")

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text)
    return meta


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--src", required=True)
    p.add_argument("--dst", required=True)
    p.add_argument("--vintage", choices=sorted(VINTAGE_5A), required=True)
    p.add_argument("--lights-w-m2", type=float, default=None)
    p.add_argument("--skip-lights", action="store_true")
    p.add_argument("--meta-out")
    args = p.parse_args()
    meta = apply_vintage(
        Path(args.src),
        Path(args.dst),
        args.vintage,
        lights_w_m2=args.lights_w_m2,
        skip_lights=args.skip_lights,
    )
    print(json.dumps(meta, indent=2))
    if args.meta_out:
        Path(args.meta_out).write_text(json.dumps(meta, indent=2) + "\n")


if __name__ == "__main__":
    main()
