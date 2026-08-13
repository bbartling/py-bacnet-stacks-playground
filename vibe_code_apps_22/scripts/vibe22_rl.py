#!/usr/bin/env python3
"""Vibe22 RL CLI — LIVE EnergyPlus daily six-zone SB3 training / bakeoff / compare."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.rl import SCREENING_CLAIM, SIMULATOR_REQUIRED  # noqa: E402
from eplus_gym.rl.compare_baseline import (  # noqa: E402
    compare_policies,
    load_params_from_recommendation,
    load_rl_action_as_params,
)
from eplus_gym.rl.train_sb3 import bakeoff, train_sb3  # noqa: E402
from eplus_gym_app.dsm_preflight import sha256_file  # noqa: E402
from eplus_gym_app.site_bundle import load_site_ui_bundle  # noqa: E402
from eplus_gym_app.site_config import load_site_dsm_config  # noqa: E402

EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_EPLUS = 2
EXIT_INTEGRITY = 4


def _site(args) -> Path:
    site = Path(args.site_root or os.environ.get("SITE_ROOT") or "")
    if not site.is_dir():
        raise SystemExit(EXIT_CONFIG)
    return site


def _paths(site: Path):
    bundle = load_site_ui_bundle(site)
    champ = bundle.champion()
    idf = Path(champ.idf_path) if champ and champ.idf_path else Path(bundle.idf_path or "")
    epw = Path(bundle.epw) if bundle.epw else None
    if not idf.is_file() or epw is None or not epw.is_file():
        print("FAIL: champion/epw missing", file=sys.stderr)
        raise SystemExit(EXIT_CONFIG)
    return idf, epw


def cmd_train(args) -> int:
    print(SCREENING_CLAIM)
    if args.simulator != SIMULATOR_REQUIRED:
        print("REFUSED: only LIVE_ENERGYPLUS", file=sys.stderr)
        return EXIT_INTEGRITY
    site = _site(args)
    idf, epw = _paths(site)
    champ_hash = sha256_file(idf)
    days = [d.strip() for d in str(args.days).split(",") if d.strip()]
    run_id = args.run_id or f"train_{args.algo.lower()}"
    root = site / "reports" / "eplus_gym" / "rl" / run_id
    cfg = load_site_dsm_config(site)
    sp = cfg.get("setpoints_f") or {}
    summary = train_sb3(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        days=days,
        algo=args.algo,
        timesteps=int(args.timesteps),
        run_root=root,
        seed=int(args.seed),
        occupied_heating_f=float(sp.get("occupied_heating_f", 70.0)),
        unoccupied_heating_f=float(sp.get("unoccupied_heating_f", 65.0)),
    )
    if sha256_file(idf) != champ_hash:
        print("INTEGRITY FAIL: champion mutated", file=sys.stderr)
        return EXIT_INTEGRITY
    (root / "hashes.json").write_text(
        json.dumps({"champion_sha256": champ_hash, "unchanged": True}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    print("run_root", root)
    return EXIT_OK


def cmd_bakeoff(args) -> int:
    print(SCREENING_CLAIM)
    if args.simulator != SIMULATOR_REQUIRED:
        print("REFUSED: only LIVE_ENERGYPLUS", file=sys.stderr)
        return EXIT_INTEGRITY
    site = _site(args)
    idf, epw = _paths(site)
    champ_hash = sha256_file(idf)
    days = [d.strip() for d in str(args.days).split(",") if d.strip()]
    out = bakeoff(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        days=days,
        timesteps=int(args.timesteps),
        run_id=args.run_id,
        seed=int(args.seed),
    )
    if sha256_file(idf) != champ_hash:
        print("INTEGRITY FAIL: champion mutated", file=sys.stderr)
        return EXIT_INTEGRITY
    root = Path(out["root"])
    (root / "hashes.json").write_text(
        json.dumps({"champion_sha256": champ_hash, "unchanged": True}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(out, indent=2))
    return EXIT_OK


def cmd_compare(args) -> int:
    print(SCREENING_CLAIM)
    site = _site(args)
    idf, epw = _paths(site)
    root = site / "reports" / "eplus_gym" / "rl" / args.run_id
    root.mkdir(parents=True, exist_ok=True)
    # Prefer last RL reward.json params under run
    rl_params = None
    for p in sorted(root.rglob("reward.json")):
        rl_params = load_rl_action_as_params(p)
    descent = None
    if args.descent_recommendation:
        descent = load_params_from_recommendation(Path(args.descent_recommendation))
    else:
        opt = site / "reports" / "eplus_gym" / "optimization"
        if opt.is_dir():
            studies = sorted([p for p in opt.iterdir() if p.is_dir()], reverse=True)
            for s in studies:
                cand = s / "recommendation.json"
                descent = load_params_from_recommendation(cand)
                if descent is not None:
                    break
    out = compare_policies(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        day=args.day,
        run_root=root,
        rl_params=rl_params,
        descent_params=descent,
    )
    print(json.dumps(out, indent=2))
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=SCREENING_CLAIM)
    site_parent = argparse.ArgumentParser(add_help=False)
    site_parent.add_argument("--site-root", type=Path, default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("train", parents=[site_parent])
    t.add_argument("--algo", choices=["PPO", "DQN"], required=True)
    t.add_argument("--days", default="2026-01-26")
    t.add_argument("--timesteps", type=int, default=6)
    t.add_argument("--seed", type=int, default=0)
    t.add_argument("--run-id", default=None)
    t.add_argument("--simulator", default=SIMULATOR_REQUIRED)
    t.set_defaults(func=cmd_train)

    b = sub.add_parser("bakeoff", parents=[site_parent])
    b.add_argument("--days", default="2026-01-26")
    b.add_argument("--timesteps", type=int, default=6)
    b.add_argument("--seed", type=int, default=0)
    b.add_argument("--run-id", default=None)
    b.add_argument("--simulator", default=SIMULATOR_REQUIRED)
    b.set_defaults(func=cmd_bakeoff)

    c = sub.add_parser("compare", parents=[site_parent])
    c.add_argument("--run-id", required=True)
    c.add_argument("--day", default="2026-01-26")
    c.add_argument("--descent-recommendation", default=None)
    c.set_defaults(func=cmd_compare)

    args = p.parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit as exc:
        return int(exc.code or EXIT_CONFIG)


if __name__ == "__main__":
    raise SystemExit(main())
