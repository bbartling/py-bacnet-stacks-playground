#!/usr/bin/env python
"""Train one baseline arm (sklearn|torch × winter|allyear) into ml/artifacts/runs/<arm>/.

Designed to run as a subprocess from ``train_four_arms.py``.
Sets VIBE22_ALLOW_CLI_TRAIN=1 for this process.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

os.environ["VIBE22_ALLOW_CLI_TRAIN"] = "1"

from chrono_splits import build_split_manifest, write_manifest  # noqa: E402
from feature_compile_15min import matrix_xy_15min_multi  # noqa: E402
from run_provenance import make_run_id  # noqa: E402
from timing_utils import TimingReport, format_hms  # noqa: E402
from train_real_baseline_15min import (  # noqa: E402
    export_real_baseline_artifacts,
    lean_bake_off,
    load_real_baseline_frame,
)
from training_profile import require_profile  # noqa: E402

ARMS = ("sklearn_winter", "sklearn_allyear", "torch_winter", "torch_allyear")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--arm", required=True, choices=ARMS)
    ap.add_argument(
        "--profile",
        default=os.environ.get("VIBE22_TRAINING_PROFILE", "full_evaluation"),
        help="TrainingProfile mode (default full_evaluation; smoke caps days)",
    )
    ap.add_argument("--max-days", type=int, default=None, help="Override profile max_days")
    ap.add_argument("--lean-torch", action="store_true", default=True)
    ap.add_argument("--full-torch", action="store_true", help="5 seeds + GRU (slower)")
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument(
        "--runs-root",
        type=Path,
        default=ROOT / "ml" / "artifacts" / "runs",
    )
    return ap.parse_args(argv)


def _arm_config(arm: str) -> dict:
    family, season = arm.split("_", 1)
    return {
        "arm": arm,
        "family": family,  # sklearn | torch
        "winter_only": season == "winter",
        "season": season,
    }


def train_sklearn_arm(*, out: Path, winter_only: bool, max_days: int | None, profile) -> dict:
    from timing_utils import TimingReport

    timings = TimingReport()
    run_id = make_run_id(prefix=f"sklearn_{'winter' if winter_only else 'allyear'}")
    with timings.time("load_frame"):
        df = load_real_baseline_frame(
            winter_only=winter_only, max_days=max_days, profile=profile
        )
    with timings.time("split_manifest"):
        _, _, _, _, _, feat = matrix_xy_15min_multi(df)
        manifest = build_split_manifest(feat)
        write_manifest(out / "eval" / "split_manifest.json", manifest)
    with timings.time("lean_bake_off"):
        result = lean_bake_off(df, split_manifest=manifest, out_dir=out)
    result["run_id"] = run_id
    result["winter_only"] = winter_only
    result["arm_season"] = "winter" if winter_only else "allyear"
    with timings.time("export_artifacts"):
        paths = export_real_baseline_artifacts(result, out)
    timings.print_summary(f"sklearn {'winter' if winter_only else 'allyear'}")
    timings.write_json(
        out / "timing.json",
        extra={
            "arm": f"sklearn_{'winter' if winter_only else 'allyear'}",
            "run_id": run_id,
            "winter_only": winter_only,
            "n_rows": int(len(df)),
            "n_days": int(df["day"].nunique()),
            "champion": result.get("champion"),
            "card": str(paths["card"]),
        },
    )
    return {
        "run_id": run_id,
        "champion": result.get("champion"),
        "card": str(paths["card"]),
        "timing_hms": format_hms(timings.total_seconds()),
        "n_days": int(df["day"].nunique()),
    }


def train_torch_arm(
    *,
    out: Path,
    winter_only: bool,
    max_days: int | None,
    profile,
    lean: bool,
    epochs: int | None,
) -> dict:
    from train_real_baseline_torch_15min import (
        export_torch_baseline_artifacts,
        train_torch_baseline,
    )

    timings = TimingReport()
    with timings.time("load_frame"):
        df = load_real_baseline_frame(
            winter_only=winter_only, max_days=max_days, profile=profile
        )
    with timings.time("split_manifest"):
        _, _, _, _, _, feat = matrix_xy_15min_multi(df)
        manifest = build_split_manifest(feat)
        write_manifest(out / "eval" / "split_manifest.json", manifest)
    ep = epochs if epochs is not None else (25 if lean else 40)
    kwargs: dict = {"epochs": ep, "split_manifest": manifest}
    if lean:
        kwargs.update(families=["resmlp_dualhead"], seeds=[11], epochs=min(25, ep))
    with timings.time("train_torch_baseline"):
        result = train_torch_baseline(df, **kwargs)
    result["winter_only"] = winter_only
    result["arm_season"] = "winter" if winter_only else "allyear"
    with timings.time("export_artifacts"):
        paths = export_torch_baseline_artifacts(result, out)
    timings.print_summary(f"torch {'winter' if winter_only else 'allyear'}")
    timings.write_json(
        out / "timing.json",
        extra={
            "arm": f"torch_{'winter' if winter_only else 'allyear'}",
            "run_id": result.get("run_id"),
            "winter_only": winter_only,
            "n_rows": int(len(df)),
            "n_days": int(df["day"].nunique()),
            "family": result.get("family"),
            "card": str(paths["card"]),
        },
    )
    return {
        "run_id": result.get("run_id"),
        "family": result.get("family"),
        "card": str(paths["card"]),
        "timing_hms": format_hms(timings.total_seconds()),
        "n_days": int(df["day"].nunique()),
        "zone_mae": (result.get("cv_teacher_forced") or {}).get("zone_temp_mae_mean"),
    }


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    cfg = _arm_config(args.arm)
    profile = require_profile(args.profile)
    max_days = args.max_days if args.max_days is not None else profile.max_days
    lean = not args.full_torch

    out = Path(args.runs_root) / args.arm
    out.mkdir(parents=True, exist_ok=True)
    (out / "eval").mkdir(parents=True, exist_ok=True)
    log_path = out / "train.log"

    t0 = time.perf_counter()
    print(f"=== arm {args.arm} -> {out} ===", flush=True)
    print(
        f"profile={profile.mode} winter_only={cfg['winter_only']} max_days={max_days}",
        flush=True,
    )

    # Tee-ish: also append a one-line start marker to train.log
    log_path.write_text(
        f"START {args.arm} profile={profile.mode} winter_only={cfg['winter_only']} "
        f"max_days={max_days}\n",
        encoding="utf-8",
    )

    try:
        if cfg["family"] == "sklearn":
            summary = train_sklearn_arm(
                out=out,
                winter_only=cfg["winter_only"],
                max_days=max_days,
                profile=profile,
            )
        else:
            summary = train_torch_arm(
                out=out,
                winter_only=cfg["winter_only"],
                max_days=max_days,
                profile=profile,
                lean=lean,
                epochs=args.epochs,
            )
    except Exception as e:
        err = {"arm": args.arm, "ok": False, "error": f"{type(e).__name__}: {e}"}
        (out / "result.json").write_text(json.dumps(err, indent=2), encoding="utf-8")
        log_path.write_text(log_path.read_text(encoding="utf-8") + f"FAIL {e}\n", encoding="utf-8")
        print(f"FAIL {args.arm}: {e}", flush=True)
        raise

    wall = time.perf_counter() - t0
    doc = {
        "arm": args.arm,
        "ok": True,
        "wall_seconds": wall,
        "wall_hms": format_hms(wall),
        "winter_only": cfg["winter_only"],
        "profile": profile.mode,
        "max_days": max_days,
        "out_dir": str(out),
        **summary,
    }
    (out / "result.json").write_text(json.dumps(doc, indent=2, default=str), encoding="utf-8")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"OK wall={format_hms(wall)}\n")
    print(json.dumps(doc, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
