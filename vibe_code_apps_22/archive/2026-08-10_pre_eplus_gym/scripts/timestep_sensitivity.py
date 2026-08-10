#!/usr/bin/env python
"""Timestep sensitivity scaffold (4 / 6 / 12 zone steps per hour).

Writes reports/eplus/timestep_sensitivity.csv. Full E+ offline; CI --dry-run.
Can stage W2A Timestep patches via --stage-w2a without overwriting champion IDF.
IdealLoads farm remains STRUCTURAL_LOAD_DIAGNOSTIC; W2A_PHYSICAL_DSM is separate.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP), str(_APP / "scripts"), str(_APP / "ml")]
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
                "staged_idf": "",
                "note": "SCAFFOLD — run offline on IdealLoads diagnostic and/or W2A_PHYSICAL_DSM",
            }
        )
    return rows


def rows_with_w2a_stage(eval_day: str, out_dir: Path) -> list[dict]:
    from eplus_w2a_dsm_farm_scaffold import stage_w2a_idf

    rows = []
    for n in STEPS:
        staged = stage_w2a_idf(out_dir=out_dir, steps_per_hour=n)
        rows.append(
            {
                "eval_day": eval_day,
                "zone_timesteps_per_hour": n,
                "physics_family": "W2A_PHYSICAL_DSM",
                "daily_kwh": "",
                "peak_kw": "",
                "peak_step": "",
                "hvac_iter_warnings": "",
                "staged_idf": str(staged),
                "note": "Staged Timestep patch only — no E+ metrics until offline run",
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
    ap.add_argument("--stage-w2a", action="store_true", help="Write staged W2A IDF copies (no champion overwrite)")
    ap.add_argument("--out", type=Path, default=OUT_DEFAULT)
    ap.add_argument("--eval-day", default="2026-01-26")
    ap.add_argument(
        "--w2a-out-dir",
        type=Path,
        default=_APP / "ml" / "artifacts" / "w2a_dsm_scaffold",
    )
    args = ap.parse_args(argv)
    if args.stage_w2a:
        rows = rows_with_w2a_stage(args.eval_day, args.w2a_out_dir)
    else:
        rows = dry_rows(args.eval_day)
    write_csv(args.out, rows)
    print(f"wrote {args.out} n={len(rows)} (scaffold)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
