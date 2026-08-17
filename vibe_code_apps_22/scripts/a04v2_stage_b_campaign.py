"""Stage B LIVE EnergyPlus campaign. Resume-safe. No surrogate. Failed runs stay in the ledger."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from a04v2_build_stage_b_candidate import build_child
from eplus_gym.demand_windows import demand_window_report
from eplus_gym.eplus_err import parse_eplus_err
from eplus_gym.objective import _facility_series
from eplus_gym.site_env import require_site_root
from eplus_gym.path_sanitize import redact_obj

# Physically bounded Stage B grid (not CapMult=28). ~24 LIVE ramp packages.
GRID = [
    {"plant": "autosize_htg", "capmult": 1.0, "mass_m2": 0.0},
    {"plant": "autosize_htg", "capmult": 1.0, "mass_m2": 800.0},
    {"plant": "autosize_htg", "capmult": 1.0, "mass_m2": 2000.0},
    {"plant": "autosize_htg", "capmult": 6.0, "mass_m2": 0.0},
    {"plant": "autosize_htg", "capmult": 6.0, "mass_m2": 800.0},
    {"plant": "autosize_htg", "capmult": 6.0, "mass_m2": 2000.0},
    {"plant": "autosize_htg", "capmult": 12.0, "mass_m2": 0.0},
    {"plant": "autosize_htg", "capmult": 12.0, "mass_m2": 800.0},
    {"plant": "hp_scaled_3ton", "capmult": 1.0, "mass_m2": 0.0},
    {"plant": "hp_scaled_3ton", "capmult": 1.0, "mass_m2": 800.0},
    {"plant": "hp_scaled_3ton", "capmult": 6.0, "mass_m2": 800.0},
    {"plant": "hp_scaled_3ton", "capmult": 12.0, "mass_m2": 800.0},
    {"plant": "a04_capacity", "capmult": 6.0, "mass_m2": 800.0},
    {"plant": "a04_capacity", "capmult": 12.0, "mass_m2": 2000.0},
]


def run_id_for(spec: dict, day: str) -> str:
    plant = spec["plant"].replace("_", "")
    return f"sb_{plant}_c{int(spec['capmult'])}_m{int(spec['mass_m2'])}_{day.replace('-', '')}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default=None)
    p.add_argument(
        "--days",
        default="2026-01-12,2026-01-20,2026-01-17,2026-02-09,2025-12-06",
        help="train_dev days: weekday, weekday, weekend, mild weekday, extra weekend; not Jan 25/26 or Mar 16",
    )
    p.add_argument("--limit", type=int, default=0, help="Max trial packages (0 = all grid × first day, then extra days for first 4)")
    args = p.parse_args()
    site = require_site_root(args.site_root)
    days = [d.strip() for d in args.days.split(",") if d.strip()]
    out_root = _APP / "docs" / "audits" / "figures" / "a04v2" / "stageB"
    out_root.mkdir(parents=True, exist_ok=True)
    ledger_path = out_root / "campaign_ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else {
        "schema": "vibe22.a04v2.stageB_ledger.v1",
        "trials": [],
    }
    done = {t["run_id"] for t in ledger["trials"] if t.get("status") in {"success", "eplus_failed", "ramp_failed"}}
    for rec in ledger["trials"]:
        if rec.get("warning_gate"):
            continue
        dest = out_root / rec["run_id"]
        err = next(dest.rglob("eplusout.err"), None) if dest.is_dir() else None
        if not err:
            continue
        quality = parse_eplus_err(err)
        rec["eplus_quality"] = rec.get("eplus_quality") or quality
        n_air = int((quality.get("recurring") or {}).get("w2a_low_airflow") or 0)
        rec["warning_gate"] = {
            "max_w2a_low_airflow": 0,
            "w2a_low_airflow": n_air,
            "passed": n_air <= 0 and int(quality.get("severe_count") or 0) == 0
            and int(quality.get("fatal_count") or 0) == 0,
        }
    ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    planned = []
    # All grid on days[0] (~14). Extra weekday on first 6 specs. Diversity days on CapMult>=12.
    for spec in GRID:
        planned.append((spec, days[0]))
    for spec in GRID[:6]:
        if len(days) > 1:
            planned.append((spec, days[1]))
    for spec in GRID:
        if float(spec["capmult"]) >= 12.0:
            for d in days[2:]:
                planned.append((spec, d))
    if args.limit:
        planned = planned[: args.limit]
    for spec, day in planned:
        rid = run_id_for(spec, day)
        if rid in done:
            continue
        rec = {
            "run_id": rid,
            "day": day,
            "parameters": spec,
            "started_utc": datetime.now(timezone.utc).isoformat(),
            "status": "running",
        }
        try:
            meta = build_child(plant=spec["plant"], capmult=spec["capmult"], mass_m2=spec["mass_m2"], run_id=rid)
            idf = _APP / "models" / "eplus" / "a04v2_candidates" / rid / meta["idf"]
            dest = out_root / rid
            dest.mkdir(parents=True, exist_ok=True)
            cmd = [
                sys.executable,
                str(_APP / "scripts" / "reproduce_physics_ramp_gate.py"),
                "--site-root",
                str(site),
                "--day",
                day,
                "--idf",
                str(idf),
                "--out",
                str(dest),
                "--write-artifact",
                str(dest / "ramp_gate.json"),
            ]
            proc = subprocess.run(cmd, cwd=_APP, capture_output=True, text=True)
            rec["returncode"] = proc.returncode
            rec["idf_sha256"] = meta["idf_sha256"]
            rec["parent_sha256"] = meta["parent_sha256"]
            ramp_p = dest / "ramp_gate.json"
            if ramp_p.is_file():
                rec["ramp"] = redact_obj(json.loads(ramp_p.read_text(encoding="utf-8")))
            traj = dest / "incumbent" / "trajectory.parquet"
            if traj.is_file():
                import pandas as pd

                df = pd.read_parquet(traj)
                fac = _facility_series(df)
                idx = pd.date_range(day, periods=len(fac), freq="15min")
                rec["demand_windows"] = demand_window_report(pd.Series(fac.to_numpy(), index=idx))
            err = next(dest.rglob("eplusout.err"), None)
            if err:
                rec["eplus_quality"] = parse_eplus_err(err)
            rec["status"] = "success" if proc.returncode == 0 else "ramp_failed"
            if proc.returncode not in (0, 4):
                rec["status"] = "eplus_failed"
                rec["stderr_tail"] = (proc.stderr or "")[-2000:]
            quality = rec.get("eplus_quality") or {}
            n_air = int((quality.get("recurring") or {}).get("w2a_low_airflow") or 0)
            rec["warning_gate"] = {
                "max_w2a_low_airflow": 0,
                "w2a_low_airflow": n_air,
                "passed": n_air <= 0 and int(quality.get("severe_count") or 0) == 0
                and int(quality.get("fatal_count") or 0) == 0,
            }
        except KeyboardInterrupt:
            raise
        except (Exception, SystemExit) as exc:  # noqa: BLE001 — ledger must retain failures
            rec["status"] = "eplus_failed"
            rec["error"] = str(exc)
        rec["finished_utc"] = datetime.now(timezone.utc).isoformat()
        ledger["trials"].append(rec)
        ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
        hb = {
            "run_id": rid,
            "status": rec["status"],
            "n_done": len(ledger["trials"]),
            "n_planned": len(planned),
            "utc": rec["finished_utc"],
        }
        (out_root / "heartbeat.json").write_text(json.dumps(hb, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(hb), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
