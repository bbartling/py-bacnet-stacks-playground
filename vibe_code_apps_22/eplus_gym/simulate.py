"""Run a rule-controller episode (live E+ or farm lookup)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import pandas as pd

from .controllers import RuleController
from .discover import energyplus_available
from .honesty import HONESTY_IDEALLOADS, HONESTY_W2A, LOOKUP_EMULATOR, PROMOTE
from .lookup_emulator import (
    FarmLookupEnv,
    list_farm_days,
    resolve_farm_root,
    resolve_w2a_farm_root,
    w2a_farm_ready,
)
from .month_calendar import DEPLOYABLE_STRATEGIES, month_kpis

FAMILY_W2A = "w2a"
FAMILY_IDEALLOADS = "idealloads"


def _norm_family(family: str) -> str:
    raw = str(family or FAMILY_IDEALLOADS).strip().lower()
    if raw in {FAMILY_W2A, "w2a_physical_dsm", "a04"}:
        return FAMILY_W2A
    return FAMILY_IDEALLOADS


def _live_episode(
    *,
    env_cls,
    epw: Path,
    idf: Path,
    output: Path,
    ctrl: RuleController,
    meta: Dict[str, Any],
    day: Optional[str],
    max_steps: int,
    verbose: bool,
) -> Dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    env = env_cls(
        {
            "epw": str(epw),
            "idf": str(idf),
            "output": str(output),
            "verbose": verbose,
        }
    )
    _obs, info = env.reset()
    meta.update(
        {
            "provenance": info.get("provenance"),
            "mode": "live",
            "day": day,
        }
    )
    rows: List[Dict[str, Any]] = []
    for t in range(max_steps):
        action = ctrl.action_c(t)
        _obs_vec, reward, done, truncated, step_info = env.step(action)
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


def _lookup_episode(
    *,
    site_root: Path,
    farm_root: Path,
    honesty: str,
    ctrl: RuleController,
    strategy_id: str,
    day: Optional[str],
    month: Optional[str],
    max_steps: int,
    meta: Dict[str, Any],
    missing_msg: str,
) -> Dict[str, Any]:
    days = list_farm_days(site_root, strategy_id, month=month, farm_root=farm_root)
    if day is None:
        if not days:
            raise FileNotFoundError(missing_msg)
        day = days[-1]
    env_l = FarmLookupEnv(
        site_root=site_root,
        day=day,
        strategy_id=strategy_id,
        htg_setpoints_f=ctrl.series_f(),
        farm_root=farm_root,
        honesty=honesty,
    )
    obs, _info = env_l.reset()
    meta.update(
        {
            "provenance": LOOKUP_EMULATOR,
            "mode": "lookup",
            "day": day,
            "month": month,
            "honesty": honesty,
        }
    )
    rows: List[Dict[str, Any]] = [
        {
            "step": 0,
            "htg_sp_f": ctrl.setpoint_f(0),
            "htg_sp_c": ctrl.action_c(0),
            "reward": -float(obs["facility_kw"]) / 100.0,
            **obs,
        }
    ]
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


def run_rule_episode(
    *,
    site_root: Path,
    strategy_id: str = "baseline",
    day: Optional[str] = None,
    mode: str = "auto",
    epw: Optional[Path] = None,
    idf: Optional[Path] = None,
    output: Optional[Path] = None,
    max_steps: int = 96,
    verbose: bool = False,
    month: Optional[str] = None,
    family: str = FAMILY_IDEALLOADS,
) -> Dict[str, Any]:
    """Return trajectory dict with rows + meta.

    ``family='w2a'`` never falls back to the IdealLoads farm.
    ``auto`` on W2A: lookup if ``eplus/dsm_farm_w2a`` exists, else live if E+
    + epw/idf, else a clear error.
    """
    site_root = Path(site_root)
    fam = _norm_family(family)
    ctrl = RuleController(strategy_id)
    honesty = HONESTY_W2A if fam == FAMILY_W2A else HONESTY_IDEALLOADS
    meta: Dict[str, Any] = {
        "strategy_id": strategy_id,
        "honesty": honesty,
        "promote": PROMOTE,
        "family": fam,
    }

    if fam == FAMILY_W2A:
        farm_root = resolve_w2a_farm_root(site_root)
        missing = (
            f"no farm days for {strategy_id} under {farm_root} "
            "(dsm_farm_w2a) and live E+ unavailable/failed — "
            "will not fall back to IdealLoads"
        )
        resolved = mode
        if mode == "auto":
            if w2a_farm_ready(site_root):
                resolved = "lookup"
            elif energyplus_available() and epw is not None and idf is not None:
                resolved = "live"
            else:
                raise FileNotFoundError(missing)
        if resolved == "live":
            if epw is None or idf is None:
                raise FileNotFoundError(
                    "W2A live mode requires --epw and --idf; "
                    "will not fall back to IdealLoads"
                )
            from .envs.lakeside_w2a import LakesideW2AEnv

            out = Path(output or (site_root / "eplus" / "gym_runs"))
            try:
                return _live_episode(
                    env_cls=LakesideW2AEnv,
                    epw=Path(epw),
                    idf=Path(idf),
                    output=out,
                    ctrl=ctrl,
                    meta=meta,
                    day=day,
                    max_steps=max_steps,
                    verbose=verbose,
                )
            except Exception as exc:  # noqa: BLE001
                raise FileNotFoundError(
                    f"W2A live EnergyPlus failed ({exc}); "
                    "will not fall back to IdealLoads"
                ) from exc
        return _lookup_episode(
            site_root=site_root,
            farm_root=farm_root,
            honesty=honesty,
            ctrl=ctrl,
            strategy_id=strategy_id,
            day=day,
            month=month,
            max_steps=max_steps,
            meta=meta,
            missing_msg=missing,
        )

    want_live = mode == "live" or (mode == "auto" and energyplus_available())
    if want_live and mode != "lookup":
        if epw is None or idf is None:
            want_live = False
            meta["live_skip_reason"] = "epw/idf not provided"
        else:
            try:
                from .envs.lakeside_idealloads import LakesideIdealLoadsEnv

                out = Path(output or (site_root / "eplus" / "gym_runs"))
                return _live_episode(
                    env_cls=LakesideIdealLoadsEnv,
                    epw=Path(epw),
                    idf=Path(idf),
                    output=out,
                    ctrl=ctrl,
                    meta=meta,
                    day=day,
                    max_steps=max_steps,
                    verbose=verbose,
                )
            except Exception as exc:  # noqa: BLE001
                meta["live_error"] = str(exc)
                want_live = False

    farm_root = resolve_farm_root(site_root)
    return _lookup_episode(
        site_root=site_root,
        farm_root=farm_root,
        honesty=HONESTY_IDEALLOADS,
        ctrl=ctrl,
        strategy_id=strategy_id,
        day=day,
        month=month,
        max_steps=max_steps,
        meta=meta,
        missing_msg=(
            f"no farm days for {strategy_id} under {farm_root} "
            "and live E+ unavailable/failed"
        ),
    )


def run_rule_month_lookup(
    *,
    site_root: Path,
    month: str,
    strategies: Optional[Sequence[str]] = None,
    family: str = FAMILY_IDEALLOADS,
) -> Dict[str, Any]:
    """Stack all available farm days in a month for each strategy (no EnergyPlus)."""
    site_root = Path(site_root)
    fam = _norm_family(family)
    honesty = HONESTY_W2A if fam == FAMILY_W2A else HONESTY_IDEALLOADS
    strats = list(strategies or DEPLOYABLE_STRATEGIES)
    by_strategy: Dict[str, Any] = {}
    for sid in strats:
        days = list_farm_days(
            site_root,
            sid,
            month=month,
            farm_root=(
                resolve_w2a_farm_root(site_root)
                if fam == FAMILY_W2A
                else resolve_farm_root(site_root)
            ),
        )
        day_frames = []
        for d in days:
            try:
                result = run_rule_episode(
                    site_root=site_root,
                    strategy_id=sid,
                    day=d,
                    mode="lookup",
                    month=month,
                    family=fam,
                )
                df = trajectory_frame(result)
                df["day"] = d
                df["strategy_id"] = sid
                day_frames.append(df)
            except FileNotFoundError:
                continue
        by_strategy[sid] = {
            "days": days,
            "n_days": len(day_frames),
            "frame": pd.concat(day_frames, ignore_index=True) if day_frames else pd.DataFrame(),
        }
    return {
        "month": month,
        "strategies": by_strategy,
        "kpis": month_kpis(site_root, month, strats),
        "honesty": honesty,
        "provenance": LOOKUP_EMULATOR,
        "promote": PROMOTE,
        "family": fam,
    }


def trajectory_frame(result: Dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(result["rows"])
