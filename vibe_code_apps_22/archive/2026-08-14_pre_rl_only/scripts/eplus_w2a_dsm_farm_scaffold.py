#!/usr/bin/env python
"""Scaffold a W2A_PHYSICAL_DSM farm seed from the A04 champion (no IDF overwrite).

Writes a staged IDF copy with extra Output:Variable lines for plant diagnostics.
Does NOT claim validated treatment effects. IdealLoads remains STRUCTURAL_LOAD_DIAGNOSTIC.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP), str(_APP / "archive" / "ml")]

from physics_families import (  # noqa: E402
    W2A_PHYSICAL_DSM,
    resolve_w2a_dsm_seed,
)

EXTRA_OUTPUTS = """
!- W2A_PHYSICAL_DSM scaffold outputs (do not treat as validated DSM twin)
Output:Variable,*,Site Outdoor Air Drybulb Temperature,Timestep;
Output:Variable,*,Site Outdoor Air Relative Humidity,Timestep;
Output:Variable,*,Site Diffuse Solar Radiation Rate per Area,Timestep;
Output:Variable,*,Pump Electricity Rate,Timestep;
Output:Variable,*,Fan Electricity Rate,Timestep;
Output:Variable,*,Heating Coil Electricity Rate,Timestep;
Output:Variable,*,Cooling Coil Electricity Rate,Timestep;
Output:Variable,*,Plant Supply Side Inlet Temperature,Timestep;
Output:Variable,*,Plant Supply Side Outlet Temperature,Timestep;
"""


def patch_timestep(text: str, steps_per_hour: int) -> str:
    if steps_per_hour not in (4, 6, 12):
        raise ValueError("steps_per_hour must be 4, 6, or 12")
    return re.sub(
        r"(Timestep\s*,\s*)\d+(\s*;)",
        rf"\g<1>{steps_per_hour}\2",
        text,
        count=1,
        flags=re.I,
    )


def stage_w2a_idf(*, out_dir: Path, steps_per_hour: int = 4) -> Path:
    seed = resolve_w2a_dsm_seed()
    text = seed.read_text(encoding="utf-8", errors="replace")
    text = patch_timestep(text, steps_per_hour)
    if "W2A_PHYSICAL_DSM scaffold outputs" not in text:
        text = text.rstrip() + "\n" + EXTRA_OUTPUTS
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"w2a_dsm_scaffold_ts{steps_per_hour}.idf"
    out.write_text(text, encoding="utf-8")
    meta = out_dir / "w2a_dsm_scaffold_meta.txt"
    meta.write_text(
        f"physics_family={W2A_PHYSICAL_DSM}\n"
        f"seed={seed}\n"
        f"staged={out}\n"
        f"note=NOT a validated treatment model; IdealLoads farm remains STRUCTURAL_LOAD_DIAGNOSTIC\n",
        encoding="utf-8",
    )
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=_APP / "archive" / "ml" / "artifacts" / "w2a_dsm_scaffold",
    )
    ap.add_argument("--steps-per-hour", type=int, default=4, choices=(4, 6, 12))
    args = ap.parse_args(argv)
    out = stage_w2a_idf(out_dir=args.out_dir, steps_per_hour=args.steps_per_hour)
    print(f"staged {out} physics_family={W2A_PHYSICAL_DSM}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
