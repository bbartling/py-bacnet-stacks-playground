#!/usr/bin/env python3
"""Gas G14 ladder: patch → DinD sim → score → publish Twin iterations (any site).

Uses workspace ``patch_reheat_envelope.py`` + product ``wattlab score-monthly`` /
``publish_run_for_studio``. Stamp ``hypothesis`` on each ``run_manifest.json`` so
Studio Twin **Iteration history** shows the knob story.

Not Liberty-hardcoded — pass --src / --bills / --epw / ladder JSON.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from wattlab.energyplus.docker import run_energyplus
from wattlab.energyplus.score_monthly import score_monthly_run
from wattlab.studio.ep_viz import publish_run_for_studio


def _load_patch_mod(path: Path):
    spec = importlib.util.spec_from_file_location("patch_reheat_envelope", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _load_g14(path: Path):
    spec = importlib.util.spec_from_file_location("score_g14_monthly", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def run_one(
    *,
    run_id: str,
    idf: Path,
    epw: Path,
    bills: Path,
    area_ft2: float,
    hypothesis: str,
    art_root: Path,
    g14,
) -> dict:
    art = art_root / f"out_{run_id}"
    if art.exists():
        shutil.rmtree(art)
    art.mkdir(parents=True)
    out = art / "output"
    runs = Path(f"/data/runs/{run_id}")
    runs.mkdir(parents=True, exist_ok=True)

    print(f"SIM {run_id}", flush=True)
    cp = run_energyplus(idf, epw, out, timeout=900, progress_dir=runs)
    err = (out / "eplusout.err").read_text(errors="replace") if (out / "eplusout.err").is_file() else ""
    sev = len(re.findall(r"\*\* Severe", err))
    fat = len(re.findall(r"\*\*  Fatal", err))
    ok = cp.returncode == 0 and (out / "eplusout.csv").is_file() and fat == 0

    # Stage tree for publish: eplusout + model.idf
    stage = art / "publish_stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    if (out / "eplusout.csv").is_file():
        shutil.copy2(out / "eplusout.csv", stage / "eplusout.csv")
    if (out / "eplusout.err").is_file():
        shutil.copy2(out / "eplusout.err", stage / "eplusout.err")
    shutil.copy2(idf, stage / "model.idf")

    scorecard = None
    g14_score = None
    if ok:
        scorecard = score_monthly_run(
            stage / "eplusout.csv",
            bills,
            area_ft2=area_ft2,
            run_id=run_id,
        )
        (stage / "scorecard.json").write_text(json.dumps(scorecard, indent=2) + "\n")
        g14_score = g14.score(stage / "eplusout.csv", bills)
        g14_score["g14_pass"] = bool(g14_score["elec_pass"] and g14_score["gas_pass"])
        (stage / "g14_score.json").write_text(json.dumps(g14_score, indent=2) + "\n")
        # Twin tip G14 charts read calibration_scorecard.json (utility_bills.stats_*),
        # not our g14_score.json / wattlab_report.g14 shape.
        cal = _load_g14(Path(__file__).resolve().parent / "write_calibration_scorecard.py")
        (stage / "calibration_scorecard.json").write_text(
            json.dumps(cal.g14_to_calibration_scorecard(g14_score), indent=2) + "\n"
        )

    man = {
        "run_id": run_id,
        "hypothesis": hypothesis,
        "weather": str(epw),
        "status": "SUCCESS" if ok else "FAIL",
        "severe": sev,
        "fatal": fat,
        "rc": cp.returncode,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "elec_pass": g14_score["elec_pass"] if g14_score else None,
        "gas_pass": g14_score["gas_pass"] if g14_score else None,
        "g14_pass": g14_score["g14_pass"] if g14_score else None,
        "gas_nmbe_pct": g14_score["gas"]["nmbe_pct"] if g14_score else None,
        "gas_cvrmse_pct": g14_score["gas"]["cvrmse_pct"] if g14_score else None,
        "elec_nmbe_pct": g14_score["elec"]["nmbe_pct"] if g14_score else None,
        "elec_cvrmse_pct": g14_score["elec"]["cvrmse_pct"] if g14_score else None,
        "annual_gas_delta_pct": g14_score["annual_gas_delta_pct"] if g14_score else None,
        "annual_elec_delta_pct": g14_score["annual_elec_delta_pct"] if g14_score else None,
        "model_eui_kbtu_ft2": scorecard.get("model_site_eui") if scorecard else None,
    }
    (stage / "run_manifest.json").write_text(json.dumps(man, indent=2) + "\n")

    report = {
        "run_id": run_id,
        "hypothesis": hypothesis,
        "scorecard": scorecard,
        "g14": g14_score,
        "model_eui_kbtu_ft2": man["model_eui_kbtu_ft2"],
    }
    (stage / "wattlab_report.json").write_text(json.dumps(report, indent=2) + "\n")

    publish_run_for_studio(stage, run_id=run_id, report=report)
    # ensure hypothesis survives publish overwrite
    dest = Path(f"/data/runs/{run_id}")
    if (dest / "run_manifest.json").is_file():
        existing = json.loads((dest / "run_manifest.json").read_text())
        existing.update({k: v for k, v in man.items() if v is not None})
        (dest / "run_manifest.json").write_text(json.dumps(existing, indent=2) + "\n")
    for name in (
        "g14_score.json",
        "scorecard.json",
        "wattlab_report.json",
        "calibration_scorecard.json",
    ):
        if (stage / name).is_file():
            shutil.copy2(stage / name, dest / name)

    print(json.dumps(man, indent=2), flush=True)
    return man


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="Base IDF (e.g. dial_r4)")
    ap.add_argument("--epw", required=True)
    ap.add_argument("--bills", required=True)
    ap.add_argument("--area-ft2", type=float, required=True)
    ap.add_argument("--ladder-json", required=True, help="List of step dicts")
    ap.add_argument(
        "--patch-script",
        default="/data/tools/patch_reheat_envelope.py",
    )
    ap.add_argument(
        "--g14-script",
        default="/data/tools/score_g14_monthly.py",
    )
    ap.add_argument(
        "--art-root",
        default="/data/.artifacts/geo_b100_6fl_glass",
        help="Run outputs / metas (not the tool scripts)",
    )
    ap.add_argument("--idf-out-dir", default="/data/uploads/prototypes")
    args = ap.parse_args()

    patch_mod = _load_patch_mod(Path(args.patch_script))
    g14 = _load_g14(Path(args.g14_script))
    steps = json.loads(Path(args.ladder_json).read_text())
    results = []
    for step in steps:
        run_id = step["run_id"]
        dst = Path(args.idf_out_dir) / f"{run_id}.idf"
        meta = patch_mod.patch(
            Path(args.src),
            dst,
            sat_c=step.get("sat_c"),
            sat_winter_c=step.get("sat_winter_c"),
            sat_summer_c=step.get("sat_summer_c"),
            window_u=step["window_u"],
            window_shgc=step.get("window_shgc", 0.45),
            infil_mult_on_current=step.get("infil_mult", 1.0),
            hw_loop_c=step.get("hw_c"),
            insulation_cond_mult=step.get("insulation_cond_mult", 1.0),
            oa_per_person_mult=step.get("oa_per_person_mult", 1.0),
            winter_oa_earlier=bool(step.get("winter_oa_earlier", False)),
            require_hits=True,
        )
        meta_path = Path(args.art_root) / f"{run_id}_meta.json"
        meta["hypothesis"] = step.get("hypothesis", run_id)
        meta_path.write_text(json.dumps(meta, indent=2) + "\n")
        print("PATCH", json.dumps(meta), flush=True)
        man = run_one(
            run_id=run_id,
            idf=dst,
            epw=Path(args.epw),
            bills=Path(args.bills),
            area_ft2=args.area_ft2,
            hypothesis=step.get("hypothesis", run_id),
            art_root=Path(args.art_root),
            g14=g14,
        )
        results.append(man)

    summary = Path(args.art_root) / "gas_ladder_summary.json"
    summary.write_text(json.dumps(results, indent=2) + "\n")
    print("SUMMARY", summary, flush=True)
    for m in results:
        print(
            f"{m['run_id']}: gas NMBE={m.get('gas_nmbe_pct')} "
            f"CVRMSE={m.get('gas_cvrmse_pct')} ann_gas={m.get('annual_gas_delta_pct')} "
            f"elec_pass={m.get('elec_pass')} gas_pass={m.get('gas_pass')}",
            flush=True,
        )
    if any(not m.get("g14_pass") for m in results):
        # honest exit 0 — screening may fail G14; don't break shell pipelines
        pass


if __name__ == "__main__":
    main()
