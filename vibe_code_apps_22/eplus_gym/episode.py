"""Public Gymnasium episode runner for EnergyPlus DSM screening."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import numpy as np

from eplus_gym.honesty import PROVENANCE_LIVE
from eplus_gym.simulate import runtime_day_from_obs, validate_live_trajectory_calendar

SCREENING_CLAIM = "ENERGYPLUS DSM OPTIMIZATION SCREENING / RETROSPECTIVE REPLAY"
SIMULATOR = "LIVE_ENERGYPLUS / ENERGYPLUS_PYTHON_API"


def run_controller_episode(
    env_factory: Callable[[], Any],
    controller: Any,
    *,
    lookback_days: int = 0,
    scored_day: str | None = None,
    max_steps: int | None = None,
) -> Dict[str, Any]:
    """Run one closed-loop episode using only public reset/step/close.

    ``controller.action(step)`` must return a Gym action (scalar or length-6).
    When ``lookback_days>0`` and controller exposes ``action_lookback(step)``,
    that series is used for lookback intervals; scored intervals use ``action``.
    """
    env = env_factory()
    rows: List[Dict[str, Any]] = []
    meta: Dict[str, Any] = {
        "scientific_claim": SCREENING_CLAIM,
        "simulator": SIMULATOR,
        "provenance": PROVENANCE_LIVE,
        "lookback_days": int(lookback_days),
        "scored_day": scored_day,
    }
    try:
        _obs, info = env.reset()
        meta["reset_info"] = {
            k: info[k]
            for k in ("honesty", "provenance", "promote", "default_action")
            if k in info
        }
        # Infer horizon from RunPeriod if not provided
        if max_steps is None:
            max_steps = 96 * (int(lookback_days) + 1)
        scored_begin = None
        if scored_day:
            scored_begin = date.fromisoformat(str(scored_day)[:10])
        lookback_steps = int(lookback_days) * 96
        for t in range(int(max_steps)):
            use_lookback = t < lookback_steps and hasattr(controller, "action_lookback")
            if use_lookback:
                action = controller.action_lookback(t)
            else:
                # Target-day local step index for 96-step daily controllers
                local = t - lookback_steps if lookback_steps else t
                action = controller.action(local)
            _obs_vec, reward, terminated, truncated, step_info = env.step(action)
            od = dict(step_info.get("obs_dict") or {})
            row: Dict[str, Any] = {
                "step": t,
                "local_step": (t - lookback_steps) if lookback_steps else t,
                "lookback": bool(use_lookback or (lookback_steps and t < lookback_steps)),
                "reward": float(reward),
            }
            act = step_info.get("action")
            if isinstance(act, list):
                row["action_c"] = [float(x) for x in act]
            elif act is not None:
                row["action_c"] = float(act)
            for k, v in od.items():
                if isinstance(v, (int, float)):
                    row[k] = float(v)
            rt = runtime_day_from_obs(od)
            if rt:
                row["day"] = rt
            if "facility_kw" not in row and "facility_j" in row:
                j = row["facility_j"]
                row["facility_kw"] = (j / 900_000.0) if j == j else float("nan")
            rows.append(row)
            if terminated or truncated:
                break
    finally:
        try:
            env.close()
        except Exception:  # noqa: BLE001
            pass

    # Score only target-day rows when scored_day provided
    scored = rows
    if scored_begin is not None:
        scored = [r for r in rows if r.get("day") == scored_begin.isoformat()]
        # Also drop lookback-flagged rows
        scored = [r for r in scored if not r.get("lookback")]
        expected_end = scored_begin.isoformat()
        cal = validate_live_trajectory_calendar(
            scored,
            expected_day=scored_begin.isoformat(),
            expected_end=expected_end,
            expect_steps=96,
        )
    else:
        cal = validate_live_trajectory_calendar(
            scored,
            expected_day=None,
            expect_steps=len(scored) if scored else 96,
        )
    meta["calendar_validation"] = cal
    if not cal.get("ok"):
        raise ValueError(
            "episode calendar validation failed: " + "; ".join(cal.get("issues") or [])
        )
    return {"rows": scored, "all_rows": rows, "meta": meta, "controller": controller}
