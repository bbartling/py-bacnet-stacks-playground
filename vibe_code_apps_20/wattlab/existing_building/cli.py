"""CLI for the Existing Building Hypothesis Lab."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from .explore import run_explore_existing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Explore existing-building hypotheses")
    parser.add_argument("--config", required=True, help="YAML hypothesis-lab configuration")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="write plans without EnergyPlus")
    mode.add_argument("--live", action="store_true", help="run EnergyPlus scenarios")
    parser.add_argument("--out", default="wattlab_existing_building_output", help="artifact directory")
    args = parser.parse_args(argv)
    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    result = run_explore_existing(
        config,
        dry_run=not args.live,
        live=args.live,
        out_dir=args.out,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
