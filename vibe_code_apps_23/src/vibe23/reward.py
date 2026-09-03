"""Vibe 23's explicit Vibe 22 operator-pay/reward compatibility contract."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .tariff import BillingState, TariffScenario, billing_cost

REWARD_SCHEMA = "vibe23.operator_pay_v22_compatible.v1"
N_INTERVALS = 96  # legacy default; ComfortContract.n_intervals overrides


@dataclass(frozen=True)
class ComfortContract:
    """A building-specific comfort schedule and explicit band supplied by the frozen contract."""

    readiness_steps: tuple[int, ...]
    occupied_steps: tuple[int, ...]
    low_f: float
    high_f: float
    required_zone_names: tuple[str, ...] = ()
    n_intervals: int = N_INTERVALS

    def __post_init__(self) -> None:
        if self.n_intervals < 1:
            raise ValueError("n_intervals must be positive")
        if not self.readiness_steps:
            raise ValueError("readiness_steps must not be empty")
        for step in (*self.readiness_steps, *self.occupied_steps):
            if not 0 <= int(step) < self.n_intervals:
                raise ValueError(f"comfort step out of range: {step}")
        if self.low_f >= self.high_f:
            raise ValueError("low_f must be below high_f")

    @property
    def dt_hours(self) -> float:
        return 24.0 / float(self.n_intervals)


@dataclass(frozen=True)
class OperatorPayPolicy:
    """The transparent successor to Vibe 22's 2x/3x operator-pay policy.

    The displayed paycheck is intentionally separate from the training reward.
    It never becomes the optimization criterion by accident.
    """

    savings_multiplier: float = 2.0
    base_wage_usd: float = 100.0
    payout_cap_usd: float = 500.0
    cost_scale_usd: float = 100.0
    occupied_degree_hour_penalty: float = 0.05
    smooth_action_penalty: float = 0.02
    readiness_fail_reward: float = -20.0
    reward_clip_low: float = -5.0
    reward_clip_high: float = 5.0
    reward_name: str = REWARD_SCHEMA

    def __post_init__(self) -> None:
        if self.savings_multiplier not in {2.0, 3.0}:
            raise ValueError("savings_multiplier must be exactly 2 or 3")
        if self.payout_cap_usd < 0 or self.base_wage_usd < 0:
            raise ValueError("pay values must be non-negative")
        if self.cost_scale_usd <= 0:
            raise ValueError("cost_scale_usd must be positive")


@dataclass(frozen=True)
class RewardResult:
    schema: str
    reward_name: str
    training_reward: float
    selection_cost_usd: float
    savings_usd: float
    display_paycheck_usd: float
    readiness_ok: bool
    readiness_failed_zones: tuple[str, ...]
    occupied_low_degree_hours: float
    occupied_high_degree_hours: float
    action_smoothness: float
    between_day_action_delta: float
    candidate_billing: Mapping[str, Any]
    baseline_billing: Mapping[str, Any]
    labels: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        body = asdict(self)
        body["candidate_billing"] = dict(self.candidate_billing)
        body["baseline_billing"] = dict(self.baseline_billing)
        body["labels"] = dict(self.labels)
        return body


def _validate_kw(values: Sequence[float], name: str, n_intervals: int) -> tuple[float, ...]:
    if len(values) != n_intervals:
        raise ValueError(f"{name} must contain {n_intervals} intervals")
    converted = tuple(float(v) for v in values)
    if any(v != v or v in (float("inf"), float("-inf")) or v < 0 for v in converted):
        raise ValueError(f"{name} must be finite and non-negative")
    return converted


def _validate_zones(
    zone_temperatures_f: Mapping[str, Sequence[float]], comfort: ComfortContract
) -> dict[str, tuple[float, ...]]:
    if not zone_temperatures_f:
        raise ValueError("at least one zone trajectory is required")
    if comfort.required_zone_names:
        missing = set(comfort.required_zone_names).difference(zone_temperatures_f)
        extra = set(zone_temperatures_f).difference(comfort.required_zone_names)
        if missing or extra:
            raise ValueError(f"zone contract mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
    out: dict[str, tuple[float, ...]] = {}
    for name, values in zone_temperatures_f.items():
        row = tuple(float(v) for v in values)
        if len(row) != comfort.n_intervals or any(v != v or v in (float("inf"), float("-inf")) for v in row):
            raise ValueError(f"zone {name!r} must contain {comfort.n_intervals} finite values")
        out[str(name)] = row
    return out


def comfort_score(zone_temperatures_f: Mapping[str, Sequence[float]], comfort: ComfortContract) -> dict[str, Any]:
    zones = _validate_zones(zone_temperatures_f, comfort)
    readiness_failed: list[str] = []
    low_dh = 0.0
    high_dh = 0.0
    dt = comfort.dt_hours
    for name, values in zones.items():
        for step in comfort.readiness_steps:
            value = values[step]
            if not comfort.low_f <= value <= comfort.high_f:
                readiness_failed.append(f"{name}@{step}")
        for step in comfort.occupied_steps:
            value = values[step]
            low_dh += max(0.0, comfort.low_f - value) * dt
            high_dh += max(0.0, value - comfort.high_f) * dt
    return {
        "readiness_ok": not readiness_failed,
        "readiness_failed_zones": tuple(readiness_failed),
        "occupied_low_degree_hours": float(low_dh),
        "occupied_high_degree_hours": float(high_dh),
    }


def action_smoothness(schedules: Mapping[str, Sequence[float]] | None, *, n_intervals: int = N_INTERVALS) -> float:
    """Mean absolute within-day setpoint change across all provided schedules."""

    if not schedules:
        return 0.0
    changes: list[float] = []
    for name, values in schedules.items():
        row = tuple(float(v) for v in values)
        if len(row) != n_intervals or any(not math.isfinite(value) for value in row):
            raise ValueError(f"schedule {name!r} must contain {n_intervals} finite values")
        changes.extend(abs(b - a) for a, b in zip(row, row[1:], strict=False))
    return float(sum(changes) / len(changes)) if changes else 0.0


def between_day_action_delta(
    previous_schedules: Mapping[str, Sequence[float]] | None,
    candidate_schedules: Mapping[str, Sequence[float]] | None,
    *,
    n_intervals: int = N_INTERVALS,
) -> float:
    if not previous_schedules or not candidate_schedules:
        return 0.0
    common = sorted(set(previous_schedules).intersection(candidate_schedules))
    deltas: list[float] = []
    for name in common:
        previous = tuple(float(v) for v in previous_schedules[name])
        candidate = tuple(float(v) for v in candidate_schedules[name])
        if (
            len(previous) != n_intervals
            or len(candidate) != n_intervals
            or any(not math.isfinite(value) for value in (*previous, *candidate))
        ):
            raise ValueError(f"schedule {name!r} must contain {n_intervals} finite values")
        deltas.append(abs(candidate[0] - previous[-1]))
    return float(sum(deltas) / len(deltas)) if deltas else 0.0


def score_operator_pay_day(
    *,
    candidate_kw: Sequence[float],
    baseline_kw: Sequence[float] | None,
    candidate_zone_temperatures_f: Mapping[str, Sequence[float]],
    comfort: ComfortContract,
    tariff: TariffScenario,
    opening_billing_state: BillingState,
    policy: OperatorPayPolicy = OperatorPayPolicy(),
    candidate_schedules: Mapping[str, Sequence[float]] | None = None,
    previous_schedules: Mapping[str, Sequence[float]] | None = None,
) -> RewardResult:
    """Score a candidate against an identical-state paired baseline.

    Both trajectories use the exact same tariff and opening billing state.
    Candidate-as-baseline is rejected rather than implicitly accepted.
    """

    if tariff.intervals_per_day != comfort.n_intervals:
        raise ValueError("tariff intervals must match comfort.n_intervals")
    n = comfort.n_intervals
    candidate_kw = _validate_kw(candidate_kw, "candidate_kw", n)
    if baseline_kw is None:
        raise ValueError("paired baseline_kw is required; candidate-as-baseline is forbidden")
    baseline_kw = _validate_kw(baseline_kw, "baseline_kw", n)
    candidate_bill = billing_cost(candidate_kw, tariff=tariff, opening_state=opening_billing_state)
    baseline_bill = billing_cost(baseline_kw, tariff=tariff, opening_state=opening_billing_state)
    comfort_result = comfort_score(candidate_zone_temperatures_f, comfort)
    savings = float(baseline_bill["total_cost_usd"] - candidate_bill["total_cost_usd"])
    smoothness = action_smoothness(candidate_schedules, n_intervals=n)
    day_delta = between_day_action_delta(previous_schedules, candidate_schedules, n_intervals=n)
    readiness_ok = bool(comfort_result["readiness_ok"])
    if readiness_ok:
        paycheck = min(policy.payout_cap_usd, max(0.0, policy.base_wage_usd + policy.savings_multiplier * savings))
        shaped = max(policy.reward_clip_low, min(policy.reward_clip_high, savings / policy.cost_scale_usd))
        training_reward = max(
            policy.reward_clip_low,
            min(
                policy.reward_clip_high,
                shaped
                - policy.occupied_degree_hour_penalty
                * (comfort_result["occupied_low_degree_hours"] + comfort_result["occupied_high_degree_hours"])
                - policy.smooth_action_penalty * smoothness,
            ),
        )
    else:
        paycheck = 0.0
        degree_violation = (
            comfort_result["occupied_low_degree_hours"] + comfort_result["occupied_high_degree_hours"]
        )
        training_reward = policy.readiness_fail_reward - degree_violation / max(1, len(candidate_zone_temperatures_f))
    labels = {
        "reward_policy": "VIBE22_OPERATOR_PAY_2X_3X_WITH_SEPARATE_TRAINING_REWARD",
        "paycheck": "ILLUSTRATIVE_OPERATOR_PAYCHECK; NEVER_DIRECTLY_OPTIMIZED",
        "readiness": "ALL_REQUIRED_ZONES_IN_BAND_AT_EVERY_READINESS_STEP",
        "demand": "INCREMENTAL_DEMAND_COST_FROM_IDENTICAL_OPENING_BILLING_FLOOR",
        "smoothness": "WITHIN_DAY_MEAN_ABSOLUTE_SETPOINT_DELTA; APPLIES_TO_TRAINING_REWARD",
        "between_day_delta": "REPORTED_FOR_AUDIT; NOT_CURRENTLY_PENALIZED",
        "tariff": tariff.money_label,
        "selection": tariff.selection_label,
    }
    return RewardResult(
        schema=REWARD_SCHEMA,
        reward_name=policy.reward_name,
        training_reward=float(training_reward),
        selection_cost_usd=float(candidate_bill["total_cost_usd"]),
        savings_usd=savings,
        display_paycheck_usd=float(paycheck),
        readiness_ok=readiness_ok,
        readiness_failed_zones=tuple(comfort_result["readiness_failed_zones"]),
        occupied_low_degree_hours=float(comfort_result["occupied_low_degree_hours"]),
        occupied_high_degree_hours=float(comfort_result["occupied_high_degree_hours"]),
        action_smoothness=float(smoothness),
        between_day_action_delta=float(day_delta),
        candidate_billing=candidate_bill,
        baseline_billing=baseline_bill,
        labels=labels,
    )
