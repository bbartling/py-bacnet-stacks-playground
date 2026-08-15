"""Deterministic saved-policy evaluation (never train jsonl)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Sequence

from eplus_gym.rl.billing_state import BillingState
from eplus_gym.rl.live_day_worker import run_live_day_subprocess
from eplus_gym.rl.obs_context import observation_and_context
from eplus_gym.rl.policy_pack import DailyPolicyPack
from eplus_gym.six_zone_daily_controller import incumbent_lookback_params


def eval_days(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    days: Sequence[str],
    pack_path: Path | None,
    out_csv: Path,
    policy_label: str,
    lookback_days: int = 1,
    reward_name: str = "operator_pay_2x_v1",
    params_override: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pack = DailyPolicyPack.load(pack_path) if pack_path else None
    billing = BillingState()
    for day in days:
        ep_dir = out_csv.parent / "eval_eps" / f"{policy_label}_{day}"
        harvest_dir = ep_dir / "harvest_lookback"
        harvest = run_live_day_subprocess(
            site_root=site_root,
            epw=epw,
            champion_idf=champion_idf,
            day=str(day)[:10],
            params=incumbent_lookback_params().to_dict(),
            ep_dir=harvest_dir,
            lookback_days=lookback_days,
            reward_name="legacy_reward_v1",
            skip_paired_baseline=True,
        )
        temps = harvest.get("start_zone_temps_f")
        if not temps:
            raise ValueError(f"eval harvest missing lookback zone temps for {day}")
        floor = float(billing.start_of_day(str(day)[:10]))
        obs, ctx = observation_and_context(
            day=str(day)[:10],
            epw=epw,
            billing_floor_kw=floor,
            zone_temps_f=temps,
            mtd_peak_kw=floor,
        )
        (ep_dir / "eval_obs_context.json").write_text(json.dumps(ctx, indent=2) + "\n", encoding="utf-8")
        if params_override is not None:
            params = dict(params_override)
        elif pack is not None:
            params = pack.predict_params(obs).to_dict()
        else:
            params = incumbent_lookback_params().to_dict()
        (ep_dir / "eval_action_context.json").write_text(
            json.dumps({"params": params, "obs_unnormalized": ctx}, indent=2) + "\n",
            encoding="utf-8",
        )
        payload = run_live_day_subprocess(
            site_root=site_root,
            epw=epw,
            champion_idf=champion_idf,
            day=str(day)[:10],
            params=params,
            ep_dir=ep_dir,
            lookback_days=lookback_days,
            reward_name=reward_name,
        )
        payload["policy"] = policy_label
        payload["artifact_kind"] = "eval"
        payload["obs_context"] = ctx
        rows.append(payload)
        if payload.get("peak_kw") is not None:
            billing.observe_peak(float(payload["peak_kw"]))
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        keys = sorted({k for r in rows for k in r if k not in {"extras", "obs_context", "episode_manifest", "params"}})
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in keys})
    (out_csv.with_suffix(".jsonl")).write_text(
        "".join(json.dumps({k: v for k, v in r.items() if k not in {"params", "extras"}}) + "\n" for r in rows),
        encoding="utf-8",
    )
    return rows
