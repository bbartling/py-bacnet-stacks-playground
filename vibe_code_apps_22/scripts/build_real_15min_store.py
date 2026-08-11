#!/usr/bin/env python
"""CLI: build real BAS 15-min feature store under site ml/artifacts/."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))
_ML = _APP / "archive" / "ml"
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from lakeside.paths import site_root  # noqa: E402
from real_store import build_real_15min_store  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", type=Path, default=None)
    args = ap.parse_args(argv)
    site = args.site or site_root()
    df, manifest = build_real_15min_store(site)
    print(f"rows={manifest['row_count']} days={manifest['day_count']}")
    print(f"parquet={manifest['paths']['parquet']}")
    print(df.head(3).to_string())
    # continuity sample
    c = df.groupby("day")["step_15"].count()
    print(f"steps/day min={c.min()} median={c.median()} max={c.max()}")
    for z in (
        "zone_temp_1F_A_f",
        "zone_temp_1F_B_f",
        "zone_temp_1F_C_f",
        "zone_temp_1F_D_f",
        "zone_temp_2F_A_f",
        "zone_temp_2F_B_f",
    ):
        print(f"  {z}: non-null={df[z].notna().sum()} mean={df[z].mean():.2f}")
    assert (df["provenance"] == "REAL_BAS_15MIN").all()
    print("DoD: 15-min store OK — no E+ rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
