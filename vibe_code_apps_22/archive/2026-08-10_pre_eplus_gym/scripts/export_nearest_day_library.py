#!/usr/bin/env python
"""Export nearest-day + E+ delta library for desktop (full_deployment only)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from nearest_day_delta_benchmark import build_library_from_frame  # noqa: E402
from run_provenance import make_run_id  # noqa: E402
from train_real_baseline_15min import load_real_baseline_frame  # noqa: E402
from training_profile import require_profile  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--profile",
        default=None,
        help="TrainingProfile mode (or set VIBE22_TRAINING_PROFILE). Desktop export needs full_deployment.",
    )
    ap.add_argument("--out-dir", type=Path, default=ROOT / "ml" / "artifacts")
    ap.add_argument("--desktop-dir", type=Path, default=ROOT / "desktop" / "artifacts")
    ap.add_argument("--strategy-id", default="stagger_preheat")
    args = ap.parse_args(argv)

    profile = require_profile(args.profile)
    run_id = make_run_id(prefix="nearest_day_lib")
    df = load_real_baseline_frame(profile=profile)
    out = build_library_from_frame(
        df,
        profile=profile,
        out_dir=args.out_dir,
        desktop_dir=args.desktop_dir if profile.allow_desktop_library_export else None,
        run_id=run_id,
        strategy_id=args.strategy_id,
    )
    print(
        json.dumps(
            {
                "run_id": run_id,
                "profile": profile.mode,
                "library_path": str(out.get("library_path")),
                "ood_threshold": out.get("ood_threshold"),
                "summary": out.get("summary"),
                "frozen_eval_n": (out.get("frozen_eval") or {}).get("n_evaluated_days"),
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
