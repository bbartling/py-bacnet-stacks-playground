#!/usr/bin/env python
"""Run rule-DR strategies on Lakeside E+ gym (live or farm lookup).

Examples:
  python -u scripts/run_eplus_gym_rules.py --mode lookup --strategies baseline,deep_setback
  python -u scripts/run_eplus_gym_rules.py --mode live --epw PATH --idf PATH
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eplus_gym.controllers import list_strategies  # noqa: E402
from eplus_gym.simulate import run_rule_episode, trajectory_frame  # noqa: E402
from lakeside.paths import site_root  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("auto", "live", "lookup"), default="auto")
    ap.add_argument(
        "--strategies",
        default="baseline,flat_24_7,deep_setback",
        help="comma-separated strategy ids",
    )
    ap.add_argument("--day", default=None, help="YYYY-MM-DD (lookup); default=last farm day")
    ap.add_argument("--epw", type=Path, default=None)
    ap.add_argument("--idf", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=ROOT / "reports" / "eplus_gym")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    site = site_root()
    os.environ.setdefault("LAKESIDE_SITE_ROOT", str(site))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    fig_dir = out / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    wanted = [s.strip() for s in args.strategies.split(",") if s.strip()]
    available = set(list_strategies())
    missing = [s for s in wanted if s not in available]
    if missing:
        print(f"WARN missing contracts: {missing}; available={sorted(available)}")
    strategies = [s for s in wanted if s in available] or sorted(available)[:3]

    # Pick a farm day covering as many requested strategies as possible.
    from collections import defaultdict

    from eplus_gym.lookup_emulator import list_farm_days

    day = args.day
    if day is None and strategies:
        by_day: dict[str, set[str]] = defaultdict(set)
        for s in strategies:
            for d in list_farm_days(site, s):
                by_day[d].add(s)
        full = sorted(d for d, ss in by_day.items() if set(strategies) <= ss)
        if full:
            day = full[-1]
        elif by_day:
            day = max(by_day.items(), key=lambda kv: (len(kv[1]), kv[0]))[0]
        print(f"shared_day={day} coverage={sorted(by_day.get(day, []))}")

    if day is not None:
        present = []
        for s in strategies:
            if day in set(list_farm_days(site, s)):
                present.append(s)
            else:
                print(f"WARN skip {s}: not in farm for {day}")
        strategies = present or strategies

    summary = []
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    colors = ["#264653", "#2a9d8f", "#e76f51", "#e9c46a", "#6c757d"]

    for i, sid in enumerate(strategies):
        result = run_rule_episode(
            site_root=site,
            strategy_id=sid,
            day=day,
            mode=args.mode,
            epw=args.epw,
            idf=args.idf,
            output=out / "runs",
            verbose=args.verbose,
        )
        df = trajectory_frame(result)
        meta = result["meta"]
        pq = out / f"traj_{sid}_{meta.get('day', 'noday')}.parquet"
        df.to_parquet(pq, index=False)
        peak = float(df["facility_kw"].max()) if "facility_kw" in df.columns else float("nan")
        kwh = (
            float(df["facility_kw"].sum() * 0.25)
            if "facility_kw" in df.columns
            else float("nan")
        )
        row = {
            "strategy_id": sid,
            "day": meta.get("day"),
            "mode": meta.get("mode"),
            "provenance": meta.get("provenance"),
            "honesty": meta.get("honesty"),
            "promote": meta.get("promote"),
            "peak_kw": peak,
            "kwh": kwh,
            "parquet": str(pq),
        }
        summary.append(row)
        print(json.dumps(row, indent=None))
        c = colors[i % len(colors)]
        t_h = df["step"] / 4.0
        if "facility_kw" in df.columns:
            axes[0].plot(t_h, df["facility_kw"], color=c, lw=1.8, label=sid)
        axes[1].plot(t_h, df["htg_sp_f"], color=c, lw=1.4, label=sid)

    axes[0].set_ylabel("facility kW")
    axes[0].set_title(
        f"E+ gym rule DR — {summary[0].get('mode')} / {summary[0].get('day')} "
        f"({summary[0].get('honesty')})"
    )
    axes[0].legend(loc="best", fontsize=8)
    axes[0].grid(True, alpha=0.3)
    axes[1].set_ylabel("htg SP °F")
    axes[1].set_xlabel("hour")
    axes[1].legend(loc="best", fontsize=8)
    axes[1].grid(True, alpha=0.3)
    fig.tight_layout()
    fig_path = fig_dir / "rule_dr_overlay.png"
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)

    card = {
        "strategies": summary,
        "figure": str(fig_path),
        "note": "IdealLoads = STRUCTURAL_LOAD_DIAGNOSTIC; lookup ≠ live closed-loop",
    }
    (out / "rule_dr_scorecard.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    print("wrote", fig_path)
    print("wrote", out / "rule_dr_scorecard.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
