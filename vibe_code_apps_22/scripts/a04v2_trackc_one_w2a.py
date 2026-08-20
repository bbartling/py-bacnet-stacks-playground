"""Track C1/C2 sequential candidate: one W2A per zone. Never overwrite A04."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.a04_identity import A04_IDF_NAME, A04_SHA_ALLOWED, A04_SHA_LF
from eplus_gym.energyplus_cli import run_energyplus_cli
from eplus_gym.eplus_err import parse_eplus_err, scored_runtime_w2a_count
from eplus_gym.epw_stage import stage_year_aware_epw
from eplus_gym.idf_diagnostics import aggregate_heating_capacity_w, count_w2a_objects
from eplus_gym.site_env import require_site_root
from eplus_gym.site_pins import resolve_a04_and_epw
from eplus_gym.stage_idf import stage_idf_for_period
from eplus_gym.trackb_banks import sizing_totals_from_eio
from eplus_gym.trackc_one_w2a import (
    PUBLIC_LABEL,
    freeze_explicit_from_eio,
    hard_size_heating,
    one_w2a_per_zone_ok,
    prepare_c1_autosize_parent,
    trackc_plan,
)

A04 = _APP / "models" / "eplus" / A04_IDF_NAME


def _write(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--site-root", default="")
    p.add_argument("--variant", choices=("c1", "c2"), default="c1")
    p.add_argument("--sensitivity", choices=("low", "base", "high"), default="base")
    p.add_argument("--day", default="2026-01-12")
    p.add_argument("--run-id", default="trackc_c1_20260112")
    args = p.parse_args()
    site = require_site_root(args.site_root or None)
    idf, epw = resolve_a04_and_epw(site)
    pinned = site / "eplus" / "weather" / "madison_amy_202508_202608.epw"
    if pinned.is_file():
        epw = pinned
    raw = A04.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    lf = hashlib.sha256(raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
    if digest not in A04_SHA_ALLOWED and lf != A04_SHA_LF:
        raise SystemExit("refusing to patch: A04 hash mismatch")
    if idf.read_bytes() != raw and idf.resolve() != A04.resolve():
        raw_site = idf.read_bytes()
        digest_s = hashlib.sha256(raw_site).hexdigest()
        lf_s = hashlib.sha256(raw_site.replace(b"\r\n", b"\n").replace(b"\r", b"\n")).hexdigest()
        if digest_s not in A04_SHA_ALLOWED and lf_s != A04_SHA_LF:
            raise SystemExit("site A04 hash mismatch")
        raw = raw_site
    text = raw.decode("utf-8", errors="replace")
    if not one_w2a_per_zone_ok(text):
        raise SystemExit("A04 parent is not one W2A per zone; refusing Track C")
    out = site / "reports" / "eplus_gym" / "final_physics" / args.run_id
    out.mkdir(parents=True, exist_ok=True)
    child_dir = _APP / "models" / "eplus" / "a04v2_candidates" / args.run_id
    child_dir.mkdir(parents=True, exist_ok=True)
    child = child_dir / "lakeside_w2a_trackc_child.idf"
    plan = trackc_plan(sensitivity=args.sensitivity)
    staged_epw = stage_year_aware_epw(epw, out / f"staged_{epw.name}")
    epw_path = Path(staged_epw["staged_epw"])
    if args.variant == "c1":
        autosize_text, auto_meta = prepare_c1_autosize_parent(text)
        sizing_idf = out / "sizing_parent_autosize.idf"
        sizing_idf.write_text(autosize_text, encoding="utf-8")
        staged = stage_idf_for_period(
            sizing_idf, out / "staged_sizing.idf", args.day, args.day, disable_sizing=False
        )
        r1 = run_energyplus_cli(idf=staged, epw=epw_path, output=out / "sizing", timeout_s=7200)
        eio = out / "sizing" / "eplusout.eio"
        if not eio.is_file():
            _write(out / "failed.json", {"reason": "c1_eio_missing", "returncode": r1["returncode"]})
            return 2
        totals = sizing_totals_from_eio(eio.read_text(encoding="utf-8", errors="replace"))
        _write(out / "sizing_totals.json", totals)
        frozen = freeze_explicit_from_eio(text, totals)
        child.write_text(frozen, encoding="utf-8")
        meta_extra = {"autosize": auto_meta, "sizing_returncode": r1["returncode"]}
    else:
        frozen = hard_size_heating(text, sensitivity=args.sensitivity)
        child.write_text(frozen, encoding="utf-8")
        totals = None
        meta_extra = {"c2_hard_sized": True}
        r1 = {"returncode": 0}
    if A04.read_bytes() != raw and idf.resolve() == A04.resolve():
        raise SystemExit("A04 mutated")
    data = child.read_bytes()
    scored_idf = stage_idf_for_period(child, out / "staged_child.idf", args.day, args.day)
    r2 = run_energyplus_cli(idf=scored_idf, epw=epw_path, output=out / "one_day", extra_args=["-r"], timeout_s=7200)
    src = child.read_text(encoding="utf-8", errors="replace")
    err_path = out / "one_day" / "eplusout.err"
    gate = parse_eplus_err(err_path) if err_path.is_file() else {}
    w2a_phase = gate.get("w2a_low_airflow_by_phase") or {}
    scored_w2a = scored_runtime_w2a_count(gate) if gate else None
    blockers = []
    if scored_w2a not in (0,):
        blockers.append("w2a_scored_runtime_not_zero")
    meta = {
        "schema": "vibe22.trackc.candidate.v1",
        "run_id": args.run_id,
        "variant": args.variant,
        "public_label": PUBLIC_LABEL,
        "parent": A04_IDF_NAME,
        "idf": str(child),
        "idf_sha256": hashlib.sha256(data).hexdigest(),
        "one_w2a_per_zone": one_w2a_per_zone_ok(src),
        "object_counts": count_w2a_objects(src),
        "aggregate_heating_capacity_w": aggregate_heating_capacity_w(src),
        "one_day_returncode": r2["returncode"],
        "plan": plan,
        **meta_extra,
        "w2a_raw_err": {
            "scored_runtime": scored_w2a,
            "warmup": w2a_phase.get("warmup"),
            "sizing": w2a_phase.get("sizing"),
            "total": int(w2a_phase.get("warmup") or 0)
            + int(w2a_phase.get("sizing") or 0)
            + int(w2a_phase.get("scored_runtime") or scored_w2a or 0),
        },
        "severe_count": gate.get("severe_count"),
        "fatal_count": gate.get("fatal_count"),
        "champion": False,
        "SIMULATION_TRAINING_READY": False,
        "champion_blockers": blockers,
        "three_day_live_screen": bool(scored_w2a == 0),
        "three_day_skip_reason": None
        if scored_w2a == 0
        else "scored-runtime W2A != 0 on the instrumented development day",
    }
    _write(child_dir / "parameters.json", meta)
    _write(out / "trackc_meta.json", meta)
    fig = _APP / "docs" / "audits" / "figures" / "vibe22_final_physics_rl" / f"{args.run_id}.json"
    _write(fig, meta)
    print(json.dumps({k: meta[k] for k in meta if k != "plan"}, indent=2, default=str))
    return 0 if r2["returncode"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
