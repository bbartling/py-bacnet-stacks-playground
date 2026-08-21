"""Publish Vibe22 RL PoC results pack from finished research-long artifacts (no E+/train)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.rl.poc_result_figures import write_all_figures
from eplus_gym.rl.poc_results_publish import build_pack
from eplus_gym.rl.poc_slide_outline import write_slide_outline
from eplus_gym.site_env import require_site_root


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site-root", type=Path, default=None)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=_APP / "docs" / "results",
    )
    args = p.parse_args()
    site = require_site_root(args.site_root)
    out = Path(args.out_dir)
    pack = build_pack(site_root=site, out_dir=out)
    write_all_figures(
        primary=pack["primary"],
        secondary=pack["secondary"],
        out_dir=out / "figures",
    )
    write_slide_outline(
        out / "vibe22_rl_poc_10_slide_outline.md",
        summary=pack["summary"],
        primary=pack["primary"],
        secondary=pack["secondary"],
    )
    print(f"wrote pack under {out}", flush=True)
    print(
        "PRIMARY leader:",
        pack["summary"]["primary"]["validation_leader"],
        "SECONDARY leader:",
        pack["summary"]["secondary"]["validation_leader"],
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
