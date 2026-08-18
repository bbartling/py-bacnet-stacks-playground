"""Bounded Track B physics matrix. Pre-registered in execution_plan.json. Retain failures."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
PLAN = _APP / "docs" / "audits" / "figures" / "vibe22_live_trackb_long_rl" / "execution_plan.json"
LEDGER = _APP / "docs" / "audits" / "figures" / "vibe22_live_trackb_long_rl" / "matrix_ledger.json"


def cells_from_plan(plan: dict) -> list[dict]:
    mx = plan["physics_matrix_preregistered"]
    days = mx["days"]
    out = []
    for sens in mx["sensitivities"]:
        for role, day in days.items():
            for arm in mx["arms"]:
                run_id = f"trackb_live_v3_{sens}_{day.replace('-', '')}_{arm}"
                out.append(
                    {
                        "run_id": run_id,
                        "sensitivity": sens,
                        "day": day,
                        "day_role": role,
                        "arm": arm,
                    }
                )
    return out


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default=r"C:\Users\ben\OneDrive\Desktop\testing\sp_creekside")
    p.add_argument("--sizing-totals-json", default="")
    p.add_argument("--first-only", action="store_true")
    p.add_argument("--base-arms-only", action="store_true")
    args = p.parse_args()
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    site = str(args.site_root)
    reuse = str(args.sizing_totals_json or "")
    cells = cells_from_plan(plan)
    if args.first_only:
        cells = [c for c in cells if c["run_id"] == "trackb_live_v3_base_20260112_continuous_70"]
    elif args.base_arms_only:
        cells = [c for c in cells if c["sensitivity"] == "base"]
    ledger = {
        "schema": "vibe22.trackb.matrix_ledger.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "public_line": "MODEL DEVELOPMENT INCOMPLETE — LONG RL BLOCKED",
        "cells": [],
    }
    if LEDGER.is_file():
        ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    done = {str(r.get("run_id")) for r in ledger.get("cells") or []}
    for cell in cells:
        if cell["run_id"] in done:
            continue
        cmd = [
            sys.executable,
            str(_APP / "scripts" / "a04v2_trackb_two_pass.py"),
            "--site-root",
            site,
            "--run-id",
            cell["run_id"],
            "--sensitivity",
            cell["sensitivity"],
            "--arm",
            cell["arm"],
            "--begin",
            cell["day"],
            "--end",
            cell["day"],
        ]
        if reuse:
            cmd.extend(["--sizing-totals-json", reuse])
        proc = subprocess.run(cmd, cwd=str(_APP), capture_output=True, text=True)
        rec = {
            **cell,
            "returncode": proc.returncode,
            "stdout_tail": (proc.stdout or "")[-2000:],
            "stderr_tail": (proc.stderr or "")[-2000:],
            "retained_failure": proc.returncode != 0,
        }
        ledger.setdefault("cells", []).append(rec)
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        LEDGER.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        if proc.returncode != 0 and args.first_only:
            break
    print(json.dumps({"n": len(ledger.get("cells") or []), "path": str(LEDGER)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
