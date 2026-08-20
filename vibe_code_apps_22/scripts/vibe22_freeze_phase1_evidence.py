#!/usr/bin/env python3
"""Freeze Phase 1 date-use ledger + completed research-long audit (render-only)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.phase1_evidence_freeze import (  # noqa: E402
    build_phase1_evidence_freeze,
    write_phase1_evidence_freeze,
)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--research-long-run",
        type=Path,
        required=True,
        help="Site reports/eplus_gym/rl/research_long_* run root.",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=_APP / "docs" / "audits" / "figures" / "vibe22_mega_phase1" / "phase1_evidence_freeze.json",
        help="Repo-relative output JSON path.",
    )
    args = ap.parse_args(argv)
    if not args.research_long_run.is_dir():
        raise SystemExit(f"missing run root: {args.research_long_run}")

    body = build_phase1_evidence_freeze(research_long_run_root=args.research_long_run)
    write_phase1_evidence_freeze(args.out, body)
    print(json.dumps({"out": str(args.out), "freeze_sha256": body.get("freeze_sha256")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
