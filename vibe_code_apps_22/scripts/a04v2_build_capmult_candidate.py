"""Build A04-v2 candidate IDFs with ZoneCapacitanceMultiplier:ResearchSpecial.

Does not modify the immutable A04 source. Stage-A one-factor trials.
"""
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
    CAPMULT_HI,
    CAPMULT_LO,
    assert_finite_in_range,
)

A04 = _APP / "models" / "eplus" / "lakeside_w2a_a04_dual_champion.idf"
A04_SHA = A04_SHA_CRLF

ZONE_NAMES = [
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inject_capacitance(src: str, temp_mult: float) -> str:
    if "ZoneCapacitanceMultiplier:ResearchSpecial" in src:
        raise ValueError("source already has ZoneCapacitanceMultiplier")
    blocks = []
    for z in ZONE_NAMES:
        blocks.append(
            "ZoneCapacitanceMultiplier:ResearchSpecial,\n"
            f"  CapMult_{z},           !- Name\n"
            f"  {z},                    !- Zone or ZoneList Name\n"
            f"  {temp_mult:.6g},                    !- Temperature Capacity Multiplier\n"
            "  1.0,                    !- Humidity Capacity Multiplier\n"
            "  1.0,                    !- Carbon Dioxide Capacity Multiplier\n"
            "  1.0;                    !- Generic Contaminant Capacity Multiplier\n"
        )
    header = (
        "\n!- ====== A04-v2 Stage A: ZoneCapacitanceMultiplier (temperature only) ======\n"
        f"!- Parent A04 SHA-256: {A04_SHA}\n"
        f"!- Temperature Capacity Multiplier: {temp_mult}\n"
        "!- Physical rationale: increase effective zone air capacitance so DualSP steps\n"
        "!- produce gradual zone-air response matching BAS 15-min deltas; not a setpoint ramp.\n"
    )
    # Append before end of file
    return src.rstrip() + "\n" + header + "\n".join(blocks) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--temp-mult", type=float, required=True)
    p.add_argument("--run-id", type=str, required=True)
    args = p.parse_args()
    temp_mult = assert_finite_in_range(args.temp_mult, lo=CAPMULT_LO, hi=CAPMULT_HI, name="temp-mult")
    raw = A04.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    lf = hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    if digest not in A04_SHA_ALLOWED and lf not in A04_SHA_ALLOWED:
        raise SystemExit("refusing to patch: A04 hash mismatch")
    text = raw.decode("utf-8", errors="replace")
    out_text = inject_capacitance(text, temp_mult)
    out_dir = _APP / "models" / "eplus" / "a04v2_candidates" / args.run_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_idf = out_dir / f"lakeside_w2a_a04v2_{args.run_id}.idf"
    data = out_text.encode("utf-8")
    out_idf.write_bytes(data)
    meta = {
        "schema": "vibe22.a04v2.candidate.v1",
        "run_id": args.run_id,
        "parent_model": "lakeside_w2a_a04_dual_champion.idf",
        "parent_sha256": A04_SHA,
        "idf": out_idf.name,
        "idf_sha256": sha256_bytes(data),
        "parameters": [
            {
                "name": "ZoneCapacitanceMultiplier:ResearchSpecial.Temperature_Capacity_Multiplier",
                "baseline": 1.0,
                "value": float(args.temp_mult),
                "lo": CAPMULT_LO,
                "hi": CAPMULT_HI,
                "units": "dimensionless",
                "affects": ["temperature_dynamics", "possibly_peak_timing"],
                "justification": (
                    "A04 has zero InternalMass and no capacitance multiplier; "
                    "evening DualSP step tracks ~5F in one 15-min step."
                ),
                "source": "EnergyPlus ZoneCapacitanceMultiplier:ResearchSpecial; Stage A one-factor trial",
            }
        ],
        "stage": "A_one_factor",
    }
    (out_dir / "parameters.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
