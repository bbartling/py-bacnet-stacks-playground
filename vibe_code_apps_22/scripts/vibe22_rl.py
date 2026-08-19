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
    load_eval_params_from_run,
    load_params_from_recommendation,
)
from eplus_gym.rl.day_pool import (  # noqa: E402
    build_year_plus_heating2x_pool,
    sample_unique_heating_days,
)
from eplus_gym.rl.field_sidecar import midnight_tick  # noqa: E402
from eplus_gym.rl.policy_pack import DailyPolicyPack  # noqa: E402
from eplus_gym.rl.report_bundle import build_report  # noqa: E402
from eplus_gym.rl.split_manifest import persist_train_fold  # noqa: E402
from eplus_gym.rl.operator_pay_experiment import refuse_full_campaign  # noqa: E402
from eplus_gym.rl.train_sb3 import bakeoff, train_sb3  # noqa: E402
from eplus_gym.site_pins import resolve_a04_and_epw, resolve_site_epw, sha256_file  # noqa: E402

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
    try:
        return resolve_a04_and_epw(site)
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(EXIT_CONFIG) from exc


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
    days, _specs, manifest = persist_train_fold(days, root / "split_manifest.json")
    print(json.dumps({"split": manifest.get("n"), "sha256": manifest.get("sha256")}))
    summary = train_sb3(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        days=days,
        algo=args.algo,
        timesteps=int(args.timesteps),
        run_root=root,
        seed=int(args.seed),
        occupied_heating_f=70.0,
        unoccupied_heating_f=65.0,
        reward_name=str(getattr(args, "reward_name", "reward_v2")),
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
    # Deterministic zip predict. Last train reward.json is not eval.
    rl_params, rl_src = load_eval_params_from_run(root, day=args.day, epw=epw, algo="PPO")
    if rl_params is None:
        for p in sorted(root.rglob("reward.json")):
            rl_params = load_rl_action_as_params(p)
            rl_src = "train_reward_json_not_eval"
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
    out["rl_params_source"] = rl_src
    print(json.dumps(out, indent=2))
    return EXIT_OK


def cmd_pretrain(args) -> int:
    """Office continuous-horizon pretrain: many 1-day LIVE episodes, pickle pack."""
    print(SCREENING_CLAIM)
    if args.simulator != SIMULATOR_REQUIRED:
        print("REFUSED: only LIVE_ENERGYPLUS", file=sys.stderr)
        return EXIT_INTEGRITY
    site = _site(args)
    idf, epw = _paths(site)
    champ_hash = sha256_file(idf)
    days = [d.strip() for d in str(args.days).split(",") if d.strip()]
    run_id = args.run_id or "office_pretrain_horizon"
    root = site / "reports" / "eplus_gym" / "rl" / run_id
    summary = train_sb3(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        days=days,
        algo=args.algo,
        timesteps=int(args.timesteps),
        run_root=root,
        seed=int(args.seed),
        occupied_heating_f=70.0,
        unoccupied_heating_f=65.0,
    )
    if sha256_file(idf) != champ_hash:
        print("INTEGRITY FAIL: champion mutated", file=sys.stderr)
        return EXIT_INTEGRITY
    pack = root / "models" / "daily_policy.pkl"
    shared = site / "reports" / "eplus_gym" / "rl" / "field_shared"
    shared.mkdir(parents=True, exist_ok=True)
    if pack.is_file():
        dest = shared / "daily_policy.pkl"
        dest.write_bytes(pack.read_bytes())
        js = pack.with_suffix(".json")
        if js.is_file():
            (shared / "daily_policy.json").write_text(js.read_text(encoding="utf-8"), encoding="utf-8")
        summary["field_shared_pack"] = str(dest)
    (root / "hashes.json").write_text(
        json.dumps({"champion_sha256": champ_hash, "unchanged": True}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    print("policy_pack", pack)
    return EXIT_OK


def cmd_midnight(args) -> int:
    print(SCREENING_CLAIM)
    site = _site(args)
    _idf, epw = _paths(site)
    pack = Path(args.pack) if args.pack else (
        site / "reports" / "eplus_gym" / "rl" / "field_shared" / "daily_policy.pkl"
    )
    if not pack.is_file():
        print(f"FAIL: missing policy pack {pack}", file=sys.stderr)
        return EXIT_CONFIG
    out = Path(args.out) if args.out else (
        site / "reports" / "eplus_gym" / "rl" / "field_shared" / "proposed_setpoints.json"
    )
    proposal = midnight_tick(
        pack_path=pack,
        day=args.day,
        epw=epw,
        forecast_source=args.forecast_source,
        out_path=out,
    )
    print(json.dumps(proposal, indent=2))
    return EXIT_OK


def cmd_eval(args) -> int:
    print(SCREENING_CLAIM)
    site = _site(args)
    idf, epw = _paths(site)
    days = [d.strip() for d in str(args.days).split(",") if d.strip()]
    root = site / "reports" / "eplus_gym" / "rl" / args.run_id
    from eplus_gym.rl.eval_policy import eval_days
    from eplus_gym.six_zone_daily_controller import SixZoneDailyParams, incumbent_lookback_params

    override = None
    pack = Path(args.pack) if args.pack else None
    if args.arm == "incumbent":
        override = incumbent_lookback_params().to_dict()
        pack = None
    elif args.arm == "no_setback":
        override = SixZoneDailyParams(occupied_heating_f=70.0, unoccupied_heating_f=70.0).to_dict()
        pack = None
    rows = eval_days(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        days=days,
        pack_path=pack,
        out_csv=root / "eval_episodes.csv",
        policy_label=str(args.arm) + "_eval",
        reward_name=str(args.reward_name),
        params_override=override,
    )
    print(json.dumps({"n": len(rows), "failed": sum(1 for r in rows if r.get("failed"))}, indent=2))
    return EXIT_OK


def cmd_operator_pay_experiment(args) -> int:
    from eplus_gym.rl.operator_pay_experiment import (
        OperatorPayExperimentError,
        run_operator_pay_experiment,
    )

    print(SCREENING_CLAIM)
    try:
        out = run_operator_pay_experiment(
            app_root=_APP,
            site_root=_site(args),
            run_id=str(args.run_id),
            reward_name=str(args.reward_name),
            mode=str(args.mode),
            simulator=str(args.simulator),
            seed=int(args.seed),
        )
    except OperatorPayExperimentError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return EXIT_INTEGRITY
    printable = {k: v for k, v in out.items() if k not in {"manifest"}}
    print(json.dumps(printable, indent=2, default=str))
    return int(out.get("exit_code") or EXIT_OK)


def cmd_research_long(args) -> int:
    """Labeled research-long. Cannot enable campaign or long_campaign_allowed."""
    from eplus_gym.rl.research_long import ResearchLongError, run_research_long
    from eplus_gym.rl.research_model import ResearchModelError

    if str(getattr(args, "simulator", SIMULATOR_REQUIRED)) != SIMULATOR_REQUIRED:
        print(json.dumps({"command": "research-long", "allowed": False, "reason": "only LIVE_ENERGYPLUS"}))
        return EXIT_INTEGRITY
    if not bool(getattr(args, "confirm_simulation_only_physics_limits", False)) or not bool(
        getattr(args, "confirm_a04_not_transient_validated", False)
    ):
        print(
            json.dumps(
                {
                    "command": "research-long",
                    "allowed": False,
                    "reason": "missing --confirm-simulation-only-physics-limits and/or --confirm-a04-not-transient-validated",
                    "long_campaign_allowed": False,
                    "SIMULATION_TRAINING_READY": False,
                    "OPERATIONAL_DSM_READY": False,
                }
            )
        )
        return EXIT_INTEGRITY
    try:
        live = bool(getattr(args, "micro_gate", False)) or bool(getattr(args, "execute_live", False))
        site = _site(args) if live else Path(args.site_root or os.environ.get("SITE_ROOT") or ".")
        out = run_research_long(
            app_root=_APP,
            site_root=site,
            confirm_simulation_only_physics_limits=True,
            confirm_a04_not_transient_validated=True,
            max_wall_hours=float(getattr(args, "max_wall_hours", 30.0) or 30.0),
            micro_gate=bool(getattr(args, "micro_gate", False)),
            execute_live=bool(getattr(args, "execute_live", False)),
            heartbeat_path=Path(args.heartbeat) if getattr(args, "heartbeat", None) else None,
            seed=int(getattr(args, "seed", 0) or 0),
            obs_schema=str(getattr(args, "obs_schema", "v4") or "v4"),
            tariff_mode=str(getattr(args, "tariff_mode", "flat_illustrative") or "flat_illustrative"),
            child_idf=Path(args.child_idf) if getattr(args, "child_idf", None) else None,
            campaign_labels=tuple(str(x) for x in (getattr(args, "campaign_labels", "") or "").split("|") if x) or None,
        )
    except (ResearchLongError, ResearchModelError, SystemExit) as exc:
        print(json.dumps({"command": "research-long", "allowed": False, "reason": str(exc), "long_campaign_allowed": False}))
        return EXIT_INTEGRITY
    print(json.dumps(out, indent=2, default=str))
    return EXIT_OK


def cmd_research_poc(args) -> int:
    """Bounded real-EnergyPlus research PoC. Cannot enable --mode full or long_campaign_allowed."""
    from eplus_gym.rl.research_model import ResearchModelError
    from eplus_gym.rl.research_poc import ResearchPocError, run_research_poc

    if str(getattr(args, "simulator", SIMULATOR_REQUIRED)) != SIMULATOR_REQUIRED:
        print(json.dumps({"command": "research-poc", "allowed": False, "reason": "only LIVE_ENERGYPLUS"}))
        return EXIT_INTEGRITY
    if not bool(getattr(args, "confirm_simulation_only_physics_limits", False)):
        print(
            json.dumps(
                {
                    "command": "research-poc",
                    "allowed": False,
                    "reason": "missing --confirm-simulation-only-physics-limits",
                    "long_campaign_allowed": False,
                }
            )
        )
        return EXIT_INTEGRITY
    try:
        site = _site(args)
        out = run_research_poc(
            app_root=_APP,
            site_root=site,
            confirm_simulation_only_physics_limits=True,
            max_wall_hours=float(args.max_wall_hours),
            seed=int(getattr(args, "seed", 0) or 0),
        )
    except (ResearchPocError, ResearchModelError, SystemExit) as exc:
        print(json.dumps({"command": "research-poc", "allowed": False, "reason": str(exc)}))
        return EXIT_INTEGRITY
    if bool(getattr(args, "execute_live", False)):
        from eplus_gym.rl.research_poc_live import execute_research_poc_live

        live = execute_research_poc_live(
            app_root=_APP,
            site_root=site,
            max_wall_hours=float(args.max_wall_hours),
            seed=int(getattr(args, "seed", 0) or 0),
        )
        out["live"] = live
    print(json.dumps(out, indent=2, default=str))
    return EXIT_OK


def cmd_campaign(args) -> int:
    """Contiguous-block campaign after verified Track B active model. Refuses A04 by default."""
    print(SCREENING_CLAIM)
    if args.simulator != SIMULATOR_REQUIRED:
        print("REFUSED: only LIVE_ENERGYPLUS", file=sys.stderr)
        return EXIT_INTEGRITY
    decision = refuse_full_campaign(_APP)
    if not decision["allowed"]:
        stub = {
            "command": "campaign",
            "allowed": False,
            "verdict": decision.get("verdict"),
            "reason": decision.get("reason") or "physics-ramp gate is not PASS; long campaign refused",
            "n_days": int(getattr(args, "n_days", 0) or 0),
        }
        print(json.dumps(stub, indent=2, default=str))
        return EXIT_INTEGRITY
    from eplus_gym.a04_identity import is_canonical_a04_idf_filename
    from eplus_gym.rl.active_model import ActiveModelError, verify_active_model

    try:
        manifest = verify_active_model(_APP)
    except ActiveModelError as exc:
        print(json.dumps({"command": "campaign", "allowed": False, "reason": str(exc)}, indent=2))
        return EXIT_INTEGRITY
    rel = str(manifest.get("idf_path") or "")
    idf = _APP / rel
    if is_canonical_a04_idf_filename(idf.name) and not manifest.get("a04_explicitly_verified_active"):
        print(
            json.dumps(
                {
                    "command": "campaign",
                    "allowed": False,
                    "reason": "campaign refuses A04 unless it is explicitly the verified active model",
                },
                indent=2,
            )
        )
        return EXIT_INTEGRITY
    site = _site(args)
    try:
        epw = resolve_site_epw(site)
    except FileNotFoundError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return EXIT_CONFIG
    champ_hash = sha256_file(idf)
    n = int(args.n_days)
    if str(getattr(args, "pool", "unique_heating")) == "year2xsyn":
        synth = site / "reports" / "eplus_gym" / "rl" / (args.run_id or "year2xsyn") / "synthetic_epw"
        pool = build_year_plus_heating2x_pool(epw, seed=int(args.seed), synth_dir=synth)
    else:
        pool = sample_unique_heating_days(epw, n=n, seed=int(args.seed))
    days = list(pool["days"])
    specs = list(pool.get("specs") or [])
    if not days:
        print("FAIL: no unique EPW days", file=sys.stderr)
        return EXIT_CONFIG
    run_id = args.run_id
    if pool.get("pool") == "year_plus_heating2x_synthetic" and run_id in (
        "unique100_winter",
        None,
        "",
    ):
        run_id = "year2xsyn"
    root = site / "reports" / "eplus_gym" / "rl" / run_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "day_pool.json").write_text(json.dumps(pool, indent=2) + "\n", encoding="utf-8")
    days, specs, manifest = persist_train_fold(
        days, root / "split_manifest.json", day_specs=specs
    )
    print(
        json.dumps(
            {
                "split": manifest.get("n"),
                "sha256": manifest.get("sha256"),
                "train_only": True,
            }
        )
    )
    dqn_root = root / "dqn"
    kwargs = dict(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        days=days,
        timesteps=len(days),
        seed=int(args.seed),
        occupied_heating_f=70.0,
        unoccupied_heating_f=65.0,
        day_specs=specs,
        reward_name=str(args.reward_name),
    )
    n_train = len(days)
    print(
        json.dumps(
            {
                "budget": {
                    "n_days": n_train,
                    "expected_eplus_calls_ppo_one_pass": n_train,
                    "note": "contextual bandit; one E+ day per SB3 step; DQN ablation extra",
                    "rough_wall_s": n_train * 20,
                }
            }
        )
    )
    print(json.dumps({"phase": "PPO", "n_days": len(days), "pool": pool.get("pool"), "shortfall": pool["shortfall"]}))
    ppo_sum = train_sb3(algo="PPO", run_root=root, **kwargs)
    print(json.dumps({"phase": "DQN", "n_days": len(days)}))
    dqn_sum = train_sb3(algo="DQN", run_root=dqn_root, **kwargs)
    if sha256_file(idf) != champ_hash:
        print("INTEGRITY FAIL: champion mutated", file=sys.stderr)
        return EXIT_INTEGRITY
    repo_copy = Path(__file__).resolve().parents[1] / (
        "plots/rl_report_year2x"
        if pool.get("pool") == "year_plus_heating2x_synthetic"
        else "plots/rl_report"
    )
    print(json.dumps({"phase": "report", "random_and_heuristic": len(days), "repo_copy": str(repo_copy)}))
    comparison = build_report(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        run_root=root,
        days=days,
        random_timesteps=len(days),
        heuristic_days=not args.skip_heuristic,
        seed=int(args.seed),
        repo_copy=repo_copy,
        dqn_run_root=dqn_root,
        day_pool=pool,
    )
    (root / "campaign_summary.json").write_text(
        json.dumps(
            {
                "ppo": ppo_sum,
                "dqn": dqn_sum,
                "comparison": comparison,
                "scientific_claim": SCREENING_CLAIM,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(comparison, indent=2))
    print("repo_copy", repo_copy)
    return EXIT_OK


def cmd_preflight_campaign(args) -> int:
    from eplus_gym.rl.campaign_preflight import PreflightError, preflight_campaign

    path = Path(args.bundle)
    bundle = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    try:
        out = preflight_campaign(bundle, app_root=_APP)
    except PreflightError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, indent=2))
        return EXIT_INTEGRITY
    print(json.dumps(out, indent=2))
    return EXIT_OK


def cmd_prepare_campaign(args) -> int:
    from eplus_gym.rl.campaign_bundle import CampaignBundleError, prepare_campaign_bundle, write_bundle
    from eplus_gym.rl.campaign_preflight import PreflightError, preflight_campaign

    days = [d.strip() for d in str(args.days).split(",") if d.strip()]
    out_path = Path(args.out)
    try:
        bundle = prepare_campaign_bundle(
            app_root=_APP,
            site_root=_site(args),
            days=days,
            live_incumbent_baselines=bool(args.live_baselines),
            output_root=out_path.parent,
        )
        write_bundle(out_path, bundle)
        preflight_campaign(bundle, app_root=_APP)
    except (CampaignBundleError, PreflightError, SystemExit) as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, indent=2))
        return EXIT_INTEGRITY
    print(json.dumps({"ok": True, "out": str(out_path), "n_days": len(days)}, indent=2))
    return EXIT_OK


def cmd_legacy_daily_env(args) -> int:
    """Explicit diagnostic: DailySixZoneGymEnv. Unreachable from campaign."""
    from eplus_gym.rl.daily_env import DailySixZoneGymEnv
    from eplus_gym.rl.train_sb3 import campaign_env_class

    print(
        json.dumps(
            {
                "command": "legacy-daily-env",
                "legacy_diagnostic": True,
                "env": DailySixZoneGymEnv.__name__,
                "campaign_env": campaign_env_class.__name__,
                "unreachable_from_campaign": True,
                "did_not_train": True,
            }
        )
    )
    return EXIT_OK


def cmd_report(args) -> int:
    print(SCREENING_CLAIM)
    site = _site(args)
    idf, epw = _paths(site)
    app = Path(__file__).resolve().parents[1]
    root = site / "reports" / "eplus_gym" / "rl" / args.run_id
    if not root.is_dir():
        print(f"FAIL: missing run_root {root}", file=sys.stderr)
        return EXIT_CONFIG
    dqn_root = root / "dqn"
    pool = None
    use_year2x = str(getattr(args, "pool", "") or "") == "year2xsyn" or str(args.run_id) == "year2xsyn"
    if use_year2x:
        pool_path = root / "day_pool.json"
        if not pool_path.is_file():
            print(f"FAIL: missing {pool_path}", file=sys.stderr)
            return EXIT_CONFIG
        pool = json.loads(pool_path.read_text(encoding="utf-8"))
        days = [str(d) for d in pool.get("days") or []]
        if not days:
            print("FAIL: empty day_pool days", file=sys.stderr)
            return EXIT_CONFIG
        random_n = len(days)
        repo_copy = app / "plots" / "rl_report_year2x"
        seed = int(args.seed)
    else:
        days = [d.strip() for d in str(args.days).split(",") if d.strip()]
        random_n = int(args.random_timesteps)
        repo_copy = app / "plots" / "rl_report"
        seed = int(args.seed)
    print(
        json.dumps(
            {
                "phase": "report",
                "run_id": args.run_id,
                "n_days": len(days),
                "random_timesteps": random_n,
                "repo_copy": str(repo_copy),
                "year2xsyn": use_year2x,
            }
        )
    )
    out = build_report(
        site_root=site,
        epw=epw,
        champion_idf=idf,
        run_root=root,
        days=days,
        random_timesteps=random_n,
        heuristic_days=not args.skip_heuristic,
        seed=seed,
        repo_copy=repo_copy,
        dqn_run_root=dqn_root if (dqn_root / "episodes.jsonl").is_file() else None,
        day_pool=pool,
    )
    if use_year2x:
        ppo_sum = {}
        dqn_sum = {}
        ppo_p = root / "train_summary.json"
        dqn_p = dqn_root / "train_summary.json"
        if ppo_p.is_file():
            ppo_sum = json.loads(ppo_p.read_text(encoding="utf-8"))
        if dqn_p.is_file():
            dqn_sum = json.loads(dqn_p.read_text(encoding="utf-8"))
        (root / "campaign_summary.json").write_text(
            json.dumps(
                {
                    "ppo": ppo_sum,
                    "dqn": dqn_sum,
                    "comparison": out,
                    "scientific_claim": SCREENING_CLAIM,
                    "resumed": "report_only_no_retrain",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    print(json.dumps(out, indent=2))
    print("repo_copy", repo_copy)
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
    t.add_argument("--reward-name", required=True)
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

    pt = sub.add_parser("pretrain", parents=[site_parent])
    pt.add_argument("--algo", choices=["PPO", "DQN"], default="PPO")
    pt.add_argument(
        "--days",
        default="2026-01-20,2026-01-21,2026-01-22,2026-01-23,2026-01-24,2026-01-25,2026-01-26",
    )
    pt.add_argument("--timesteps", type=int, default=20)
    pt.add_argument("--seed", type=int, default=0)
    pt.add_argument("--run-id", default="office_pretrain_horizon")
    pt.add_argument("--simulator", default=SIMULATOR_REQUIRED)
    pt.set_defaults(func=cmd_pretrain)

    m = sub.add_parser("midnight-tick", parents=[site_parent])
    m.add_argument("--day", default="2026-01-26")
    m.add_argument("--pack", default=None)
    m.add_argument("--out", default=None)
    m.add_argument("--forecast-source", default="epw_replay")
    m.set_defaults(func=cmd_midnight)

    rp = sub.add_parser("report", parents=[site_parent])
    rp.add_argument("--run-id", default="office_pretrain_horizon")
    rp.add_argument(
        "--days",
        default="2026-01-20,2026-01-21,2026-01-22,2026-01-23,2026-01-24,2026-01-25,2026-01-26",
    )
    rp.add_argument("--random-timesteps", type=int, default=20)
    rp.add_argument("--seed", type=int, default=0)
    rp.add_argument("--skip-heuristic", action="store_true")
    rp.add_argument(
        "--pool",
        choices=["unique_heating", "year2xsyn"],
        default="unique_heating",
        help="year2xsyn loads day_pool.json and writes plots/rl_report_year2x (does not wipe unique-100)",
    )
    rp.set_defaults(func=cmd_report)

    camp = sub.add_parser("campaign", parents=[site_parent])
    camp.add_argument("--n-days", type=int, default=100)
    camp.add_argument("--seed", type=int, default=0)
    camp.add_argument("--run-id", default="unique100_winter")
    camp.add_argument("--simulator", default=SIMULATOR_REQUIRED)
    camp.add_argument("--skip-heuristic", action="store_true")
    camp.add_argument(
        "--pool",
        choices=["unique_heating", "year2xsyn"],
        default="unique_heating",
        help="unique_heating = n unique EPW days; year2xsyn = full AMY + synthetic 2x heating",
    )
    camp.add_argument("--reward-name", default="reward_v2")
    camp.set_defaults(func=cmd_campaign)

    pf = sub.add_parser("preflight-campaign")
    pf.add_argument("--bundle", required=True)
    pf.set_defaults(func=cmd_preflight_campaign)

    prep = sub.add_parser("prepare-campaign", parents=[site_parent])
    prep.add_argument("--days", default="2025-12-08,2025-12-09,2025-12-10")
    prep.add_argument("--out", required=True)
    prep.add_argument("--live-baselines", action="store_true")
    prep.add_argument("--model-manifest", default="contracts/active_rl_model_v1.json")
    prep.set_defaults(func=cmd_prepare_campaign)

    legacy = sub.add_parser("legacy-daily-env", parents=[site_parent])
    legacy.add_argument("--confirm-legacy-diagnostic", action="store_true", required=True)
    legacy.set_defaults(func=cmd_legacy_daily_env)

    ev = sub.add_parser("eval", parents=[site_parent])
    ev.add_argument("--run-id", required=True)
    ev.add_argument("--days", required=True)
    ev.add_argument("--arm", default="incumbent")
    ev.add_argument("--pack", default=None)
    ev.add_argument("--reward-name", required=True)
    ev.set_defaults(func=cmd_eval)

    op = sub.add_parser("operator-pay-experiment", parents=[site_parent])
    op.add_argument("--run-id", required=True)
    op.add_argument("--reward-name", required=True, choices=["operator_pay_2x_v1", "operator_pay_3x_v1"])
    op.add_argument("--mode", required=True, choices=["smoke", "full"])
    op.add_argument("--simulator", default=SIMULATOR_REQUIRED)
    op.add_argument("--seed", type=int, default=0)
    op.set_defaults(func=cmd_operator_pay_experiment)

    rp = sub.add_parser("research-poc", parents=[site_parent])
    rp.add_argument("--confirm-simulation-only-physics-limits", action="store_true")
    rp.add_argument("--max-wall-hours", type=float, default=6.0)
    rp.add_argument("--seed", type=int, default=0)
    rp.add_argument("--simulator", default=SIMULATOR_REQUIRED)
    rp.add_argument("--execute-live", action="store_true")
    rp.set_defaults(func=cmd_research_poc)

    rl = sub.add_parser("research-long", parents=[site_parent])
    rl.add_argument("--confirm-simulation-only-physics-limits", action="store_true")
    rl.add_argument("--confirm-a04-not-transient-validated", action="store_true")
    rl.add_argument("--max-wall-hours", type=float, default=30.0)
    rl.add_argument("--seed", type=int, default=0)
    rl.add_argument("--simulator", default=SIMULATOR_REQUIRED)
    rl.add_argument("--micro-gate", action="store_true")
    rl.add_argument("--execute-live", action="store_true")
    rl.add_argument("--heartbeat", default=None)
    rl.add_argument("--obs-schema", default="v4", choices=("v3", "v4"))
    rl.add_argument("--tariff-mode", default="flat_illustrative")
    rl.add_argument("--child-idf", default=None)
    rl.add_argument("--campaign-labels", default="", help="pipe-separated terminal labels")
    rl.set_defaults(func=cmd_research_long)

    args = p.parse_args(argv)
    try:
        return int(args.func(args))
    except SystemExit as exc:
        return int(exc.code or EXIT_CONFIG)


if __name__ == "__main__":
    raise SystemExit(main())
