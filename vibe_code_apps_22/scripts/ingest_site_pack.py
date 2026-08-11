#!/usr/bin/env python
"""Ingest a site pack (zip or folder) and publish site_ui_bundle_v1.

Examples:
  python -u scripts/ingest_site_pack.py --src PATH\\site.zip
  python -u scripts/ingest_site_pack.py --src PATH\\pack_dir --dest %LAKESIDE_SITE_ROOT%
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eplus_gym_app.site_pack import SitePackError, ingest_site_pack, inventory_site_pack  # noqa: E402
from lakeside.paths import site_root  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, required=True, help="zip or folder site pack")
    ap.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="site root (default LAKESIDE_SITE_ROOT)",
    )
    ap.add_argument(
        "--inventory-only",
        action="store_true",
        help="print readiness checklist without copying",
    )
    args = ap.parse_args()

    src = Path(args.src)
    if args.inventory_only:
        root = src if src.is_dir() else src
        from eplus_gym_app.site_pack import extract_pack

        inv = inventory_site_pack(extract_pack(src) if src.is_file() else src)
        print(
            json.dumps(
                {
                    "fuel_ready": inv.fuel_ready,
                    "twin_ready": inv.twin_ready,
                    "actual_ready": inv.actual_ready,
                    "campus": str(inv.campus_json) if inv.campus_json else None,
                    "idf": str(inv.champion_idf) if inv.champion_idf else None,
                    "interval": str(inv.interval_csv) if inv.interval_csv else None,
                    "checklist": [
                        {
                            "key": i.key,
                            "status": i.status,
                            "note": i.note,
                            "path": str(i.path) if i.path else None,
                        }
                        for i in inv.checklist
                    ],
                },
                indent=2,
            )
        )
        return 0 if inv.fuel_ready else 2

    dest = Path(args.dest) if args.dest else site_root()
    os.environ.setdefault("LAKESIDE_SITE_ROOT", str(dest))
    try:
        inv = ingest_site_pack(src, dest)
    except SitePackError as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "dest": str(dest),
                "fuel_ready": inv.fuel_ready,
                "twin_ready": inv.twin_ready,
                "actual_ready": inv.actual_ready,
                "campus": str(inv.campus_json) if inv.campus_json else None,
                "idf": str(inv.champion_idf) if inv.champion_idf else None,
                "bundle": str(dest / "reports" / "site_ui_bundle_v1.json"),
                "checklist": [
                    {"key": i.key, "status": i.status, "note": i.note}
                    for i in inv.checklist
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
