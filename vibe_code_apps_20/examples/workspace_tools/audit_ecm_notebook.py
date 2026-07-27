#!/usr/bin/env python3
"""Audit ECM notebooks — validate sheets, charts, Twin honesty (workspace copy)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def audit_dir(nb_dir: Path) -> dict:
    from wattlab.notebooks.builder import validate_notebook

    rows = []
    for xlsx in sorted(nb_dir.glob("*.xlsx")):
        v = validate_notebook(xlsx)
        rows.append({"file": xlsx.name, **v})
    ok = all(r.get("ok") for r in rows)
    return {"ok": ok, "dir": str(nb_dir), "notebooks": rows}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dir", type=Path, default=Path("reports/notebooks"))
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    result = audit_dir(args.dir)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for row in result["notebooks"]:
            status = "PASS" if row.get("ok") else "FAIL"
            print(f"{status}  {row['file']}")
            for err in row.get("errors") or []:
                print(f"  ERROR: {err}")
            for warn in row.get("warnings") or []:
                print(f"  warn: {warn}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
