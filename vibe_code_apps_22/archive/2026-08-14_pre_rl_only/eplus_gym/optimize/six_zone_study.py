"""Coordinate-descent six-zone DSM optimizer (LIVE_ENERGYPLUS only)."""
from __future__ import annotations

import csv
import hashlib
import json
import traceback
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import pandas as pd

from eplus_gym.episode import SCREENING_CLAIM, SIMULATOR, run_controller_episode
from eplus_gym.objective import ComfortGates, ObjectiveResult, score_trajectory
from eplus_gym.optimize import (
    append_jsonl,
    ensure_study_tree,
    new_study_id,
    pareto_front,
    study_root,
    write_json,
)
from eplus_gym.six_zone_daily_controller import (
    ACTION_KEYS,
    SixZoneDailyController,
    SixZoneDailyParams,
    ZoneOffsets,
    controller_hash,
)
from eplus_gym.tariff_contract import TariffContract
from eplus_native.six_zone_htg_stage import ACTION_KEYS as _AK

assert tuple(ACTION_KEYS) == tuple(_AK)

GLOBAL_UNOCC = (62.0, 63.0, 64.0, 65.0)
GLOBAL_RECOVERY_MIN = (0, 60, 120, 180)
ZONE_MOVES = (
    ("setback_down", "setback_offset_f", -1.0),
    ("setback_up", "setback_offset_f", 1.0),
    ("recover_later", "recovery_offset_min", -30),
    ("recover_earlier", "recovery_offset_min", 30),
)
MAX_COORDINATE_PASSES = 2


def _rows_to_frame(rows: List[Dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def physical_better(
    cand: ObjectiveResult,
    incumbent: ObjectiveResult,
    *,
    max_kwh_penalty: float,
) -> bool:
    """PHYSICAL_ONLY selection: comfort → kWh penalty → peak → kWh → movement."""
    if not cand.feasible:
        return False
    if not incumbent.feasible:
        return True
    base_kwh = float(incumbent.daily_kwh)
    # Compare cand to baseline kWh via delta if present else absolute
    cand_pen = float(cand.daily_kwh) - base_kwh
    # When comparing two candidates, caller passes baseline separately for penalty;
    # here treat incumbent kwh as reference only for peak/kwh/movement.
    if cand.delta_kwh is not None:
        # delta_kwh = baseline - cand → penalty = -delta
        penalty = -float(cand.delta_kwh)
        if penalty > float(max_kwh_penalty):
            return False
    if float(cand.peak_kw) < float(incumbent.peak_kw) - 1e-9:
        return True
    if abs(float(cand.peak_kw) - float(incumbent.peak_kw)) <= 1e-9:
        if float(cand.daily_kwh) < float(incumbent.daily_kwh) - 1e-9:
            return True
        if abs(float(cand.daily_kwh) - float(incumbent.daily_kwh)) <= 1e-9:
            cm = float((cand.extras or {}).get("movement_total_f", 0.0))
            im = float((incumbent.extras or {}).get("movement_total_f", 0.0))
            return cm < im
    return False


def run_six_zone_study(
    *,
    site_root: Path,
    day: str,
    epw: Path,
    champion_idf: Path,
    stage_fn: Callable[..., Path],
    env_factory_fn: Callable[[Path, Path, Path], Any],
    tariff: TariffContract,
    lookback_days: int = 3,
    budget: int = 64,
    max_kwh_penalty: float = 100.0,
    money_mode: str = "PHYSICAL_ONLY",
    no_cache: bool = True,
    study_id: str | None = None,
    site_cfg: dict | None = None,
    sha256_file: Callable[[Path], str],
) -> Dict[str, Any]:
    if money_mode != tariff.money_mode:
        tariff.money_mode = money_mode  # type: ignore[assignment]
    if str(getattr(tariff, "money_mode", "")) not in {
        "PHYSICAL_ONLY",
        "ILLUSTRATIVE",
        "VERIFIED_TARIFF",
    }:
        raise ValueError("invalid money mode")

    site_root = Path(site_root)
    study_id = study_id or new_study_id("sixzone")
    root = ensure_study_tree(study_root(site_root, study_id))
    ledger = {
        "proposals_generated": 0,
        "duplicates_skipped": 0,
        "simulations_attempted": 0,
        "simulations_succeeded": 0,
        "simulations_failed": 0,
        "candidates_scored": 0,
        "candidates_rejected": 0,
        "cache_hits": 0,
    }
    seen: set[str] = set()
    scored_rows: List[Dict[str, Any]] = []
    jl = root / "candidates.jsonl"
    history_path = root / "evaluation_history.csv"

    target = date.fromisoformat(str(day)[:10])
    begin = target - timedelta(days=int(lookback_days))
    champ_hash = sha256_file(champion_idf)
    epw_hash = sha256_file(epw)

    write_json(
        root / "study_request.json",
        {
            "schema": "eplus_gym_six_zone_study_v1",
            "scientific_claim": SCREENING_CLAIM,
            "simulator": SIMULATOR,
            "study_id": study_id,
            "day": target.isoformat(),
            "lookback_days": lookback_days,
            "budget": budget,
            "money_mode": tariff.money_mode,
            "max_kwh_penalty": max_kwh_penalty,
            "no_cache": bool(no_cache),
            "champion_idf": str(champion_idf),
            "champion_sha256": champ_hash,
            "epw": str(epw),
            "epw_sha256": epw_hash,
            "action_keys": list(ACTION_KEYS),
            "auto_promote": False,
        },
    )

    def _eval(ctrl: SixZoneDailyController, label: str) -> Dict[str, Any]:
        ledger["proposals_generated"] += 1
        h = controller_hash(ctrl)
        if h in seen and no_cache:
            # still skip exact duplicate params
            ledger["duplicates_skipped"] += 1
            return {"status": "duplicate", "candidate_hash": h}
        if h in seen and not no_cache:
            ledger["cache_hits"] += 1
            ledger["duplicates_skipped"] += 1
            return {"status": "cache_hit", "candidate_hash": h}
        seen.add(h)
        if ledger["simulations_attempted"] >= int(budget):
            return {"status": "budget_exhausted", "candidate_hash": h}

        cdir = root / "candidates" / h
        cdir.mkdir(parents=True, exist_ok=True)
        ledger["simulations_attempted"] += 1
        row: Dict[str, Any] = {
            "candidate_hash": h,
            "label": label,
            "params": ctrl.params.to_dict(),
            "schedule_sha256": ctrl.schedule_sha256(),
            "movement_total_f": ctrl.movement_total_f(),
        }
        t0 = datetime.now(timezone.utc)
        try:
            staged = stage_fn(
                champion_idf,
                cdir / f"staged_{champion_idf.name}",
                begin.isoformat(),
                target.isoformat(),
                site_root=site_root,
                site_config=site_cfg,
                six_zone_actuators=True,
            )
            if sha256_file(champion_idf) != champ_hash:
                raise RuntimeError("champion IDF mutated during study")
            env_factory = lambda: env_factory_fn(epw, staged, cdir / "eplus")  # noqa: E731
            result = run_controller_episode(
                env_factory,
                ctrl,
                lookback_days=lookback_days,
                scored_day=target.isoformat(),
            )
            df = _rows_to_frame(result["rows"])
            pq = cdir / "trajectory.parquet"
            df.to_parquet(pq, index=False)
            all_df = _rows_to_frame(result.get("all_rows") or result["rows"])
            all_df.to_parquet(cdir / "trajectory_full.parquet", index=False)
            meta = result.get("meta") or {}
            write_json(
                cdir / "episode_meta.json",
                {
                    "lookback_days": lookback_days,
                    "scored_day": target.isoformat(),
                    "n_scored": len(df),
                    "n_full": len(all_df),
                    "calendar_validation": meta.get("calendar_validation"),
                    "scientific_claim": SCREENING_CLAIM,
                },
            )
            # Require six applied / aggregate columns
            for key in ACTION_KEYS:
                col = f"htg_sp_{key}_f"
                if col not in df.columns and f"zone_temp_{key}_f" not in df.columns:
                    # zone_temp columns use 1F_A naming via contract output_cols
                    pass
            bas_cols = [
                "zone_temp_1F_A_f",
                "zone_temp_1F_B_f",
                "zone_temp_1F_C_f",
                "zone_temp_1F_D_f",
                "zone_temp_2F_A_f",
                "zone_temp_2F_B_f",
            ]
            missing = [c for c in bas_cols if c not in df.columns]
            if missing:
                raise ValueError(f"missing BAS zone columns: {missing}")
            base_obj = None
            if scored_rows:
                # first successful is baseline
                b0 = next((r for r in scored_rows if r.get("status") == "ok"), None)
                if b0 and b0.get("_obj"):
                    base_obj = b0["_obj"]
            scored = score_trajectory(df, tariff, baseline=base_obj)
            scored.extras["movement_total_f"] = ctrl.movement_total_f()
            # kWh penalty vs baseline
            if base_obj is not None:
                pen = float(scored.daily_kwh) - float(base_obj.daily_kwh)
                if pen > float(max_kwh_penalty):
                    scored.feasible = False
                    scored.reject_reason = (
                        (scored.reject_reason or "") + f"; kwh_penalty={pen:.1f}"
                    ).strip("; ")
            row.update(scored.to_dict())
            row["status"] = "ok"
            row["trajectory"] = str(pq)
            row["staged_idf"] = str(staged)
            row["staged_sha256"] = sha256_file(staged)
            row["champion_sha256"] = champ_hash
            row["_obj"] = scored
            ledger["simulations_succeeded"] += 1
            ledger["candidates_scored"] += 1
            if not scored.feasible:
                ledger["candidates_rejected"] += 1
        except Exception as exc:  # noqa: BLE001
            ledger["simulations_failed"] += 1
            ledger["candidates_rejected"] += 1
            row["status"] = "failed"
            row["error"] = str(exc)
            row["traceback"] = traceback.format_exc()[-2000:]
            row["feasible"] = False
            # fail-closed: no zero cost fields
            row["daily_kwh"] = None
            row["peak_kw"] = None
            row["total_incremental_cost"] = None
        row["runtime_start"] = t0.isoformat()
        row["runtime_finish"] = datetime.now(timezone.utc).isoformat()
        append_jsonl(jl, {k: v for k, v in row.items() if k != "_obj"})
        scored_rows.append(row)
        write_json(root / "study_status.json", {"ledger": ledger, "study_id": study_id})
        return row

    # Baseline
    sp = (site_cfg or {}).get("setpoints_f") or {}
    baseline_ctrl = SixZoneDailyController(
        SixZoneDailyParams(
            occupied_heating_f=float(sp.get("occupied_heating_f", 70.0)),
            unoccupied_heating_f=float(sp.get("unoccupied_heating_f", 65.0)),
            recovery_start_minutes_before_occupancy=0,
            recovery_ramp_minutes=60,
        )
    )
    base_row = _eval(baseline_ctrl, "baseline")
    if base_row.get("status") != "ok":
        write_json(root / "audit.json", {"ledger": ledger, "error": "baseline_failed", "base": base_row})
        return {"study_id": study_id, "root": root, "ledger": ledger, "ok": False}

    write_json(root / "baseline.json", {k: v for k, v in base_row.items() if k != "_obj"})
    df_base = pd.read_parquet(base_row["trajectory"])
    df_base.to_parquet(root / "trajectory_baseline.parquet", index=False)
    incumbent = base_row
    incumbent_ctrl = baseline_ctrl

    # Phase A — global grid
    for unocc in GLOBAL_UNOCC:
        for lead in GLOBAL_RECOVERY_MIN:
            if ledger["simulations_attempted"] >= budget:
                break
            ctrl = SixZoneDailyController(
                SixZoneDailyParams(
                    occupied_heating_f=baseline_ctrl.params.occupied_heating_f,
                    unoccupied_heating_f=float(unocc),
                    recovery_start_minutes_before_occupancy=int(lead),
                    recovery_ramp_minutes=60,
                )
            )
            row = _eval(ctrl, f"global_unocc={unocc}_lead={lead}")
            if row.get("status") == "ok" and row.get("_obj"):
                if physical_better(
                    row["_obj"],
                    incumbent["_obj"],
                    max_kwh_penalty=max_kwh_penalty,
                ):
                    # also enforce penalty vs baseline
                    pen = float(row["daily_kwh"]) - float(base_row["daily_kwh"])
                    if pen <= max_kwh_penalty and row.get("feasible"):
                        incumbent = row
                        incumbent_ctrl = ctrl

    # Phase B — coordinate descent
    for _pass in range(MAX_COORDINATE_PASSES):
        improved = False
        for zone in ACTION_KEYS:
            for move_name, field, delta in ZONE_MOVES:
                if ledger["simulations_attempted"] >= budget:
                    break
                ctrl = incumbent_ctrl.with_zone_move(zone, **{field: delta})
                row = _eval(ctrl, f"pass{_pass}_{zone}_{move_name}")
                if row.get("status") == "ok" and row.get("feasible") and row.get("_obj"):
                    pen = float(row["daily_kwh"]) - float(base_row["daily_kwh"])
                    if pen <= max_kwh_penalty and physical_better(
                        row["_obj"], incumbent["_obj"], max_kwh_penalty=max_kwh_penalty
                    ):
                        incumbent = row
                        incumbent_ctrl = ctrl
                        improved = True
        if not improved:
            break

    ok_rows = [r for r in scored_rows if r.get("status") == "ok"]
    frontier = pareto_front(
        [{k: v for k, v in r.items() if k != "_obj"} for r in ok_rows],
        money_mode=tariff.money_mode,
    )
    write_json(root / "pareto_frontier.json", {"frontier": frontier})

    # schedule csv
    sched = incumbent_ctrl.series_f()
    with (root / "six_zone_schedule.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["step", *ACTION_KEYS])
        for i in range(96):
            w.writerow([i, *[sched[k][i] for k in ACTION_KEYS]])

    # history csv
    with history_path.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "candidate_hash",
            "label",
            "status",
            "peak_kw",
            "daily_kwh",
            "feasible",
            "comfort_degree_hours",
        ]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in scored_rows:
            w.writerow({k: r.get(k) for k in fields})

    rec = {
        "schema": "eplus_gym_recommendation_v1",
        "scientific_claim": SCREENING_CLAIM,
        "study_id": study_id,
        "day": target.isoformat(),
        "proposal_only": True,
        "auto_promote_site_config": False,
        "auto_promote_bacnet": False,
        "money_mode": tariff.money_mode,
        "tariff_status": tariff.money_mode,
        "real_energyplus_executions": ledger["simulations_succeeded"],
        "baseline": {k: v for k, v in base_row.items() if k != "_obj"},
        "recommended": {k: v for k, v in incumbent.items() if k != "_obj"},
        "action_keys": list(ACTION_KEYS),
        "note": "Approve writes approved_recommendation.json only.",
    }
    write_json(root / "recommendation.json", rec)
    if incumbent.get("trajectory"):
        pd.read_parquet(incumbent["trajectory"]).to_parquet(
            root / "trajectory_recommendation.parquet", index=False
        )
    write_json(
        root / "hashes.json",
        {
            "champion_sha256": champ_hash,
            "champion_unchanged": sha256_file(champion_idf) == champ_hash,
            "epw_sha256": epw_hash,
        },
    )
    write_json(root / "audit.json", {"ledger": ledger, "scientific_claim": SCREENING_CLAIM})
    (root / "report.md").write_text(
        f"# {SCREENING_CLAIM}\n\n"
        f"Study `{study_id}` day `{target.isoformat()}`\n\n"
        f"Simulations succeeded: {ledger['simulations_succeeded']} / "
        f"attempted {ledger['simulations_attempted']}\n\n"
        f"Baseline peak_kW={base_row.get('peak_kw')} kWh={base_row.get('daily_kwh')}\n\n"
        f"Recommended peak_kW={incumbent.get('peak_kw')} kWh={incumbent.get('daily_kwh')}\n"
        f"Proposal only — no Site Config / BACnet mutation.\n",
        encoding="utf-8",
    )
    write_json(root / "study_status.json", {"state": "succeeded", "ledger": ledger})
    return {
        "study_id": study_id,
        "root": str(root),
        "ledger": ledger,
        "ok": True,
        "recommendation": rec,
    }
