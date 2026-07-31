#!/usr/bin/env python3
"""Export Unity-friendly geometry + equipment manifest from BEST Twin IDF."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path("/data") if Path("/data/runs").is_dir() else Path.home() / "wattlab_workspace"
TWIN_ID = "geo_b100_dual_ahu_shape_ops11"
IDF = ROOT / "runs" / TWIN_ID / "model.idf"
OUT_DIR = ROOT / "reports" / "full_parity_july_demand"


def parse_objects(idf: str, obj_type: str):
    # IDF objects are often indented: "  Zone,\n    Name, ..."
    pat = re.compile(rf"(?im)^\s*{re.escape(obj_type)}\s*,(.*?);", re.S | re.M)
    for m in pat.finditer(idf):
        cleaned_lines = [line.split("!-")[0] for line in m.group(1).splitlines()]
        cleaned = " ".join(cleaned_lines)
        fields = [p.strip() for p in cleaned.split(",")]
        while fields and fields[-1] == "":
            fields.pop()
        yield fields


def main() -> int:
    if not IDF.is_file():
        print("missing", IDF, file=sys.stderr)
        return 2
    text = IDF.read_text(encoding="utf-8", errors="replace")

    zones = []
    for f in parse_objects(text, "Zone"):
        if not f:
            continue
        zones.append(
            {
                "name": f[0],
                "x": float(f[1]) if len(f) > 1 and f[1] else 0.0,
                "y": float(f[2]) if len(f) > 2 and f[2] else 0.0,
                "z": float(f[3]) if len(f) > 3 and f[3] else 0.0,
                "entity_id": f"zone_{f[0].lower()}",
            }
        )

    surfaces = []
    for f in parse_objects(text, "BuildingSurface:Detailed"):
        if len(f) < 12:
            continue
        name, stype, const, zone = f[0], f[1], f[2], f[3]
        # Fields: Name, Type, Const, Zone, Space, OutBC, OutBCObj, Sun, Wind, VFG, NVerts, then xyz...
        try:
            nverts = int(float(f[10]))
        except ValueError:
            nverts = 0
        coords = []
        for tok in f[11:]:
            try:
                coords.append(float(tok))
            except ValueError:
                continue
        verts = [
            {"x": coords[i], "y": coords[i + 1], "z": coords[i + 2]}
            for i in range(0, min(len(coords), nverts * 3 if nverts else len(coords)) - 2, 3)
        ]
        surfaces.append(
            {
                "name": name,
                "surface_type": stype,
                "construction": const,
                "zone": zone,
                "n_vertices": nverts,
                "vertices_m": verts,
                "entity_id": f"surf_{name.lower().replace(' ', '_')}",
            }
        )

    fen = []
    for f in parse_objects(text, "FenestrationSurface:Detailed"):
        if len(f) < 5:
            continue
        fen.append(
            {
                "name": f[0],
                "surface_type": f[1],
                "construction": f[2],
                "building_surface": f[3],
            }
        )

    airloops = [
        {"name": f[0], "entity_id": f"airloop_{f[0].lower().replace(' ', '_')}"}
        for f in parse_objects(text, "AirLoopHVAC")
        if f
    ]
    plant = [
        {"name": f[0], "entity_id": f"plant_{f[0].lower().replace(' ', '_')}"}
        for f in parse_objects(text, "PlantLoop")
        if f
    ]
    chillers = []
    seen_ch = set()
    for f in parse_objects(text, "Chiller:Electric:EIR"):
        if not f or f[0] in seen_ch:
            continue
        seen_ch.add(f[0])
        chillers.append(
            {"name": f[0], "entity_id": f"chiller_{f[0].lower().replace(' ', '_')}"}
        )

    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    for s in surfaces:
        for v in s["vertices_m"]:
            xs.append(v["x"])
            ys.append(v["y"])
            zs.append(v["z"])

    manifest = {
        "schema_version": "vibe21.unity_twin_manifest.v1",
        "purpose": "demand_management_digital_twin",
        "twin_run_id": TWIN_ID,
        "best_model": True,
        "g14": "PASS",
        "idf_path_in_package": "assets/twin_b100_ops11/model.idf",
        "epw_path_in_package": "assets/twin_b100_ops11/amy.epw",
        "units": {"geometry": "meters", "demand": "kW"},
        "bbox_m": {
            "dx": round(max(xs) - min(xs), 3) if xs else None,
            "dy": round(max(ys) - min(ys), 3) if ys else None,
            "dz": round(max(zs) - min(zs), 3) if zs else None,
            "xmin": round(min(xs), 3) if xs else None,
            "ymin": round(min(ys), 3) if ys else None,
            "zmin": round(min(zs), 3) if zs else None,
        },
        "zones": zones,
        "n_surfaces": len(surfaces),
        "surfaces": surfaces,
        "fenestration": fen,
        "hvac": {
            "airloops": airloops,
            "plant_loops": plant,
            "chillers": chillers,
            "dual_ahu": True,
        },
        "dm_strategies_seed": [
            "baseline",
            "setpoint_raise_p5f",
            "deadband_10f",
            "chiller_off",
            "hvac_off",
            "precool_shift",
            "precool_chiller_off",
        ],
        "unity_visual_modes": [
            "facility_kw_heatmap_by_hour",
            "zone_temp_vs_setpoint",
            "dr_window_overlay",
            "strategy_delta_kw",
            "precool_vs_relax_phase",
            "plant_avail_status",
        ],
        "notes": [
            "IDF BuildingSurface:Detailed vertices are the architectural massing source for Unity.",
            "Lumped Floor_N_AHU{1,2} zones — not room-level VAV geometry.",
            "Demand management ML targets hourly Electricity:Facility kW under OA + HVAC actions.",
        ],
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "unity_twin_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    slim_keys = (
        "schema_version",
        "purpose",
        "twin_run_id",
        "best_model",
        "bbox_m",
        "zones",
        "n_surfaces",
        "surfaces",
        "fenestration",
        "hvac",
        "dm_strategies_seed",
        "unity_visual_modes",
        "units",
        "notes",
    )
    slim = {k: manifest[k] for k in slim_keys}
    (OUT_DIR / "unity_geometry.json").write_text(json.dumps(slim, indent=2) + "\n")
    print(
        "zones",
        len(zones),
        "surfaces",
        len(surfaces),
        "fen",
        len(fen),
        "bbox",
        manifest["bbox_m"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
