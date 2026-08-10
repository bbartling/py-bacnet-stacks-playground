#!/usr/bin/env python
"""CLI-only live IdealLoads month run (closed-loop rule DR).

Stages a copy of the IdealLoads IDF, patches RunPeriod for one month, drives
SCH_HtgSP via eplus_gym runner. NEVER call from Streamlit or Jupyter.

  python -u scripts/run_eplus_gym_month_live.py --month 2026-01 --strategy baseline --max-steps 96
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_APP), str(_APP / "scripts")]

from lakeside.paths import site_root  # noqa: E402
from eplus_gym.controllers import RuleController  # noqa: E402
from eplus_gym.honesty import HONESTY_IDEALLOADS, PROMOTE, PROVENANCE_LIVE  # noqa: E402
from eplus_gym.month_calendar import parse_month, days_in_month  # noqa: E402
from eplus_native.idf_stage import patch_run_period  # noqa: E402


def _resolve_idf(site: Path) -> Path:
    pinned = _APP / "models" / "eplus" / "lakeside_6zone_gshp_best_utility.idf"
    site_idf = site / "eplus" / "models" / "lakeside_6zone_gshp_best_utility.idf"
    for p in (site_idf, pinned):
        if p.is_file():
            return p
    raise FileNotFoundError("IdealLoads utility IDF not found")


def _resolve_epw(site: Path) -> Path:
    epw = site / "eplus" / "weather" / "madison_amy_202508_202607.epw"
    if epw.is_file():
        return epw
    cands = list((site / "eplus" / "weather").glob("madison_amy*.epw"))
    if cands:
        return cands[0]
    raise FileNotFoundError(f"missing AMY EPW under {site / 'eplus' / 'weather'}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--month", default="2026-01")
    ap.add_argument("--strategy", default="baseline")
    ap.add_argument(
        "--max-steps",
        type=int,
        default=96,
        help="cap steps (default one day smoke); full month needs ~2880–2976",
    )
    ap.add_argument("--out", type=Path, default=_APP / "reports" / "eplus_gym" / "live")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)

    os.environ.setdefault("LAKESIDE_SITE_ROOT", str(site_root()))
    site = site_root()
    year, month = parse_month(args.month)
    n_days = len(days_in_month(args.month))
    idf_src = _resolve_idf(site)
    epw = _resolve_epw(site)

    out = Path(args.out) / f"{args.month}_{args.strategy}"
    if out.exists():
        shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)

    text = idf_src.read_text(encoding="utf-8")
    text = patch_run_period(
        text,
        begin_month=month,
        begin_day=1,
        end_month=month,
        end_day=n_days,
        begin_year=year,
        end_year=year,
        name=f"GYM_{args.month}",
    )
    staged = out / "model_staged.idf"
    staged.write_text(text, encoding="utf-8")

    from eplus_gym.envs.lakeside_idealloads import LakesideIdealLoadsEnv

    ctrl = RuleController(args.strategy)
    env = LakesideIdealLoadsEnv(
        {
            "epw": str(epw),
            "idf": str(staged),
            "output": str(out / "eplus_out"),
            "verbose": args.verbose,
        }
    )
    rows = []
    try:
        _obs, info = env.reset()
        for t in range(int(args.max_steps)):
            action = ctrl.action_c(t % 96)
            _v, reward, done, truncated, step_info = env.step(action)
            od = step_info.get("obs_dict") or {}
            rows.append(
                {
                    "step": t,
                    "htg_sp_f": ctrl.setpoint_f(t % 96),
                    "htg_sp_c": action,
                    "reward": reward,
                    **{k: float(v) for k, v in od.items()},
                }
            )
            if done or truncated:
                break
    finally:
        env.close()

    import pandas as pd

    df = pd.DataFrame(rows)
    pq = out / "trajectory.parquet"
    df.to_parquet(pq, index=False)
    card = {
        "month": args.month,
        "strategy_id": args.strategy,
        "n_steps": len(df),
        "n_days_in_month": n_days,
        "max_steps_cap": int(args.max_steps),
        "honesty": HONESTY_IDEALLOADS,
        "provenance": PROVENANCE_LIVE,
        "promote": PROMOTE,
        "parquet": str(pq),
        "staged_idf": str(staged),
        "epw": str(epw),
        "note": "CLI-only live month; IdealLoads STRUCTURAL_LOAD_DIAGNOSTIC",
    }
    (out / "live_month_card.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
