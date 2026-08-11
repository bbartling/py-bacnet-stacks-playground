#!/usr/bin/env python3
"""Cold-Monday COP dial on E20: rated heating COP ~2.6–2.8 + optional 43°F loop SP.

BAS: January well return ~43°F. Hypothesis operating COP ~2.6–2.8.
Base expanded rated heating COP = 4.2 → mult = target/4.2.
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
OVERNIGHT_MAX_KW = 160.0  # allow a bit higher — low COP raises electric overnight
LOOP_43F_C = (43.0 - 32.0) * 5.0 / 9.0  # 6.111… °C


def _cop_mult(target: float) -> float:
    return round(target / BASE_RATED_COP, 6)


def _e20(**overrides: Any) -> W2APlantKnobs:
    d = dict(
        htg_coil_capacity_mult=1.7,
        htg_coil_cop_mult=1.2,  # overwritten in trials
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
        "CM01_cop26",
        _e20(htg_coil_cop_mult=_cop_mult(2.6)),
        {"target_rated_cop": 2.6, "loop_f": None},
    ),
    (
        "CM02_cop27",
        _e20(htg_coil_cop_mult=_cop_mult(2.7)),
        {"target_rated_cop": 2.7, "loop_f": None},
    ),
    (
        "CM03_cop28",
        _e20(htg_coil_cop_mult=_cop_mult(2.8)),
        {"target_rated_cop": 2.8, "loop_f": None},
    ),
    (
        "CM04_cop27_loop43F",
        _e20(htg_coil_cop_mult=_cop_mult(2.7), loop_setpoint_c=LOOP_43F_C),
        {"target_rated_cop": 2.7, "loop_f": 43.0},
    ),
    (
        "CM05_cop27_loop43F_cap145",
        _e20(
            htg_coil_capacity_mult=1.45,
            htg_coil_cop_mult=_cop_mult(2.7),
            loop_setpoint_c=LOOP_43F_C,
        ),
        {"target_rated_cop": 2.7, "loop_f": 43.0, "note": "L22 capacity + cold COP + 43F"},
    ),
    (
        "CM06_cop26_loop43F_cap170",
        _e20(
            htg_coil_capacity_mult=1.70,
            htg_coil_cop_mult=_cop_mult(2.6),
            loop_setpoint_c=LOOP_43F_C,
            equip_w_area_mult=0.70,
        ),
        {"target_rated_cop": 2.6, "loop_f": 43.0, "note": "deep cold COP + 43F + equip cut"},
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
        / f"w2a_e20_cold_monday_cop_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    )
    camp.mkdir(parents=True)
    base = (
        site
        / "eplus/campaigns/w2a_integrity_closure_20260808T161626Z/shared/expand/expanded.idf"
    )
    base_text = base.read_text(encoding="utf-8", errors="replace")
    epw = site / "eplus/weather/madison_amy_202508_202607.epw"

    print(f"CAMPAIGN {camp.name}", flush=True)
    print(f"43F loop setpoint_c={LOOP_43F_C:.4f}", flush=True)
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
        # report effective rated COP from ledger if present
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
            f"RUN {tid} target_cop={meta.get('target_rated_cop')} "
            f"eff_rated≈{rated} loop_f={meta.get('loop_f')} fields={applied['n_fields_changed']}",
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
            "expanded_idf_sha256": applied["expanded_idf_sha256"],
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
        rec["overnight_ok"] = ov is not None and float(ov) <= OVERNIGHT_MAX_KW
        peak = rec.get("jan26_peak_kw")
        rec["peak_near_285"] = peak is not None and 275.0 <= float(peak) <= 300.0
        if rec["gl14_pass"] and rec["overnight_ok"]:
            rec["status"] = "ok_dual_candidate"
        elif rec["gl14_pass"]:
            rec["status"] = "ok_gl14_high_overnight"
        else:
            rec["status"] = "ok_gl14_fail"
        existing.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
        results.append(rec)
        print(
            f"  peak={peak} ov={ov} gl14={rec['gl14_pass']} "
            f"nmbe={rec['nmbe_pct']} cv={rec['cvrmse_pct']}",
            flush=True,
        )

    dual = [
        r
        for r in results
        if r.get("gl14_pass") and r.get("overnight_ok") and r.get("jan26_peak_kw") is not None
    ]
    dual.sort(key=lambda r: -float(r["jan26_peak_kw"]))
    summary = {
        "campaign_id": camp.name,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "family": "W2A_e20_cold_monday_cop_26_28",
        "hypothesis": {
            "jan_well_return_f": 43.0,
            "cold_monday_operating_cop": [2.6, 2.8],
            "note": "Rated COP dialed to 2.6–2.8; optional loop high SP → 43°F (6.11°C)",
        },
        "e20_anchor": {
            "peak_kw": 270.8,
            "rated_cop": 5.04,
            "gl14": True,
        },
        "n_trials": len(results),
        "gl14_passers": sum(1 for r in results if r.get("gl14_pass")),
        "dual_candidates": [r["trial_id"] for r in dual],
        "best_dual": dual[0] if dual else None,
        "trials": [
            {
                "trial_id": r["trial_id"],
                "status": r.get("status"),
                "effective_rated_htg_cop": r.get("effective_rated_htg_cop"),
                "target_rated_cop": (r.get("meta") or {}).get("target_rated_cop"),
                "loop_f": (r.get("meta") or {}).get("loop_f"),
                "jan26_peak_kw": r.get("jan26_peak_kw"),
                "overnight_0_4_sim_kw": r.get("overnight_0_4_sim_kw"),
                "gl14_pass": r.get("gl14_pass"),
                "nmbe_pct": r.get("nmbe_pct"),
                "cvrmse_pct": r.get("cvrmse_pct"),
            }
            for r in results
        ],
    }
    (camp / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    mirror = ROOT / "docs" / "superpowers" / "specs" / "2026-08-09-e20-cold-monday-cop-summary.json"
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: summary[k] for k in (
        "campaign_id", "n_trials", "gl14_passers", "dual_candidates", "trials"
    )}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
