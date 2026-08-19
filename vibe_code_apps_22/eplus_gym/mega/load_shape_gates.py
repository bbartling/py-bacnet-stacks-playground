"""Phase 5: hourly vs monthly load-shape promotion gates (before strategy development)."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from eplus_gym.mega._json import sha256_obj
from eplus_gym.rl.physics_ramp_gate import ENGINEERING_MARGIN, evaluate_ramp_gate

SCHEMA = "vibe22.mega.load_shape_promotion_gate.v1"
SCREEN_UNAVAILABLE = "SCREEN_UNAVAILABLE_NO_PROMOTION"

# Hourly screening (research calibration).
HOURLY_NMBE_ABS_MAX = 10.0
HOURLY_CVRMSE_MAX = 30.0
# Monthly screening (ASHRAE Guideline 14 monthly).
MONTHLY_NMBE_ABS_MAX = 5.0
MONTHLY_CVRMSE_MAX = 15.0

CORRELATION_MIN = 0.85
PEAK_TIMING_ERROR_HOURS_MAX = 2.0
MORNING_RECOVERY_ERROR_F_MAX = 3.0
OVERNIGHT_LOAD_ERROR_PCT_MAX = 25.0


@dataclass
class GateMetric:
    name: str
    value: float | None
    threshold: float | None
    passed: bool | None
    unavailable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "threshold": self.threshold,
            "passed": self.passed,
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass
class LoadShapePromotionGate:
    screen: str
    metrics: list[GateMetric] = field(default_factory=list)
    ramp_gate: dict[str, Any] | None = None

    def add_metric(self, metric: GateMetric) -> None:
        self.metrics.append(metric)

    def blocks_promotion(self) -> bool:
        for m in self.metrics:
            if m.unavailable_reason == SCREEN_UNAVAILABLE:
                return True
            if m.passed is False:
                return True
        if self.ramp_gate and not self.ramp_gate.get("passed", True):
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "screen": self.screen,
            "metrics": [m.to_dict() for m in self.metrics],
            "ramp_gate": self.ramp_gate,
            "blocks_promotion": self.blocks_promotion(),
            "load_shape_published": not self.blocks_promotion(),
            "ramp_margin_unchanged": ENGINEERING_MARGIN,
        }

    def write(self, path: Path) -> dict[str, Any]:
        body = self.to_dict()
        body["gate_sha256"] = sha256_obj(body)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        return body


def _add_threshold_metric(
    gate: LoadShapePromotionGate,
    *,
    name: str,
    val: float | None,
    thr: float,
    cmp_fn,
    unavailable: str | None = None,
) -> None:
    if val is None:
        gate.add_metric(
            GateMetric(
                name,
                None,
                thr,
                None,
                unavailable or SCREEN_UNAVAILABLE,
            )
        )
    else:
        gate.add_metric(GateMetric(name, val, thr, cmp_fn(val, thr)))


def evaluate_hourly_load_shape_gate(
    *,
    hourly_nmbe_pct: float | None,
    hourly_cvrmse_pct: float | None,
    load_shape_correlation: float | None = None,
    peak_timing_error_hours: float | None = None,
    morning_recovery_error_f: float | None = None,
    overnight_load_error_pct: float | None = None,
    shape_15min_nmbe_pct: float | None = None,
    meter_alignment_ok: bool = True,
    ramp_gate_result: Mapping[str, Any] | None = None,
) -> LoadShapePromotionGate:
    gate = LoadShapePromotionGate(
        screen="hourly",
        ramp_gate=dict(ramp_gate_result) if ramp_gate_result else None,
    )
    _add_threshold_metric(
        gate,
        name="hourly_nmbe_abs_pct",
        val=hourly_nmbe_pct,
        thr=HOURLY_NMBE_ABS_MAX,
        cmp_fn=lambda v, t: abs(v) <= t,
    )
    if hourly_cvrmse_pct is None and not meter_alignment_ok:
        gate.add_metric(
            GateMetric(
                "hourly_cvrmse_pct",
                None,
                HOURLY_CVRMSE_MAX,
                None,
                SCREEN_UNAVAILABLE,
            )
        )
    else:
        _add_threshold_metric(
            gate,
            name="hourly_cvrmse_pct",
            val=hourly_cvrmse_pct,
            thr=HOURLY_CVRMSE_MAX,
            cmp_fn=lambda v, t: v <= t,
        )
    if load_shape_correlation is not None:
        _add_threshold_metric(
            gate,
            name="load_shape_correlation",
            val=load_shape_correlation,
            thr=CORRELATION_MIN,
            cmp_fn=lambda v, t: v >= t,
        )
    if peak_timing_error_hours is not None:
        _add_threshold_metric(
            gate,
            name="peak_timing_error_hours",
            val=peak_timing_error_hours,
            thr=PEAK_TIMING_ERROR_HOURS_MAX,
            cmp_fn=lambda v, t: v <= t,
        )
    if morning_recovery_error_f is not None:
        _add_threshold_metric(
            gate,
            name="morning_recovery_error_f",
            val=morning_recovery_error_f,
            thr=MORNING_RECOVERY_ERROR_F_MAX,
            cmp_fn=lambda v, t: v <= t,
        )
    if overnight_load_error_pct is not None:
        _add_threshold_metric(
            gate,
            name="overnight_load_error_pct",
            val=overnight_load_error_pct,
            thr=OVERNIGHT_LOAD_ERROR_PCT_MAX,
            cmp_fn=lambda v, t: abs(v) <= t,
        )
    if shape_15min_nmbe_pct is None and not meter_alignment_ok:
        gate.add_metric(
            GateMetric(
                "shape_15min_nmbe_abs_pct",
                None,
                HOURLY_NMBE_ABS_MAX,
                None,
                SCREEN_UNAVAILABLE,
            )
        )
    elif shape_15min_nmbe_pct is not None:
        _add_threshold_metric(
            gate,
            name="shape_15min_nmbe_abs_pct",
            val=shape_15min_nmbe_pct,
            thr=HOURLY_NMBE_ABS_MAX,
            cmp_fn=lambda v, t: abs(v) <= t,
        )
    return gate


def evaluate_monthly_load_shape_gate(
    *,
    monthly_nmbe_pct: float | None,
    monthly_cvrmse_pct: float | None,
    ramp_gate_result: Mapping[str, Any] | None = None,
) -> LoadShapePromotionGate:
    gate = LoadShapePromotionGate(
        screen="monthly",
        ramp_gate=dict(ramp_gate_result) if ramp_gate_result else None,
    )
    _add_threshold_metric(
        gate,
        name="monthly_nmbe_abs_pct",
        val=monthly_nmbe_pct,
        thr=MONTHLY_NMBE_ABS_MAX,
        cmp_fn=lambda v, t: abs(v) <= t,
    )
    _add_threshold_metric(
        gate,
        name="monthly_cvrmse_pct",
        val=monthly_cvrmse_pct,
        thr=MONTHLY_CVRMSE_MAX,
        cmp_fn=lambda v, t: v <= t,
    )
    return gate


def evaluate_load_shape_gate(
    *,
    hourly_nmbe_pct: float | None,
    hourly_cvrmse_pct: float | None,
    load_shape_correlation: float | None = None,
    peak_timing_error_hours: float | None = None,
    morning_recovery_error_f: float | None = None,
    overnight_load_error_pct: float | None = None,
    shape_15min_nmbe_pct: float | None = None,
    meter_alignment_ok: bool = True,
    ramp_gate_result: Mapping[str, Any] | None = None,
    monthly_nmbe_pct: float | None = None,
    monthly_cvrmse_pct: float | None = None,
) -> LoadShapePromotionGate:
    """Combined gate: hourly screen plus optional monthly fields (never cross-mapped)."""
    gate = evaluate_hourly_load_shape_gate(
        hourly_nmbe_pct=hourly_nmbe_pct,
        hourly_cvrmse_pct=hourly_cvrmse_pct,
        load_shape_correlation=load_shape_correlation,
        peak_timing_error_hours=peak_timing_error_hours,
        morning_recovery_error_f=morning_recovery_error_f,
        overnight_load_error_pct=overnight_load_error_pct,
        shape_15min_nmbe_pct=shape_15min_nmbe_pct,
        meter_alignment_ok=meter_alignment_ok,
        ramp_gate_result=ramp_gate_result,
    )
    if monthly_nmbe_pct is not None or monthly_cvrmse_pct is not None:
        monthly = evaluate_monthly_load_shape_gate(
            monthly_nmbe_pct=monthly_nmbe_pct,
            monthly_cvrmse_pct=monthly_cvrmse_pct,
            ramp_gate_result=None,
        )
        gate.metrics.extend(monthly.metrics)
    return gate


__all__ = [
    "LoadShapePromotionGate",
    "evaluate_load_shape_gate",
    "evaluate_hourly_load_shape_gate",
    "evaluate_monthly_load_shape_gate",
    "evaluate_ramp_gate",
    "SCHEMA",
    "SCREEN_UNAVAILABLE",
]
