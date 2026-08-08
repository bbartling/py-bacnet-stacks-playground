#!/usr/bin/env python3
"""Small multiobjective search on provisional expanded W2A plant (post-smoke)."""
from __future__ import annotations

import itertools
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_native.hashes import sha256_file  # noqa: E402
from eplus_native.runner import energyplus_version, run_energyplus  # noqa: E402
from eplus_stage_provisional_w2a import expand_objects, stage_w2a  # noqa: E402
from eplus_schedule_sanity_campaign import _score_trial  # noqa: E402
from eplus_plant_proxy_calib import composite_score, promotion_gates  # noqa: E402
from eplus_native.schedule_calendar_repair import repair_idf_file  # noqa: E402


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    camp = site / "eplus" / "campaigns" / f"w2a_plant_calib_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    camp.mkdir(parents=True)
    champ = sorted((site / "eplus" / "campaigns").glob("freeze_pre_schedule_plant_*/champion_B_equip_mult_mid_model.idf"))[-1]
    epw = site / "eplus" / "weather" / "madison_amy_202508_202607.epw"

    # 5×3 = 15 trials in the 20–40 band (lower end; annual W2A ~25s)
    grid = list(itertools.product([2.3, 2.5, 2.7, 2.9, 3.2], [62.0, 65.0, 68.0]))
    results = []
    for i, (cap, unocc) in enumerate(grid):
        tid = f"W{i:02d}_cap{cap}_u{unocc}".replace(".", "p")
        tdir = camp / "trials" / tid
        tdir.mkdir(parents=True)
        repaired = tdir / "repaired.idf"
        repair_idf_file(champ, repaired, heating_capacity_mmbtu_h=cap)
        # patch unocc SP in SCH_HtgSP via rewrite of repaired with plant proxy setpoints
        from eplus_native.provisional_plant import PlantProxyKnobs, apply_plant_proxy

        text = apply_plant_proxy(
            champ.read_text(encoding="utf-8", errors="replace"),
            PlantProxyKnobs(heating_capacity_mmbtu_h=cap, unocc_heat_sp_f=unocc),
        )
        repaired.write_text(text, encoding="utf-8", newline="\n")
        staged = tdir / "trial_template.idf"
        stage_w2a(repaired, staged)
        expanded = expand_objects(staged, tdir / "expand")
        shutil.copy2(expanded, tdir / "trial.idf")
        print(f"RUN {tid}", flush=True)
        man = run_energyplus(
            run_id=f"{camp.name}_{tid}",
            scenario_id=tid,
            idf_path=expanded,
            epw_path=epw,
            output_dir=tdir / "sim",
            require_zero_severe=False,
            allow_staged_idf=True,
        )
        rec = {
            "trial_id": tid,
            "knobs": {"heating_capacity_mmbtu_h": cap, "unocc_heat_sp_f": unocc},
            "exit_code": man.exit_code,
            "runtime_sec": man.runtime_sec,
            "idf_sha256": sha256_file(expanded),
            "status": "failed",
        }
        if man.exit_code == 0 and (tdir / "sim" / "eplusmtr.csv").is_file():
            try:
                metrics = _score_trial(site, tdir / "sim", heat_cop=3.5, cool_cop=4.5)
                rec["metrics"] = {
                    "utility_monthly": {
                        k: metrics["utility_monthly"].get(k)
                        for k in ("nmbe_pct", "cvrmse_pct", "status")
                    },
                    "structural": metrics.get("structural"),
                }
                rec["composite_score"] = composite_score(metrics)
                rec["gates"] = promotion_gates(metrics)
                rec["status"] = "succeeded"
            except Exception as e:
                rec["score_error"] = f"{type(e).__name__}: {e}"
        (tdir / "trial_result.json").write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        results.append(rec)

    ok = [r for r in results if r["status"] == "succeeded"]
    ok.sort(key=lambda r: r.get("composite_score", 1e9))
    any_raw = any((r.get("gates") or {}).get("raw_eplus_gates_pass") for r in ok)
    summary = {
        "campaign_id": camp.name,
        "created_utc": _utc(),
        "provenance": "PROVISIONAL_W2A_HVACTEMPLATE",
        "planned": len(grid),
        "succeeded": len(ok),
        "failed": len(results) - len(ok),
        "raw_eplus_gates_any_pass": any_raw,
        "dsm_status": "NO-GO",
        "audit": "NO-GO" if not any_raw else "SCREENING ONLY",
        "best_trial_id": None if not ok else ok[0]["trial_id"],
        "energyplus_version": energyplus_version(),
        "trials": results,
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    slim = {k: v for k, v in summary.items() if k != "trials"}
    slim["trial_status"] = {r["trial_id"]: r["status"] for r in results}
    (ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-w2a-plant-calib-summary.json").write_text(
        json.dumps(slim, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(slim, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
