#!/usr/bin/env python3
"""Dial Liberty B100 internal gains via EnergyPlus MCP, then sim + score.

Uses LBNL EnergyPlus-MCP inside energyplus-mcp-dev (modify_lights /
modify_electric_equipment / optional change_infiltration_by_mult).
Simulate via WattLab DinD (run from vibe20 host with docker.sock).

Run inside energyplus-mcp-dev for the MCP patch step only; sim is separate.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def mcp_dial(
    src_idf: Path,
    dst_idf: Path,
    *,
    lights_w_per_m2: float,
    equip_w_per_m2: float,
    infil_mult: float | None,
) -> dict:
    from energyplus_mcp_server.energyplus_tools import EnergyPlusManager

    ep = EnergyPlusManager()
    # MCP writes _modified if output_path quirks; we always copy to dst after
    tmp = dst_idf.with_name(dst_idf.stem + "_mcp_tmp.idf")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(src_idf, tmp)

    r1 = ep.modify_lights(
        str(tmp),
        [
            {
                "target": "all",
                "field_updates": {
                    "Design_Level_Calculation_Method": "Watts/Area",
                    "Watts_per_Floor_Area": lights_w_per_m2,
                },
            }
        ],
        output_path=str(tmp),
    )
    r2 = ep.modify_electric_equipment(
        str(tmp),
        [
            {
                "target": "all",
                "field_updates": {
                    "Design_Level_Calculation_Method": "Watts/Area",
                    "Watts_per_Floor_Area": equip_w_per_m2,
                },
            }
        ],
        output_path=str(tmp),
    )
    r3 = None
    if infil_mult is not None and infil_mult != 1.0:
        r3 = ep.change_infiltration_by_mult(
            str(tmp), infil_mult, output_path=str(tmp)
        )

    shutil.copy2(tmp, dst_idf)
    return {
        "lights": str(r1)[:500],
        "equip": str(r2)[:500],
        "infil": None if r3 is None else str(r3)[:500],
        "lights_w_per_m2": lights_w_per_m2,
        "equip_w_per_m2": equip_w_per_m2,
        "infil_mult": infil_mult,
        "dst": str(dst_idf),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--src", required=True)
    p.add_argument("--dst", required=True)
    p.add_argument("--lights", type=float, default=7.0, help="W/m2")
    p.add_argument("--equip", type=float, default=6.5, help="W/m2")
    p.add_argument("--infil-mult", type=float, default=None)
    p.add_argument("--meta-out")
    args = p.parse_args()
    meta = mcp_dial(
        Path(args.src),
        Path(args.dst),
        lights_w_per_m2=args.lights,
        equip_w_per_m2=args.equip,
        infil_mult=args.infil_mult,
    )
    print(json.dumps(meta, indent=2))
    if args.meta_out:
        Path(args.meta_out).write_text(json.dumps(meta, indent=2) + "\n")


if __name__ == "__main__":
    main()
