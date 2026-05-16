#!/usr/bin/env python3
"""Evaluate and run jobs from bas_build_spec/cron/jobs.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
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


def next_cron_fire(expr: str, after: datetime) -> datetime | None:
    """Smallest minute-aligned UTC time strictly after `after` where cron_due is true."""
    t = after + timedelta(minutes=1)
    t = t.replace(second=0, microsecond=0)
    for _ in range(527040):  # ~366 days at 1-minute steps
        if cron_due(expr, t):
            return t
        t += timedelta(minutes=1)
    return None


def next_every_fire(minutes: int, meta: dict, now: datetime) -> datetime | None:
    if minutes <= 0:
        return None
    last = meta.get("last_run_at")
    if not last:
        return now
    try:
        last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
    except ValueError:
        return now
    return last_dt + timedelta(minutes=minutes)


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


def _parse_wake_log_summary(log_path: Path) -> dict:
    if not log_path.is_file():
        return {"log_path": str(log_path), "error": "missing"}
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    start_idxs: list[int] = []
    end_idxs: list[int] = []
    for i, line in enumerate(lines):
        if line.startswith("=== bas_wake start ") and line.endswith(" ==="):
            start_idxs.append(i)
        if line.startswith("=== bas_wake end ") and " log=" in line:
            end_idxs.append(i)
    tok_total = 0
    tok_hits = 0
    for i, line in enumerate(lines):
        if line.strip() == "tokens used" and i + 1 < len(lines):
            nxt = lines[i + 1].strip().replace(",", "")
            if nxt.isdigit():
                tok_total += int(nxt)
                tok_hits += 1
    out: dict = {
        "log_path": str(log_path),
        "size_bytes": log_path.stat().st_size,
        "line_count": len(lines),
        "token_hits": tok_hits,
        "tokens_used_sum": tok_total,
    }
    if not end_idxs:
        out["parse_note"] = "no bas_wake end line found"
        return out
    last_end_i = end_idxs[-1]
    starts_before = [i for i in start_idxs if i < last_end_i]
    start_i = starts_before[-1] if starts_before else (start_idxs[-1] if start_idxs else None)
    if start_i is None:
        out["parse_note"] = "no bas_wake start line found"
        return out

    sl = lines[start_i]
    if sl.startswith("=== bas_wake start ") and sl.endswith(" ==="):
        out["wake_start_line"] = sl[len("=== bas_wake start ") : -len(" ===")].strip()
    el = lines[last_end_i]
    if el.startswith("=== bas_wake end ") and " log=" in el:
        rest = el[len("=== bas_wake end ") :]
        out["wake_end_line"] = rest.split(" log=", 1)[0].strip()
    try:
        t0 = datetime.fromisoformat(out["wake_start_line"])
        t1 = datetime.fromisoformat(out["wake_end_line"])
        out["duration_seconds"] = round((t1 - t0).total_seconds(), 3)
    except (KeyError, TypeError, ValueError):
        out["duration_seconds"] = None
    return out


def wake_status_json(jobs_path: Path, state_path: Path, log_dir: Path, state_dir: Path | None) -> dict:
    """Payload for read-only dashboard: next Codex wake ETA + last log stats."""
    jobs_doc = load_json(jobs_path, {"jobs": []})
    jobs = jobs_doc.get("jobs") or []
    state = load_json(state_path, {})
    now = utc_now()
    waiting_human = bool(state_dir and (state_dir / "waiting_human").is_file())
    cron_note = (
        "Cron expressions are evaluated in UTC (see bas_cron_engine.py). "
        "User crontab may call bas_cron_scheduler.sh run-due more often than bas_wake fires."
    )
    def _schedule_entry(job: dict) -> dict:
        jid = str(job.get("id", ""))
        meta = state.get(jid) or {}
        sched = job.get("schedule") or {}
        stype = sched.get("type")
        entry: dict = {
            "id": jid,
            "name": job.get("name", ""),
            "schedule_type": stype,
            "last_run_at": meta.get("last_run_at"),
            "last_rc": meta.get("last_rc"),
            "status": meta.get("status"),
        }
        if stype == "cron":
            expr = str(sched.get("expr", ""))
            entry["cron_expr"] = expr
            nxt = next_cron_fire(expr, now)
            if nxt:
                entry["next_fire_utc"] = nxt.isoformat().replace("+00:00", "Z")
                entry["seconds_until_next"] = max(0, int((nxt - now).total_seconds()))
        elif stype == "every":
            mins = int(sched.get("minutes", 0) or 0)
            entry["every_minutes"] = mins
            nxt = next_every_fire(mins, meta, now)
            if nxt:
                if nxt <= now:
                    entry["next_fire_utc"] = "due"
                    entry["seconds_until_next"] = 0
                else:
                    entry["next_fire_utc"] = nxt.isoformat().replace("+00:00", "Z")
                    entry["seconds_until_next"] = int((nxt - now).total_seconds())
        return entry

    scheduled_jobs: list[dict] = []
    wake_jobs: list[dict] = []
    for job in jobs:
        if not job.get("enabled", True):
            continue
        entry = _schedule_entry(job)
        sched = job.get("schedule") or {}
        if sched.get("type") == "every" and int(sched.get("minutes", 0) or 0) <= 0:
            continue
        scheduled_jobs.append(entry)
        cmd = str(job.get("command", ""))
        if "bas_wake.sh" in cmd or job.get("service") == "bas_wake":
            wake_jobs.append(entry)
    last_log: dict = {}
    if log_dir.is_dir():
        logs = sorted(log_dir.glob("wake-*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if logs:
            last_log = _parse_wake_log_summary(logs[0])
    return {
        "now_utc": now.isoformat().replace("+00:00", "Z"),
        "waiting_human": waiting_human,
        "cron_timezone_note": jobs_doc.get("timezone"),
        "engine_note_utc": cron_note,
        "bas_wake_jobs": wake_jobs,
        "scheduled_jobs": scheduled_jobs,
        "last_wake_log": last_log,
    }


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[1] == "wake-status-json":
        if len(argv) < 5:
            print(
                "usage: bas_cron_engine.py wake-status-json <jobs.json> <state.json> <log_dir> [cron_codex_state_dir]",
                file=sys.stderr,
            )
            return 2
        jobs_path = Path(argv[2])
        state_path = Path(argv[3])
        log_dir = Path(argv[4])
        state_dir = Path(argv[5]) if len(argv) > 5 else log_dir.parent / "state"
        print(json.dumps(wake_status_json(jobs_path, state_path, log_dir, state_dir), indent=2))
        return 0

    if len(argv) < 5:
        print(
            "usage: bas_cron_engine.py <jobs.json> <state.json> <runs_dir> <dry-run|run-due> [grace_sec]",
            file=sys.stderr,
        )
        print(
            "       bas_cron_engine.py wake-status-json <jobs.json> <state.json> <log_dir> [state_dir]",
            file=sys.stderr,
        )
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
