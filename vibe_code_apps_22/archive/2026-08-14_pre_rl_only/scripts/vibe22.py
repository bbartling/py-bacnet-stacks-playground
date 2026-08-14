#!/usr/bin/env python3
"""Vibe22 CLI — ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_APP = Path(__file__).resolve().parents[1]
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from eplus_gym.episode import SCREENING_CLAIM, SIMULATOR  # noqa: E402
from eplus_gym.optimize.six_zone_study import run_six_zone_study  # noqa: E402
from eplus_gym.tariff_contract import TariffContract  # noqa: E402
from eplus_gym_app.dsm_console import stage_idf_for_period  # noqa: E402
from eplus_gym_app.dsm_preflight import sha256_file  # noqa: E402
from eplus_gym_app.site_bundle import load_site_ui_bundle  # noqa: E402
from eplus_gym_app.site_config import load_site_dsm_config  # noqa: E402

EXIT_OK = 0
EXIT_CONFIG = 1
EXIT_EPLUS = 2
EXIT_NO_FEASIBLE = 3
EXIT_INTEGRITY = 4


def _site(args) -> Path:
    site = Path(args.site_root or os.environ.get("SITE_ROOT") or "")
    if not site.is_dir():
        raise SystemExit(EXIT_CONFIG)
    return site


def cmd_status(args) -> int:
    site = _site(args)
    print(SCREENING_CLAIM)
    bundle = load_site_ui_bundle(site)
    champ = bundle.champion()
    idf = Path(champ.idf_path) if champ and champ.idf_path else Path(bundle.idf_path or "")
    epw = Path(bundle.epw) if bundle.epw else None
    print(f"site={site}")
    print(f"champion={idf.name if idf.is_file() else 'MISSING'}")
    if idf.is_file():
        print(f"champion_sha256={sha256_file(idf)}")
    print(f"epw={epw}")
    if epw and epw.is_file():
        print(f"epw_sha256={sha256_file(epw)}")
    opt = site / "reports" / "eplus_gym" / "optimization"
    studies = sorted(opt.glob("*")) if opt.is_dir() else []
    print(f"studies={len(studies)}")
    for p in studies[:10]:
        print(f"  - {p.name}")
    print("simulator_required=", SIMULATOR)
    print("streamlit=REMOVED")
    print("bacnet_writes=NO")
    return EXIT_OK


def cmd_optimize_day(args) -> int:
    print(SCREENING_CLAIM)
    if args.simulator != "LIVE_ENERGYPLUS":
        print("REFUSED: only LIVE_ENERGYPLUS permitted", file=sys.stderr)
        return EXIT_INTEGRITY
    site = _site(args)
    bundle = load_site_ui_bundle(site)
    champ = bundle.champion()
    idf = Path(champ.idf_path) if champ and champ.idf_path else Path(bundle.idf_path or "")
    epw = Path(bundle.epw) if bundle.epw else None
    if not idf.is_file() or epw is None or not epw.is_file():
        print("FAIL: champion/epw missing", file=sys.stderr)
        return EXIT_CONFIG
    site_cfg = load_site_dsm_config(site)
    if args.money_mode == "PHYSICAL_ONLY":
        tariff = TariffContract.physical_only(
            existing_billing_peak_kw=float(args.existing_billing_peak_kw)
        )
    elif args.money_mode == "ILLUSTRATIVE":
        tariff = TariffContract.illustrative(
            energy_rate_per_kwh=0.12,
            demand_rate_per_kw=15.0,
            existing_billing_peak_kw=float(args.existing_billing_peak_kw),
        )
    else:
        tariff = TariffContract(
            money_mode="VERIFIED_TARIFF",
            energy_rate_per_kwh=float(args.energy_rate),
            demand_rate_per_kw=float(args.demand_rate),
            existing_billing_peak_kw=float(args.existing_billing_peak_kw),
            verified=True,
        )

    from eplus_gym.envs.lakeside_w2a import LakesideW2AEnv

    def env_factory(epw_p: Path, idf_p: Path, out: Path):
        return LakesideW2AEnv(
            {
                "epw": str(epw_p),
                "idf": str(idf_p),
                "output": str(out),
                "occupied_heating_f": float(
                    (site_cfg.get("setpoints_f") or {}).get("occupied_heating_f", 70.0)
                ),
                "queue_timeout_s": 180.0,
                "six_zone_actuators": True,
            }
        )

    result = run_six_zone_study(
        site_root=site,
        day=args.day,
        epw=epw,
        champion_idf=idf,
        stage_fn=stage_idf_for_period,
        env_factory_fn=env_factory,
        tariff=tariff,
        lookback_days=int(args.lookback_days),
        budget=int(args.budget),
        max_kwh_penalty=float(args.max_kwh_penalty),
        money_mode=args.money_mode,
        no_cache=bool(args.no_cache),
        study_id=args.study_id,
        site_cfg=site_cfg,
        sha256_file=sha256_file,
    )
    print(json.dumps({k: result[k] for k in result if k != "recommendation"}, indent=2))
    if not result.get("ok"):
        return EXIT_EPLUS
    rec = result.get("recommendation") or {}
    if not (rec.get("recommended") or {}).get("feasible", True):
        # may still have a recommendation that is baseline
        pass
    ledger = result.get("ledger") or {}
    if ledger.get("simulations_succeeded", 0) == 0:
        return EXIT_EPLUS
    feas = [
        r
        for r in json.loads(
            (Path(result["root"]) / "pareto_frontier.json").read_text(encoding="utf-8")
        ).get("frontier")
        or []
        if r.get("feasible")
    ]
    if not feas and args.money_mode == "PHYSICAL_ONLY":
        # baseline may be infeasible under strict comfort — still integrity ok
        print("WARN: no feasible candidates on Pareto; see recommendation.json")
        return EXIT_NO_FEASIBLE
    print("study_root", result["root"])
    return EXIT_OK


def cmd_show_study(args) -> int:
    site = _site(args)
    root = site / "reports" / "eplus_gym" / "optimization" / args.study_id
    if not root.is_dir():
        print("missing study", root, file=sys.stderr)
        return EXIT_CONFIG
    for name in (
        "study_request.json",
        "study_status.json",
        "recommendation.json",
        "audit.json",
        "hashes.json",
    ):
        p = root / name
        print(f"=== {name} ===")
        if p.is_file():
            print(p.read_text(encoding="utf-8")[:4000])
        else:
            print("MISSING")
    return EXIT_OK


def cmd_approve(args) -> int:
    site = _site(args)
    root = site / "reports" / "eplus_gym" / "optimization" / args.study_id
    rec_path = root / "recommendation.json"
    if not rec_path.is_file():
        print("missing recommendation.json", file=sys.stderr)
        return EXIT_CONFIG
    rec = json.loads(rec_path.read_text(encoding="utf-8"))
    approved = {
        **rec,
        "approved": True,
        "approved_note": (
            "Human/agent approved proposal artifact only — "
            "Site Config / BACnet / champion / ECM NOT modified."
        ),
    }
    out = root / "approved_recommendation.json"
    out.write_text(json.dumps(approved, indent=2) + "\n", encoding="utf-8")
    print("wrote", out)
    print("site_config_mutated=false")
    print("bacnet_mutated=false")
    return EXIT_OK


def cmd_export_study(args) -> int:
    site = _site(args)
    root = site / "reports" / "eplus_gym" / "optimization" / args.study_id
    if args.format != "csv":
        print("only --format csv supported", file=sys.stderr)
        return EXIT_CONFIG
    src = root / "evaluation_history.csv"
    if not src.is_file():
        print("missing evaluation_history.csv", file=sys.stderr)
        return EXIT_CONFIG
    dest = root / "export_evaluation_history.csv"
    dest.write_bytes(src.read_bytes())
    print("wrote", dest)
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=SCREENING_CLAIM)
    site_parent = argparse.ArgumentParser(add_help=False)
    site_parent.add_argument("--site-root", type=Path, default=None)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("status", parents=[site_parent])
    s.set_defaults(func=cmd_status)

    o = sub.add_parser("optimize-day", parents=[site_parent])
    o.add_argument("--day", required=True)
    o.add_argument("--lookback-days", type=int, default=3)
    o.add_argument("--budget", type=int, default=64)
    o.add_argument(
        "--money-mode",
        default="PHYSICAL_ONLY",
        choices=["PHYSICAL_ONLY", "ILLUSTRATIVE", "VERIFIED_TARIFF"],
    )
    o.add_argument("--max-kwh-penalty", type=float, default=100.0)
    o.add_argument("--simulator", default="LIVE_ENERGYPLUS")
    o.add_argument("--no-cache", action="store_true", default=True)
    o.add_argument("--study-id", default=None)
    o.add_argument("--existing-billing-peak-kw", type=float, default=0.0)
    o.add_argument("--energy-rate", type=float, default=0.0)
    o.add_argument("--demand-rate", type=float, default=0.0)
    o.set_defaults(func=cmd_optimize_day)

    sh = sub.add_parser("show-study", parents=[site_parent])
    sh.add_argument("--study-id", required=True)
    sh.set_defaults(func=cmd_show_study)

    a = sub.add_parser("approve", parents=[site_parent])
    a.add_argument("--study-id", required=True)
    a.set_defaults(func=cmd_approve)

    e = sub.add_parser("export-study", parents=[site_parent])
    e.add_argument("--study-id", required=True)
    e.add_argument("--format", default="csv")
    e.set_defaults(func=cmd_export_study)

    args = p.parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit as exc:
        return int(exc.code or EXIT_CONFIG)


if __name__ == "__main__":
    raise SystemExit(main())
