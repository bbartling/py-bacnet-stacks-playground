"""Run one LIVE EnergyPlus day in a clean process (no torch/SB3).

Torch + EnergyPlus ``delete_state`` heap-corrupts on Windows (0xC0000374).
SB3 training therefore must never import pyenergyplus in the trainer process.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict

from eplus_gym.rl.reward import FAIL_REWARD


def run_live_day_inprocess(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    day: str,
    params: Dict[str, Any],
    ep_dir: Path,
    queue_timeout_s: float = 180.0,
    lookback_days: int = 1,
    reward_name: str = "legacy_reward_v1",
    reward_weights: Dict[str, Any] | None = None,
    mtd_peak_kw: float = 0.0,
) -> Dict[str, Any]:
    """Execute one day; safe only in a process that has not imported torch."""
    import pandas as pd

    from datetime import date, timedelta

    from eplus_gym.episode import SCREENING_CLAIM, run_controller_episode
    from eplus_gym.envs.lakeside_w2a import LakesideW2AEnv
    from eplus_gym.eplus_err import assert_eplus_quality, parse_eplus_err
    from eplus_gym.epw_stage import stage_year_aware_epw
    from eplus_gym.rl.day_pool import illustrative_school_day, unique_dates_from_epw
    from eplus_gym.rl.reward import RewardWeights, score_day
    from eplus_gym.six_zone_daily_controller import SixZoneDailyController
    from eplus_gym.stage_idf import stage_idf_for_period

    ep_dir = Path(ep_dir)
    ep_dir.mkdir(parents=True, exist_ok=True)
    ctrl = SixZoneDailyController(params)
    target = date.fromisoformat(str(day)[:10])
    lb = int(lookback_days)
    begin = target
    if lb > 0:
        begin = target - timedelta(days=lb)
        known = {d.isoformat() for d in unique_dates_from_epw(Path(epw))}
        if begin.isoformat() not in known:
            raise ValueError(
                f"no contiguous prior day {begin.isoformat()} in EPW for target {target.isoformat()}; "
                "refusing silent wrap"
            )
    staged_epw = stage_year_aware_epw(Path(epw), ep_dir / f"staged_{Path(epw).name}")["staged_epw"]
    staged = stage_idf_for_period(
        Path(champion_idf),
        ep_dir / f"staged_{Path(champion_idf).name}",
        begin.isoformat(),
        target.isoformat(),
        site_root=Path(site_root),
        six_zone_actuators=True,
    )

    def factory():
        return LakesideW2AEnv(
            {
                "epw": str(staged_epw),
                "idf": str(staged),
                "output": str(ep_dir / "eplus"),
                "queue_timeout_s": float(queue_timeout_s),
                "occupied_heating_f": float(ctrl.params.occupied_heating_f),
                "default_action_c": list(ctrl.action(0)),
                "six_zone_actuators": True,
            }
        )

    result = run_controller_episode(
        factory,
        ctrl,
        lookback_days=lb,
        scored_day=target.isoformat(),
        max_steps=None,
    )
    df = pd.DataFrame(result["rows"])
    pq = ep_dir / "trajectory.parquet"
    df.to_parquet(pq, index=False)
    w = RewardWeights(**reward_weights) if isinstance(reward_weights, dict) else RewardWeights()
    br = score_day(
        df,
        reward_name=str(reward_name),
        weights=w,
        school_day=illustrative_school_day(day),
        mtd_peak_kw=float(mtd_peak_kw),
    )
    payload = {
        "reward": br.reward,
        "daily_kwh": br.daily_kwh,
        "peak_kw": br.peak_kw,
        "pre8_violations": br.pre8_violations,
        "pre8_degree_hours": br.pre8_degree_hours,
        "occ_violations": br.occ_violations,
        "energy_cost": br.energy_cost,
        "peak_cost": br.peak_cost,
        "failed": br.failed,
        "extras": br.extras,
        "params": ctrl.params.to_dict(),
        "day": day,
        "n_rows": int(len(df)),
        "trajectory": str(pq),
        "scientific_claim": SCREENING_CLAIM,
        "simulator": "LIVE_ENERGYPLUS",
    }
    (ep_dir / "reward.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    err = ep_dir / "eplus" / "eplusout.err"
    if not err.is_file():
        found = list(ep_dir.rglob("eplusout.err"))
        err = found[0] if found else err
    gate = parse_eplus_err(err)
    payload["eplus_quality"] = gate
    payload["lookback_days"] = lb
    payload["n_all_rows"] = int(len(result.get("all_rows") or []))
    assert_eplus_quality(gate)
    return payload


def run_live_day_subprocess(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    day: str,
    params: Dict[str, Any],
    ep_dir: Path,
    queue_timeout_s: float = 180.0,
    timeout_s: float = 600.0,
    lookback_days: int = 1,
    reward_name: str = "legacy_reward_v1",
    reward_weights: Dict[str, Any] | None = None,
    mtd_peak_kw: float = 0.0,
) -> Dict[str, Any]:
    """Spawn a fresh interpreter for one LIVE day; return reward payload."""
    ep_dir = Path(ep_dir)
    ep_dir.mkdir(parents=True, exist_ok=True)
    job = {
        "site_root": str(site_root),
        "epw": str(epw),
        "champion_idf": str(champion_idf),
        "day": str(day)[:10],
        "params": params,
        "ep_dir": str(ep_dir),
        "queue_timeout_s": float(queue_timeout_s),
        "lookback_days": int(lookback_days),
        "reward_name": str(reward_name),
        "reward_weights": reward_weights,
        "mtd_peak_kw": float(mtd_peak_kw),
    }
    job_path = ep_dir / "job.json"
    out_path = ep_dir / "worker_result.json"
    job_path.write_text(json.dumps(job, indent=2) + "\n", encoding="utf-8")
    cmd = [
        sys.executable,
        "-m",
        "eplus_gym.rl.live_day_worker",
        "--job",
        str(job_path),
        "--out",
        str(out_path),
    ]
    # Fresh env: do not inherit CUDA/torch side effects; keep SITE_ROOT if set.
    proc = subprocess.run(
        cmd,
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
        timeout=float(timeout_s),
        check=False,
    )
    if proc.returncode != 0 or not out_path.is_file():
        err = (proc.stderr or proc.stdout or "")[-4000:]
        payload = {
            "reward": FAIL_REWARD,
            "failed": True,
            "error": f"rc={proc.returncode} day={day} {err[-800:]}",
            "daily_kwh": None,
            "peak_kw": None,
            "pre8_violations": 0,
            "params": params,
            "day": str(day),
            "n_rows": 0,
        }
        out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload
    return json.loads(out_path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="LIVE EnergyPlus day worker (no torch)")
    p.add_argument("--job", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args(argv)
    job = json.loads(Path(args.job).read_text(encoding="utf-8"))
    try:
        date.fromisoformat(str(job["day"])[:10])
        payload = run_live_day_inprocess(
            site_root=Path(job["site_root"]),
            epw=Path(job["epw"]),
            champion_idf=Path(job["champion_idf"]),
            day=str(job["day"])[:10],
            params=dict(job["params"]),
            ep_dir=Path(job["ep_dir"]),
            queue_timeout_s=float(job.get("queue_timeout_s", 180.0)),
            lookback_days=int(job.get("lookback_days", 1)),
            reward_name=str(job.get("reward_name") or "legacy_reward_v1"),
            reward_weights=job.get("reward_weights"),
            mtd_peak_kw=float(job.get("mtd_peak_kw") or 0.0),
        )
        Path(args.out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return 0
    except Exception as exc:  # noqa: BLE001
        Path(args.out).write_text(
            json.dumps({"failed": True, "error": str(exc)}, indent=2) + "\n",
            encoding="utf-8",
        )
        print(str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
