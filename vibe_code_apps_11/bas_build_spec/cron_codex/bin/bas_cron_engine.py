#!/usr/bin/env python3
"""Gateway scheduler for bas_build_spec/cron/jobs.json (outside Codex)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def cron_fields_match(expr: str, now: datetime) -> bool:
    parts = expr.split()
    if len(parts) != 5:
        return False
    minute, hour, dom, month, dow = parts
    checks = [
        (minute, now.minute, 0, 59),
        (hour, now.hour, 0, 23),
        (dom, now.day, 1, 31),
        (month, now.month, 1, 12),
        (dow, now.weekday(), 0, 6),  # Mon=0
    ]
    for field, value, lo, hi in checks:
        if field == "*":
            continue
        allowed: set[int] = set()
        for part in field.split(","):
            if part == "*":
                allowed.update(range(lo, hi + 1))
                continue
            if "/" in part:
                base, step_s = part.split("/", 1)
                step = int(step_s)
                if base == "*":
                    vals = range(lo, hi + 1)
                elif "-" in base:
                    a, b = base.split("-", 1)
                    vals = range(int(a), int(b) + 1)
                else:
                    vals = [int(base)]
                allowed.update(v for v in vals if lo <= v <= hi and (v - lo) % step == 0)
            elif "-" in part:
                a, b = part.split("-", 1)
                allowed.update(range(int(a), int(b) + 1))
            else:
                allowed.add(int(part))
        if value not in allowed:
            return False
    return True


def schedule_due(job: dict[str, Any], now: datetime, last_iso: str | None) -> bool:
    sched = job.get("schedule") or {}
    stype = sched.get("type")
    if stype == "every":
        minutes = int(sched.get("minutes", 0))
        if minutes <= 0:
            return False
        last = parse_iso(last_iso)
        if last is None:
            return True
        return (now - last.astimezone(now.tzinfo)).total_seconds() >= minutes * 60
    if stype == "at":
        at_iso = sched.get("at")
        if not at_iso:
            return False
        at_dt = parse_iso(at_iso)
        if at_dt is None:
            return False
        if last_iso:
            return False
        return now >= at_dt.astimezone(now.tzinfo)
    if stype == "cron":
        expr = sched.get("expr", "")
        if not cron_fields_match(expr, now):
            return False
        last = parse_iso(last_iso)
        if last is None:
            return True
        return (now - last.astimezone(now.tzinfo)).total_seconds() >= 45
    return False


def running_stale(entry: dict[str, Any], grace: int, now: datetime) -> bool:
    if entry.get("status") != "running":
        return False
    started = parse_iso(entry.get("started_at"))
    if started is None:
        return True
    return (now - started.astimezone(now.tzinfo)).total_seconds() > grace


def cmd_list(jobs_doc: dict[str, Any]) -> int:
    for job in jobs_doc.get("jobs", []):
        en = "on" if job.get("enabled", True) else "off"
        print(f"{job.get('id')}: [{en}] {job.get('style')} {job.get('service')} {job.get('schedule')}")
    return 0


def cmd_runs(runs_dir: Path, job_id: str | None, limit: int) -> int:
    if not runs_dir.is_dir():
        print("(no runs yet)")
        return 0
    paths: list[Path] = []
    if job_id:
        paths = sorted((runs_dir / job_id).glob("*.json"), reverse=True)[:limit]
    else:
        paths = sorted(runs_dir.glob("*/*.json"), reverse=True)[:limit]
    for path in paths:
        data = load_json(path)
        print(f"{path.parent.name}/{path.name}: {data}")
    return 0


def cmd_run_due(
    jobs_path: Path,
    state_path: Path,
    runs_dir: Path,
    dry_run: bool,
    grace: int,
) -> int:
    jobs_doc = load_json(jobs_path)
    state = load_json(state_path)
    tz_name = jobs_doc.get("timezone", "UTC")
    tz = ZoneInfo(tz_name) if ZoneInfo else timezone.utc
    now = datetime.now(tz)
    due: list[dict[str, Any]] = []

    for job in jobs_doc.get("jobs", []):
        if not job.get("enabled", True):
            continue
        jid = job["id"]
        entry = state.setdefault(jid, {})
        if running_stale(entry, grace, now):
            entry["status"] = "stale"
            entry["reconciled_at"] = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if entry.get("status") == "running":
            continue
        last = entry.get("last_run_at")
        if schedule_due(job, now, last):
            due.append(job)

    if not due:
        print("No due jobs.")
        if not dry_run:
            save_json(state_path, state)
        return 0

    for job in due:
        jid = job["id"]
        run_id = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        run_dir = runs_dir / jid
        run_dir.mkdir(parents=True, exist_ok=True)
        run_file = run_dir / f"{run_id}.json"
        cmd = [job.get("command", "")]
        cmd.extend(job.get("args") or [])
        env = os.environ.copy()
        for k, v in (job.get("env") or {}).items():
            env[str(k)] = str(v)
        print(f"{'DRY ' if dry_run else ''}RUN {jid}: {' '.join(cmd)}")
        if dry_run:
            continue
        started = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        state[jid] = {
            **state.get(jid, {}),
            "status": "running",
            "started_at": started,
            "last_run_id": run_id,
        }
        save_json(state_path, state)
        rc = 0
        err: str | None = None
        try:
            proc = subprocess.run(cmd, env=env, check=False)
            rc = int(proc.returncode)
        except Exception as exc:  # noqa: BLE001
            rc = 1
            err = str(exc)
        finished = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        payload = {
            "job_id": jid,
            "run_id": run_id,
            "started_at": started,
            "finished_at": finished,
            "rc": rc,
            "command": cmd,
        }
        if err:
            payload["error"] = err
        run_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        state[jid] = {
            **state.get(jid, {}),
            "status": "idle",
            "last_run_at": finished,
            "last_run_id": run_id,
            "last_rc": rc,
        }
        if job.get("schedule", {}).get("type") == "at":
            job["enabled"] = False
    if not dry_run:
        save_json(jobs_path, jobs_doc)
        save_json(state_path, state)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="BAS cron gateway")
    parser.add_argument("command", choices=["run-due", "dry-run", "list", "runs"])
    parser.add_argument("--jobs", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--runs-dir", required=True)
    parser.add_argument("--job-id")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--grace-seconds", type=int, default=7200)
    args = parser.parse_args()
    jobs_path = Path(args.jobs)
    state_path = Path(args.state)
    runs_dir = Path(args.runs_dir)
    if args.command == "list":
        return cmd_list(load_json(jobs_path))
    if args.command == "runs":
        return cmd_runs(runs_dir, args.job_id, args.limit)
    dry = args.command == "dry-run"
    return cmd_run_due(jobs_path, state_path, runs_dir, dry, args.grace_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
