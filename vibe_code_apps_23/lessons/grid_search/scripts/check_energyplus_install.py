"""Day 00 / Day 03 helper — verify EnergyPlus is installed and runnable locally.

No network, no BACnet. Prints a clear PASS/FAIL checklist for students.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_ROOT = Path(os.environ.get("ENERGYPLUS_ROOT", r"C:\EnergyPlusV26-1-0"))
WEATHER_REL = Path("WeatherData") / "USA_IL_Chicago-OHare.Intl.AP.725300_TMY3.epw"
EXAMPLE_REL = Path("ExampleFiles") / "1ZoneUncontrolled.idf"


def find_exe(root: Path) -> Path | None:
    for name in ("energyplus.exe", "energyplus"):
        candidate = root / name
        if candidate.is_file():
            return candidate
    which = shutil.which("energyplus") or shutil.which("energyplus.exe")
    return Path(which) if which else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_ROOT,
        help="EnergyPlus install root (or set ENERGYPLUS_ROOT)",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write a machine-readable checklist",
    )
    args = parser.parse_args()

    root = args.root
    exe = find_exe(root)
    weather = root / WEATHER_REL
    example = root / EXAMPLE_REL

    checks = [
        ("install_root_exists", root.is_dir(), str(root)),
        ("energyplus_executable", exe is not None and exe.is_file(), str(exe) if exe else "missing"),
        ("chicago_tmy3_epw", weather.is_file(), str(weather)),
        ("example_1zone_idf", example.is_file(), str(example)),
    ]

    version_line = None
    version_ok = False
    if exe is not None:
        try:
            proc = subprocess.run(
                [str(exe), "--version"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30,
            )
            version_line = (proc.stdout or proc.stderr or "").strip().splitlines()
            version_line = version_line[0] if version_line else f"exit={proc.returncode}"
            version_ok = proc.returncode == 0 and "EnergyPlus" in version_line
        except (OSError, subprocess.TimeoutExpired) as exc:
            version_line = str(exc)
            version_ok = False
    checks.append(("energyplus_version_runs", version_ok, version_line or "not run"))

    print("ENERGYPLUS LOCAL INSTALL CHECK")
    print("=" * 60)
    print(f"ENERGYPLUS_ROOT / --root: {root}")
    print()
    failed = 0
    for name, ok, detail in checks:
        mark = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print(f"  [{mark}] {name}")
        print(f"         {detail}")
    print()
    if failed:
        print("RESULT: FAIL — install EnergyPlus 26.1 (or set ENERGYPLUS_ROOT) before Days 03–10.")
        print("Hint: https://energyplus.net/downloads")
        print("Also: from vibe_code_apps_23 run  vibe23 energyplus-doctor --out reports/runtime/energyplus_capability.json")
        rc = 1
    else:
        print("RESULT: PASS — EnergyPlus looks ready for the grid-search lessons.")
        rc = 0

    payload = {
        "root": str(root),
        "checks": [
            {"name": name, "ok": ok, "detail": detail} for name, ok, detail in checks
        ],
        "result": "PASS" if failed == 0 else "FAIL",
    }
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {args.json_out}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
