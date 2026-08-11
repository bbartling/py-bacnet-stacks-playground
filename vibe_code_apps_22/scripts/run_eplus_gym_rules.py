#!/usr/bin/env python
"""Run rule-DR strategies on Lakeside E+ gym (live or farm lookup).

Examples:
  python -u scripts/run_eplus_gym_rules.py --mode lookup
  python -u scripts/run_eplus_gym_rules.py --mode lookup --month 2026-01
  python -u scripts/run_eplus_gym_rules.py --mode live --epw PATH --idf PATH
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from eplus_gym.controllers import list_strategies  # noqa: E402
from eplus_gym.lookup_emulator import (  # noqa: E402
    list_farm_days,
    resolve_farm_root,
    resolve_w2a_farm_root,
)
from eplus_gym.month_calendar import write_month_scorecard  # noqa: E402
from eplus_gym.simulate import (  # noqa: E402
    run_rule_episode,
    run_rule_month_lookup,
    trajectory_frame,
)
from lakeside.paths import site_root  # noqa: E402


def _run_month(
    site: Path,
    month: str,
    strategies: list[str],
    out: Path,
    fig_dir: Path,
    family: str = "idealloads",
) -> int:
    result = run_rule_month_lookup(
        site_root=site, month=month, strategies=strategies, family=family
    )
    summary = []
    fig, ax = plt.subplots(figsize=(11, 4))
    colors = ["#264653", "#2a9d8f", "#e76f51", "#e9c46a", "#6c757d"]
    for i, sid in enumerate(strategies):
        pack = result["strategies"].get(sid) or {}
        df = pack.get("frame")
        if df is None or getattr(df, "empty", True):
            print(f"WARN no data for {sid} in {month}")
            continue
        pq = out / f"month_{month}_{sid}.parquet"
        df.to_parquet(pq, index=False)
        peak = float(df["facility_kw"].max()) if "facility_kw" in df.columns else float("nan")
        kwh = float(df["facility_kw"].sum() * 0.25) if "facility_kw" in df.columns else float("nan")
        row = {
            "strategy_id": sid,
            "month": month,
            "n_days": int(pack.get("n_days") or 0),
            "peak_kw": peak,
            "kwh": kwh,
            "parquet": str(pq),
        }
        summary.append(row)
        print(json.dumps(row))
        # mean daily profile
        if "step" in df.columns and "facility_kw" in df.columns:
            profile = df.groupby("step")["facility_kw"].mean()
            ax.plot(profile.index / 4.0, profile.values, color=colors[i % len(colors)], lw=1.8, label=sid)
    ax.set_xlabel("hour")
    ax.set_ylabel("mean facility kW")
    ax.set_title(f"E+ gym month lookup · {month}")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig_path = fig_dir / f"month_{month}_overlay.png"
    fig.savefig(fig_path, dpi=120)
    plt.close(fig)
    monthly = out / "monthly"
    write_month_scorecard(monthly, yyyy_mm=month, strategies=strategies, site=site)
    card = {"month": month, "strategies": summary, "figure": str(fig_path), "kpis": result["kpis"]}
    (out / f"month_{month}_scorecard.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    print("wrote", fig_path)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=("auto", "live", "lookup"), default="lookup")
    ap.add_argument(
        "--family",
        choices=("w2a", "idealloads"),
        default="idealloads",
        help="w2a = A04 champion (never falls back to IdealLoads farm)",
    )
    ap.add_argument(
        "--strategies",
        default="baseline,flat_24_7,deep_setback",
        help="comma-separated strategy ids",
    )
    ap.add_argument("--day", default=None, help="YYYY-MM-DD (lookup); default=best shared day")
    ap.add_argument("--month", default=None, help="YYYY-MM — lookup all available days in month")
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

    if args.month:
        return _run_month(site, args.month, strategies, out, fig_dir, family=args.family)

    farm_root = (
        resolve_w2a_farm_root(site)
        if args.family == "w2a"
        else resolve_farm_root(site)
    )
    day = args.day
    if day is None and strategies:
        by_day: dict[str, set[str]] = defaultdict(set)
        for s in strategies:
            for d in list_farm_days(site, s, farm_root=farm_root):
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
            if day in set(list_farm_days(site, s, farm_root=farm_root)):
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
            family=args.family,
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
        "note": (
            "w2a = W2A_PHYSICAL_DSM; idealloads = STRUCTURAL_LOAD_DIAGNOSTIC; "
            "lookup ≠ live closed-loop; promote=False"
        ),
        "family": args.family,
    }
    (out / "rule_dr_scorecard.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    print("wrote", fig_path)
    print("wrote", out / "rule_dr_scorecard.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
