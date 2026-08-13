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


def load_rl_action_as_params(path: Path) -> SixZoneDailyParams | None:
    """Load last continuous action vector from a train episode reward.json if present."""
    if not path.is_file():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    params = doc.get("params")
    if isinstance(params, dict):
        return SixZoneDailyController(params).params
    return None
