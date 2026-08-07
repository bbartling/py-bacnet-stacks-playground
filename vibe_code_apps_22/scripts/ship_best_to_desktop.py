#!/usr/bin/env python
"""Pick best sklearn arm from runs/, promote hybrid ship, launch desktop sim.

Usage (from vibe_code_apps_22)::

    python scripts/ship_best_to_desktop.py
    python scripts/ship_best_to_desktop.py --arm sklearn_winter   # force arm
    python scripts/ship_best_to_desktop.py --no-launch            # promote only

Selection (when --arm omitted): among ok sklearn_winter / sklearn_allyear,
lowest recursive peak MAE wins; winter wins ties. Torch never ships.

Copies winner baseline into ml/artifacts/ (keeps existing E+ delta), runs
promote_hybrid, then ``cargo run --release`` in desktop/ unless --no-launch.
Promote gate failure stops the script (does not launch).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ML = ROOT / "ml"
SCRIPTS = ROOT / "scripts"
RUNS = ML / "artifacts" / "runs"
ART = ML / "artifacts"
DESK = ROOT / "desktop" / "artifacts"
DESKTOP = ROOT / "desktop"

sys.path.insert(0, str(ML))
sys.path.insert(0, str(SCRIPTS))

os.environ.setdefault("VIBE22_ALLOW_CLI_TRAIN", "1")

SKLEARN_ARMS = ("sklearn_winter", "sklearn_allyear")
BASELINE_STEM = "real_baseline_15min_v1"
BASELINE_SUFFIXES = (".joblib", ".onnx", "_feature_meta.json", "_model_card.json")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def peak_mae_from_card(card: dict[str, Any]) -> float | None:
    """Recursive held-out peak MAE for the champion (lower is better)."""
    champ = card.get("champion")
    rec = card.get("cv_recursive_96_heldout") or {}
    if isinstance(rec, dict) and champ and isinstance(rec.get(champ), dict):
        block = rec[champ]
    elif isinstance(rec, dict):
        block = rec
    else:
        return None
    val = block.get("facility_kw_mae_peak_05_09")
    if val is None:
        tf = card.get("cv_teacher_forced") or {}
        if isinstance(tf, dict) and champ and isinstance(tf.get(champ), dict):
            val = tf[champ].get("facility_kw_mae_peak_05_09")
        elif isinstance(tf, dict):
            val = tf.get("facility_kw_mae_peak_05_09")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def score_arm(arm: str) -> dict[str, Any]:
    arm_dir = RUNS / arm
    result = _read_json(arm_dir / "result.json") or {}
    card = _read_json(arm_dir / f"{BASELINE_STEM}_model_card.json") or {}
    joblib = arm_dir / f"{BASELINE_STEM}.joblib"
    peak = peak_mae_from_card(card) if card else None
    ok = bool(result.get("ok")) and joblib.is_file() and peak is not None
    return {
        "arm": arm,
        "ok": ok,
        "peak_mae": peak,
        "champion": result.get("champion") or card.get("champion"),
        "winter_only": bool(result.get("winter_only", arm.endswith("_winter"))),
        "arm_dir": arm_dir,
        "result": result,
        "card": card,
    }


def pick_best_arm(*, force: str | None = None) -> dict[str, Any]:
    if force:
        if force not in SKLEARN_ARMS:
            raise SystemExit(f"--arm must be one of {SKLEARN_ARMS}, got {force!r}")
        scored = score_arm(force)
        if not scored["ok"]:
            raise SystemExit(
                f"arm {force} is not shippable (need ok result.json + joblib + peak MAE). "
                f"peak={scored['peak_mae']} dir={scored['arm_dir']}"
            )
        return scored

    candidates = [score_arm(a) for a in SKLEARN_ARMS]
    ok = [c for c in candidates if c["ok"]]
    if not ok:
        detail = ", ".join(
            f"{c['arm']}: ok={c['ok']} peak={c['peak_mae']}" for c in candidates
        )
        raise SystemExit(
            "No shippable sklearn arm under ml/artifacts/runs/. "
            f"Run train_four_arms first. ({detail})"
        )
    # lower peak MAE wins; winter preferred on tie
    ok.sort(key=lambda c: (float(c["peak_mae"]), 0 if c["winter_only"] else 1))
    return ok[0]


def copy_baseline_into_artifacts(arm_dir: Path) -> list[str]:
    """Overwrite ml/artifacts baseline stems from the winning arm."""
    ART.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for suf in BASELINE_SUFFIXES:
        src = arm_dir / f"{BASELINE_STEM}{suf}"
        if not src.is_file():
            if suf == ".joblib":
                raise FileNotFoundError(f"missing required {src}")
            continue
        dst = ART / src.name
        shutil.copy2(src, dst)
        copied.append(src.name)
    # Also copy eval recursive days if present (useful for desktop honesty UI)
    eval_src = arm_dir / "eval" / "baseline_recursive_days.json"
    if eval_src.is_file():
        eval_dst = ART / "eval" / "baseline_recursive_days.json"
        eval_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(eval_src, eval_dst)
        copied.append("eval/baseline_recursive_days.json")
    return copied


def launch_desktop() -> int:
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    print(f"Launching desktop: cargo run --release (cwd={DESKTOP})", flush=True)
    proc = subprocess.run(
        ["cargo", "run", "--release"],
        cwd=str(DESKTOP),
        env=env,
        check=False,
    )
    return int(proc.returncode)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", choices=SKLEARN_ARMS, default=None, help="Force this sklearn arm")
    ap.add_argument("--no-launch", action="store_true", help="Promote only; do not start cargo")
    ap.add_argument(
        "--artifacts",
        type=Path,
        default=ART,
        help="ml artifacts dir (baseline land + promote source)",
    )
    ap.add_argument("--desktop-artifacts", type=Path, default=DESK)
    args = ap.parse_args(argv)

    os.environ["VIBE22_ALLOW_CLI_TRAIN"] = "1"

    winner = pick_best_arm(force=args.arm)
    print(
        f"SELECTED {winner['arm']} champ={winner['champion']} "
        f"peak_mae={winner['peak_mae']:.3f}kW",
        flush=True,
    )

    delta_job = Path(args.artifacts) / "eplus_delta_15min_v1.joblib"
    if not delta_job.is_file():
        raise SystemExit(
            f"Missing {delta_job} — need an existing E+ delta train before hybrid promote."
        )

    copied = copy_baseline_into_artifacts(winner["arm_dir"])
    print(f"Copied baseline into {args.artifacts}: {', '.join(copied)}", flush=True)

    # Record selection for notebooks / audit
    selection = {
        "selected_arm": winner["arm"],
        "champion": winner["champion"],
        "peak_mae_kw": winner["peak_mae"],
        "winter_only": winner["winter_only"],
        "copied": copied,
    }
    (RUNS / "ship_selection.json").write_text(json.dumps(selection, indent=2), encoding="utf-8")

    from promote_hybrid_ship import promote_hybrid

    try:
        out = promote_hybrid(
            artifacts=Path(args.artifacts),
            desktop_artifacts=Path(args.desktop_artifacts),
        )
    except Exception as e:
        print(f"PROMOTE FAILED — not launching desktop: {type(e).__name__}: {e}", flush=True)
        return 2

    print(
        json.dumps(
            {
                "selection": selection,
                "walk": str(out["walk"]),
                "desktop": str(out["desktop"]),
                "summary": out.get("summary"),
            },
            indent=2,
            default=str,
        ),
        flush=True,
    )

    if args.no_launch:
        print("--no-launch: promote done; skip cargo", flush=True)
        return 0
    return launch_desktop()


if __name__ == "__main__":
    raise SystemExit(main())
