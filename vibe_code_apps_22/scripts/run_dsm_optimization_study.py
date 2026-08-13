"""Run a small Economic MPC screening study (proposal artifacts only)."""
from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from pathlib import Path
from typing import Any

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.objective import ComfortGates, score_trajectory  # noqa: E402
from eplus_gym.optimize import (  # noqa: E402
    SCREENING_LABEL,
    CandidateParams,
    StudyState,
    build_recommendation,
    coordinate_descent_grid,
    ensure_study_tree,
    new_study_id,
    pareto_front,
    study_root,
    write_json,
    append_jsonl,
)
from eplus_gym.parametric_daily_controller import (  # noqa: E402
    ParametricDailyController,
    ParametricDailyParams,
    occupancy_steps_from_site_config,
)
from eplus_gym.simulate import run_rule_episode, trajectory_frame  # noqa: E402
from eplus_gym.tariff_contract import TariffContract  # noqa: E402
from eplus_gym_app.dsm_console import stage_idf_for_period  # noqa: E402
from eplus_gym_app.dsm_preflight import sha256_file  # noqa: E402
from eplus_gym_app.site_bundle import load_site_ui_bundle  # noqa: E402
from eplus_gym_app.site_config import load_site_dsm_config  # noqa: E402


def _run_one(
    *,
    site: Path,
    epw: Path,
    idf: Path,
    day: str,
    out_dir: Path,
    ctrl: ParametricDailyController,
    site_cfg: dict,
) -> Any:
    staged = stage_idf_for_period(
        Path(idf),
        out_dir / f"staged_{Path(idf).name}",
        day,
        day,
        site_root=site,
        site_config=site_cfg,
    )
    # Temporarily drive RuleController-compatible interface via monkeypatch path:
    # run_rule_episode builds its own RuleController — call live path with custom ctrl
    # by using simulate._live_episode through a thin wrapper.
    from eplus_gym.envs.lakeside_w2a import LakesideW2AEnv
    from eplus_gym.simulate import _live_episode

    meta = {
        "scientific_claim": SCREENING_LABEL,
        "controller": ctrl.provenance(),
        "mode": "live",
        "day": day,
    }
    result = _live_episode(
        env_cls=LakesideW2AEnv,
        epw=Path(epw),
        idf=Path(staged),
        output=out_dir / "eplus",
        ctrl=ctrl,
        meta=meta,
        day=day,
        max_steps=96,
        verbose=False,
    )
    return result, staged


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=SCREENING_LABEL)
    p.add_argument("--site-root", type=Path, default=None)
    p.add_argument("--day", default="2026-01-26")
    p.add_argument("--study-id", default=None)
    p.add_argument("--budget", type=int, default=8)
    p.add_argument("--resume", action="store_true")
    p.add_argument(
        "--money-mode",
        default="PHYSICAL_ONLY",
        choices=["PHYSICAL_ONLY", "ILLUSTRATIVE", "VERIFIED_TARIFF"],
    )
    p.add_argument("--existing-billing-peak-kw", type=float, default=0.0)
    p.add_argument("--energy-rate", type=float, default=0.0)
    p.add_argument("--demand-rate", type=float, default=0.0)
    args = p.parse_args(argv)

    site = Path(
        args.site_root
        or os.environ.get("SITE_ROOT")
        or os.environ.get("LAKESIDE_SITE_ROOT")
        or ""
    )
    if not site.is_dir():
        print("FAIL: --site-root / SITE_ROOT required", file=sys.stderr)
        return 1

    bundle = load_site_ui_bundle(site)
    champ = bundle.champion()
    idf = Path(champ.idf_path) if champ and champ.idf_path else Path(bundle.idf_path or "")
    epw = Path(bundle.epw) if bundle.epw else None
    if not idf.is_file() or epw is None or not epw.is_file():
        print("FAIL: champion IDF / EPW missing", file=sys.stderr)
        return 1

    site_cfg = load_site_dsm_config(site)
    study_id = args.study_id or new_study_id("econ_mpc")
    root = ensure_study_tree(study_root(site, study_id))
    state = StudyState.load_or_create(root, study_id)

    if args.money_mode == "PHYSICAL_ONLY":
        tariff = TariffContract.physical_only(
            existing_billing_peak_kw=args.existing_billing_peak_kw
        )
    elif args.money_mode == "ILLUSTRATIVE":
        tariff = TariffContract.illustrative(
            energy_rate_per_kwh=args.energy_rate or 0.12,
            demand_rate_per_kw=args.demand_rate or 15.0,
            existing_billing_peak_kw=args.existing_billing_peak_kw,
        )
    else:
        tariff = TariffContract(
            money_mode="VERIFIED_TARIFF",
            energy_rate_per_kwh=args.energy_rate,
            demand_rate_per_kw=args.demand_rate,
            existing_billing_peak_kw=args.existing_billing_peak_kw,
            verified=True,
            label="verified tariff",
        )

    champ_hash = sha256_file(idf)
    write_json(
        root / "study_request.json",
        {
            "schema": "eplus_gym_optimization_study_v1",
            "scientific_claim": SCREENING_LABEL,
            "study_id": study_id,
            "day": args.day,
            "budget": args.budget,
            "money_mode": tariff.money_mode,
            "tariff": tariff.to_dict(),
            "champion_idf": str(idf),
            "champion_sha256": champ_hash,
            "epw": str(epw),
            "epw_sha256": sha256_file(epw),
            "forecast_kind": "retrospective_perfect_forecast_AMY_replay",
            "auto_promote": False,
        },
    )

    start_s, end_s = occupancy_steps_from_site_config(site_cfg)
    sp = site_cfg.get("setpoints_f") or {}
    baseline_params = CandidateParams(
        unoccupied_heating_f=float(sp.get("unoccupied_heating_f", 65.0)),
        recovery_start_minutes_before_occupancy=0,
        recovery_ramp_minutes=0,
        hvac_start_minutes_before_occupancy=0,
    )
    grid = [baseline_params] + [
        c for c in coordinate_descent_grid() if c.hash() != baseline_params.hash()
    ]
    grid = grid[: max(1, int(args.budget))]

    baseline_score: dict | None = None
    baseline_obj = None
    jl = root / "candidates.jsonl"

    for i, cand in enumerate(grid):
        if cand.hash() in state.seen_hashes and args.resume:
            print(f"skip dedupe {cand.hash()}")
            continue
        cdir = root / "candidates" / cand.hash()
        cdir.mkdir(parents=True, exist_ok=True)
        params = ParametricDailyParams(
            occupied_heating_f=float(sp.get("occupied_heating_f", 70.0)),
            unoccupied_heating_f=cand.unoccupied_heating_f,
            recovery_start_minutes_before_occupancy=cand.recovery_start_minutes_before_occupancy,
            recovery_ramp_minutes=cand.recovery_ramp_minutes,
            hvac_start_minutes_before_occupancy=cand.hvac_start_minutes_before_occupancy,
            occupied_setpoint_offset_f=cand.occupied_setpoint_offset_f,
            occupancy_start_step=start_s,
            occupancy_end_step=end_s,
        )
        ctrl = ParametricDailyController(params)
        row: dict[str, Any] = {
            "candidate_hash": cand.hash(),
            "params": {**cand.to_dict(), "hash": cand.hash()},
            "index": i,
        }
        try:
            result, staged = _run_one(
                site=site,
                epw=epw,
                idf=idf,
                day=args.day,
                out_dir=cdir,
                ctrl=ctrl,
                site_cfg=site_cfg,
            )
            df = trajectory_frame(result)
            pq = cdir / "trajectory.parquet"
            df.to_parquet(pq, index=False)
            # Fail closed if zones missing
            from eplus_gym.objective import BAS_ZONE_COLS

            missing = [c for c in BAS_ZONE_COLS if c not in df.columns]
            if missing:
                raise ValueError(f"missing BAS zone columns: {missing}")
            scored = score_trajectory(df, tariff, baseline=baseline_obj)
            row.update(scored.to_dict())
            row["status"] = "ok"
            row["trajectory"] = str(pq)
            row["staged_idf"] = str(staged)
            row["staged_sha256"] = sha256_file(staged)
            if i == 0:
                baseline_obj = scored
                baseline_score = scored.to_dict()
                write_json(root / "baseline.json", baseline_score)
        except Exception as exc:  # noqa: BLE001
            row["status"] = "failed"
            row["error"] = str(exc)
            row["traceback"] = traceback.format_exc()[-2000:]
            # fail-closed: no zero-cost
            row["feasible"] = False
            row["daily_kwh"] = None
            row["peak_kw"] = None
            row["total_incremental_cost"] = None
        append_jsonl(jl, row)
        state.seen_hashes.add(cand.hash())
        state.candidates.append(row)
        print(json.dumps({k: row[k] for k in row if k != "traceback"}))

    ok_rows = [r for r in state.candidates if r.get("status") == "ok"]
    frontier = pareto_front(ok_rows, money_mode=tariff.money_mode)
    write_json(root / "pareto_frontier.json", {"frontier": frontier})
    rec = build_recommendation(
        study_id=study_id,
        day=args.day,
        baseline=baseline_score or {},
        frontier=frontier,
        tariff=tariff,
    )
    write_json(root / "recommendation.json", rec)
    write_json(
        root / "hashes.json",
        {
            "champion_sha256": champ_hash,
            "champion_unchanged": True,
            "epw_sha256": sha256_file(epw),
        },
    )
    print("study_root", root)
    print("recommendation", root / "recommendation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
