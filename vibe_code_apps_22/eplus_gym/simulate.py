"""Run a rule-controller episode (live E+ or farm lookup)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .controllers import RuleController
from .discover import energyplus_available
from .honesty import HONESTY_IDEALLOADS, LOOKUP_EMULATOR, PROMOTE
from .lookup_emulator import FarmLookupEnv, list_farm_days


def run_rule_episode(
    *,
    site_root: Path,
    strategy_id: str = "baseline",
    day: Optional[str] = None,
    mode: str = "auto",  # auto | live | lookup
    epw: Optional[Path] = None,
    idf: Optional[Path] = None,
    output: Optional[Path] = None,
    max_steps: int = 96,
    verbose: bool = False,
) -> Dict[str, Any]:
    """Return trajectory dict with rows + meta. Prefer live when available."""
    site_root = Path(site_root)
    ctrl = RuleController(strategy_id)
    want_live = mode == "live" or (mode == "auto" and energyplus_available())

    rows: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {
        "strategy_id": strategy_id,
        "honesty": HONESTY_IDEALLOADS,
        "promote": PROMOTE,
    }

    if want_live and mode != "lookup":
        if epw is None or idf is None:
            # fall through to lookup if paths missing
            want_live = False
            meta["live_skip_reason"] = "epw/idf not provided"
        else:
            try:
                from .envs.lakeside_idealloads import LakesideIdealLoadsEnv

                out = Path(output or (site_root / "eplus" / "gym_runs"))
                out.mkdir(parents=True, exist_ok=True)
                env = LakesideIdealLoadsEnv(
                    {
                        "epw": str(epw),
                        "idf": str(idf),
                        "output": str(out),
                        "verbose": verbose,
                    }
                )
                obs, info = env.reset()
                meta.update(
                    {
                        "provenance": info.get("provenance"),
                        "mode": "live",
                        "day": day,
                    }
                )
                for t in range(max_steps):
                    action = ctrl.action_c(t)
                    obs_vec, reward, done, truncated, step_info = env.step(action)
                    od = step_info.get("obs_dict") or {}
                    rows.append(
                        {
                            "step": t,
                            "htg_sp_f": ctrl.setpoint_f(t),
                            "htg_sp_c": action,
                            "reward": reward,
                            **{k: float(v) for k, v in od.items()},
                        }
                    )
                    if done or truncated:
                        break
                env.close()
                return {"rows": rows, "meta": meta, "controller": ctrl}
            except Exception as exc:  # noqa: BLE001
                meta["live_error"] = str(exc)
                want_live = False

    # Lookup path
    days = list_farm_days(site_root, strategy_id)
    if day is None:
        if not days:
            raise FileNotFoundError(
                f"no farm days for {strategy_id} under {site_root}/eplus/dsm_farm_paired "
                "and live E+ unavailable/failed"
            )
        day = days[-1]
    env_l = FarmLookupEnv(
        site_root=site_root,
        day=day,
        strategy_id=strategy_id,
        htg_setpoints_f=ctrl.series_f(),
    )
    obs, info = env_l.reset()
    meta.update(
        {
            "provenance": LOOKUP_EMULATOR,
            "mode": "lookup",
            "day": day,
            "honesty": HONESTY_IDEALLOADS,
        }
    )
    rows.append(
        {
            "step": 0,
            "htg_sp_f": ctrl.setpoint_f(0),
            "htg_sp_c": ctrl.action_c(0),
            "reward": -float(obs["facility_kw"]) / 100.0,
            **obs,
        }
    )
    for t in range(1, max_steps):
        obs, reward, done, truncated, _ = env_l.step(ctrl.action_c(t))
        rows.append(
            {
                "step": t,
                "htg_sp_f": ctrl.setpoint_f(t),
                "htg_sp_c": ctrl.action_c(t),
                "reward": reward,
                **obs,
            }
        )
        if done or truncated:
            break
    env_l.close()
    return {"rows": rows, "meta": meta, "controller": ctrl}


def trajectory_frame(result: Dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(result["rows"])
