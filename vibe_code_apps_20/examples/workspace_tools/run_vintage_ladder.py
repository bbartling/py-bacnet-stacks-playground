#!/usr/bin/env python3
"""Build DOE vintage site-scale IDFs, sim, G14-score, publish Twin iterations."""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from wattlab.energyplus.docker import run_energyplus
from wattlab.energyplus.score_monthly import score_monthly_run
from wattlab.studio.ep_viz import publish_run_for_studio

TOOLS = Path("/data/tools")
ART = Path("/data/.artifacts/geo_b100_6fl_glass")
EPW = Path("/data/.artifacts/calibrate_20260723T002036Z/amy.epw")
BILLS = Path("/data/reports/utility_bills_b100_area_weighted.csv")
AREA = 140_000.0


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def run_one(run_id: str, idf: Path, hypothesis: str, g14) -> dict:
    art = ART / f"out_{run_id}"
    if art.exists():
        shutil.rmtree(art)
    art.mkdir(parents=True)
    out = art / "output"
    runs = Path(f"/data/runs/{run_id}")
    runs.mkdir(parents=True, exist_ok=True)
    print(f"SIM {run_id}", flush=True)
    cp = run_energyplus(idf, EPW, out, timeout=900, progress_dir=runs)
    err = (out / "eplusout.err").read_text(errors="replace") if (out / "eplusout.err").is_file() else ""
    sev = len(re.findall(r"\*\* Severe", err))
    fat = len(re.findall(r"\*\*  Fatal", err))
    ok = cp.returncode == 0 and (out / "eplusout.csv").is_file() and fat == 0

    stage = art / "publish_stage"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    if (out / "eplusout.csv").is_file():
        shutil.copy2(out / "eplusout.csv", stage / "eplusout.csv")
    if (out / "eplusout.err").is_file():
        shutil.copy2(out / "eplusout.err", stage / "eplusout.err")
    shutil.copy2(idf, stage / "model.idf")

    scorecard = g14_score = None
    if ok:
        scorecard = score_monthly_run(stage / "eplusout.csv", BILLS, area_ft2=AREA, run_id=run_id)
        (stage / "scorecard.json").write_text(json.dumps(scorecard, indent=2) + "\n")
        g14_score = g14.score(stage / "eplusout.csv", BILLS)
        g14_score["g14_pass"] = bool(g14_score["elec_pass"] and g14_score["gas_pass"])
        (stage / "g14_score.json").write_text(json.dumps(g14_score, indent=2) + "\n")
        cal = _load(TOOLS / "write_calibration_scorecard.py", "write_calibration_scorecard")
        (stage / "calibration_scorecard.json").write_text(
            json.dumps(cal.g14_to_calibration_scorecard(g14_score), indent=2) + "\n"
        )

    man = {
        "run_id": run_id,
        "hypothesis": hypothesis,
        "weather": str(EPW),
        "status": "SUCCESS" if ok else "FAIL",
        "severe": sev,
        "fatal": fat,
        "rc": cp.returncode,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "elec_pass": None if not g14_score else g14_score["elec_pass"],
        "gas_pass": None if not g14_score else g14_score["gas_pass"],
        "g14_pass": None if not g14_score else g14_score["g14_pass"],
        "gas_nmbe_pct": None if not g14_score else g14_score["gas"]["nmbe_pct"],
        "gas_cvrmse_pct": None if not g14_score else g14_score["gas"]["cvrmse_pct"],
        "elec_nmbe_pct": None if not g14_score else g14_score["elec"]["nmbe_pct"],
        "elec_cvrmse_pct": None if not g14_score else g14_score["elec"]["cvrmse_pct"],
        "annual_gas_delta_pct": None if not g14_score else g14_score["annual_gas_delta_pct"],
        "annual_elec_delta_pct": None if not g14_score else g14_score["annual_elec_delta_pct"],
        "model_eui_kbtu_ft2": None if not scorecard else scorecard.get("model_site_eui"),
    }
    (stage / "run_manifest.json").write_text(json.dumps(man, indent=2) + "\n")
    report = {"run_id": run_id, "hypothesis": hypothesis, "g14": g14_score, "scorecard": scorecard}
    (stage / "wattlab_report.json").write_text(json.dumps(report, indent=2) + "\n")
    publish_run_for_studio(stage, run_id=run_id, report=report)
    dest = Path(f"/data/runs/{run_id}")
    existing = json.loads((dest / "run_manifest.json").read_text()) if (dest / "run_manifest.json").is_file() else {}
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
    vintage = _load(TOOLS / "apply_doe_vintage_5a.py", "apply_doe_vintage_5a")
    g14 = _load(TOOLS / "score_g14_monthly.py", "score_g14_monthly")

    steps = [
        {
            "run_id": "geo_b100_post80_wwr60",
            "src": Path("/data/uploads/prototypes/geo_b100_6fl_wwr60_wc.idf"),
            "vintage": "post1980",
            "hypothesis": "DOE Post-1980 / 90.1-1989 climate-5A vintage on site-scale 6fl WWR0.60 WC (envelope+infil×3.75+LPD14+boiler0.75)",
        },
        {
            "run_id": "geo_b100_pre80_wwr60",
            "src": Path("/data/uploads/prototypes/geo_b100_6fl_wwr60_wc.idf"),
            "vintage": "pre1980",
            "hypothesis": "DOE Pre-1980 climate-5A vintage on site-scale 6fl WWR0.60 WC (weaker roof/glass + infil×3.75+LPD14+boiler0.70)",
        },
        {
            "run_id": "geo_b100_post80_wwr45",
            "src": Path("/data/uploads/prototypes/geo_b100_6fl_wwr45_wc.idf"),
            "vintage": "post1980",
            "hypothesis": "DOE Post-1980 climate-5A + more typical Large Office WWR0.45 (some glazing, not pure curtain)",
        },
    ]

    results = []
    for step in steps:
        dst = Path(f"/data/uploads/prototypes/{step['run_id']}.idf")
        meta = vintage.apply_vintage(step["src"], dst, step["vintage"])
        meta["hypothesis"] = step["hypothesis"]
        (ART / f"{step['run_id']}_meta.json").write_text(json.dumps(meta, indent=2) + "\n")
        print("PATCH", json.dumps(meta), flush=True)
        results.append(run_one(step["run_id"], dst, step["hypothesis"], g14))

    (ART / "vintage_ladder_summary.json").write_text(json.dumps(results, indent=2) + "\n")
    print("SUMMARY", flush=True)
    for m in results:
        print(
            f"{m['run_id']}: gas NMBE={m.get('gas_nmbe_pct')} CV={m.get('gas_cvrmse_pct')} "
            f"ann_g={m.get('annual_gas_delta_pct')} elec_pass={m.get('elec_pass')} gas_pass={m.get('gas_pass')}",
            flush=True,
        )


if __name__ == "__main__":
    main()
