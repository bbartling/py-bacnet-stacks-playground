#!/usr/bin/env python3
"""End-to-end poll harness: scan → trim → poll → probe → export/plot.

All outputs use fixed paths and are overwritten each run:

    data/feather_store/telemetry.feather
    data/exports/poll_test.log
    data/exports/feather_tail.log
    data/exports/telemetry_long.csv
    data/exports/telemetry_latest.csv
    data/exports/telemetry_plot.png

Examples:
    python scripts/run_poll_harness.py              # full run
    python scripts/run_poll_harness.py --skip-scan  # trim + poll only
    python scripts/run_poll_harness.py --step trim
    python scripts/run_poll_harness.py --step poll --duration 120
"""

from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
import tomllib
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FEATHER_STORE = ROOT / "data/feather_store/telemetry.feather"
EXPORT_DIR = ROOT / "data/exports"
DEVICES_DIR = ROOT / "config/drivers/devices"
TRIM_PROFILE = ROOT / "config/drivers/trim_profile.toml"
BACNET_APP = ROOT / "target/release/bacnet_app"
FEATHER_TAIL = ROOT / "target/release/feather_tail"
BAS_SCAN = ROOT / "target/release/bas_scan"
READ_SCRIPT = ROOT / "scripts/read_feather_store.py"
TRIM_SCRIPT = ROOT / "scripts/trim_drivers.py"

POLL_LOG = EXPORT_DIR / "poll_test.log"
PROBE_LOG = EXPORT_DIR / "feather_tail.log"
CSV_LONG = EXPORT_DIR / "telemetry_long.csv"
CSV_LATEST = EXPORT_DIR / "telemetry_latest.csv"
PLOT_PNG = EXPORT_DIR / "telemetry_plot.png"

FIXED_EXPORTS = [POLL_LOG, PROBE_LOG, CSV_LONG, CSV_LATEST, PLOT_PNG]


def python_bin() -> str:
    venv = ROOT / ".venv/bin/python"
    if venv.is_file():
        return str(venv)
    return sys.executable


def run(cmd: list[str], *, cwd: Path = ROOT, log_file: Path | None = None) -> None:
    print(f"+ {' '.join(cmd)}")
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("w", encoding="utf-8") as fh:
            subprocess.run(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, check=True)
        return
    subprocess.run(cmd, cwd=cwd, check=True)


def pkill_bacnet() -> None:
    for pattern in ("./target/release/bacnet_app", "target/release/bacnet_app"):
        subprocess.run(["pkill", "-f", pattern], check=False)
    time.sleep(1)


def ensure_release_bins(*, build: bool) -> None:
    missing = [p for p in (BACNET_APP, FEATHER_TAIL, BAS_SCAN) if not p.is_file()]
    if not missing:
        return
    if not build:
        names = ", ".join(p.name for p in missing)
        raise SystemExit(f"missing release binaries: {names} (pass --build)")
    run(["cargo", "build", "--release", "--bin", "bacnet_app", "--bin", "feather_tail", "--bin", "bas_scan"])


def load_harness_profile() -> dict:
    data = tomllib.loads(TRIM_PROFILE.read_text(encoding="utf-8"))
    return data.get("harness", {})


def reset_outputs() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    FEATHER_STORE.parent.mkdir(parents=True, exist_ok=True)
    if FEATHER_STORE.is_file():
        FEATHER_STORE.unlink()
        print(f"reset {FEATHER_STORE}")
    for path in FIXED_EXPORTS:
        if path.is_file():
            path.unlink()


def step_scan(*, merge: bool) -> None:
    pkill_bacnet()
    args = [
        "cargo",
        "run",
        "--release",
        "--bin",
        "bas_scan",
        "--",
        "--low",
        "1",
        "--high",
        "4194302",
        "--on-bac0",
    ]
    if merge:
        args.append("--merge")
    else:
        args.append("--no-merge")
    run(args)


def step_trim() -> None:
    run([python_bin(), str(TRIM_SCRIPT), "--profile", str(TRIM_PROFILE)])


def run_feather_tail_once(timeout_secs: int = 12) -> int:
    """Run feather_tail briefly; return 0 if WEATHER PASS seen."""
    PROBE_LOG.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        ["timeout", str(timeout_secs), str(FEATHER_TAIL)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    out = (result.stdout or "") + (result.stderr or "")
    PROBE_LOG.write_text(out, encoding="utf-8")
    print(out, end="")
    passed = "WEATHER PASS" in out
    print(f"probe: {'PASS' if passed else 'FAIL'} → {PROBE_LOG}")
    return 0 if passed else 2


def step_poll(duration_secs: int, *, probe_at_end: bool = False) -> int:
    pkill_bacnet()
    reset_outputs()
    ensure_release_bins(build=False)

    with POLL_LOG.open("w", encoding="utf-8") as fh:
        proc = subprocess.Popen(
            [str(BACNET_APP)],
            cwd=ROOT,
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    print(f"bacnet_app pid={proc.pid} duration={duration_secs}s → {POLL_LOG}")
    rc = 0
    try:
        if probe_at_end and duration_secs > 15:
            time.sleep(max(0, duration_secs - 12))
            rc = run_feather_tail_once()
            time.sleep(12)
        else:
            time.sleep(duration_secs)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=5)
        pkill_bacnet()
    print("bacnet_app stopped")
    return rc


def step_probe(timeout_secs: int = 12) -> int:
    """Standalone probe: restart bacnet_app briefly (manual step)."""
    if not FEATHER_STORE.is_file():
        print(f"WARN: no feather store at {FEATHER_STORE}", file=sys.stderr)
        return 1

    pkill_bacnet()
    with POLL_LOG.open("a", encoding="utf-8") as fh:
        fh.write("\n--- probe-only bacnet_app restart ---\n")
        proc = subprocess.Popen(
            [str(BACNET_APP)],
            cwd=ROOT,
            stdout=fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    time.sleep(5)
    try:
        return run_feather_tail_once(timeout_secs=timeout_secs)
    finally:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        pkill_bacnet()


def step_export() -> int:
    if not READ_SCRIPT.is_file():
        raise SystemExit(f"missing {READ_SCRIPT}")
    if not FEATHER_STORE.is_file():
        print(f"WARN: no feather data at {FEATHER_STORE}", file=sys.stderr)
        return 1

    cmd = [
        python_bin(),
        str(READ_SCRIPT),
        "--store",
        str(FEATHER_STORE),
        "--export-dir",
        str(EXPORT_DIR),
        "--latest",
        "--by-device",
        "--plot",
        "--plot-out",
        str(PLOT_PNG),
        "--head",
        "12",
    ]
    run(cmd)
    return 0


def print_summary() -> None:
    print("\n=== harness outputs (fixed paths, overwritten each run) ===")
    for path in [FEATHER_STORE, *FIXED_EXPORTS]:
        if path.is_file():
            print(f"  {path}  ({path.stat().st_size} bytes)")
        else:
            print(f"  {path}  (missing)")


def main() -> int:
    harness = load_harness_profile()
    default_duration = int(harness.get("duration_secs", 300))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--step",
        choices=("all", "scan", "trim", "poll", "probe", "export"),
        default="all",
        help="run one step or the full pipeline (default: all)",
    )
    parser.add_argument("--skip-scan", action="store_true", help="skip bas_scan (all mode)")
    parser.add_argument("--build", action="store_true", help="cargo build --release first")
    parser.add_argument("--duration", type=int, default=default_duration)
    parser.add_argument("--no-merge", action="store_true", help="bas_scan without --merge")
    parser.add_argument("--dry-run", action="store_true", help="print plan only")
    args = parser.parse_args()

    if args.dry_run:
        print("plan:")
        print(f"  profile={TRIM_PROFILE}")
        print(f"  duration={args.duration}s")
        print(f"  feather={FEATHER_STORE}")
        print(f"  exports={EXPORT_DIR}")
        return 0

    if shutil.which("cargo") is None:
        raise SystemExit("cargo not found on PATH")

    ensure_release_bins(build=args.build)
    rc = 0

    steps = (
        ["scan", "trim", "poll", "export"]
        if args.step == "all"
        else [args.step]
    )

    for step in steps:
        print(f"\n--- step: {step} ---")
        if step == "scan":
            if args.step == "all" and args.skip_scan:
                print("skip scan (--skip-scan)")
                continue
            step_scan(merge=not args.no_merge)
        elif step == "trim":
            step_trim()
        elif step == "poll":
            probe_during = args.step == "all"
            rc = max(rc, step_poll(args.duration, probe_at_end=probe_during))
        elif step == "probe":
            rc = max(rc, step_probe())
        elif step == "export":
            rc = max(rc, step_export())

    if args.step in ("all", "export", "poll"):
        print_summary()

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"\nfinished {stamp} rc={rc}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
