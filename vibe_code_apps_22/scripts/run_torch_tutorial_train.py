#!/usr/bin/env python
"""CLI reproduction entry for torch dual-head tutorial training.

Calls the same functions as lakeside_heating_dsm_torch.ipynb.
Requires VIBE22_ALLOW_CLI_TRAIN=1. Never overwrites desktop sklearn champion.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))

from feature_compile_15min import matrix_xy_15min_multi  # noqa: E402
from chrono_splits import build_split_manifest  # noqa: E402
from notebook_gate import TORCH_NOTEBOOK, cli_train_allowed, refuse_cli_train  # noqa: E402
from train_real_baseline_15min import load_real_baseline_frame  # noqa: E402
from train_real_baseline_torch_15min import (  # noqa: E402
    export_torch_baseline_artifacts,
    train_torch_baseline,
)


def main(argv: list[str] | None = None) -> int:
    if not cli_train_allowed():
        return refuse_cli_train("torch tutorial dual-head", notebook=TORCH_NOTEBOOK)

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-days", type=int, default=36)
    ap.add_argument("--winter-only", action="store_true", default=True)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--lean", action="store_true", help="1 seed / ResMLP only / fewer epochs")
    ap.add_argument("--out-dir", type=Path, default=ROOT / "ml" / "artifacts")
    args = ap.parse_args(argv)

    df = load_real_baseline_frame(winter_only=args.winter_only, max_days=args.max_days)
    _, _, _, _, _, feat = matrix_xy_15min_multi(df)
    manifest = build_split_manifest(feat)
    kwargs = {"epochs": args.epochs, "split_manifest": manifest}
    if args.lean:
        kwargs.update(families=["resmlp_dualhead"], seeds=[11], epochs=min(25, args.epochs))
    result = train_torch_baseline(df, **kwargs)
    paths = export_torch_baseline_artifacts(result, args.out_dir)
    print(
        json.dumps(
            {
                "run_id": result["run_id"],
                "family": result["family"],
                "zone_mae": result["cv_teacher_forced"].get("zone_temp_mae_mean"),
                "card": str(paths["card"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
