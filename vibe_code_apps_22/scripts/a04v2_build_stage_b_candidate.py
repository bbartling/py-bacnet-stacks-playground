"""Build A04-v2 child IDFs with corrected W2A heating capacity/airflow. Never overwrite A04."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from a04v2_w2a_plant_inventory import HP_COUNT_67, W_PER_HP_3TON, CFM_PER_TON, CFM_TO_M3S
from eplus_gym.a04_identity import A04_IDF_NAME, A04_SHA_ALLOWED, A04_SHA_LF, A04_SHA_CRLF
from eplus_gym.idf_objects import find_named_object, iter_objects, normalize_idf, replace_comment_field
from eplus_native.idf_inspect import NINE_ZONES

HTG_TYPE = "Coil:Heating:WaterToAirHeatPump:EquationFit"

A04 = _APP / "models" / "eplus" / A04_IDF_NAME


def _assert_a04(raw: bytes) -> None:
    d = hashlib.sha256(raw).hexdigest()
    lf = hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    if d not in A04_SHA_ALLOWED and lf != A04_SHA_LF:
        raise SystemExit("refusing to patch: A04 hash mismatch")


def patch_autosize_heating(src: str) -> str:
    """Autosize heating capacity together with already-autosized airflow. Does not touch A04 on disk."""
    out = normalize_idf(src)
    coils = iter_objects(out, HTG_TYPE)
    if len(coils) != 9:
        raise SystemExit(f"expected 9 heating coils, found {len(coils)}")
    for block in coils:
        new_block = replace_comment_field(block, "Rated Heating Capacity", "Autosize")
        out = out.replace(block, new_block, 1)
    return out


def patch_hp_scaled(src: str) -> str:
    """Scale rated heating capacity and airflow by 67-HP split × 3 ton × 400 cfm/ton."""
    out = normalize_idf(src)
    for z in NINE_ZONES:
        name = f"{z} WAHP Heating Coil"
        block = find_named_object(out, HTG_TYPE, name)
        if not block:
            raise SystemExit(f"failed to patch heating coil for {z}")
        n = HP_COUNT_67[z]
        cap = n * W_PER_HP_3TON
        flow = n * 3.0 * CFM_PER_TON * CFM_TO_M3S
        new_block = replace_comment_field(block, "Rated Air Flow Rate", f"{flow:.6g}")
        new_block = replace_comment_field(new_block, "Rated Heating Capacity", f"{cap:.6g}")
        out = out.replace(block, new_block, 1)
    return out


def inject_capmult(src: str, temp_mult: float) -> str:
    if temp_mult == 1.0:
        return src
    if "ZoneCapacitanceMultiplier:ResearchSpecial" in src:
        raise ValueError("already has CapMult")
    blocks = []
    for z in NINE_ZONES:
        blocks.append(
            "ZoneCapacitanceMultiplier:ResearchSpecial,\n"
            f"  CapMult_{z},           !- Name\n"
            f"  {z},                    !- Zone or ZoneList Name\n"
            f"  {temp_mult:.6g},                    !- Temperature Capacity Multiplier\n"
            "  1.0,                    !- Humidity Capacity Multiplier\n"
            "  1.0,                    !- Carbon Dioxide Capacity Multiplier\n"
            "  1.0;                    !- Generic Contaminant Capacity Multiplier\n"
        )
    return src.rstrip() + "\n\n" + "\n".join(blocks) + "\n"


def inject_internalmass(src: str, area_m2: float) -> str:
    if area_m2 <= 0:
        return src
    if "A04v2_Furniture" in src:
        raise ValueError("already has InternalMass furniture")
    block = [
        "MATERIAL,",
        "  Mat_Furniture,             !- Name",
        "  MediumSmooth,              !- Roughness",
        "  0.05,                      !- Thickness {m}",
        "  0.15,                      !- Conductivity {W/m-K}",
        "  600,                       !- Density {kg/m3}",
        "  1200,                      !- Specific Heat {J/kg-K}",
        "  0.9, 0.7, 0.7;",
        "CONSTRUCTION,",
        "  A04v2_Furniture,           !- Name",
        "  Mat_Furniture;             !- Outside Layer",
    ]
    for z in NINE_ZONES:
        block += [
            "INTERNALMASS,",
            f"  IM_{z},                   !- Name",
            "  A04v2_Furniture,           !- Construction Name",
            f"  {z},                      !- Zone or ZoneList Name",
            "  ,                          !- Space Name",
            f"  {area_m2:.6g};            !- Surface Area {{m2}}",
        ]
    return src.rstrip() + "\n" + "\n".join(block) + "\n"


def build_child(*, plant: str, capmult: float, mass_m2: float, run_id: str) -> dict:
    if run_id in {A04_IDF_NAME, Path(A04_IDF_NAME).stem, f"staged_{A04_IDF_NAME}"}:
        raise SystemExit("refusing to overwrite A04")
    raw = A04.read_bytes()
    _assert_a04(raw)
    text = raw.decode("utf-8", errors="replace")
    if plant == "autosize_htg":
        text = patch_autosize_heating(text)
    elif plant == "hp_scaled_3ton":
        text = patch_hp_scaled(text)
    elif plant == "a04_capacity":
        pass
    else:
        raise SystemExit(f"unknown plant {plant}")
    text = inject_capmult(text, float(capmult))
    text = inject_internalmass(text, float(mass_m2))
    out_dir = _APP / "models" / "eplus" / "a04v2_candidates" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_idf = out_dir / f"lakeside_w2a_a04v2_{run_id}.idf"
    if out_idf.name == A04_IDF_NAME:
        raise SystemExit("refusing to write A04 filename")
    data = text.encode("utf-8")
    out_idf.write_bytes(data)
    meta = {
        "schema": "vibe22.a04v2.candidate.v1",
        "run_id": run_id,
        "parent_model": A04_IDF_NAME,
        "parent_sha256": A04_SHA_CRLF,
        "idf": out_idf.name,
        "idf_sha256": hashlib.sha256(data).hexdigest(),
        "stage": "B_multivariable",
        "parameters": {
            "plant": plant,
            "capmult": float(capmult),
            "internalmass_m2": float(mass_m2),
        },
    }
    (out_dir / "parameters.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--plant", required=True, choices=("autosize_htg", "hp_scaled_3ton", "a04_capacity"))
    p.add_argument("--capmult", type=float, default=1.0)
    p.add_argument("--mass-m2", type=float, default=0.0)
    p.add_argument("--run-id", required=True)
    args = p.parse_args()
    if args.capmult < 1.0 or args.capmult > 20.0:
        raise SystemExit("capmult Stage B bound is [1, 20]; 28 is diagnostic-only")
    if args.mass_m2 < 0 or args.mass_m2 > 5000:
        raise SystemExit("mass-m2 out of range")
    meta = build_child(plant=args.plant, capmult=args.capmult, mass_m2=args.mass_m2, run_id=args.run_id)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
