#!/usr/bin/env python
"""Grow IdealLoads DSM farm for full calendar months × deployable strategies.

Dry-run prints the day×strategy matrix and writes coverage scorecards from
existing farm parquet (no EnergyPlus).

--execute runs EnergyPlus via eplus_heating_dsm_farm helpers (hours for Jan+Feb).

Examples:
  python -u scripts/run_eplus_gym_month_farm.py --months 2026-01,2026-02 --dry-run
  python -u scripts/run_eplus_gym_month_farm.py --months 2026-01 --execute --limit-days 2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP), str(_APP / "ml"), str(_APP / "scripts")]

from lakeside.paths import site_root  # noqa: E402
from eplus_gym.honesty import HONESTY_IDEALLOADS, PROMOTE  # noqa: E402
from eplus_gym.month_calendar import (  # noqa: E402
    DEPLOYABLE_STRATEGIES,
    MONTHLY_PARQUET,
    PAIRED_PARQUET,
    build_month_scenarios,
    days_in_month,
    load_farm_frames,
    write_month_scorecard,
)


def _export_monthly_slice(site: Path, months: list[str], out_farm: Path) -> Path | None:
    """Write monthly parquet slice from combined farm frames (for gym lookup)."""
    df = load_farm_frames(site)
    if df.empty:
        return None
    mask = False
    for ym in months:
        mask = mask | df["day"].astype(str).str.startswith(ym)
    sub = df.loc[mask].copy()
    if sub.empty:
        return None
    out_farm.mkdir(parents=True, exist_ok=True)
    path = out_farm / MONTHLY_PARQUET
    sub.to_parquet(path, index=False)
    return path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--months", default="2026-01,2026-02", help="comma YYYY-MM")
    ap.add_argument(
        "--strategies",
        default=",".join(DEPLOYABLE_STRATEGIES),
        help="comma strategy ids",
    )
    ap.add_argument("--dry-run", action="store_true", help="matrix + scorecards only")
    ap.add_argument(
        "--execute",
        action="store_true",
        help="run EnergyPlus for missing day×strategy (slow)",
    )
    ap.add_argument(
        "--limit-days",
        type=int,
        default=0,
        help="with --execute, only first N days per month (smoke)",
    )
    ap.add_argument("--pre-roll-days", type=int, default=0, choices=(0, 3, 7, 14))
    ap.add_argument(
        "--out",
        type=Path,
        default=_APP / "reports" / "eplus_gym" / "monthly",
    )
    args = ap.parse_args(argv)

    if not args.dry_run and not args.execute:
        args.dry_run = True

    months = [m.strip() for m in args.months.split(",") if m.strip()]
    strategies = [s.strip() for s in args.strategies.split(",") if s.strip()]
    os.environ.setdefault("LAKESIDE_SITE_ROOT", str(site_root()))
    site = site_root()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    farm_root = site / "eplus" / "dsm_farm_paired"

    scenarios = build_month_scenarios(months, strategies)
    if args.limit_days and args.limit_days > 0:
        keep_days: set[str] = set()
        for ym in months:
            keep_days.update(days_in_month(ym)[: args.limit_days])
        scenarios = [s for s in scenarios if s["day"] in keep_days]

    matrix = {
        "months": months,
        "strategies": strategies,
        "n_scenarios": len(scenarios),
        "honesty": HONESTY_IDEALLOADS,
        "promote": PROMOTE,
        "mode": "execute" if args.execute else "dry-run",
        "sample": scenarios[:5],
    }
    (out / "month_farm_matrix.json").write_text(
        json.dumps(matrix, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: matrix[k] for k in matrix if k != "sample"}, indent=2))

    for ym in months:
        path = write_month_scorecard(out, yyyy_mm=ym, strategies=strategies, site=site)
        print("scorecard", path)

    monthly_pq = _export_monthly_slice(site, months, farm_root)
    if monthly_pq:
        print("monthly parquet", monthly_pq)

    if args.dry_run and not args.execute:
        print(
            "dry-run complete — existing farm coverage only. "
            "Re-run with --execute to grow IdealLoads days (needs EnergyPlus)."
        )
        return 0

    # --- execute path: reuse farm runner internals ---
    import eplus_heating_dsm_farm as farm  # noqa: E402

    epw = site / "eplus" / "weather" / "madison_amy_202508_202607.epw"
    if not epw.is_file():
        cands = list((site / "eplus" / "weather").glob("madison_amy*.epw"))
        if not cands:
            print(f"FAIL closed: missing AMY EPW under {site / 'eplus' / 'weather'}", file=sys.stderr)
            return 2
        epw = cands[0]
    idf_src = farm._eligible_idf(site)
    print(f"EXECUTE idf={idf_src.name} epw={epw.name} n={len(scenarios)}", flush=True)

    # Monkey-patch: call farm main loop pieces by building argv for a temp approach —
    # instead, inline a thin execute using farm's functions.
    from eplus_native.hashes import sha256_file
    from eplus_native.runner import run_energyplus
    from eplus_native.extract import load_timestep_proxy_and_mat, filter_stamps_for_day
    import shutil
    import pandas as pd

    base_text = idf_src.read_text(encoding="utf-8")
    idf_sha = sha256_file(idf_src)
    epw_sha = sha256_file(epw)
    farm_root.mkdir(parents=True, exist_ok=True)

    # Seed scenarios for farm helpers
    for sc in scenarios:
        sc["seed"] = farm.stable_seed_from_scenario(sc)

    run_cache: dict = {}
    manifests: dict = {}
    accepted = 0
    rejected = 0
    all_rows: list = []

    for sc in scenarios:
        controls = farm.build_area_controls(sc["strategy_id"], sc["seed"])
        text = farm._patch_idf_for_scenario(
            base_text, sc, controls, pre_roll_days=int(args.pre_roll_days)
        )
        scen_hash = farm.input_hash(text, sc)
        run_id = f"{sc['scenario_id'].replace(':', '')}_{scen_hash[:12]}"
        run_dir = farm_root / run_id
        man_path = run_dir / "run_manifest.json"
        ts_path = run_dir / "timestep_proxy_mat.parquet"

        if man_path.is_file() and ts_path.is_file():
            man = json.loads(man_path.read_text(encoding="utf-8"))
            if man.get("accepted") and man.get("input_hash") == scen_hash:
                ts = pd.read_parquet(ts_path)
                accepted += 1
                print(f"RESUME {run_id}", flush=True)
                rows = farm.rows_from_timestep(
                    ts,
                    scenario=sc,
                    run_id=run_id,
                    input_hash_hex=scen_hash,
                    idf_sha=idf_sha,
                    epw_sha=epw_sha,
                    run_model_hash=man.get("run_model_hash") or "",
                    controls=controls,
                )
                all_rows.extend(rows)
                continue

        if run_dir.exists():
            shutil.rmtree(run_dir, ignore_errors=True)
        run_dir.mkdir(parents=True)
        idf_path = run_dir / "model.idf"
        idf_path.write_text(text, encoding="utf-8")
        run_model_hash = sha256_file(idf_path)
        try:
            man_obj = run_energyplus(
                run_id=run_id,
                scenario_id=sc["scenario_id"],
                idf_path=idf_path,
                epw_path=epw,
                output_dir=run_dir / "sim",
                require_zero_severe=True,
                allow_staged_idf=True,
            )
        except FileNotFoundError as e:
            print(f"EnergyPlus missing: {e}", file=sys.stderr)
            return 2

        man = man_obj.to_dict()
        man["input_hash"] = scen_hash
        man["run_model_hash"] = run_model_hash
        man["strategy_id"] = sc["strategy_id"]
        man_path.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
        if not man_obj.accepted:
            rejected += 1
            print(f"REJECT {run_id}: {man_obj.reject_reasons}", flush=True)
            continue
        try:
            ts = load_timestep_proxy_and_mat(run_dir / "sim", interval_hours=0.25)
            ts = filter_stamps_for_day(ts, sc["day"])
            ts = ts.drop_duplicates(subset=["eplus_stamp"], keep="last").reset_index(drop=True)
            if ts.empty:
                raise ValueError("empty after day filter")
            ts.to_parquet(ts_path, index=False)
        except Exception as e:  # noqa: BLE001
            rejected += 1
            print(f"EXTRACT FAIL {run_id}: {e}", flush=True)
            continue
        accepted += 1
        rows = farm.rows_from_timestep(
            ts,
            scenario=sc,
            run_id=run_id,
            input_hash_hex=scen_hash,
            idf_sha=idf_sha,
            epw_sha=epw_sha,
            run_model_hash=run_model_hash,
            controls=controls,
        )
        all_rows.extend(rows)
        print(f"OK {run_id} rows={len(rows)}", flush=True)

    # Merge into monthly + paired parquets
    if all_rows:
        new_df = pd.DataFrame(all_rows)
        for target in (farm_root / MONTHLY_PARQUET, farm_root / PAIRED_PARQUET):
            if target.is_file():
                old = pd.read_parquet(target)
                merged = pd.concat([old, new_df], ignore_index=True)
            else:
                merged = new_df
            if {"day", "strategy_id", "quarter_index"}.issubset(merged.columns):
                merged = merged.drop_duplicates(
                    subset=["day", "strategy_id", "quarter_index"], keep="last"
                )
            merged.to_parquet(target, index=False)
            print("wrote", target, "n=", len(merged))

    for ym in months:
        write_month_scorecard(out, yyyy_mm=ym, strategies=strategies, site=site,
                              extra={"accepted": accepted, "rejected": rejected})
    print(f"done accepted={accepted} rejected={rejected}")
    return 0 if accepted or not scenarios else 1


if __name__ == "__main__":
    raise SystemExit(main())
