#!/usr/bin/env python3
"""SC02 dials with August in-session (summer-out Jun–Jul only).

Hypothesis: school occupies ~1 month early → August uses school-day schedules.
Summer-out Through: 7/31; Aug–Dec = school year. Soft occ/plug cut + cooling COP.
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
BASE_HTG_COP = 4.2
BASE_CLG_COP = 3.5
OVERNIGHT_MAX_KW = 150.0


def _htg_mult(target: float) -> float:
    return round(target / BASE_HTG_COP, 6)


def _clg_mult(target: float) -> float:
    return round(target / BASE_CLG_COP, 6)


def _base(**overrides: Any) -> W2APlantKnobs:
    d = dict(
        htg_coil_capacity_mult=1.7,
        htg_coil_cop_mult=_htg_mult(4.5),
        clg_coil_cop_mult=1.0,
        setback_heat_sp_c=7.78,
        optimum_start_h=3.5,
        equip_w_area_mult=0.75,
        lights_w_area_mult=1.10,
        summer_sch_scale=None,
        summer_include_hvac=False,
    )
    d.update(overrides)
    return W2APlantKnobs(**d)


TRIALS: list[tuple[str, W2APlantKnobs, dict[str, Any]]] = [
    (
        "A01_sc02_sum025_clg46_augSchool",
        _base(
            summer_sch_scale=0.25,
            clg_coil_cop_mult=_clg_mult(4.6),
            summer_include_hvac=False,
        ),
        {"note": "SC02 + Jun-Jul summer-out 25% + clg 4.6; Aug in-session"},
    ),
    (
        "A02_sc02_sum025_clg46_hvac_augSchool",
        _base(
            summer_sch_scale=0.25,
            clg_coil_cop_mult=_clg_mult(4.6),
            summer_include_hvac=True,
        ),
        {"note": "same + short Jun-Jul HVAC; Aug in-session"},
    ),
    (
        "A03_r02_sum025_clg46_augSchool",
        _base(
            summer_sch_scale=0.25,
            clg_coil_cop_mult=_clg_mult(4.6),
            equip_w_area_mult=0.60,
            lights_w_area_mult=0.95,
            summer_include_hvac=False,
        ),
        {"note": "R02 dual knobs + Jun-Jul summer; Aug school"},
    ),
    (
        "A04_r02_sum040_clg48_augSchool",
        _base(
            summer_sch_scale=0.40,
            clg_coil_cop_mult=_clg_mult(4.8),
            equip_w_area_mult=0.60,
            lights_w_area_mult=0.95,
            summer_include_hvac=False,
        ),
        {"note": "R02 + milder Jun-Jul 40% + clg 4.8; Aug school"},
    ),
    (
        "A05_eq065_li100_sum025_clg46",
        _base(
            summer_sch_scale=0.25,
            clg_coil_cop_mult=_clg_mult(4.6),
            equip_w_area_mult=0.65,
            lights_w_area_mult=1.00,
            summer_include_hvac=False,
        ),
        {"note": "R01-like plugs + Jun-Jul summer; Aug school"},
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
    }


def main() -> int:
    site = Path(os.environ["LAKESIDE_SITE_ROOT"])
    camp = (
        site
        / "eplus"
        / "campaigns"
        / f"w2a_sc02_aug_in_session_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    camp.mkdir(parents=True)
    base = (
        site
        / "eplus/campaigns/w2a_integrity_closure_20260808T161626Z/shared/expand/expanded.idf"
    )
    base_text = base.read_text(encoding="utf-8", errors="replace")
    epw = site / "eplus/weather/madison_amy_202508_202607.epw"

    print(f"CAMPAIGN {camp.name}", flush=True)
    print("August in-session; summer-out Through: 7/31 only", flush=True)
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
        trial_idf = tdir / "trial.idf"
        trial_idf.write_text(applied["text"], encoding="utf-8", newline="\n")
        print(
            f"RUN {tid} summer={knobs.summer_sch_scale} hvac_cut={knobs.summer_include_hvac} "
            f"clg={knobs.clg_coil_cop_mult} eq={knobs.equip_w_area_mult} "
            f"li={knobs.lights_w_area_mult} fields={applied['n_fields_changed']}",
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
        pairs = {p["month"]: p for p in (util.get("monthly_pairs") or [])}
        for mkey in ("2025-08", "2025-09", "2025-07"):
            if mkey in pairs:
                p = pairs[mkey]
                rec[f"err_pct_{mkey}"] = 100.0 * (p["kwh_sim"] - p["kwh_obs"]) / p["kwh_obs"]
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
            f"nmbe={rec['nmbe_pct']} cv={rec['cvrmse_pct']} "
            f"aug={rec.get('err_pct_2025-08')} sep={rec.get('err_pct_2025-09')} "
            f"jul={rec.get('err_pct_2025-07')}",
            flush=True,
        )

    dual = [r for r in results if r.get("status") == "ok_dual_peak"]
    dual.sort(key=lambda r: abs(float(r["jan26_peak_kw"]) - 285.0))
    summary = {
        "campaign_id": camp.name,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "family": "W2A_sc02_aug_in_session",
        "hypothesis": "August in-session (early occupancy); summer-out Jun–Jul only (Through:7/31).",
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
                "err_pct_2025-07": r.get("err_pct_2025-07"),
                "err_pct_2025-08": r.get("err_pct_2025-08"),
                "err_pct_2025-09": r.get("err_pct_2025-09"),
            }
            for r in results
        ],
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
