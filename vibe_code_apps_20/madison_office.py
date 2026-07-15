"""Madison conceptual office screening via OpenFDD WattLab easy button.

Thin wrapper so agents / humans have a named playbook entrypoint.

  python madison_office.py --dry-run
  python madison_office.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from config import ROOT
from easy_button import (
    DISCLAIMER,
    GL36_LIT,
    PRODUCT,
    plan_dry_run,
    run_easy_button,
    validate_against_literature,
)

PROFILE = ROOT / "examples" / "buildings" / "madison_office.json"
EVIDENCE = ROOT / "examples" / "evidence" / "madison_office_evidence.json"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=f"{PRODUCT} Madison office playbook")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--skip-ecm2", action="store_true")
    args = p.parse_args(argv)
    if not PROFILE.is_file():
        print(f"Missing profile: {PROFILE}", file=sys.stderr)
        return 2
    report = run_easy_button(PROFILE, skip_ecm2=args.skip_ecm2, dry_run=args.dry_run)
    if args.dry_run:
        report["evidence_path"] = str(EVIDENCE)
        report["disclaimer"] = DISCLAIMER
        report["literature"] = GL36_LIT
    print(json.dumps(report, indent=2))
    if args.dry_run:
        return 0
    records = report.get("result_records") or []
    return 0 if records and all(r.get("status") == "COMPLETE" for r in records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
