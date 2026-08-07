#!/usr/bin/env python
"""Launch four baseline train arms in parallel (sklearn/torch × winter/allyear).

Usage (from vibe_code_apps_22)::

    python scripts/train_four_arms.py
    python scripts/train_four_arms.py --profile smoke          # fast debug
    python scripts/train_four_arms.py --profile full_evaluation
    python scripts/train_four_arms.py --arms sklearn_winter torch_winter
    python scripts/train_four_arms.py --profile full_evaluation --ship-desktop

Each arm writes under ``ml/artifacts/runs/<arm>/`` (cards, timing.json, result.json).
When all finish, writes ``ml/artifacts/runs/index.json`` for notebook viewers.

Does not train inside Jupyter — open the slim sklearn/torch notebooks afterward
to compare timings and metrics.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRAIN_ARM = ROOT / "scripts" / "train_arm.py"
RUNS = ROOT / "ml" / "artifacts" / "runs"
ALL_ARMS = ("sklearn_winter", "sklearn_allyear", "torch_winter", "torch_allyear")

# Serialize interleaved arm lines so Windows consoles stay readable.
_PRINT_LOCK = threading.Lock()


def _safe_print(msg: str) -> None:
    """Print one line; drop chars the console codec cannot encode."""
    with _PRINT_LOCK:
        try:
            print(msg, flush=True)
        except UnicodeEncodeError:
            enc = getattr(sys.stdout, "encoding", None) or "utf-8"
            print(msg.encode(enc, errors="replace").decode(enc, errors="replace"), flush=True)


def _stream_worker(arm: str, stream, logf) -> None:
    """Tee subprocess stdout -> launcher.log and console with [arm] prefix."""
    for raw in iter(stream.readline, ""):
        if raw == "":
            break
        line = raw.rstrip("\n").rstrip("\r")
        logf.write(raw if raw.endswith("\n") else raw + "\n")
        logf.flush()
        if line.strip():
            _safe_print(f"[{arm}] {line}")
    stream.close()


def _arm_summary_bits(out_dir: Path, result: dict | None) -> str:
    """One-line champion / peak MAE snippet for the DONE banner."""
    bits: list[str] = []
    if result:
        champ = result.get("champion") or result.get("family")
        if champ:
            bits.append(f"champ={champ}")
        if result.get("timing_hms"):
            bits.append(f"train={result['timing_hms']}")
        if result.get("n_days") is not None:
            bits.append(f"days={result['n_days']}")
    # Prefer recursive peak MAE from model card when present.
    for name in (
        "real_baseline_15min_v1_model_card.json",
        "real_baseline_15min_torch_v1_model_card.json",
    ):
        card_path = out_dir / name
        if not card_path.is_file():
            continue
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            break
        champ = card.get("champion") or card.get("family") or (result or {}).get("champion")
        rec = card.get("cv_recursive_96_heldout") or {}
        block = rec.get(champ) if isinstance(rec, dict) and champ in rec else rec
        if isinstance(block, dict):
            peak = block.get("facility_kw_mae_peak_05_09")
            zone = block.get("zone_temp_mae_mean")
            if peak is not None:
                bits.append(f"peak_mae={peak:.2f}kW")
            if zone is not None:
                bits.append(f"zone_mae={zone:.2f}F")
        break
    return " | ".join(bits) if bits else ""


def _run_one(arm: str, *, profile: str, max_days: int | None, full_torch: bool, epochs: int | None) -> dict:
    out_dir = RUNS / arm
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "launcher.log"
    cmd = [
        sys.executable,
        "-u",
        str(TRAIN_ARM),
        "--arm",
        arm,
        "--profile",
        profile,
        "--runs-root",
        str(RUNS),
    ]
    if max_days is not None:
        cmd.extend(["--max-days", str(max_days)])
    if full_torch:
        cmd.append("--full-torch")
    if epochs is not None:
        cmd.extend(["--epochs", str(epochs)])

    env = os.environ.copy()
    env["VIBE22_ALLOW_CLI_TRAIN"] = "1"
    env["VIBE22_TRAINING_PROFILE"] = profile
    env["PYTHONUNBUFFERED"] = "1"
    # Windows consoles often use cp1252; keep worker logs ASCII-safe.
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "ml"), str(ROOT / "scripts"), str(ROOT), env.get("PYTHONPATH", "")]
    )

    _safe_print(f"[launch] {arm}")
    t0 = time.perf_counter()
    with log_path.open("w", encoding="utf-8", errors="replace") as logf:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        assert proc.stdout is not None
        reader = threading.Thread(target=_stream_worker, args=(arm, proc.stdout, logf), daemon=True)
        reader.start()
        rc = proc.wait()
        reader.join(timeout=30)

    wall = time.perf_counter() - t0
    result_path = out_dir / "result.json"
    payload: dict = {
        "arm": arm,
        "returncode": rc,
        "launcher_wall_seconds": wall,
        "log": str(log_path),
    }
    if result_path.is_file():
        try:
            payload["result"] = json.loads(result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            payload["result"] = None
    payload["ok"] = rc == 0 and bool((payload.get("result") or {}).get("ok", False))
    status = "OK" if payload["ok"] else "FAIL"
    extra = _arm_summary_bits(out_dir, payload.get("result"))
    suffix = f" | {extra}" if extra else ""
    _safe_print(f"[{status}] {arm} done in {wall:.1f}s{suffix}")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument(
        "--profile",
        default=os.environ.get("VIBE22_TRAINING_PROFILE", "full_evaluation"),
        help="smoke | full_evaluation | full_deployment",
    )
    ap.add_argument("--max-days", type=int, default=None)
    ap.add_argument("--arms", nargs="+", choices=ALL_ARMS, default=list(ALL_ARMS))
    ap.add_argument("--jobs", type=int, default=4, help="Max parallel subprocesses")
    ap.add_argument("--full-torch", action="store_true")
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument(
        "--ship-desktop",
        action="store_true",
        help="After all arms succeed, run ship_best_to_desktop (promote + cargo run)",
    )
    ap.add_argument(
        "--ship-no-launch",
        action="store_true",
        help="With --ship-desktop: promote only, do not start cargo",
    )
    args = ap.parse_args(argv)

    RUNS.mkdir(parents=True, exist_ok=True)
    arms = list(args.arms)
    _safe_print(f"Training {len(arms)} arms in parallel (jobs={args.jobs}, profile={args.profile})")
    _safe_print("Arms: " + ", ".join(arms))
    _safe_print("Live logs stream as [arm] lines; full copies under ml/artifacts/runs/<arm>/launcher.log")

    t0 = time.perf_counter()
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, min(args.jobs, len(arms)))) as pool:
        futs = {
            pool.submit(
                _run_one,
                arm,
                profile=args.profile,
                max_days=args.max_days,
                full_torch=args.full_torch,
                epochs=args.epochs,
            ): arm
            for arm in arms
        }
        for fut in as_completed(futs):
            results.append(fut.result())

    wall = time.perf_counter() - t0
    results.sort(key=lambda r: r["arm"])
    index = {
        "profile": args.profile,
        "max_days": args.max_days,
        "arms": arms,
        "wall_seconds": wall,
        "results": results,
        "ok_count": sum(1 for r in results if r.get("ok")),
        "fail_count": sum(1 for r in results if not r.get("ok")),
        "viewer_notebooks": [
            "notebooks/lakeside_heating_dsm_sklearn.ipynb",
            "notebooks/lakeside_heating_dsm_torch.ipynb",
        ],
    }
    index_path = RUNS / "index.json"
    index_path.write_text(json.dumps(index, indent=2, default=str), encoding="utf-8")
    _safe_print("")
    _safe_print("=== four-arm summary ===")
    for r in results:
        tag = "OK" if r.get("ok") else "FAIL"
        bits = _arm_summary_bits(RUNS / r["arm"], r.get("result"))
        _safe_print(f"  [{tag}] {r['arm']}: {bits or '(no metrics yet)'}")
    _safe_print(
        f"wall={wall:.1f}s ok={index['ok_count']} fail={index['fail_count']} index={index_path}"
    )

    if index["fail_count"] != 0:
        if args.ship_desktop:
            _safe_print("skip --ship-desktop: one or more arms failed")
        return 1

    if args.ship_desktop:
        # Ship selection needs both sklearn arms present/ok (torch optional).
        from ship_best_to_desktop import SKLEARN_ARMS, score_arm

        missing = []
        for arm in SKLEARN_ARMS:
            if arm not in arms:
                missing.append(f"{arm} (not in --arms)")
                continue
            scored = score_arm(arm)
            if not scored["ok"]:
                missing.append(f"{arm} (not shippable: peak={scored['peak_mae']})")
        if missing:
            _safe_print(
                "refuse --ship-desktop: both sklearn arms must be present and ok; "
                + "; ".join(missing)
            )
            return 2
        ship_cmd = [sys.executable, "-u", str(ROOT / "scripts" / "ship_best_to_desktop.py")]
        if args.ship_no_launch:
            ship_cmd.append("--no-launch")
        _safe_print(f"=== ship desktop === {' '.join(ship_cmd)}")
        ship_rc = subprocess.run(ship_cmd, cwd=str(ROOT), check=False).returncode
        return int(ship_rc)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
