"""Midnight-only weather-trigger daily policy selection (retrospective EPW)."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

_APP = Path(__file__).resolve().parents[2]
CONTRACT_NAME = "weather_triggered_continuous_v1.json"

C_TO_F = 1.8
C_OFFSET_F = 32.0


@dataclass(frozen=True)
class DailySelection:
    day: str
    policy_id: str
    selected_mode: str
    hourly_oat_f: list[float]
    trigger_reason: str
    continuous_day: bool
    discrete_index: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_weather_trigger_contract(app_root: Path | None = None) -> dict[str, Any]:
    root = Path(app_root) if app_root else _APP
    path = root / "contracts" / CONTRACT_NAME
    return json.loads(path.read_text(encoding="utf-8"))


def oat_c_to_f(hourly_oat_c: Sequence[float]) -> list[float]:
    return [float(c) * C_TO_F + C_OFFSET_F for c in hourly_oat_c]


def _require_24(hourly_oat_f: Sequence[float], *, day: str) -> list[float]:
    vals = [float(x) for x in hourly_oat_f]
    if len(vals) != 24:
        raise ValueError(f"{day}: expected 24 hourly OAT °F values, got {len(vals)}")
    return vals


def _continuous_selection(day: str, policy_id: str, hourly_oat_f: list[float], reason: str) -> DailySelection:
    return DailySelection(
        day=day,
        policy_id=policy_id,
        selected_mode="continuous_68_74",
        hourly_oat_f=hourly_oat_f,
        trigger_reason=reason,
        continuous_day=True,
        discrete_index=None,
    )


def _discrete_selection(
    day: str, policy_id: str, hourly_oat_f: list[float], reason: str, *, index: int
) -> DailySelection:
    return DailySelection(
        day=day,
        policy_id=policy_id,
        selected_mode=f"discrete_{index}",
        hourly_oat_f=hourly_oat_f,
        trigger_reason=reason,
        continuous_day=False,
        discrete_index=int(index),
    )


def select_daily_policy(
    *,
    policy_id: str,
    day: str,
    hourly_oat_f: Sequence[float],
    contract: Mapping[str, Any] | None = None,
) -> DailySelection:
    """Select exactly one complete daily schedule at midnight from realized OAT °F."""
    contract = contract or load_weather_trigger_contract()
    policies = contract.get("policies") or {}
    if policy_id not in policies:
        raise ValueError(f"unknown weather-trigger policy_id {policy_id!r}")
    spec = policies[policy_id]
    oat = _require_24(hourly_oat_f, day=day)
    kind = str(spec["kind"])
    if kind == "always_discrete":
        idx = int(spec["discrete_index"])
        return _discrete_selection(day, policy_id, oat, f"always_discrete_{idx}", index=idx)
    if kind == "always_continuous_68_74":
        return _continuous_selection(day, policy_id, oat, "always_continuous_68_74")
    if kind == "cold_trigger_min":
        thr = float(spec["threshold_f"])
        else_idx = int(spec["else_discrete_index"])
        mn = min(oat)
        if mn <= thr:
            return _continuous_selection(
                day, policy_id, oat, f"min_oat_{mn:.2f}F_le_{thr:g}F"
            )
        return _discrete_selection(
            day, policy_id, oat, f"min_oat_{mn:.2f}F_gt_{thr:g}F_use_discrete_{else_idx}", index=else_idx
        )
    if kind == "cold_trigger_duration":
        thr = float(spec["threshold_f"])
        min_h = int(spec["min_hours"])
        else_idx = int(spec["else_discrete_index"])
        n_cold = sum(1 for t in oat if t <= thr)
        if n_cold >= min_h:
            return _continuous_selection(
                day, policy_id, oat, f"n_hours_le_{thr:g}F={n_cold}_ge_{min_h}"
            )
        return _discrete_selection(
            day,
            policy_id,
            oat,
            f"n_hours_le_{thr:g}F={n_cold}_lt_{min_h}_use_discrete_{else_idx}",
            index=else_idx,
        )
    raise ValueError(f"unsupported policy kind {kind!r}")


def select_daily_policy_from_forecast_vector(
    *,
    policy_id: str,
    day: str,
    forecast_hourly_oat_f: Sequence[float],
    contract: Mapping[str, Any] | None = None,
) -> DailySelection:
    """Future hook for forecast vectors. Does not invent forecast accuracy.

    Retrospective experiments must use ``select_daily_policy`` with realized EPW OAT
    and label ``RETROSPECTIVE_WEATHER_POLICY_SCREEN``.
    """
    return select_daily_policy(
        policy_id=policy_id,
        day=day,
        hourly_oat_f=forecast_hourly_oat_f,
        contract=contract,
    )


def params_for_selection(selection: DailySelection, *, day: str):
    """Map a DailySelection to SixZoneDailyParamsV2."""
    from eplus_gym.control_v2 import continuous_params
    from eplus_gym.rl.research_spaces import decode_discrete_research_v3

    if selection.continuous_day:
        return continuous_params(68.0)
    if selection.discrete_index is None:
        raise ValueError("non-continuous selection requires discrete_index")
    return decode_discrete_research_v3(int(selection.discrete_index), day=day)
