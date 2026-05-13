#!/usr/bin/env python3
"""Evaluate and run jobs from bas_build_spec/cron/jobs.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_json(path: Path, default):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_cron_field(field: str, value: int) -> bool:
    field = field.strip()
    if field == "*":
        return True
    for part in field.split(","):
        part = part.strip()
        if part.isdigit() and int(part) == value:
            return True
        if "/" in part:
            base, step = part.split("/", 1)
            if base == "*" and step.isdigit() and value % int(step) == 0:
                return True
    return False


def cron_due(expr: str, now: datetime) -> bool:
    parts = expr.split()
    if len(parts) != 5:
        return False
    minute, hour, dom, month, dow = parts
    return (
        parse_cron_field(minute, now.minute)
        and parse_cron_field(hour, now.hour)
        and parse_cron_field(dom, now.day)
        and parse_cron_field(month, now.month)
        and parse_cron_field(dow, now.weekday())
    )


def every_due(minutes: int, state: dict, now: datetime) -> bool:
    if minutes <= 0:
        return False
    last = state.get("last_run_at")
    if not last:
        return True
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return True
    delta = now - last_dt
    return delta.total_seconds() >= minutes * 60


def at_due(when: str, state: dict, now: datetime) -> bool:
    if state.get("last_run_at"):
        return False
    try:
        target = datetime.fromisoformat(when.replace("Z", "+00:00"))
    except ValueError:
        return False
    return now >= target


def job_due(job: dict, state: dict, now: datetime) -> bool:
    if not job.get("enabled", True):
        return False
    if state.get("status") == "running":
        return False
    sched = job.get("schedule") or {}
    stype = sched.get("type")
    if stype == "cron":
        return cron_due(str(sched.get("expr", "")), now)
    if stype == "every":
        return every_due(int(sched.get("minutes", 0) or 0), state, now)
    if stype == "at":
        return at_due(str(sched.get("at", "")), state, now)
    return False


def reconcile(state: dict, grace_sec: int, now: datetime) -> None:
    for meta in state.values():
        if meta.get("status") != "running":
            continue
        started = meta.get("started_at") or meta.get("last_run_at")
        if not started:
            continue
        try:
            started_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
        except ValueError:
            meta["status"] = "failed"
            continue
        if (now - started_dt).total_seconds() > grace_sec:
            meta["status"] = "failed"
            meta["last_rc"] = 124


def run_job(job: dict, env: dict, runs_dir: Path) -> int:
    cmd = [str(job["command"])]
    cmd.extend(str(a) for a in job.get("args") or [])
    job_env = os.environ.copy()
    job_env.update(env)
    for key, val in (job.get("env") or {}).items():
        job_env[str(key)] = str(val)
    run_dir = runs_dir / str(job["id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    stamp = utc_now().strftime("%Y%m%dT%H%M%SZ")
    log_path = run_dir / f"{stamp}.json"
    proc = subprocess.run(cmd, env=job_env, capture_output=True, text=True)
    log_path.write_text(
        json.dumps(
            {
                "command": cmd,
                "returncode": proc.returncode,
                "stdout": proc.stdout[-8000:],
                "stderr": proc.stderr[-8000:],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return proc.returncode


def main(argv: list[str]) -> int:
    if len(argv) < 4:
        print("usage: bas_cron_engine.py <jobs.json> <state.json> <runs_dir> <dry-run|run-due> [grace_sec]", file=sys.stderr)
        return 2
    jobs_path = Path(argv[1])
    state_path = Path(argv[2])
    runs_dir = Path(argv[3])
    mode = argv[4]
    grace = int(argv[5]) if len(argv) > 5 else 7200
    jobs_doc = load_json(jobs_path, {"jobs": []})
    jobs = jobs_doc.get("jobs") or []
    state = load_json(state_path, {})
    now = utc_now()
    reconcile(state, grace, now)
    due = []
    for job in jobs:
        jid = str(job.get("id", ""))
        if not jid:
            continue
        meta = state.setdefault(jid, {})
        if job_due(job, meta, now):
            due.append(job)
    if mode == "dry-run":
        if not due:
            print("No due jobs.")
            return 0
        for job in due:
            print(f"due: {job['id']} -> {' '.join([job['command'], *(job.get('args') or [])])}")
        return 0
    if mode != "run-due":
        print(f"unknown mode: {mode}", file=sys.stderr)
        return 2
    rc = 0
    for job in due:
        jid = str(job["id"])
        meta = state.setdefault(jid, {})
        meta["status"] = "running"
        meta["started_at"] = now.isoformat().replace("+00:00", "Z")
        save_json(state_path, state)
        job_rc = run_job(job, {}, runs_dir)
        meta["status"] = "ok" if job_rc == 0 else "failed"
        meta["last_rc"] = job_rc
        meta["last_run_at"] = utc_now().isoformat().replace("+00:00", "Z")
        if job_rc != 0:
            rc = job_rc
    save_json(state_path, state)
    return rc


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
