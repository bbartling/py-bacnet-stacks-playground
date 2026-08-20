"""Stage A: InternalMass furniture trials (no CapMult). Does not modify A04 source."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import (
    A04_SHA_ALLOWED,
    A04_SHA_CRLF,
    INTERNALMASS_HI,
    INTERNALMASS_LO,
    assert_finite_in_range,
)

A04 = _APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
A04_SHA = A04_SHA_CRLF
ZONES = [
    "1F_Library_IMC",
    "1F_Cafe_Kitchen",
    "1F_Gym",
    "1F_Area_A",
    "1F_Area_B",
    "1F_Area_C",
    "1F_Area_D",
    "2F_Area_A",
    "2F_Area_B",
]


def inject(src: str, area_m2: float) -> str:
    if "InternalMass," in src and "A04v2_Furniture" in src:
        raise ValueError("already patched")
    block = [
        "",
        "!- ====== A04-v2 Stage A: InternalMass furniture ======",
        f"!- Parent A04 SHA-256: {A04_SHA}",
        f"!- Furniture surface area per zone: {area_m2} m2",
        "!- Rationale: add thermal mass so DualSP steps yield gradual zone-air response.",
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
    for z in ZONES:
        block += [
            "INTERNALMASS,",
            f"  IM_{z},                   !- Name",
            "  A04v2_Furniture,           !- Construction Name",
            f"  {z},                      !- Zone or ZoneList Name",
            "  ,                          !- Space or SpaceList Name",
            f"  {area_m2:.4g};                  !- Surface Area {{m2}}",
        ]
    return src.rstrip() + "\n" + "\n".join(block) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--area-m2", type=float, required=True)
    p.add_argument("--run-id", required=True)
    args = p.parse_args()
    area = assert_finite_in_range(args.area_m2, lo=INTERNALMASS_LO, hi=INTERNALMASS_HI, name="area-m2")
    raw = A04.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    lf = hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    if digest not in A04_SHA_ALLOWED and lf not in A04_SHA_ALLOWED:
        raise SystemExit("A04 hash mismatch")
    out_dir = _APP / "models" / "eplus" / "a04v2_candidates" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    text = inject(raw.decode("utf-8", errors="replace"), area)
    out_idf = out_dir / f"lakeside_w2a_a04v2_{args.run_id}.idf"
    data = text.encode("utf-8")
    out_idf.write_bytes(data)
    meta = {
        "schema": "vibe22.a04v2.candidate.v1",
        "run_id": args.run_id,
        "parent_sha256": A04_SHA,
        "idf": out_idf.name,
        "idf_sha256": hashlib.sha256(data).hexdigest(),
        "stage": "A_one_factor",
        "parameters": [
            {
                "name": "InternalMass.Surface_Area_m2_per_zone",
                "baseline": 0.0,
                "value": float(args.area_m2),
                "lo": INTERNALMASS_LO,
                "hi": INTERNALMASS_HI,
                "units": "m2",
                "affects": ["temperature_dynamics", "possibly_peak"],
                "justification": "Explicit furniture mass; CapMult-alone inflates Jan peak past ±10% band.",
            }
        ],
    }
    (out_dir / "parameters.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
