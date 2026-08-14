"""Compare RL policy day vs coordinate-descent / baseline controller (LIVE)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from eplus_gym.episode import SCREENING_CLAIM
from eplus_gym.rl import SIMULATOR_REQUIRED
from eplus_gym.rl.live_day_worker import run_live_day_subprocess
from eplus_gym.rl.plots import plot_day_facility_kw, plot_rl_vs_baseline, plot_zone_temps_vs_sp
from eplus_gym.six_zone_daily_controller import SixZoneDailyController, SixZoneDailyParams


def _run_day(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    day: str,
    ctrl: SixZoneDailyController,
    out_dir: Path,
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = run_live_day_subprocess(
        site_root=site_root,
        epw=epw,
        champion_idf=champion_idf,
        day=day,
        params=ctrl.params.to_dict(),
        ep_dir=out_dir,
    )
    return {
        "daily_kwh": payload.get("daily_kwh"),
        "peak_kw": payload.get("peak_kw"),
        "reward": payload.get("reward"),
        "pre8_violations": payload.get("pre8_violations"),
        "trajectory": payload.get("trajectory") or str(out_dir / "trajectory.parquet"),
        "params": ctrl.params.to_dict(),
        "failed": bool(payload.get("failed")),
    }


def compare_policies(
    *,
    site_root: Path,
    epw: Path,
    champion_idf: Path,
    day: str,
    run_root: Path,
    rl_params: Optional[SixZoneDailyParams] = None,
    descent_params: Optional[SixZoneDailyParams] = None,
) -> Dict[str, Any]:
    plots = Path(run_root) / "plots"
    rows: List[Dict[str, Any]] = []

    base_ctrl = SixZoneDailyController(SixZoneDailyParams())
    base = _run_day(
        site_root=site_root,
        epw=epw,
        champion_idf=champion_idf,
        day=day,
        ctrl=base_ctrl,
        out_dir=Path(run_root) / "compare" / "baseline_site",
    )
    base["label"] = "site_baseline"
    rows.append(base)

    if rl_params is not None:
        rl = _run_day(
            site_root=site_root,
            epw=epw,
            champion_idf=champion_idf,
            day=day,
            ctrl=SixZoneDailyController(rl_params),
            out_dir=Path(run_root) / "compare" / "rl",
        )
        rl["label"] = "rl"
        rows.append(rl)
        df = pd.read_parquet(rl["trajectory"])
        plot_day_facility_kw(df, plots, title=f"RL facility kW {day}", filename="compare_rl_facility.png")
        plot_zone_temps_vs_sp(df, plots, title=f"RL zones {day}", filename="compare_rl_zones.png")

    if descent_params is not None:
        cd = _run_day(
            site_root=site_root,
            epw=epw,
            champion_idf=champion_idf,
            day=day,
            ctrl=SixZoneDailyController(descent_params),
            out_dir=Path(run_root) / "compare" / "coordinate_descent",
        )
        cd["label"] = "coordinate_descent"
        rows.append(cd)

    plot_rl_vs_baseline(rows, plots)
    out = {
        "scientific_claim": SCREENING_CLAIM,
        "simulator": SIMULATOR_REQUIRED,
        "day": day,
        "rows": rows,
    }
    (Path(run_root) / "compare_summary.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out


def load_params_from_recommendation(path: Path) -> SixZoneDailyParams | None:
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    rec = doc.get("recommended") or doc
    params = rec.get("params") or (rec.get("controller") or {}).get("params")
    if not isinstance(params, dict):
        return None
    return SixZoneDailyController(params).params


def load_eval_params_from_run(
    run_root: Path,
    *,
    day: str,
    epw: Path,
    algo: str = "PPO",
) -> tuple[SixZoneDailyParams | None, str]:
    """Deterministic zip predict first. Train reward.json is not eval."""
    from datetime import date

    from eplus_gym.rl.midnight_forecast import forecast_from_epw_replay
    from eplus_gym.rl.policy_pack import pack_from_sb3_zip
    from eplus_gym.rl.spaces import build_day_observation

    root = Path(run_root)
    algo_u = str(algo).upper()
    zips = [
        root / "models" / f"{algo_u.lower()}_final.zip",
        root / "models" / "ppo_final.zip",
        root / "dqn" / "models" / "dqn_final.zip",
    ]
    zip_path = next((p for p in zips if p.is_file()), None)
    if zip_path is not None:
        pack = pack_from_sb3_zip(zip_path, algo=algo_u)
        d = date.fromisoformat(str(day)[:10])
        fc = forecast_from_epw_replay(Path(epw), d)
        mean_c, min_c, max_c, morn_c, h0, hm10 = fc.features()
        obs = build_day_observation(
            month=d.month,
            dow=d.weekday(),
            doy=int(d.strftime("%j")),
            oat_mean_c=mean_c,
            oat_min_c=min_c,
            oat_max_c=max_c,
            morning_min_c=morn_c,
            hours_below_0c=h0,
            hours_below_m10c=hm10,
        )
        return pack.predict_params(obs), f"sb3_zip_deterministic:{zip_path.name}"
    last = None
    for p in sorted(root.rglob("reward.json")):
        cand = load_rl_action_as_params(p)
        if cand is not None:
            last = cand
    return last, "train_reward_json_not_eval"
