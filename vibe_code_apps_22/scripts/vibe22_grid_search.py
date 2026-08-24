"""CLI for Vibe22 LIVE EnergyPlus discrete grid-search comparator (no RL training)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))

from eplus_gym.rl.day_ahead_tariff import write_default_fixtures
from eplus_gym.rl.grid_search_menu import build_candidate_menu
from eplus_gym.rl.grid_search_publish import publish_grid_pack
from eplus_gym.rl.grid_search_runner import (
    load_experiment_contract,
    resolve_paths,
    run_fixed_policy_screen,
    run_micro_gate,
    run_pilot,
)
from eplus_gym.site_env import require_site_root


def cmd_freeze_check(args: argparse.Namespace) -> int:
    site = require_site_root(args.site_root)
    contract = load_experiment_contract(_APP)
    paths = resolve_paths(_APP, site)
    write_default_fixtures(_APP / "contracts" / "fixtures" / "tariffs")
    menu = build_candidate_menu()
    out = {
        "contract_version": contract.get("version"),
        "idf_sha256": paths["idf_sha256"],
        "epw_sha256": paths["epw_sha256"],
        "idf": str(paths["idf"]),
        "epw": str(paths["epw"]),
        "declared_action_count": menu["declared_action_count"],
        "n_unique_fixed_policies": menu["n_unique_fixed_policies"],
        "candidate_menu_sha256": menu["candidate_menu_sha256"],
        "DAILY_ADAPTIVE_GRID_STATUS": contract.get("daily_adaptive_grid_status"),
        "wall_time_limit_hours": contract.get("wall_time_limit_hours"),
        "preregistered_bounded_subset_indices": contract.get("preregistered_bounded_subset_indices"),
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_micro(args: argparse.Namespace) -> int:
    site = require_site_root(args.site_root)
    body = run_micro_gate(app_root=_APP, site_root=site, out_root=args.out_root)
    print(json.dumps({k: body[k] for k in body if k != "arms"}, indent=2))
    return 0 if body.get("status") == "MICRO_GATE_PASSED" else 2


def cmd_pilot(args: argparse.Namespace) -> int:
    site = require_site_root(args.site_root)
    body = run_pilot(app_root=_APP, site_root=site, out_root=args.out_root)
    slim = {k: v for k, v in body.items() if k != "candidates"}
    print(json.dumps(slim, indent=2))
    return 0 if body.get("status") == "PILOT_PASSED" else 2


def cmd_screen(args: argparse.Namespace) -> int:
    site = require_site_root(args.site_root)
    pilot = None
    if args.pilot_json:
        pilot = json.loads(Path(args.pilot_json).read_text(encoding="utf-8"))
    force = True if args.bounded else (False if args.exhaustive else None)
    body = run_fixed_policy_screen(
        app_root=_APP,
        site_root=site,
        out_root=args.out_root,
        force_bounded=force,
        pilot_result=pilot,
    )
    slim = {k: v for k, v in body.items() if k not in {"scorecard", "leaders_full"}}
    print(json.dumps(slim, indent=2))
    return 0


def cmd_publish(args: argparse.Namespace) -> int:
    body = publish_grid_pack(
        app_root=_APP,
        screen_root=Path(args.screen_root),
        pilot_root=Path(args.pilot_root) if args.pilot_root else None,
        micro_root=Path(args.micro_root) if args.micro_root else None,
        docs_out=Path(args.docs_out) if args.docs_out else None,
    )
    print(json.dumps({"docs_out": body["docs_out"], "verdict_flat": body["verdict"]["FLAT_PLUS_DEMAND"]["verdict"], "verdict_tou": body["verdict"]["ILLUSTRATIVE_TOU_PLUS_DEMAND"]["verdict"]}, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--site-root", type=Path, default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    s0 = sub.add_parser("freeze-check")
    s0.set_defaults(func=cmd_freeze_check)

    s1 = sub.add_parser("micro-gate")
    s1.add_argument("--out-root", type=Path, default=None)
    s1.set_defaults(func=cmd_micro)

    s2 = sub.add_parser("pilot")
    s2.add_argument("--out-root", type=Path, default=None)
    s2.set_defaults(func=cmd_pilot)

    s3 = sub.add_parser("fixed-policy-screen")
    s3.add_argument("--out-root", type=Path, default=None)
    s3.add_argument("--pilot-json", type=Path, default=None)
    g = s3.add_mutually_exclusive_group()
    g.add_argument("--bounded", action="store_true")
    g.add_argument("--exhaustive", action="store_true")
    s3.set_defaults(func=cmd_screen)

    s4 = sub.add_parser("publish")
    s4.add_argument("--screen-root", type=Path, required=True)
    s4.add_argument("--pilot-root", type=Path, default=None)
    s4.add_argument("--micro-root", type=Path, default=None)
    s4.add_argument("--docs-out", type=Path, default=None)
    s4.set_defaults(func=cmd_publish)

    args = p.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
