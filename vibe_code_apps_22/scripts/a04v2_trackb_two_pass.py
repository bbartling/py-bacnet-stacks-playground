"""Track B two-pass sizing + short-weather smoke. Never overwrite A04."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME
from eplus_gym.eplus_err import parse_eplus_err
from eplus_gym.energyplus_cli import run_energyplus_cli
from eplus_gym.path_sanitize import redact_obj
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import resolve_a04_and_epw, sha256_file
from eplus_gym.stage_idf import stage_idf_for_period
from eplus_gym.trackb_banks import (
    PUBLIC_LABEL,
    assert_reference_integrity,
    nine_zone_plan,
    scored_runtime_w2a_pass,
    sizing_totals_from_eio,
)
from a04v2_build_trackb_banks import build_trackb_plan


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default="")
    p.add_argument("--run-id", default="trackb_two_pass_base")
    p.add_argument("--begin", default="2026-01-12")
    p.add_argument("--end", default="2026-01-12")
    args = p.parse_args()
    site = require_site_root(args.site_root or None)
    idf, epw = resolve_a04_and_epw(site)
    if idf.name != A04_IDF_NAME:
        raise SystemExit(f"expected A04, got {idf.name}")
    out = site / "reports" / "eplus_gym" / "trackb_two_pass" / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    pass1 = out / "pass1_equivalent_unit"
    staged = stage_idf_for_period(
        idf, pass1 / "staged_a04.idf", args.begin, args.end, six_zone_actuators=False, disable_sizing=False
    )
    r1 = run_energyplus_cli(idf=staged, epw=epw, output=pass1 / "eplus")
    eio = pass1 / "eplus" / "eplusout.eio"
    if not eio.is_file():
        hits = list((pass1 / "eplus").rglob("eplusout.eio"))
        eio = hits[0] if hits else eio
    if not eio.is_file():
        (out / "failed.json").write_text(
            json.dumps({"failed": True, "reason": "pass1_eio_missing", "run": redact_obj(r1)}, indent=2) + "\n",
            encoding="utf-8",
        )
        raise SystemExit("pass 1 did not write eplusout.eio")
    totals = sizing_totals_from_eio(eio.read_text(encoding="utf-8", errors="replace"))
    (out / "pass1_sizing_totals.json").write_text(json.dumps(totals, indent=2) + "\n", encoding="utf-8")
    meta = build_trackb_plan(sensitivity="base", run_id=args.run_id, sizing_totals=totals)
    child = _APP / "models" / "eplus" / "a04v2_candidates" / args.run_id / meta["idf"]
    pass2 = out / "pass2_banks_smoke"
    staged2 = stage_idf_for_period(child, pass2 / "staged_trackb.idf", args.begin, args.end, six_zone_actuators=True)
    r2 = run_energyplus_cli(idf=staged2, epw=epw, output=pass2 / "eplus")
    err_hits = list((pass2 / "eplus").rglob("eplusout.err"))
    gate = parse_eplus_err(err_hits[0]) if err_hits else {"completed_successfully": False}
    integrity = assert_reference_integrity(child.read_text(encoding="utf-8", errors="replace"), nine_zone_plan())
    pass2_completed = bool(gate.get("completed_successfully")) and r2["returncode"] in (0, 1)
    heating_sources = sorted({str(v.get("heating_capacity_source") or "unknown") for v in totals.values()})
    report = {
        "schema": "vibe22.trackb.two_pass.v1",
        "public_label": PUBLIC_LABEL,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "parent_idf_sha256": sha256_file(idf),
        "child_idf_sha256": meta["idf_sha256"],
        "pass1_returncode": r1["returncode"],
        "pass2_returncode": r2["returncode"],
        "eplus_quality": gate,
        "scored_runtime_w2a_pass": scored_runtime_w2a_pass(gate),
        "reference_integrity": integrity,
        "track_b_live_energyplus_executed": pass2_completed,
        "track_b_completed": False,
        "champion": None,
        "long_campaign_allowed": False,
        "sizing_provenance": "live_energyplus_eio_component_sizing",
        "heating_capacity_source": heating_sources,
        "heating_capacity_note": (
            "A04 parent heating coils report User-Specified Rated Heating Capacity "
            "(149430 W every zone). Airflow is Design Size. Banks split those eio totals; "
            "this is not as-built tonnage."
        ),
    }
    compact = redact_obj(report)
    (out / "two_pass_report.json").write_text(json.dumps(compact, indent=2) + "\n", encoding="utf-8")
    git_out = _APP / "docs" / "audits" / "figures" / "vibe22_repair" / "trackb_two_pass"
    git_out.mkdir(parents=True, exist_ok=True)
    (git_out / "two_pass_report.json").write_text(json.dumps(compact, indent=2) + "\n", encoding="utf-8")
    (git_out / "pass1_sizing_totals.json").write_text(json.dumps(totals, indent=2) + "\n", encoding="utf-8")
    plan_path = _APP / "docs" / "audits" / "figures" / "a04v2" / "trackB" / "plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["track_b_structural_validation_passed"] = bool(integrity.get("ok"))
    plan["track_b_live_energyplus_executed"] = pass2_completed
    plan["track_b_executed"] = pass2_completed
    plan["track_b_completed"] = False
    plan["track_b_failed_honestly"] = False
    plan["status"] = (
        "live_two_pass_executed_no_champion" if pass2_completed else "live_two_pass_ran_but_pass2_did_not_complete"
    )
    plan["reason"] = (
        "Track B two-pass LIVE EnergyPlus ran. Banks split live eio totals. "
        "Heating capacity on A04 is user-specified 149430 W/zone, not autosized demand. "
        "No champion. Do not start long RL."
        if pass2_completed
        else "Track B pass2 EnergyPlus did not complete successfully. No champion. Do not start long RL."
    )
    plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    params_path = child.parent / "parameters.json"
    if params_path.is_file():
        params = json.loads(params_path.read_text(encoding="utf-8"))
        params["track_b_live_energyplus_executed"] = pass2_completed
        params["track_b_completed"] = False
        gates = params.get("champion_gates") or {}
        g = dict(gates.get("gates") or {})
        g["energyplus_success"] = "pass2_completed_successfully" if pass2_completed else "pass2_did_not_complete"
        g["zero_severe_fatal"] = "fail" if int(gate.get("severe_count") or 0) or int(gate.get("fatal_count") or 0) else "pass"
        g["zero_scored_runtime_w2a"] = "pass" if scored_runtime_w2a_pass(gate) else "fail"
        gates["gates"] = g
        params["champion_gates"] = gates
        params_path.write_text(json.dumps(params, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("pass1_returncode", "pass2_returncode", "scored_runtime_w2a_pass", "track_b_live_energyplus_executed", "public_label")}, indent=2))
    if r1["returncode"] not in (0, 1) or r2["returncode"] not in (0, 1) or not pass2_completed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
