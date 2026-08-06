#!/usr/bin/env python
"""CLI reproduction entry for sklearn hybrid tutorial training (A + B + optional promote).

Calls the same functions as lakeside_heating_dsm_sklearn.ipynb.
Requires VIBE22_ALLOW_CLI_TRAIN=1.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from notebook_gate import SKLEARN_NOTEBOOK, cli_train_allowed, refuse_cli_train  # noqa: E402
from run_provenance import make_run_id  # noqa: E402
from train_eplus_delta_15min import export_delta_artifacts, lean_train_delta, load_paired_and_build_delta  # noqa: E402
from train_real_baseline_15min import (  # noqa: E402
    export_real_baseline_artifacts,
    lean_bake_off,
    load_real_baseline_frame,
)


def main(argv: list[str] | None = None) -> int:
    if not cli_train_allowed():
        return refuse_cli_train("sklearn tutorial train A+B", notebook=SKLEARN_NOTEBOOK)

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-days", type=int, default=36)
    ap.add_argument("--winter-only", action="store_true", default=True)
    ap.add_argument("--out-dir", type=Path, default=ROOT / "ml" / "artifacts")
    ap.add_argument("--promote-smoke", action="store_true")
    args = ap.parse_args(argv)

    run_id = make_run_id(prefix="sklearn_tutorial")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("=== A: real baseline ===", flush=True)
    df = load_real_baseline_frame(winter_only=args.winter_only, max_days=args.max_days)
    a = lean_bake_off(df)
    a["run_id"] = run_id
    paths_a = export_real_baseline_artifacts(a, out)

    print("=== B: E+ delta ===", flush=True)
    delta, paired = load_paired_and_build_delta(out_dir=out)
    b = lean_train_delta(delta)
    b["run_id"] = run_id
    paths_b = export_delta_artifacts(b, out, paired_source=str(paired))

    promote_result = None
    if args.promote_smoke:
        os.environ["VIBE22_ALLOW_SMOKE_PROMOTE"] = "1"
        from promote_hybrid_ship import promote_hybrid

        promote_result = promote_hybrid(out, desktop_dir=ROOT / "desktop" / "artifacts")
    else:
        print("skip promote (pass --promote-smoke for underpowered watermark path)", flush=True)

    print(
        json.dumps(
            {
                "run_id": run_id,
                "champion_a": a.get("champion"),
                "champion_b": b.get("champion"),
                "card_a": str(paths_a["card"]),
                "card_b": str(paths_b["card"]),
                "promote": promote_result,
            },
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
