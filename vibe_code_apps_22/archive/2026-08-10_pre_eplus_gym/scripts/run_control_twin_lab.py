#!/usr/bin/env python
"""Run Lakeside Control Twin Lab V1 (smoke or full_lab).

Stages A04 copies (never overwrites champion), fills spin-up/timestep/treatment
CSVs, trains SYNTHETIC_W2A_PROVENANCE plant-electric surrogate.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP / "ml"), str(_APP / "scripts"), str(_APP)]

from control_twin_lab.runner import run_lab  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--profile", choices=("smoke", "full_lab"), default="smoke")
    ap.add_argument("--eval-day", default="2026-01-26")
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=_APP / "ml" / "artifacts" / "w2a_dsm_lab",
    )
    ap.add_argument(
        "--reports-eplus",
        type=Path,
        default=_APP / "reports" / "eplus",
    )
    ap.add_argument(
        "--reports-ml",
        type=Path,
        default=_APP / "reports" / "ml",
    )
    ap.add_argument(
        "--include-prbs",
        action="store_true",
        help="Include farm-only PRBS arms (full_lab only; never desktop)",
    )
    args = ap.parse_args(argv)
    summary = run_lab(
        profile=args.profile,
        eval_day=args.eval_day,
        out_dir=args.out_dir,
        reports_eplus=args.reports_eplus,
        reports_ml=args.reports_ml,
        include_prbs=args.include_prbs,
    )
    print(
        f"Control Twin Lab profile={summary['profile']} cases={summary['n_cases']} "
        f"surr_mae_kw={summary.get('surrogate_holdout_mae_kw')} "
        f"provenance={summary['provenance']} promote={summary['promote']}"
    )
    for k, v in summary["artifacts"].items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
