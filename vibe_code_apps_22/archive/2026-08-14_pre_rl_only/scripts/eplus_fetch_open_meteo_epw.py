#!/usr/bin/env python
"""Agent tool: fetch Open-Meteo archive at site lat/lon and write an AMY EPW.

  python -u scripts/eplus_fetch_open_meteo_epw.py
  python -u scripts/eplus_fetch_open_meteo_epw.py --force
  python -u scripts/eplus_fetch_open_meteo_epw.py --start 2025-08-01 --end 2026-08-08

Does not download or invent TMY. Does not copy Chicago screening weather.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from lakeside.paths import site_root  # noqa: E402
from eplus_gym_app.open_meteo_epw import refresh_amy_epw  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", type=Path, default=None, help="LAKESIDE_SITE_ROOT (default: env/pin)")
    ap.add_argument("--start", default=None, help="UTC start YYYY-MM-DD (default: answers.json)")
    ap.add_argument("--end", default=None, help="UTC end YYYY-MM-DD (default: max(answers, archive lag))")
    ap.add_argument("--force", action="store_true", help="Fetch even if existing AMY is fresh")
    args = ap.parse_args(argv)

    site = Path(args.site) if args.site else site_root()
    meta = refresh_amy_epw(
        site,
        start=args.start,
        end=args.end,
        force=bool(args.force),
    )
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
