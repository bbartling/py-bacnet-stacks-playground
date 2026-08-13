#!/usr/bin/env python
"""Iterate Site Config optimum-start variants on Lakeside peak day; pick lowest cost.

ILLUSTRATIVE rates (document in skill): $/kWh energy + $/kW demand on peak day.
Does not overwrite published champion IDF.
"""
from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eplus_gym.simulate import run_rule_episode, trajectory_frame  # noqa: E402
from eplus_gym_app.dsm_console import stage_idf_for_period  # noqa: E402
from eplus_gym_app.site_config import (  # noqa: E402
    load_site_dsm_config,
    optimum_start_lead_hours,
)
from eplus_gym_app.site_bundle import load_site_ui_bundle  # noqa: E402
from lakeside.paths import site_root  # noqa: E402

# ILLUSTRATIVE screening tariffs (not verified tariff schedule)
RATE_KWH = 0.12  # $/kWh
RATE_KW = 15.0  # $/kW-month demand — applied to peak-day peak as screening proxy


def _score(peak_kw: float, kwh: float) -> dict[str, float]:
    energy_usd = float(kwh) * RATE_KWH
    demand_usd = float(peak_kw) * RATE_KW
    return {
        "energy_usd": round(energy_usd, 2),
        "demand_usd": round(demand_usd, 2),
        "total_usd": round(energy_usd + demand_usd, 2),
    }


def _champion_has_schedule_opt_start(idf_text: str) -> bool:
    """True if champion already encodes morning HVAC lead (not AllDays 24h HeatAvail)."""
    import re

    if re.search(r"AvailabilityManager:OptimumStart", idf_text, re.I):
        return True
    m = re.search(
        r"SCHEDULE:COMPACT,\s*\n\s*SCH_HeatAvail,(.*?);",
        idf_text,
        re.I | re.S,
    )
    if not m:
        return False
    body = m.group(1)
    # Always-on AllDays 24:00 = 1.0 → no schedule opt-start ECM needed for "add opt-start"
    if re.search(r"For:\s*AllDays", body, re.I) and re.search(
        r"Until:\s*24:00", body, re.I
    ):
        # single always-on block
        if body.count("Until:") <= 1:
            return False
    # Per-weekday Until morning times imply a schedule window (may include lead)
    return bool(re.search(r"Until:\s*0[0-6]:\d\d", body))


def _cases(base: dict) -> list[dict]:
    """Opt-start / deadband grid for peak-day screening."""
    out = []
    # No opt-start baseline deadband, then opt-start across unocc setpoints.
    grid = [
        (False, 65.0),
        (True, 65.0),
        (True, 60.0),
        (True, 55.0),
    ]
    for opt, unocc in grid:
        cfg = deepcopy(base)
        cfg["optimum_start"] = opt
        cfg["apply_people_plug_schedules"] = True
        cfg["apply_hvac_schedules"] = True
        cfg["optimum_start_f_per_min"] = 0.10
        cfg["optimum_start_max_h"] = 4.0
        cfg["setpoints_f"]["unoccupied_heating_f"] = unocc
        cfg["setpoints_f"]["occupied_heating_f"] = 70.0
        label = f"opt={'on' if opt else 'off'}_unocc={unocc:.0f}"
        out.append({"label": label, "cfg": cfg})
    return out


def main() -> int:
    """Quarantined: refuses Site Config / last_dsm_run / ECM mutation.

    Pass ``--legacy-diagnostic`` only to run sims that write under
    ``reports/eplus_gym/runs/*_optstart_iter/`` with INVALID markers — still
    never mutates Site Config, last_dsm_run, or ecm_compare.
    """
    if "--help" in sys.argv or "-h" in sys.argv:
        print(
            "INVALID/LEGACY. Prefer scripts/run_dsm_optimization_study.py.\n"
            "Use --legacy-diagnostic for read-only-ish sims (no Site Config / "
            "last_dsm_run / ECM writes)."
        )
        return 0
    if "--legacy-diagnostic" not in sys.argv:
        print(
            "REFUSED: iterate_optstart_lakeside.py is INVALID / LEGACY DIAGNOSTIC.\n"
            "It previously contaminated sizing-day trajectories, used illustrative\n"
            "tariffs, and auto-promoted Site Config / last_dsm_run / ECM.\n"
            "Use skills/eplus-economic-mpc + scripts/run_dsm_optimization_study.py.\n"
            "Pass --legacy-diagnostic only for quarantined diagnostic sims "
            "(still will NOT mutate Site Config / last_dsm_run / ecm_compare).",
            file=sys.stderr,
        )
        return 2

    site = Path(os.environ.get("SITE_ROOT") or site_root())
    os.environ["SITE_ROOT"] = str(site)
    os.environ["LAKESIDE_SITE_ROOT"] = str(site)
    day = "2026-01-26"
    strategies = ["baseline", "deep_setback"]

    bundle = load_site_ui_bundle(site)
    champ = bundle.champion()
    idf = Path(champ.idf_path) if champ and champ.idf_path else bundle.idf_path
    epw = bundle.epw
    if idf is None or not Path(idf).is_file():
        print("FAIL: no champion IDF", file=sys.stderr)
        return 1
    if epw is None or not Path(epw).is_file():
        print("FAIL: no EPW", file=sys.stderr)
        return 1

    idf_text = Path(idf).read_text(encoding="utf-8")
    champ_has_opt = _champion_has_schedule_opt_start(idf_text)
    print(f"champion={Path(idf).name} schedule_opt_start_already={champ_has_opt}")

    base = load_site_dsm_config(site)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_root = site / "reports" / "eplus_gym" / "runs" / f"{stamp}_optstart_iter"
    out_root.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for case in _cases(base):
        label = case["label"]
        cfg = case["cfg"]
        # Quarantine: pass cfg only to staging; never write site_dsm_config.json
        lead = optimum_start_lead_hours(cfg)
        case_dir = out_root / label
        case_dir.mkdir(parents=True, exist_ok=True)
        staged = stage_idf_for_period(
            Path(idf),
            case_dir / f"staged_{Path(idf).name}",
            day,
            day,
            site_root=site,
            site_config=cfg,
        )
        print(f"\n=== {label} lead_h={lead:.3f} staged={staged.name} ===")
        for sid in strategies:
            result = run_rule_episode(
                site_root=site,
                strategy_id=sid,
                day=day,
                mode="live",
                epw=Path(epw),
                idf=staged,
                output=case_dir / sid,
                verbose=False,
                family="w2a",
                max_steps=96,
                period=f"{day}/{day}",
                weather_kind="AMY_OPEN_METEO",
            )
            df = trajectory_frame(result)
            peak = float(df["facility_kw"].max()) if "facility_kw" in df.columns else float("nan")
            kwh = (
                float(df["facility_kw"].sum() * 0.25)
                if "facility_kw" in df.columns
                else float("nan")
            )
            costs = _score(peak, kwh)
            pq = case_dir / sid / f"traj_{sid}_{day}.parquet"
            pq.parent.mkdir(parents=True, exist_ok=True)
            df.to_parquet(pq, index=False)
            row = {
                "label": label,
                "strategy_id": sid,
                "optimum_start": bool(cfg["optimum_start"]),
                "unocc_heat_f": float(cfg["setpoints_f"]["unoccupied_heating_f"]),
                "lead_h": lead,
                "peak_kw": peak,
                "kwh": kwh,
                **costs,
                "parquet": str(pq),
                "staged_idf": str(staged),
            }
            rows.append(row)
            print(json.dumps(row))

    # Rank site-config cases by deep_setback cost (DSM strategy of interest).
    deep_rows = [r for r in rows if r["strategy_id"] == "deep_setback"]
    ranked = sorted(
        deep_rows,
        key=lambda r: (r["total_usd"], r["peak_kw"], r["kwh"]),
    )
    best = ranked[0]
    best_label = best["label"]
    by_label = [r for r in rows if r["label"] == best_label]
    best_base = next(r for r in by_label if r["strategy_id"] == "baseline")
    best_deep = next(r for r in by_label if r["strategy_id"] == "deep_setback")

    # Quarantine: do NOT persist winning Site Config
    win_cfg = next(c["cfg"] for c in _cases(base) if c["label"] == best_label)

    summary = {
        "schema": "lakeside_optstart_iter_v1",
        "scientific_validity": "INVALID",
        "day": day,
        "rates_illustrative": {"usd_per_kwh": RATE_KWH, "usd_per_kw": RATE_KW},
        "champion_idf": str(idf),
        "champion_had_schedule_opt_start": champ_has_opt,
        "best_label": best_label,
        "best_row": best,
        "best_baseline": best_base,
        "best_deep_setback": best_deep,
        "rows": rows,
        "out_root": str(out_root),
        "site_config_mutated": False,
        "last_dsm_run_mutated": False,
        "ecm_compare_mutated": False,
    }
    (out_root / "iteration_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    (site / "reports" / "eplus_gym" / "optstart_iteration_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    # Energy ECM: only if champion lacked schedule opt-start AND winner uses opt-start
    measures: list[dict] = []
    ecm_empty_note = "No optimum-start Energy ECM."
    if win_cfg.get("optimum_start") and not champ_has_opt:
        off_rows = [
            r
            for r in rows
            if (not r["optimum_start"])
            and r["strategy_id"] == "deep_setback"
            and r["unocc_heat_f"] == best_deep["unocc_heat_f"]
        ]
        if not off_rows:
            off_rows = [
                r
                for r in rows
                if (not r["optimum_start"]) and r["strategy_id"] == "deep_setback"
            ]
        ref = min(off_rows, key=lambda r: r["total_usd"]) if off_rows else None
        if ref is not None:
            d_kw = float(ref["peak_kw"]) - float(best_deep["peak_kw"])
            d_kwh = float(ref["kwh"]) - float(best_deep["kwh"])
            d_usd = float(ref["total_usd"]) - float(best_deep["total_usd"])
            measures.append(
                {
                    "measure_id": "ECM-OPTIMUM-START-HVAC-LEAD",
                    "name": "HVAC optimum start (schedule lead)",
                    "ss_kwh": max(0.0, d_kwh),
                    "ep_kwh": max(0.0, d_kwh),
                    "ss_usd": max(0.0, d_usd),
                    "ep_usd": max(0.0, d_usd),
                    "capital_usd": 5000.0,
                    "status": "published",
                    "note": (
                        f"Peak-day {day} deep_setback: opt-start vs no opt-start "
                        f"(unocc {best_deep['unocc_heat_f']}F). "
                        f"ILLUSTRATIVE rates ${RATE_KWH}/kWh + ${RATE_KW}/kW. "
                        f"Delta peak_kW={d_kw:.2f}."
                    ),
                }
            )
        else:
            ecm_empty_note = "Opt-start won but no off-baseline row to delta against."
    elif champ_has_opt:
        ecm_empty_note = (
            "No Energy ECM for optimum start: published champion already encodes "
            "schedule / AvailabilityManager optimum-start behavior."
        )
    else:
        ecm_empty_note = (
            "Winning iteration did not enable optimum start; no ECM-OPTIMUM-START published."
        )

    # Quarantine: never mutate Site Config / last_dsm_run / ecm_compare.
    invalid_note = {
        "status": "INVALID",
        "scientific_validity": "INVALID",
        "reason": (
            "Legacy opt-start iteration: sizing-day risk + illustrative tariff; "
            "mutation of Site Config / last_dsm_run / ECM is disabled."
        ),
        "best_label": best_label,
        "best": best,
        "measures_not_published": measures,
        "ecm_empty_note": ecm_empty_note,
    }
    (out_root / "INVALID.md").write_text(
        "# INVALID — legacy opt-start iteration\n\n"
        "Do not rank or publish. See skills/eplus-economic-mpc.\n",
        encoding="utf-8",
    )
    summary_path = out_root / "iteration_summary.json"
    if summary_path.is_file():
        try:
            doc = json.loads(summary_path.read_text(encoding="utf-8"))
            if isinstance(doc, dict):
                doc["scientific_validity"] = "INVALID"
                doc["quarantine"] = invalid_note
                summary_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    (out_root / "quarantine_note.json").write_text(
        json.dumps(invalid_note, indent=2), encoding="utf-8"
    )

    print("\nBEST (INVALID/LEGACY — not promoted)", json.dumps(best, indent=2))
    print("wrote", out_root / "iteration_summary.json")
    print("REFUSED Site Config / last_dsm_run / ecm_compare mutation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
