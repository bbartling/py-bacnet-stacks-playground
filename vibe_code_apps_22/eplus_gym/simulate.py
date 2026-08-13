"""Run a rule-controller episode (live E+ or farm lookup)."""
from __future__ import annotations

from datetime import date, timedelta
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


def day_for_step(begin: str, step: int) -> str:
    """DEPRECATED synthetic calendar — lookup emulator only.

    Live EnergyPlus trajectories must use Runtime ``ep_year/ep_month/ep_day``.
    """
    return (date.fromisoformat(str(begin)[:10]) + timedelta(days=int(step) // 96)).isoformat()


def runtime_day_from_obs(od: Dict[str, Any]) -> Optional[str]:
    """ISO date from EnergyPlus Runtime calendar fields on an observation."""
    try:
        y = int(float(od["ep_year"]))
        m = int(float(od["ep_month"]))
        d = int(float(od["ep_day"]))
        if y <= 0 or m <= 0 or d <= 0:
            return None
        return date(y, m, d).isoformat()
    except (KeyError, TypeError, ValueError):
        return None


def validate_live_trajectory_calendar(
    rows: List[Dict[str, Any]],
    *,
    expected_day: Optional[str] = None,
    expect_steps: int = 96,
) -> Dict[str, Any]:
    """Fail closed on sizing contamination / synthetic dating / wrong count."""
    issues: List[str] = []
    if len(rows) != int(expect_steps):
        issues.append(f"expected {expect_steps} scored rows, got {len(rows)}")
    kinds = [int(float(r.get("kind_of_sim", -1))) for r in rows]
    if any(k != 3 for k in kinds):
        issues.append("non-weather kind_of_sim in scored rows (sizing contamination)")
    warm = [float(r.get("warmup", 0.0)) for r in rows]
    if any(w > 0.5 for w in warm):
        issues.append("warmup rows present in scored trajectory")
    days = [runtime_day_from_obs(r) for r in rows]
    if any(d is None for d in days):
        issues.append("missing Runtime calendar fields on scored rows")
    if expected_day and days and any(d != expected_day for d in days if d):
        issues.append(f"calendar day != expected {expected_day}: {sorted(set(days))}")
    # Contaminated Jan-26 OAT pattern detector (design-day then jump)
    oats = [float(r["oat_c"]) for r in rows if "oat_c" in r and r["oat_c"] == r["oat_c"]]
    if len(oats) >= 10:
        first = oats[: max(1, len(oats) // 2)]
        second = oats[len(oats) // 2 :]
        if (
            abs(sum(first) / len(first) + 17.8) < 1.5
            and abs(sum(second) / len(second) - 24.65) < 2.0
        ):
            issues.append(
                "contaminated OAT pattern (~−17.8°C then ~+24.65°C) — sizing-day signature"
            )
    # Monotonic 15-min stamps within day
    stamps = []
    for r in rows:
        try:
            stamps.append(
                (
                    int(float(r["ep_year"])),
                    int(float(r["ep_month"])),
                    int(float(r["ep_day"])),
                    int(float(r["ep_hour"])),
                    int(float(r["ep_minute"])),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    if len(stamps) >= 2:
        for a, b in zip(stamps, stamps[1:]):
            if b < a:
                issues.append("non-monotonic Runtime timestamps")
                break
    ok = not issues
    return {"ok": ok, "issues": issues}


def detect_synthetic_step_dating(rows: List[Dict[str, Any]], begin: str) -> bool:
    """True if ``day`` column matches deprecated day_for_step(begin, step)."""
    if not rows or "day" not in rows[0] or "step" not in rows[0]:
        return False
    return all(
        str(r.get("day")) == day_for_step(begin, int(r["step"]))
        and "ep_year" not in r
        for r in rows
    )

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
    begin = None
    if day:
        try:
            begin = date.fromisoformat(str(day)[:10])
        except ValueError:
            begin = None
    env = env_cls(
        {
            "epw": str(epw),
            "idf": str(idf),
            "output": str(output),
            "verbose": verbose,
            "queue_timeout_s": 120.0,
            "occupied_heating_f": float(getattr(ctrl, "occ_htg_sp_f", 70.0)),
            "default_action_c": float(ctrl.action_c(0)),
        }
    )
    _obs, info = env.reset()
    meta.update(
        {
            "provenance": info.get("provenance"),
            "mode": "live",
            "day": day,
            "loop": "CLOSED_LOOP_RULE_DR",
            "weekend_sp": "repeat_96_step_profile",
        }
    )
    rows: List[Dict[str, Any]] = []
    for t in range(max_steps):
        action = ctrl.action_c(t)
        _obs_vec, reward, done, truncated, step_info = env.step(action)
        od = step_info.get("obs_dict") or {}
        row = {
            "step": t,
            "htg_sp_f": ctrl.setpoint_f(t),
            "htg_sp_c": action,
            "reward": reward,
            **{k: float(v) for k, v in od.items() if isinstance(v, (int, float))},
        }
        # Prefer EnergyPlus Runtime calendar — never fabricate via day_for_step.
        rt_day = runtime_day_from_obs(od)
        if rt_day:
            row["day"] = rt_day
        elif begin is not None:
            # Legacy fallback only when Runtime fields absent (should not happen live).
            row["day"] = begin.isoformat()
            row["day_source"] = "requested_begin_fallback"
        if "facility_kw" not in row and "facility_j" in row:
            # Electricity:Facility at 15-min zone timestep → kW
            j = row["facility_j"]
            row["facility_kw"] = (j / 900_000.0) if j == j else float("nan")
        rows.append(row)
        if done or truncated:
            break
    env.close()
    expected = begin.isoformat() if begin is not None else None
    cal = validate_live_trajectory_calendar(rows, expected_day=expected, expect_steps=max_steps)
    meta["calendar_validation"] = cal
    if not cal["ok"]:
        raise ValueError(
            "live trajectory calendar validation failed: " + "; ".join(cal["issues"])
        )
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
    def _lookup_row(t: int, obs_row: Dict[str, Any], reward: float) -> Dict[str, Any]:
        row = {
            "step": t,
            "htg_sp_f": ctrl.setpoint_f(t),
            "htg_sp_c": ctrl.action_c(t),
            "reward": reward,
            **obs_row,
        }
        if day:
            row["day"] = day_for_step(str(day), t)
        return row

    rows: List[Dict[str, Any]] = [
        _lookup_row(0, obs, -float(obs["facility_kw"]) / 100.0)
    ]
    for t in range(1, max_steps):
        obs, reward, done, truncated, _ = env_l.step(ctrl.action_c(t))
        rows.append(_lookup_row(t, obs, reward))
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
    period: Optional[str] = None,
    weather_kind: Optional[str] = None,
) -> Dict[str, Any]:
    """Return trajectory dict with rows + meta.

    ``family='w2a'`` never falls back to the IdealLoads farm.
    ``auto`` on W2A: lookup if ``eplus/dsm_farm_w2a`` exists, else live if E+
    + epw/idf, else a clear error.
    """
    site_root = Path(site_root)
    fam = _norm_family(family)
    occ_f: float | None = None
    unocc_f: float | None = None
    try:
        from eplus_gym_app.site_config import load_site_dsm_config

        sp = (load_site_dsm_config(site_root).get("setpoints_f") or {})
        if "occupied_heating_f" in sp:
            occ_f = float(sp["occupied_heating_f"])
        if "unoccupied_heating_f" in sp:
            unocc_f = float(sp["unoccupied_heating_f"])
    except Exception:  # noqa: BLE001
        occ_f = unocc_f = None
    ctrl = RuleController(
        strategy_id,
        occ_htg_sp_f=occ_f,
        unocc_htg_sp_f=unocc_f,
    )
    honesty = HONESTY_W2A if fam == FAMILY_W2A else HONESTY_IDEALLOADS
    meta: Dict[str, Any] = {
        "strategy_id": strategy_id,
        "honesty": honesty,
        "promote": PROMOTE,
        "family": fam,
        "loop": "CLOSED_LOOP_RULE_DR",
        "weekend_sp": "repeat_96_step_profile",
        "period": period,
        "weather_kind": weather_kind,
        "max_steps": int(max_steps),
        "site_occ_htg_sp_f": occ_f,
        "site_unocc_htg_sp_f": unocc_f,
        "eff_occ_htg_sp_f": ctrl.occ_htg_sp_f,
        "eff_unocc_htg_sp_f": ctrl.unocc_htg_sp_f,
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
                from .errors import EnergyPlusStartupError

                if isinstance(exc, EnergyPlusStartupError):
                    raise
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
