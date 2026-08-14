"""Disk-backed DSM campaign supervisor state + job gates.

Streamlit starts ``scripts/run_dsm_campaign.py`` once via Popen; that CLI is the
only writer of ``current_dsm_run.json`` / ``campaign_status.json`` transitions.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from eplus_gym.month_calendar import DEPLOYABLE_STRATEGIES
from eplus_gym_app.dsm_console import live_run_jobs
from eplus_gym_app.weather_files import KIND_AMY, KIND_TMY_MSN

SCHEMA_VERSION = 1
ACTIVE_STATES = frozenset({"preflight", "queued", "starting", "running"})
TERMINAL_STATES = frozenset({"succeeded", "failed", "cancelled"})
DEFAULT_JOB_TIMEOUT_S = 6 * 3600
HEARTBEAT_STALE_S = 90.0
SCORECARD_TOL_KW = 0.05
SCORECARD_TOL_KWH = 0.25


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def eplus_gym_dir(site: Path) -> Path:
    return Path(site) / "reports" / "eplus_gym"


def current_run_path(site: Path) -> Path:
    return eplus_gym_dir(site) / "current_dsm_run.json"


def last_run_path(site: Path) -> Path:
    return eplus_gym_dir(site) / "last_dsm_run.json"


def cancel_request_path(site: Path) -> Path:
    return eplus_gym_dir(site) / "cancel_dsm_run.request"


def campaign_status_path(site: Path, run_id: str) -> Path:
    return eplus_gym_dir(site) / "runs" / run_id / "campaign_status.json"


def atomic_write_json(path: Path, doc: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(doc, indent=2, default=str) + "\n"
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def read_json(path: Path) -> dict[str, Any] | None:
    path = Path(path)
    if not path.is_file():
        return None
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return doc if isinstance(doc, dict) else None


def pid_alive(pid: int | None) -> bool:
    if pid is None or int(pid) <= 0:
        return False
    pid = int(pid)
    try:
        if os.name == "nt":
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                return False
            try:
                code = ctypes.c_ulong()
                if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code)) == 0:
                    return False
                return int(code.value) == STILL_ACTIVE
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)
        else:
            os.kill(pid, 0)
            return True
    except OSError:
        return False


def elapsed_seconds(doc: dict[str, Any], *, now: float | None = None) -> float:
    """Live elapsed while running; freeze on finished_at when terminal."""
    started = doc.get("started_at") or doc.get("created_at")
    if not started:
        return 0.0
    try:
        t0 = datetime.fromisoformat(str(started).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0
    finished = doc.get("finished_at")
    state = str(doc.get("state") or "")
    if finished and state in TERMINAL_STATES:
        try:
            t1 = datetime.fromisoformat(str(finished).replace("Z", "+00:00")).timestamp()
            return max(0.0, t1 - t0)
        except ValueError:
            pass
    now_ts = time.time() if now is None else float(now)
    return max(0.0, now_ts - t0)


def default_strategy_selection(selected: str | None = None) -> list[str]:
    """Baseline + one selected strategy (default deep_setback)."""
    pick = selected or "deep_setback"
    if pick not in DEPLOYABLE_STRATEGIES:
        pick = "deep_setback"
    if pick == "baseline":
        return ["baseline"]
    return ["baseline", pick]


def build_jobs(
    *,
    strategies: list[str],
    weather_mode: str,
    amy: Path | None,
    tmy: Path | None,
    begin: str,
    end: str,
    max_steps: int,
) -> list[dict[str, Any]]:
    weathers: list[tuple[str, Path]] = []
    mode = (weather_mode or "AMY").strip()
    if mode == "TMY":
        if tmy is not None:
            weathers.append((KIND_TMY_MSN, Path(tmy)))
        elif amy is not None:
            weathers.append((KIND_AMY, Path(amy)))
    elif mode == "Both":
        if amy is not None:
            weathers.append((KIND_AMY, Path(amy)))
        if tmy is not None:
            weathers.append((KIND_TMY_MSN, Path(tmy)))
    else:
        if amy is not None:
            weathers.append((KIND_AMY, Path(amy)))
    return live_run_jobs(
        strategies=list(strategies),
        weathers=weathers,
        begin=begin,
        end=end,
        max_steps=max_steps,
    )


def new_campaign_doc(
    *,
    run_id: str,
    site: Path,
    idf: Path,
    idf_sha256: str,
    begin: str,
    end: str,
    max_steps: int,
    n_days: int,
    strategies: list[str],
    weather_mode: str,
    jobs: list[dict[str, Any]],
    epw_meta: list[dict[str, Any]],
    preset: str,
    peak_day: str,
    git_sha: str | None = None,
    supervisor_pid: int | None = None,
) -> dict[str, Any]:
    now = utc_now_iso()
    serial_jobs = []
    for j in jobs:
        serial_jobs.append(
            {
                "strategy_id": j["strategy_id"],
                "weather_kind": j["weather_kind"],
                "epw": str(j["epw"]),
                "begin": j["begin"],
                "end": j["end"],
                "max_steps": int(j["max_steps"]),
                "key": j["key"],
                "state": "queued",
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "site": str(site),
        "state": "preflight",
        "created_at": now,
        "started_at": now,
        "finished_at": None,
        "heartbeat_at": now,
        "supervisor_pid": supervisor_pid or os.getpid(),
        "child_pid": None,
        "completed_jobs": 0,
        "total_jobs": len(serial_jobs),
        "jobs": serial_jobs,
        "idf": str(idf),
        "idf_sha256": idf_sha256,
        "epws": epw_meta,
        "begin": str(begin)[:10],
        "end": str(end)[:10],
        "n_days": int(n_days),
        "max_steps": int(max_steps),
        "strategies": list(strategies),
        "weather_mode": weather_mode,
        "preset": preset,
        "peak_day": peak_day,
        "git_sha": git_sha,
        "log": None,
        "error": None,
        "cancel_requested": False,
    }


def write_campaign(site: Path, doc: dict[str, Any]) -> None:
    doc = dict(doc)
    doc["heartbeat_at"] = utc_now_iso()
    atomic_write_json(current_run_path(site), doc)
    run_id = str(doc.get("run_id") or "")
    if run_id:
        atomic_write_json(campaign_status_path(site, run_id), doc)


def request_cancel(site: Path) -> Path:
    path = cancel_request_path(site)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(utc_now_iso(), encoding="utf-8")
    doc = read_json(current_run_path(site))
    if doc and str(doc.get("state") or "") in ACTIVE_STATES:
        doc["cancel_requested"] = True
        write_campaign(site, doc)
    return path


def cancel_requested(site: Path) -> bool:
    if cancel_request_path(site).is_file():
        return True
    doc = read_json(current_run_path(site))
    return bool(doc and doc.get("cancel_requested"))


def clear_cancel_request(site: Path) -> None:
    cancel_request_path(site).unlink(missing_ok=True)


def active_campaign_running(site: Path) -> dict[str, Any] | None:
    doc = read_json(current_run_path(site))
    if not doc:
        return None
    state = str(doc.get("state") or "")
    if state not in ACTIVE_STATES:
        return None
    if pid_alive(doc.get("supervisor_pid")) or pid_alive(doc.get("child_pid")):
        return doc
    return None


def reconcile_campaign(site: Path, *, now: float | None = None) -> dict[str, Any] | None:
    """Mark stale active campaigns failed when heartbeat is dead and no PIDs."""
    doc = read_json(current_run_path(site))
    if not doc:
        return None
    state = str(doc.get("state") or "")
    if state not in ACTIVE_STATES:
        return doc
    hb = doc.get("heartbeat_at") or doc.get("started_at")
    stale = True
    if hb:
        try:
            t_hb = datetime.fromisoformat(str(hb).replace("Z", "+00:00")).timestamp()
            age = (time.time() if now is None else float(now)) - t_hb
            stale = age > HEARTBEAT_STALE_S
        except ValueError:
            stale = True
    alive = pid_alive(doc.get("supervisor_pid")) or pid_alive(doc.get("child_pid"))
    if stale and not alive:
        doc["state"] = "failed"
        doc["finished_at"] = utc_now_iso()
        doc["error"] = {
            "type": "StaleCampaign",
            "message": (
                "Campaign marked failed: heartbeat stale and supervisor/E+ PIDs not alive. "
                f"completed_jobs={doc.get('completed_jobs', 0)}/{doc.get('total_jobs', 0)}."
            ),
        }
        write_campaign(site, doc)
    return doc


def collect_traj(out_dir: Path) -> Path | None:
    out_dir = Path(out_dir)
    frames = sorted(out_dir.glob("traj_*.parquet"))
    if not frames and (out_dir / "runs").is_dir():
        frames = sorted((out_dir / "runs").glob("*.parquet"))
    return frames[0] if frames else None


def validate_job_outputs(
    out_dir: Path,
    *,
    max_steps: int,
    begin: str,
    end: str,
) -> dict[str, Any]:
    """BOPTEST-style gates before incrementing completed_jobs."""
    out_dir = Path(out_dir)
    pq = collect_traj(out_dir)
    if pq is None:
        raise ValueError(f"no trajectory parquet under {out_dir}")
    df = pd.read_parquet(pq)
    if df is None or getattr(df, "empty", True):
        raise ValueError("trajectory is empty")
    if "facility_kw" not in df.columns:
        raise ValueError("trajectory missing facility_kw")
    kw = pd.to_numeric(df["facility_kw"], errors="coerce")
    if not kw.notna().any() or not bool((~kw.isna()).all() or kw.notna().sum() > 0):
        raise ValueError("facility_kw has no finite values")
    if not bool(kw.replace([float("inf"), float("-inf")], pd.NA).notna().all()):
        # allow NaN-free finite check
        if (~kw.apply(lambda x: x == x and abs(x) != float("inf"))).any():  # noqa: PLR0124
            bad = (~kw.apply(lambda x: isinstance(x, (int, float)) and x == x and abs(float(x)) != float("inf"))).sum()
            if bad:
                raise ValueError("facility_kw has non-finite values")

    n = len(df)
    # Allow ±1 row slack for E+ boundary quirks; reject huge under/over.
    if n < max(1, int(max_steps) - 1) or n > int(max_steps) + 4:
        raise ValueError(
            f"trajectory row count {n} != expected ~{max_steps} for {begin}→{end}"
        )

    # Reject design-day / synthetic contamination when day stamps exist.
    if "day" in df.columns:
        days = sorted({str(d)[:10] for d in df["day"].astype(str) if str(d)[:10]})
        if days:
            if days[0] < str(begin)[:10] or days[-1] > str(end)[:10]:
                raise ValueError(
                    f"trajectory day stamps {days[0]}→{days[-1]} outside requested "
                    f"{begin}→{end} (possible design-day contamination)"
                )
            # Classic EnergyPlus design-day marker years
            if any(d.startswith("1900-") or d.startswith("0001-") for d in days):
                raise ValueError(
                    f"trajectory day stamps look like design-day ({days[:3]}); rejecting"
                )

    peak = float(kw.max())
    kwh = float(kw.sum() * 0.25)
    card = out_dir / "rule_dr_scorecard.json"
    if card.is_file():
        try:
            doc = json.loads(card.read_text(encoding="utf-8"))
            rows = doc.get("strategies") or []
            if rows:
                sc_peak = rows[0].get("peak_kw")
                sc_kwh = rows[0].get("kwh")
                if sc_peak is not None and abs(float(sc_peak) - peak) > SCORECARD_TOL_KW:
                    raise ValueError(
                        f"scorecard peak_kw {sc_peak} != traj {peak} (tol {SCORECARD_TOL_KW})"
                    )
                if sc_kwh is not None and abs(float(sc_kwh) - kwh) > SCORECARD_TOL_KWH:
                    raise ValueError(
                        f"scorecard kwh {sc_kwh} != traj {kwh} (tol {SCORECARD_TOL_KWH})"
                    )
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            if "scorecard" in str(exc) or "traj" in str(exc):
                raise
            raise ValueError(f"scorecard unreadable: {exc}") from exc

    return {
        "parquet": str(pq),
        "n_rows": n,
        "peak_kw": peak,
        "kwh": kwh,
        "days": (
            sorted({str(d)[:10] for d in df["day"].astype(str)})
            if "day" in df.columns
            else []
        ),
    }


def mark_failed(site: Path, doc: dict[str, Any], error: dict[str, Any] | str) -> dict[str, Any]:
    doc = dict(doc)
    doc["state"] = "failed"
    doc["finished_at"] = utc_now_iso()
    if isinstance(error, str):
        doc["error"] = {"type": "CampaignError", "message": error}
    else:
        doc["error"] = error
    write_campaign(site, doc)
    return doc


def mark_cancelled(site: Path, doc: dict[str, Any]) -> dict[str, Any]:
    doc = dict(doc)
    doc["state"] = "cancelled"
    doc["finished_at"] = utc_now_iso()
    doc["error"] = {"type": "Cancelled", "message": "Cancel requested"}
    write_campaign(site, doc)
    clear_cancel_request(site)
    return doc


def mark_succeeded(site: Path, doc: dict[str, Any]) -> dict[str, Any]:
    doc = dict(doc)
    doc["state"] = "succeeded"
    doc["finished_at"] = utc_now_iso()
    doc["error"] = None
    write_campaign(site, doc)
    return doc


def peak_day_smoke_ok(
    site: Path,
    *,
    idf_sha256: str,
    epw_sha256: str | None = None,
) -> bool:
    """True if a prior successful peak-day campaign matches these hashes."""
    for path in (current_run_path(site), last_run_path(site)):
        doc = read_json(path)
        if not doc:
            continue
        if str(doc.get("state") or "") not in {"succeeded", ""} and path == current_run_path(site):
            if str(doc.get("state") or "") != "succeeded":
                continue
        # last_dsm_run may lack state; treat presence of peak-day period + matching hashes
        preset = str(doc.get("preset") or "")
        n_days = doc.get("n_days") or doc.get("window_n")
        if preset and preset != "Peak day" and int(n_days or 0) != 1:
            continue
        if doc.get("idf_sha256") and str(doc["idf_sha256"]).lower() != idf_sha256.lower():
            continue
        if epw_sha256:
            epws = doc.get("epws") or []
            hashes = [str(e.get("sha256") or "").lower() for e in epws if isinstance(e, dict)]
            if hashes and epw_sha256.lower() not in hashes:
                # also accept epw_sha256 field on last_dsm_run
                if str(doc.get("epw_sha256") or "").lower() != epw_sha256.lower():
                    continue
        if path == last_run_path(site) or str(doc.get("state")) == "succeeded":
            return True
    return False
