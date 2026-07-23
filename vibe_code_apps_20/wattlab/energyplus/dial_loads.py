"""Dial zone lights / electric equipment / infiltration on an existing IDF.

Uses LBNL EnergyPlus-MCP ``EnergyPlusManager`` when importable; otherwise
auto-routes through ``wattlab mcp-exec`` (``energyplus-mcp-dev``). Run
``wattlab energyplus-ensure`` once per host so capability is ``ready``.

    wattlab dial-loads --src model.idf --dst dialed.idf --lights 4.5 --equip 4.2 --infil-mult 1.4
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


def _dial_local(
    src_idf: Path,
    dst_idf: Path,
    *,
    lights_w_per_m2: float,
    equip_w_per_m2: float,
    infil_mult: float | None,
    EnergyPlusManager: Any,
) -> dict[str, Any]:
    src_idf = Path(src_idf)
    dst_idf = Path(dst_idf)
    dst_idf.parent.mkdir(parents=True, exist_ok=True)
    ep = EnergyPlusManager()
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
                    "Watts_per_Floor_Area": float(lights_w_per_m2),
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
                    "Watts_per_Floor_Area": float(equip_w_per_m2),
                },
            }
        ],
        output_path=str(tmp),
    )
    r3 = None
    if infil_mult is not None and float(infil_mult) != 1.0:
        r3 = ep.change_infiltration_by_mult(
            str(tmp), float(infil_mult), output_path=str(tmp)
        )

    shutil.copy2(tmp, dst_idf)
    try:
        tmp.unlink()
    except OSError:
        pass
    return {
        "lights": str(r1)[:500],
        "equip": str(r2)[:500],
        "infil": None if r3 is None else str(r3)[:500],
        "lights_w_per_m2": float(lights_w_per_m2),
        "equip_w_per_m2": float(equip_w_per_m2),
        "infil_mult": None if infil_mult is None else float(infil_mult),
        "src": str(src_idf),
        "dst": str(dst_idf),
        "via": "local",
        "hint": "High elec + low gas ⇒ cut internal gains / raise infil — not more 5Zone schedule patches.",
    }


def dial_loads_mcp(
    src_idf: Path,
    dst_idf: Path,
    *,
    lights_w_per_m2: float,
    equip_w_per_m2: float,
    infil_mult: float | None = None,
) -> dict[str, Any]:
    """Apply Watts/Area lights+equip and optional infiltration multiplier via MCP."""
    try:
        from energyplus_mcp_server.energyplus_tools import EnergyPlusManager
    except ImportError:
        from wattlab.energyplus.mcp_runtime import dial_loads_via_docker

        return dial_loads_via_docker(
            Path(src_idf),
            Path(dst_idf),
            lights_w_per_m2=lights_w_per_m2,
            equip_w_per_m2=equip_w_per_m2,
            infil_mult=infil_mult,
        )

    return _dial_local(
        Path(src_idf),
        Path(dst_idf),
        lights_w_per_m2=lights_w_per_m2,
        equip_w_per_m2=equip_w_per_m2,
        infil_mult=infil_mult,
        EnergyPlusManager=EnergyPlusManager,
    )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="wattlab dial-loads",
        description="Dial lights/equip/infiltration via EnergyPlus MCP (any IDF).",
    )
    p.add_argument("--src", required=True)
    p.add_argument("--dst", required=True)
    p.add_argument("--lights", type=float, required=True, help="Lights W/m²")
    p.add_argument("--equip", type=float, required=True, help="Electric equipment W/m²")
    p.add_argument("--infil-mult", type=float, default=None)
    p.add_argument("--meta-out", default=None)
    args = p.parse_args(argv)
    meta = dial_loads_mcp(
        Path(args.src),
        Path(args.dst),
        lights_w_per_m2=args.lights,
        equip_w_per_m2=args.equip,
        infil_mult=args.infil_mult,
    )
    print(json.dumps(meta, indent=2))
    if args.meta_out:
        Path(args.meta_out).write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
