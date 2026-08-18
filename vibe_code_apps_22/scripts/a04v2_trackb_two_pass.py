"""Track B two-pass sizing + ContinuityPlant scored trajectory. Never overwrite A04."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.control_v2 import arm_params, build_six_schedules_f
from eplus_gym.energyplus_cli import run_energyplus_cli
from eplus_gym.epw_stage import stage_year_aware_epw
from eplus_gym.path_sanitize import redact_obj
from eplus_gym.rl.continuity_plant import EnergyPlusContinuityPlant
from eplus_gym.rl.eplus_watchdog import EplusWatchdog, WatchdogLimits, WatchdogTimeout
from eplus_gym.rl.trackb_diagnostics import bank_group_diagnostics
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import resolve_a04_and_epw, sha256_file
from eplus_gym.stage_idf import stage_idf_for_period
from eplus_gym.trackb_banks import (
    PUBLIC_LABEL,
    assert_reference_integrity,
    nine_zone_plan,
    rewrite_parent_coils_to_autosize,
    scored_runtime_w2a_pass,
    six_group_plan,
    sizing_totals_from_eio,
)
from eplus_gym.trackb_scored_run import (
    distinct_status_fields,
    frozen_six_zone_ramp,
    rows_from_continuity_payload,
    trajectory_sha256,
    validate_scored_trackb_run,
)
from a04v2_build_trackb_banks import build_trackb_plan

FIGURES = _APP / "docs" / "audits" / "figures" / "vibe22_live_trackb_long_rl"


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def run_scored_continuity_day(
    *,
    site: Path,
    child: Path,
    epw: Path,
    day: str,
    arm: str,
    output: Path,
) -> dict:
    schedules = build_six_schedules_f(arm_params(arm))
    oat = [-10.0] * 24
    try:
        from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay

        oat = list(forecast_from_epw_replay(epw, day).temps_c)
    except Exception:  # noqa: BLE001
        pass
    watchdog = EplusWatchdog(
        output / "watchdog",
        WatchdogLimits(startup_s=1200.0, no_progress_s=600.0, overall_s=7200.0),
    )
    plant = EnergyPlusContinuityPlant(
        site_root=site,
        epw=epw,
        idf=child,
        output=output / "continuity",
        days=[day],
    )
    watchdog.heartbeat("before_start_episode")
    try:
        plant.start_episode()
        watchdog.mark_started(pid=os.getpid(), note="after_start_episode")
        payload = plant.simulate_day(schedules, oat_c=oat)
        watchdog.heartbeat("after_simulate_day")
    except WatchdogTimeout:
        plant.close()
        raise
    except Exception:
        plant.close()
        watchdog.fail_artifact("scored_day_exception")
        raise
    gate = plant.finish_quality()
    watchdog.heartbeat("after_finish_quality")
    rows = rows_from_continuity_payload(payload, expected_day=day)
    return {
        "payload": payload,
        "rows": rows,
        "gate": gate,
        "watchdog": watchdog.snapshot(),
        "n_process_starts": int(payload.get("n_process_starts") or plant.n_process_starts),
        "schedules": schedules,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default="")
    p.add_argument("--run-id", default="trackb_two_pass_base")
    p.add_argument("--begin", default="2026-01-12")
    p.add_argument("--end", default="2026-01-12")
    p.add_argument("--sensitivity", choices=("low", "base", "high"), default="base")
    p.add_argument(
        "--arm",
        choices=("continuous_70", "observed_bas_incumbent", "shallow_setback", "deep_setback"),
        default="continuous_70",
    )
    p.add_argument("--sizing-totals-json", default="", help="Reuse LIVE eio totals; skip EnergyPlus pass 1 CLI")
    args = p.parse_args()
    if str(args.begin)[:10] != str(args.end)[:10]:
        raise SystemExit("scored two-pass is one civil day; begin must equal end")
    site = require_site_root(args.site_root or None)
    idf, epw = resolve_a04_and_epw(site)
    if idf.name != A04_IDF_NAME:
        raise SystemExit(f"expected A04, got {idf.name}")
    out = site / "reports" / "eplus_gym" / "trackb_two_pass" / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    staged_epw_meta = stage_year_aware_epw(epw, out / f"staged_{epw.name}")
    staged_epw = Path(staged_epw_meta["staged_epw"])
    a04_bytes = idf.read_bytes()
    a04_sha = _sha_bytes(a04_bytes)
    auto_meta = {"n_fields_rewritten": 0, "reused_sizing_totals": False, "not_a04_overwrite": True}
    r1 = {"returncode": 0}
    engine_executed = True
    if args.sizing_totals_json:
        totals = json.loads(Path(args.sizing_totals_json).read_text(encoding="utf-8"))
        sizing_completed = True
        auto_meta["reused_sizing_totals"] = True
        _write(out / "pass1_sizing_totals.json", totals)
    else:
        autosize_text, auto_meta = rewrite_parent_coils_to_autosize(
            a04_bytes.decode("utf-8", errors="replace")
        )
        if idf.read_bytes() != a04_bytes:
            raise SystemExit("refusing to continue: A04 mutated")
        pass1 = out / "pass1_equivalent_unit"
        pass1.mkdir(parents=True, exist_ok=True)
        sizing_parent = pass1 / "sizing_parent_autosize.idf"
        sizing_parent.write_text(autosize_text, encoding="utf-8")
        staged = stage_idf_for_period(
            sizing_parent, pass1 / "staged_a04.idf", args.begin, args.end, six_zone_actuators=False, disable_sizing=False
        )
        r1 = run_energyplus_cli(idf=staged, epw=staged_epw, output=pass1 / "eplus")
        eio = pass1 / "eplus" / "eplusout.eio"
        if not eio.is_file():
            hits = list((pass1 / "eplus").rglob("eplusout.eio"))
            eio = hits[0] if hits else eio
        sizing_completed = eio.is_file()
        if not sizing_completed:
            _write(
                out / "failed.json",
                {"failed": True, "reason": "pass1_eio_missing", "run": redact_obj(r1)},
            )
            raise SystemExit("pass 1 did not write eplusout.eio")
        totals = sizing_totals_from_eio(eio.read_text(encoding="utf-8", errors="replace"))
        _write(out / "pass1_sizing_totals.json", totals)
    meta = build_trackb_plan(sensitivity=args.sensitivity, run_id=args.run_id, sizing_totals=totals)
    child = _APP / "models" / "eplus" / "a04v2_candidates" / args.run_id / meta["idf"]
    if idf.read_bytes() != a04_bytes:
        raise SystemExit("refusing to continue: A04 mutated after child build")
    pass2 = out / "pass2_banks_scored"
    scored_exc = None
    try:
        scored_live = run_scored_continuity_day(
            site=site,
            child=child,
            epw=staged_epw,
            day=str(args.begin)[:10],
            arm=str(args.arm),
            output=pass2,
        )
    except Exception as exc:  # noqa: BLE001
        scored_exc = exc
        scored_live = {
            "payload": {},
            "rows": [],
            "gate": {"completed_successfully": False, "severe_count": 0, "fatal_count": 0},
            "watchdog": {},
            "n_process_starts": 0,
        }
    rows = list(scored_live.get("rows") or [])
    gate = dict(scored_live.get("gate") or {})
    payload = dict(scored_live.get("payload") or {})
    integrity = assert_reference_integrity(
        child.read_text(encoding="utf-8", errors="replace"),
        nine_zone_plan(sensitivity=args.sensitivity),
    )
    scored = validate_scored_trackb_run(
        gate=gate,
        returncode=0 if rows else 1,
        rows=rows,
        expected_day=str(args.begin)[:10],
    )
    w2a_phase = gate.get("w2a_low_airflow_by_phase") or {}
    w2a_ok = bool(scored_runtime_w2a_pass(gate)) and bool(scored["scored_runtime_proven"])
    ramp = frozen_six_zone_ramp(payload.get("zone_temps_series_f") or {})
    quality_ok = bool(w2a_ok and ramp.get("passed") and scored["ok"] and not scored_exc)
    status = distinct_status_fields(
        engine_executed=engine_executed,
        sizing_completed=sizing_completed,
        scored_runperiod_valid=bool(scored["ok"]),
        quality_gates_passed=quality_ok,
        model_champion=False,
    )
    heating_sources = sorted({str(v.get("heating_capacity_source") or "unknown") for v in totals.values()})
    diag = bank_group_diagnostics(
        plan=six_group_plan(sensitivity=args.sensitivity),
        sizing_totals=totals,
        payload=payload,
        w2a_scored_runtime=int(w2a_phase.get("scored_runtime") or 0),
    )
    _write(out / "bank_diagnostics.json", diag)
    artifact = {
        "schema": "vibe22.trackb.one_day_artifact.v1",
        "track_b_idf_sha256": meta["idf_sha256"],
        "staged_epw_sha256": sha256_file(staged_epw),
        "parent_idf_sha256": a04_sha,
        "energyplus_version": "26.1.0",
        "requested_date": str(args.begin)[:10],
        "n_rows": len(rows),
        "first_runtime_timestamp": scored.get("first_runtime_timestamp"),
        "last_runtime_timestamp": scored.get("last_runtime_timestamp"),
        "six_finite_zone_temps": bool(scored["ok"]),
        "finite_facility_kw": bool(scored["ok"]),
        "start_zone_temps_f": payload.get("start_zone_temps_f"),
        "final_zone_temps_f": payload.get("final_zone_temps_f") or payload.get("zone_temps_f"),
        "process_identity": {"pid": os.getpid(), "run_id": args.run_id},
        "n_process_starts": int(scored_live.get("n_process_starts") or 0),
        "severe_count": int(gate.get("severe_count") or 0),
        "fatal_count": int(gate.get("fatal_count") or 0),
        "w2a_by_phase": w2a_phase,
        "trajectory_sha256": trajectory_sha256(rows) if rows else None,
        "arm": args.arm,
        "sensitivity": args.sensitivity,
    }
    _write(out / "one_day_artifact.json", artifact)
    report = {
        "schema": "vibe22.trackb.two_pass.v2",
        "public_label": PUBLIC_LABEL,
        "public_line": "MODEL DEVELOPMENT INCOMPLETE — LONG RL BLOCKED",
        "claim_labels": [
            "SIMULATION_ONLY_RL_RESEARCH",
            "NOT VALIDATED FOR OPERATIONAL DSM",
            "NO BACNET COMMAND AUTHORITY",
        ],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "parent_idf_sha256": a04_sha,
        "child_idf_sha256": meta["idf_sha256"],
        "pass1_returncode": r1["returncode"],
        "pass2_exception": None if scored_exc is None else f"{type(scored_exc).__name__}:{scored_exc}",
        "eplus_quality": gate,
        "scored_runtime_w2a_pass": w2a_ok,
        "scored_runperiod": scored,
        "frozen_ramp": ramp,
        "year_aware_epw_sha256": sha256_file(staged_epw),
        "reference_integrity": integrity,
        "track_b_live_energyplus_executed": engine_executed,
        "track_b_completed": False,
        "champion": None,
        "long_campaign_allowed": False,
        "sizing_provenance": "live_energyplus_eio_component_sizing",
        "heating_capacity_source": heating_sources,
        "heating_capacity_note": (
            "Pass 1 uses a sizing-only A04 child with heating/cooling/fan/ZoneHVAC airflow "
            "rewritten to Autosize. Immutable A04 is not overwritten."
        ),
        "autosize_rewrite": auto_meta,
        "one_day_artifact": artifact,
        "watchdog": scored_live.get("watchdog"),
        **status,
    }
    compact = redact_obj(report)
    _write(out / "two_pass_report.json", compact)
    git_out = FIGURES / args.run_id
    git_out.mkdir(parents=True, exist_ok=True)
    _write(git_out / "two_pass_report.json", compact)
    _write(git_out / "pass1_sizing_totals.json", totals)
    _write(git_out / "one_day_artifact.json", artifact)
    _write(git_out / "bank_diagnostics.json", diag)
    params_path = child.parent / "parameters.json"
    if params_path.is_file():
        params = json.loads(params_path.read_text(encoding="utf-8"))
        params["track_b_live_energyplus_executed"] = engine_executed
        params["track_b_completed"] = False
        params["scored_runperiod_valid"] = bool(scored["ok"])
        gates = params.get("champion_gates") or {}
        g = dict(gates.get("gates") or {})
        g["energyplus_success"] = "engine_executed" if engine_executed else "engine_not_executed"
        g["zero_severe_fatal"] = (
            "fail" if int(gate.get("severe_count") or 0) or int(gate.get("fatal_count") or 0) else "pass"
        )
        g["zero_scored_runtime_w2a"] = "pass" if scored_runtime_w2a_pass(gate) else "fail"
        gates["gates"] = g
        params["champion_gates"] = gates
        params_path.write_text(json.dumps(params, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "pass1_returncode": r1["returncode"],
                "scored_runperiod_valid": scored["ok"],
                "n_rows": len(rows),
                "scored_runtime_w2a_pass": w2a_ok,
                "engine_executed": engine_executed,
                "sizing_completed": sizing_completed,
                "quality_gates_passed": quality_ok,
                "model_champion": False,
                "public_label": PUBLIC_LABEL,
            },
            indent=2,
        )
    )
    if scored_exc is not None:
        return 1
    if int(gate.get("severe_count") or 0) or int(gate.get("fatal_count") or 0):
        return 1
    if len(rows) != 96 or not scored["ok"]:
        return 1
    if int(scored_live.get("n_process_starts") or 0) != 1:
        return 1
    if not w2a_ok:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
