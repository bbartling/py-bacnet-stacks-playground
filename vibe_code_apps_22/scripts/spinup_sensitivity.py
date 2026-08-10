#!/usr/bin/env python
"""Spin-up / pre-roll sensitivity scaffold for DSM farm thermal history.

Writes reports/eplus/spinup_sensitivity.csv. Full EnergyPlus runs are offline;
CI uses --dry-run with synthetic rows. Short pre-roll is insufficient for GLHE
seasonal ground claims — see docs/audits/simulation_root_cause_audit.md.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP), str(_APP / "scripts"), str(_APP / "ml")]

PRE_ROLLS = (0, 3, 7, 14)
OUT_DEFAULT = _APP / "reports" / "eplus" / "spinup_sensitivity.csv"


def dry_rows(eval_day: str = "2026-01-26") -> list[dict]:
    """Synthetic scaffold rows — replace with real farm extracts offline."""
    rows = []
    for pre in PRE_ROLLS:
        rows.append(
            {
                "eval_day": eval_day,
                "pre_roll_days": pre,
                "daily_kwh": "",
                "peak_kw": "",
                "peak_step": "",
                "zone_mae_vs_pr7": "",
                "ewt_mean": "",
                "note": (
                    "SCAFFOLD — run eplus_heating_dsm_farm.py --pre-roll-days "
                    f"{pre} offline; GLHE seasonal history NOT captured by short pre-roll"
                ),
                "glhe_seasonal_ok": "false",
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
