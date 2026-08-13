#!/usr/bin/env python3
"""Supervisor CLI for Streamlit DSM campaigns (only writer of campaign state)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym_app.dsm_campaign import (  # noqa: E402
    DEFAULT_JOB_TIMEOUT_S,
    active_campaign_running,
    cancel_requested,
    clear_cancel_request,
    collect_traj,
    mark_cancelled,
    mark_failed,
    mark_succeeded,
    new_campaign_doc,
    read_json,
    validate_job_outputs,
    write_campaign,
)
from eplus_gym_app.dsm_console import (  # noqa: E402
    attach_baseline_deltas,
    dsm_kpis,
    last_run_pointer,
    persist_last_run,
    pick_frame,
)
from eplus_gym_app.dsm_preflight import PreflightError, run_preflight, sha256_file  # noqa: E402
from eplus_gym_app.weather_files import KIND_AMY  # noqa: E402

_CLI_RULES = _APP / "scripts" / "run_eplus_gym_rules.py"


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_APP),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _load_request(path: Path) -> dict[str, Any]:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("campaign request must be a JSON object")
    return doc


def _launch_job(
    *,
    site: Path,
    strategy_id: str,
    epw: Path,
    idf: Path,
    out_dir: Path,
    begin: str,
    end: str,
    max_steps: int,
) -> tuple[subprocess.Popen, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / "live.log"
    cmd = [
        sys.executable,
        "-u",
        str(_CLI_RULES),
        "--mode",
        "live",
        "--family",
        "w2a",
        "--strategies",
        strategy_id,
        "--epw",
        str(epw),
        "--idf",
        str(idf),
        "--out",
        str(out_dir),
        "--max-steps",
        str(int(max_steps)),
        "--day",
        begin,
        "--begin",
        begin,
        "--end",
        end,
    ]
    handle = log.open("w", encoding="utf-8")
    env = os.environ.copy()
    env["SITE_ROOT"] = str(site)
    env["LAKESIDE_SITE_ROOT"] = str(site)
    proc = subprocess.Popen(
        cmd,
        cwd=str(_APP),
        stdout=handle,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    # Keep handle open for child's lifetime; close when wait ends.
    proc._dsm_log_handle = handle  # type: ignore[attr-defined]
    return proc, log


def _close_log(proc: subprocess.Popen) -> None:
    handle = getattr(proc, "_dsm_log_handle", None)
    if handle is not None:
        try:
            handle.close()
        except Exception:  # noqa: BLE001
            pass


def _wait_job(
    site: Path,
    doc: dict[str, Any],
    proc: subprocess.Popen,
    *,
    timeout_s: float,
) -> int:
    t0 = time.time()
    while proc.poll() is None:
        if cancel_requested(site):
            try:
                proc.terminate()
            except OSError:
                pass
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
            _close_log(proc)
            mark_cancelled(site, doc)
            raise SystemExit(130)
        if time.time() - t0 > timeout_s:
            try:
                proc.terminate()
            except OSError:
                pass
            try:
                proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                proc.kill()
            _close_log(proc)
            raise TimeoutError(f"job exceeded timeout {timeout_s:.0f}s")
        doc["heartbeat_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        )
        doc["child_pid"] = proc.pid
        write_campaign(site, doc)
        time.sleep(1.0)
    _close_log(proc)
    return int(proc.returncode if proc.returncode is not None else 0)


def _persist_success(
    site: Path,
    doc: dict[str, Any],
    *,
    results: list[dict[str, Any]],
) -> None:
    """Write last_dsm_run.json only after all jobs validated."""
    frames_meta: dict[str, str] = {}
    kpis_by: dict[str, Any] = {}
    elapsed_by: dict[str, float] = {}
    for row in results:
        key = row["key"]
        frames_meta[key] = row["parquet"]
        elapsed_by[key] = float(row.get("elapsed_s") or 0.0)
        df = __import__("pandas").read_parquet(row["parquet"])
        meta = {
            "honesty": "W2A_PHYSICAL_DSM",
            "provenance": "ENERGYPLUS_PYTHON_API",
            "mode": "live",
            "family": "w2a",
            "promote": False,
            "day": doc.get("peak_day"),
            "strategy_id": row["strategy_id"],
            "loop": "CLOSED_LOOP_RULE_DR",
            "period": f"{doc['begin']}/{doc['end']}",
            "weekend_sp": "repeat_96_step_profile",
        }
        # Aggregate per strategy (prefer AMY when both)
        sid = row["strategy_id"]
        if sid not in kpis_by or row["weather_kind"] == KIND_AMY:
            kpis_by[sid] = dsm_kpis(df, meta)

    attach_baseline_deltas(kpis_by)
    primary_key = next(
        (k for k in frames_meta if k.startswith("baseline:")),
        next(iter(frames_meta)),
    )
    import pandas as pd

    primary_df = pd.read_parquet(frames_meta[primary_key])
    persist_last_run(
        site,
        df=primary_df,
        actual=pd.DataFrame(),
        kpis=kpis_by.get("baseline") or next(iter(kpis_by.values())),
        strategy="all",
        day=str(doc.get("peak_day") or doc["begin"]),
        preset=str(doc.get("preset") or "Peak day"),
        mode="live",
        epw_name=",".join(str(e.get("epw") or "") for e in (doc.get("epws") or [])),
        why="dsm_campaign supervisor",
        window_days=[str(doc["begin"]), str(doc["end"])],
        parquet=frames_meta[primary_key],
        elapsed_s=sum(elapsed_by.values()),
        out_dir=str(eplus_runs_root(site, doc["run_id"])),
        weather_mode=str(doc.get("weather_mode") or "AMY"),
        period=f"{doc['begin']}/{doc['end']}",
        max_steps=int(doc["max_steps"]),
        n_days=int(doc["n_days"]),
        parquets=frames_meta,
        elapsed_by_weather=elapsed_by,
        weather_kind=primary_key.split(":", 1)[-1] if ":" in primary_key else KIND_AMY,
        strategies=list(kpis_by.keys()),
        kpis_by_strategy=kpis_by,
    )
    # Enrich last_dsm_run with hashes for calendar-year gate
    ptr = last_run_pointer(site)
    disk = read_json(ptr) or {}
    disk["idf_sha256"] = doc.get("idf_sha256")
    disk["epws"] = doc.get("epws")
    disk["state"] = "succeeded"
    disk["run_id"] = doc.get("run_id")
    from eplus_gym_app.dsm_campaign import atomic_write_json

    atomic_write_json(ptr, disk)


def eplus_runs_root(site: Path, run_id: str) -> Path:
    return Path(site) / "reports" / "eplus_gym" / "runs" / run_id


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a durable DSM EnergyPlus campaign")
    ap.add_argument("--site", required=True, type=Path)
    ap.add_argument("--request", required=True, type=Path, help="JSON campaign request")
    ap.add_argument("--job-timeout-s", type=float, default=DEFAULT_JOB_TIMEOUT_S)
    args = ap.parse_args(argv)

    site = Path(args.site)
    req = _load_request(Path(args.request))

    existing = active_campaign_running(site)
    if existing is not None:
        print(
            f"refuse: campaign {existing.get('run_id')} still active "
            f"(state={existing.get('state')})",
            file=sys.stderr,
        )
        return 2

    clear_cancel_request(site)
    run_id = str(req.get("run_id") or f"{_utc_stamp()}_dsm")
    idf = Path(req["idf"])
    begin = str(req["begin"])[:10]
    end = str(req["end"])[:10]
    max_steps = int(req["max_steps"])
    strategies = list(req["strategies"])
    weather_mode = str(req.get("weather_mode") or "AMY")
    jobs_raw = list(req["jobs"])
    epw_paths = [Path(j["epw"]) for j in jobs_raw]
    # unique preserve order
    seen: set[str] = set()
    epws: list[Path] = []
    for p in epw_paths:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        epws.append(Path(p))

    out_root = eplus_runs_root(site, run_id)
    out_root.mkdir(parents=True, exist_ok=True)

    epw_meta: list[dict[str, Any]] = []
    for p in epws:
        meta = {"epw": str(p), "sha256": sha256_file(p) if p.is_file() else None}
        epw_meta.append(meta)

    doc = new_campaign_doc(
        run_id=run_id,
        site=site,
        idf=idf,
        idf_sha256=sha256_file(idf) if idf.is_file() else "",
        begin=begin,
        end=end,
        max_steps=max_steps,
        n_days=int(req.get("n_days") or 0),
        strategies=strategies,
        weather_mode=weather_mode,
        jobs=jobs_raw,
        epw_meta=epw_meta,
        preset=str(req.get("preset") or "Peak day"),
        peak_day=str(req.get("peak_day") or begin),
        git_sha=_git_sha(),
        supervisor_pid=os.getpid(),
    )
    doc["log"] = str(out_root / "campaign.log")
    doc["state"] = "preflight"
    write_campaign(site, doc)

    try:
        pf = run_preflight(
            idf=idf,
            epws=epws,
            begin=begin,
            end=end,
            max_steps=max_steps,
            strategies=strategies,
            out_root=out_root,
            expected_idf_sha256=req.get("expected_idf_sha256"),
            require_energyplus=bool(req.get("require_energyplus", True)),
        )
        # merge coverage into epw_meta
        by_path = {str(Path(e["epw"]).resolve()): e for e in pf.get("epws") or []}
        for row in doc["epws"]:
            try:
                key = str(Path(row["epw"]).resolve())
            except OSError:
                key = str(row["epw"])
            cov = by_path.get(key) or {}
            row.update({k: v for k, v in cov.items() if k != "epw"})
        doc["n_days"] = pf.get("n_days") or doc["n_days"]
        doc["idf_sha256"] = pf.get("idf_sha256") or doc["idf_sha256"]
    except PreflightError as exc:
        mark_failed(site, doc, exc.to_dict())
        print(str(exc), file=sys.stderr)
        return 1

    if cancel_requested(site):
        mark_cancelled(site, doc)
        return 130

    doc["state"] = "queued"
    write_campaign(site, doc)
    doc["state"] = "starting"
    write_campaign(site, doc)
    doc["state"] = "running"
    write_campaign(site, doc)

    results: list[dict[str, Any]] = []
    for idx, job in enumerate(doc["jobs"]):
        if cancel_requested(site):
            mark_cancelled(site, doc)
            return 130
        sid = job["strategy_id"]
        kind = job["weather_kind"]
        key = job["key"]
        job_out = out_root / f"{sid}_{kind}"
        job["state"] = "running"
        job["out_dir"] = str(job_out)
        write_campaign(site, doc)
        t0 = time.time()
        try:
            proc, log = _launch_job(
                site=site,
                strategy_id=sid,
                epw=Path(job["epw"]),
                idf=idf,
                out_dir=job_out,
                begin=begin,
                end=end,
                max_steps=max_steps,
            )
            doc["child_pid"] = proc.pid
            write_campaign(site, doc)
            code = _wait_job(site, doc, proc, timeout_s=float(args.job_timeout_s))
            elapsed = time.time() - t0
            job["elapsed_s"] = elapsed
            job["exit_code"] = code
            job["log"] = str(log)
            if code != 0:
                from eplus_gym.startup_diag import find_eplusout_err

                severe = None
                err_path = find_eplusout_err(job_out)
                if err_path is not None and err_path.is_file():
                    try:
                        err_text = err_path.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        err_text = ""
                    for line in err_text.splitlines():
                        low = line.lower()
                        if "severe" in low or "fatal" in low:
                            severe = line.strip()[:400]
                            break
                raise RuntimeError(
                    f"CLI exit {code}; see {log}"
                    + (f" | eplusout.err: {severe}" if severe else "")
                )
            gates = validate_job_outputs(
                job_out, max_steps=max_steps, begin=begin, end=end
            )
            job["state"] = "succeeded"
            job["gates"] = gates
            doc["completed_jobs"] = int(doc.get("completed_jobs") or 0) + 1
            doc["child_pid"] = None
            write_campaign(site, doc)
            results.append(
                {
                    "key": key,
                    "strategy_id": sid,
                    "weather_kind": kind,
                    "parquet": gates["parquet"],
                    "elapsed_s": elapsed,
                }
            )
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            job["state"] = "failed"
            doc["child_pid"] = None
            msg = str(exc)
            severe = None
            if "eplusout.err:" in msg:
                severe = msg.split("eplusout.err:", 1)[-1].strip()
            else:
                from eplus_gym.startup_diag import find_eplusout_err

                err_path = find_eplusout_err(job_out)
                if err_path is not None and err_path.is_file():
                    try:
                        err_text = err_path.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        err_text = ""
                    for line in err_text.splitlines():
                        low = line.lower()
                        if "severe" in low or "fatal" in low:
                            severe = line.strip()[:400]
                            break
            mark_failed(
                site,
                doc,
                {
                    "type": type(exc).__name__,
                    "message": msg,
                    "job_key": key,
                    "completed_jobs": int(doc.get("completed_jobs") or 0),
                    "severe_or_fatal": severe,
                },
            )
            print(f"job failed {key}: {exc}", file=sys.stderr)
            return 1

    mark_succeeded(site, doc)
    try:
        _persist_success(site, doc, results=results)
    except Exception as exc:  # noqa: BLE001
        print(f"warning: persist last_dsm_run failed: {exc}", file=sys.stderr)
    print(f"campaign {run_id} succeeded ({doc['completed_jobs']}/{doc['total_jobs']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
