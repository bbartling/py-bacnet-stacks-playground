"""Control Twin Lab runner — stage A04 copies, extract/synthesize, scorecards."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .cases import CaseSpec, full_lab_cases, smoke_cases
from .extract_plant import day_metrics, load_or_synthesize
from .seed import (
    HONESTY_LAB,
    PROMOTE,
    PROVENANCE,
    assert_champion_untouched,
    champion_sha256,
    stage_lab_idf,
)
from .surrogate import train_surrogate, write_surrogate_card


def run_lab(
    *,
    profile: str = "smoke",
    eval_day: str = "2026-01-26",
    out_dir: Path,
    reports_eplus: Path,
    reports_ml: Path,
    include_prbs: bool = False,
) -> dict[str, Any]:
    before = champion_sha256()
    out_dir.mkdir(parents=True, exist_ok=True)
    cases = (
        smoke_cases(eval_day)
        if profile == "smoke"
        else full_lab_cases(eval_day, include_prbs=include_prbs)
    )

    frames = []
    case_rows: list[dict[str, Any]] = []
    for case in cases:
        if case.farm_only_prbs and profile == "smoke":
            continue
        tag = f"{case.strategy}_pr{case.pre_roll_days}"
        staged = stage_lab_idf(
            out_dir=out_dir / "idf",
            steps_per_hour=case.steps_per_hour,
            tag=tag,
        )
        run_dir = out_dir / "runs" / tag
        run_dir.mkdir(parents=True, exist_ok=True)
        # Placeholder for future EnergyPlus invocation; smoke uses synthesizer
        # unless an E+ CSV was dropped into run_dir.
        (run_dir / "staged_idf.txt").write_text(str(staged), encoding="utf-8")
        df = load_or_synthesize(case, run_dir)
        pq = run_dir / "plant_15min.parquet"
        df.to_parquet(pq, index=False)
        frames.append(df)
        m = day_metrics(df)
        case_rows.append(
            {
                **case.to_dict(),
                **m,
                "staged_idf": str(staged),
                "plant_parquet": str(pq),
                "provenance": PROVENANCE,
                "honesty": HONESTY_LAB,
                "promote": PROMOTE,
                "source": df["source"].iloc[0] if "source" in df.columns else "",
            }
        )

    assert_champion_untouched(before)

    # Spin-up sensitivity from cases that vary pre_roll (smoke may only have 0)
    spin_rows = _spinup_table(case_rows, eval_day)
    ts_rows = _timestep_table(case_rows, eval_day)
    treat_rows = _treatment_scorecard(case_rows)

    reports_eplus.mkdir(parents=True, exist_ok=True)
    reports_ml.mkdir(parents=True, exist_ok=True)
    _write_csv(reports_eplus / "spinup_sensitivity.csv", spin_rows)
    _write_csv(reports_eplus / "timestep_sensitivity.csv", ts_rows)
    _write_csv(reports_ml / "dsm_treatment_scorecard.csv", treat_rows)

    model, card = train_surrogate(frames)
    write_surrogate_card(reports_ml / "w2a_plant_electric_surrogate_card.json", card)
    # Keep model out of git — write under artifacts
    try:
        import joblib

        joblib.dump(
            {"model": model, "card": card},
            out_dir / "w2a_plant_electric_surrogate.joblib",
        )
    except Exception:
        pass

    summary = {
        "profile": profile,
        "n_cases": len(case_rows),
        "champion_sha256": before,
        "provenance": PROVENANCE,
        "honesty": HONESTY_LAB,
        "promote": PROMOTE,
        "surrogate_holdout_mae_kw": card.get("holdout_mae_kw"),
        "artifacts": {
            "spinup": str(reports_eplus / "spinup_sensitivity.csv"),
            "timestep": str(reports_eplus / "timestep_sensitivity.csv"),
            "treatment": str(reports_ml / "dsm_treatment_scorecard.csv"),
            "surrogate_card": str(reports_ml / "w2a_plant_electric_surrogate_card.json"),
        },
    }
    (out_dir / "lab_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def _spinup_table(case_rows: list[dict], eval_day: str) -> list[dict]:
    by_pre: dict[int, list[dict]] = {}
    for r in case_rows:
        by_pre.setdefault(int(r["pre_roll_days"]), []).append(r)
    # Ensure all canonical pre-rolls appear
    rows = []
    for pre in (0, 3, 7, 14):
        group = by_pre.get(pre, [])
        if group:
            peak = max(float(g["peak_kw"]) for g in group)
            kwh = float(np_mean([float(g["daily_kwh"]) for g in group]))
            ewt = float(np_mean([float(g["ewt_mean"]) for g in group if g.get("ewt_mean") != ""]))
            note = (
                f"CONTROL_TWIN_LAB filled n={len(group)}; "
                "short pre-roll ≠ GLHE seasonal continuous ground init"
            )
            rec = "LAB_FILLED"
        else:
            peak = kwh = ewt = ""
            note = "No case at this pre_roll in profile — run --profile full_lab"
            rec = "MISSING_IN_PROFILE"
        rows.append(
            {
                "eval_day": eval_day,
                "pre_roll_days": pre,
                "daily_kwh": kwh,
                "peak_kw": peak,
                "peak_step": "",
                "zone_mae_vs_pr7": "",
                "ewt_mean": ewt,
                "note": note,
                "glhe_seasonal_ok": "false",
                "recommendation": rec,
                "provenance": PROVENANCE,
                "physics_family": "W2A_PHYSICAL_DSM",
            }
        )
    return rows


def _timestep_table(case_rows: list[dict], eval_day: str) -> list[dict]:
    by_ts: dict[int, list[dict]] = {}
    for r in case_rows:
        by_ts.setdefault(int(r["steps_per_hour"]), []).append(r)
    rows = []
    for n in (4, 6, 12):
        group = by_ts.get(n, [])
        if group:
            peak = max(float(g["peak_kw"]) for g in group)
            kwh = float(np_mean([float(g["daily_kwh"]) for g in group]))
            staged = group[0].get("staged_idf", "")
            note = f"CONTROL_TWIN_LAB filled n={len(group)}"
        else:
            peak = kwh = staged = ""
            note = "No case at this timestep in profile — run --profile full_lab"
        rows.append(
            {
                "eval_day": eval_day,
                "zone_timesteps_per_hour": n,
                "physics_family": "W2A_PHYSICAL_DSM",
                "daily_kwh": kwh,
                "peak_kw": peak,
                "peak_step": "",
                "hvac_iter_warnings": "",
                "staged_idf": staged,
                "note": note,
                "provenance": PROVENANCE,
            }
        )
    return rows


def _treatment_scorecard(case_rows: list[dict]) -> list[dict]:
    base = [r for r in case_rows if r["strategy"] == "baseline"]
    if not base:
        return [
            {
                "pair": "none",
                "delta_peak_kw": "",
                "delta_kwh": "",
                "sign_ok": "",
                "note": "no baseline in profile",
                "provenance": PROVENANCE,
                "promote": PROMOTE,
            }
        ]
    b0 = base[0]
    rows = []
    for r in case_rows:
        if r["strategy"] == "baseline":
            continue
        d_peak = float(r["peak_kw"]) - float(b0["peak_kw"])
        d_kwh = float(r["daily_kwh"]) - float(b0["daily_kwh"])
        # DSM strategies expected to reduce or reshape peak vs baseline (not always)
        rows.append(
            {
                "eval_day": r["eval_day"],
                "strategy": r["strategy"],
                "baseline_peak_kw": b0["peak_kw"],
                "strategy_peak_kw": r["peak_kw"],
                "delta_peak_kw": d_peak,
                "baseline_kwh": b0["daily_kwh"],
                "strategy_kwh": r["daily_kwh"],
                "delta_kwh": d_kwh,
                "sign_peak_reduction": d_peak < 0,
                "provenance": PROVENANCE,
                "honesty": HONESTY_LAB,
                "promote": PROMOTE,
                "note": "SYNTHETIC_W2A_PROVENANCE treatment deltas — not IdealLoads field claims",
            }
        )
    return rows


def np_mean(xs: list[float]) -> float:
    import numpy as np

    return float(np.mean(xs)) if xs else float("nan")
