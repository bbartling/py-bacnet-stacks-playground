"""Deterministic saved-policy evaluation (never train jsonl)."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Sequence

from eplus_gym.rl.live_day_worker import run_live_day_subprocess
from eplus_gym.rl.policy_pack import DailyPolicyPack
from eplus_gym.rl.spaces import build_day_observation
from eplus_gym.six_zone_daily_controller import SixZoneDailyParams, incumbent_lookback_params


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
    for day in days:
        ep_dir = out_csv.parent / "eval_eps" / f"{policy_label}_{day}"
        if params_override is not None:
            params = dict(params_override)
        elif pack is not None:
            obs = build_day_observation(
                month=int(str(day)[5:7]),
                dow=0,
                doy=1,
                oat_mean_c=0.0,
                oat_min_c=0.0,
                oat_max_c=0.0,
            )
            params = pack.predict_params(obs).to_dict()
        else:
            params = incumbent_lookback_params().to_dict()
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
        rows.append(payload)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if rows:
        keys = sorted({k for r in rows for k in r if k != "extras"})
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in keys})
    (out_csv.with_suffix(".jsonl")).write_text(
        "".join(json.dumps({k: v for k, v in r.items() if k != "params"}) + "\n" for r in rows),
        encoding="utf-8",
    )
    return rows
