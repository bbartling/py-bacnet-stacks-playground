#!/usr/bin/env python
"""Timestep sensitivity scaffold (4 / 6 / 12 zone steps per hour).

Writes reports/eplus/timestep_sensitivity.csv. Full E+ offline; CI --dry-run.
IdealLoads farm remains STRUCTURAL_LOAD_DIAGNOSTIC; W2A_PHYSICAL_DSM is separate.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
OUT_DEFAULT = _APP / "reports" / "eplus" / "timestep_sensitivity.csv"
STEPS = (4, 6, 12)


def dry_rows(eval_day: str = "2026-01-26") -> list[dict]:
    rows = []
    for n in STEPS:
        rows.append(
            {
                "eval_day": eval_day,
                "zone_timesteps_per_hour": n,
                "physics_family": "STRUCTURAL_LOAD_DIAGNOSTIC",
                "daily_kwh": "",
                "peak_kw": "",
                "peak_step": "",
                "hvac_iter_warnings": "",
                "note": "SCAFFOLD — run offline on IdealLoads diagnostic and/or W2A_PHYSICAL_DSM",
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--eval-day", default="2026-01-26")
    args = ap.parse_args(argv)
    rows = dry_rows(args.eval_day)
    write_csv(args.out, rows)
    print(f"wrote {args.out} n={len(rows)} (scaffold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
