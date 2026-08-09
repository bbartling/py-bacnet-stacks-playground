#!/usr/bin/env python3
"""SC02 recovery: keep rated COP 4.5 (~290 peak) and claw monthly GL14 back.

SC02 baseline (E20 knobs, COP 4.5): peak~290, ov~147, NMBE=-9.4%, CV=14.6%.
Try equip/lights/setback/opt-start cuts that hit summer+winter over-predict.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "ml"))
sys.path.insert(0, str(ROOT / "scripts"))

from eplus_native.runner import run_energyplus  # noqa: E402
from eplus_native.w2a_monthly_hold import monthly_gl14_style_pass  # noqa: E402
from eplus_native.w2a_plant_knobs import W2APlantKnobs, apply_w2a_plant_knobs  # noqa: E402
from eplus_validation_contract import (  # noqa: E402
    build_hourly_and_15min,
    utility_monthly_from_trial_sim,
)

PEAK_DESIGN_DAY = "2026-01-26"
BASE_RATED_COP = 4.2
TARGET_COP = 4.5
OVERNIGHT_MAX_KW = 150.0


def _cop_mult(target: float) -> float:
    return round(target / BASE_RATED_COP, 6)


def _sc02(**overrides: Any) -> W2APlantKnobs:
    d = dict(
        htg_coil_capacity_mult=1.7,
        htg_coil_cop_mult=_cop_mult(TARGET_COP),
        setback_heat_sp_c=7.78,
        optimum_start_h=3.5,
        equip_w_area_mult=0.75,
        lights_w_area_mult=1.10,
        loop_setpoint_c=None,
    )
    d.update(overrides)
    return W2APlantKnobs(**d)


TRIALS: list[tuple[str, W2APlantKnobs, dict[str, Any]]] = [
    (
        "R01_eq065_li100",
        _sc02(equip_w_area_mult=0.65, lights_w_area_mult=1.00),
        {"note": "cut plugs+lights vs SC02"},
    ),
    (
        "R02_eq060_li095",
        _sc02(equip_w_area_mult=0.60, lights_w_area_mult=0.95),
        {"note": "deeper plug/light cut"},
    ),
    (
        "R03_eq065_li100_sb7",
        _sc02(equip_w_area_mult=0.65, lights_w_area_mult=1.00, setback_heat_sp_c=7.0),
        {"note": "R01 + colder setback ~44.6F"},
    ),
    (
        "R04_eq065_li100_opt25",
        _sc02(equip_w_area_mult=0.65, lights_w_area_mult=1.00, optimum_start_h=2.5),
        {"note": "R01 + shorter opt-start (may trim peak)"},
    ),
    (
        "R05_eq070_li100",
        _sc02(equip_w_area_mult=0.70, lights_w_area_mult=1.00),
        {"note": "milder equip cut, lights to 1.0"},
    ),
]


def _score_day(site: Path, sim_dir: Path) -> dict[str, Any]:
    packed = build_hourly_and_15min(site, sim_dir, heat_cop=3.5, cool_cop=4.5)
    f = packed["q15"].copy()
    f["interval_end_utc"] = pd.to_datetime(f["interval_end_utc"], utc=True)
    local = f["interval_end_utc"].dt.tz_convert("America/Chicago")
    f = f.assign(local=local, d=local.dt.strftime("%Y-%m-%d"), hod=local.dt.hour)
    d = f[f["d"] == PEAK_DESIGN_DAY]
    if d.empty:
        return {"jan26_peak_kw": None, "overnight_0_4_sim_kw": None}
    ov = d[d["hod"].between(0, 3)]
    return {
        "jan26_peak_kw": float(d["simulated_kw"].max()),
        "overnight_0_4_sim_kw": float(ov["simulated_kw"].mean()) if len(ov) else None,
        "jan26_obs_peak_kw": float(d["observed_kw"].max()),
        "overnight_0_4_obs_kw": float(ov["observed_kw"].mean()) if len(ov) else None,
    }


def main() -> int:
    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    camp = (
        site
        / "eplus"
        / "campaigns"
        / f"w2a_sc02_gl14_recover_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    camp.mkdir(parents=True)
    base = (
        site
        / "eplus/campaigns/w2a_integrity_closure_20260808T161626Z/shared/expand/expanded.idf"
    )
    base_text = base.read_text(encoding="utf-8", errors="replace")
    epw = site / "eplus/weather/madison_amy_202508_202607.epw"

    print(f"CAMPAIGN {camp.name}", flush=True)
    print("SC02 recover: COP 4.5 fixed; claw GL14 via equip/lights/setback/opt", flush=True)
    results: list[dict[str, Any]] = []

    for tid, knobs, meta in TRIALS:
        tdir = camp / "trials" / tid
        tdir.mkdir(parents=True, exist_ok=True)
        existing = tdir / "trial_result.json"
        if existing.is_file():
            rec = json.loads(existing.read_text(encoding="utf-8"))
            print(f"SKIP {tid}", flush=True)
            results.append(rec)
            continue

        applied = apply_w2a_plant_knobs(base_text, knobs)
        rated = None
        for ch in applied.get("fields_changed") or []:
            if ch.get("field_comment") == "Rated Heating COP":
                try:
                    rated = float(ch["new"])
                except (TypeError, ValueError, KeyError):
                    pass
                break
        trial_idf = tdir / "trial.idf"
        trial_idf.write_text(applied["text"], encoding="utf-8", newline="\n")
        print(
            f"RUN {tid} eff_rated≈{rated} eq={knobs.equip_w_area_mult} "
            f"li={knobs.lights_w_area_mult} sb={knobs.setback_heat_sp_c} "
            f"opt={knobs.optimum_start_h}",
            flush=True,
        )
        man = run_energyplus(
            run_id=f"{camp.name}_{tid}",
            scenario_id=tid,
            idf_path=trial_idf,
            epw_path=epw,
            output_dir=tdir / "sim",
            require_zero_severe=False,
            allow_staged_idf=True,
        )
        rec: dict[str, Any] = {
            "trial_id": tid,
            "knobs": applied["knobs"],
            "meta": meta,
            "effective_rated_htg_cop": rated,
            "exit_code": man.exit_code,
            "runtime_sec": man.runtime_sec,
            "status": "pending",
        }
        if man.exit_code != 0 or not (tdir / "sim" / "eplusmtr.csv").is_file():
            rec["status"] = "failed_energyplus"
            existing.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
            results.append(rec)
            print(f"  FAILED exit={man.exit_code}", flush=True)
            continue

        day = _score_day(site, tdir / "sim")
        util = utility_monthly_from_trial_sim(site, tdir / "sim")
        hold = monthly_gl14_style_pass(util if isinstance(util, dict) else {})
        rec.update(day)
        rec["nmbe_pct"] = hold.get("nmbe_pct")
        rec["cvrmse_pct"] = hold.get("cvrmse_pct")
        rec["gl14_pass"] = bool(hold.get("pass"))
        ov = rec.get("overnight_0_4_sim_kw")
        peak = rec.get("jan26_peak_kw")
        rec["overnight_ok"] = ov is not None and float(ov) <= OVERNIGHT_MAX_KW
        rec["peak_near_285"] = peak is not None and 275.0 <= float(peak) <= 300.0
        if rec["gl14_pass"] and rec.get("peak_near_285"):
            rec["status"] = "ok_dual_peak"
        elif rec["gl14_pass"]:
            rec["status"] = "ok_gl14"
        else:
            rec["status"] = "ok_gl14_fail"
        existing.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        results.append(rec)
        print(
            f"  peak={peak} ov={ov} gl14={rec['gl14_pass']} "
            f"nmbe={rec['nmbe_pct']} cv={rec['cvrmse_pct']}",
            flush=True,
        )

    dual = [r for r in results if r.get("status") == "ok_dual_peak"]
    dual.sort(key=lambda r: abs(float(r["jan26_peak_kw"]) - 285.0))
    summary = {
        "campaign_id": camp.name,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "family": "W2A_sc02_gl14_recover",
        "sc02_anchor": {
            "rated_cop": 4.5,
            "peak_kw": 290.3,
            "overnight_kw": 147.1,
            "nmbe_pct": -9.41,
            "cvrmse_pct": 14.59,
            "gl14": False,
        },
        "n_trials": len(results),
        "gl14_passers": sum(1 for r in results if r.get("gl14_pass")),
        "dual_peak": [r["trial_id"] for r in dual],
        "best_dual_peak": dual[0] if dual else None,
        "trials": [
            {
                "trial_id": r["trial_id"],
                "status": r.get("status"),
                "jan26_peak_kw": r.get("jan26_peak_kw"),
                "overnight_0_4_sim_kw": r.get("overnight_0_4_sim_kw"),
                "gl14_pass": r.get("gl14_pass"),
                "nmbe_pct": r.get("nmbe_pct"),
                "cvrmse_pct": r.get("cvrmse_pct"),
                "knobs": {
                    k: (r.get("knobs") or {}).get(k)
                    for k in (
                        "equip_w_area_mult",
                        "lights_w_area_mult",
                        "setback_heat_sp_c",
                        "optimum_start_h",
                        "htg_coil_cop_mult",
                    )
                },
            }
            for r in results
        ],
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
