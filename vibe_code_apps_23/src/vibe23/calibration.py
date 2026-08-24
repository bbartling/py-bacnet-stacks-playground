"""Fail-closed calibration evidence, alignment, and acceptance gates.

This module deliberately separates a *score* from a *calibration claim*.  A
good NMBE/CV(RMSE) value is not sufficient: a claim also needs a complete,
hashable input set, a full-year paired meter series, and the independent load
shape checks that are possible for Building 59.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal, Mapping

import numpy as np
import pandas as pd

from vibe23.metrics import CalibrationScore, score_calibration

Aggregation = Literal["sum", "mean"]


@dataclass(frozen=True)
class AlignmentResult:
    """Paired values after an explicit common time-bucket aggregation."""

    interval: str
    aggregation: Aggregation
    paired: pd.DataFrame
    measured_rows: int
    simulated_rows: int

    @property
    def paired_rows(self) -> int:
        return len(self.paired)

    def summary(self) -> dict[str, Any]:
        return {
            "interval": self.interval,
            "aggregation": self.aggregation,
            "measured_rows": self.measured_rows,
            "simulated_rows": self.simulated_rows,
            "paired_rows": self.paired_rows,
            "overlap_start": None if self.paired.empty else self.paired.index.min().isoformat(),
            "overlap_end": None if self.paired.empty else self.paired.index.max().isoformat(),
        }


def _as_series(values: pd.Series, label: str) -> pd.Series:
    if not isinstance(values, pd.Series):
        raise TypeError(f"{label} must be a pandas Series")
    if not isinstance(values.index, pd.DatetimeIndex):
        raise TypeError(f"{label} must have a DatetimeIndex")
    if values.empty:
        raise ValueError(f"{label} is empty")
    if values.index.has_duplicates:
        raise ValueError(f"{label} contains duplicate timestamps; resolve them before alignment")
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    if not np.isfinite(numeric).all():
        raise ValueError(f"{label} contains null or non-finite values")
    return numeric.sort_index()


def _check_timezone(measured: pd.DatetimeIndex, simulated: pd.DatetimeIndex) -> None:
    # A naive timestamp and an aware timestamp are not safely comparable.  Two
    # aware series need the same named timezone because a later UTC conversion
    # can silently change local monthly buckets around DST.
    if (measured.tz is None) != (simulated.tz is None):
        raise ValueError("Measured and simulated timestamps must both be naive or use the same timezone")
    if measured.tz is not None and str(measured.tz) != str(simulated.tz):
        raise ValueError("Measured and simulated timestamps must use the same timezone before alignment")


def align_series(
    measured: pd.Series,
    simulated: pd.Series,
    *,
    interval: str,
    aggregation: Aggregation,
    minimum_pairs: int = 2,
) -> AlignmentResult:
    """Bucket and inner-join two series without inventing missing telemetry.

    ``sum`` is appropriate for energy (kWh, J) and ``mean`` for power,
    temperature, flow, and other rates.  This function intentionally performs
    no interpolation and no timezone conversion.
    """
    if aggregation not in {"sum", "mean"}:
        raise ValueError("aggregation must be 'sum' or 'mean'")
    if minimum_pairs < 2:
        raise ValueError("minimum_pairs must be at least 2")
    measured = _as_series(measured, "measured")
    simulated = _as_series(simulated, "simulated")
    _check_timezone(measured.index, simulated.index)
    if aggregation == "sum":
        measured_bucketed = measured.resample(interval).sum(min_count=1)
        simulated_bucketed = simulated.resample(interval).sum(min_count=1)
    else:
        measured_bucketed = measured.resample(interval).mean()
        simulated_bucketed = simulated.resample(interval).mean()
    paired = pd.concat(
        [measured_bucketed.rename("measured"), simulated_bucketed.rename("simulated")], axis=1, join="inner"
    ).dropna()
    if len(paired) < minimum_pairs:
        raise ValueError(f"Only {len(paired)} paired {interval} values; need at least {minimum_pairs}")
    return AlignmentResult(interval, aggregation, paired, len(measured), len(simulated))


def score_aligned(alignment: AlignmentResult, *, metric_interval: Literal["monthly", "hourly"], p: int = 1) -> CalibrationScore:
    """Apply the published ASHRAE Guideline 14 style thresholds to aligned data."""
    return score_calibration(
        alignment.paired["measured"].to_numpy(), alignment.paired["simulated"].to_numpy(), metric_interval, p=p
    )


def peak_check(measured_kw: pd.Series, simulated_kw: pd.Series, *, max_peak_error_pct: float = 15.0) -> dict[str, Any]:
    """Compare observed and simulated interval peaks after explicit hourly alignment."""
    if max_peak_error_pct <= 0:
        raise ValueError("max_peak_error_pct must be positive")
    aligned = align_series(measured_kw, simulated_kw, interval="1h", aggregation="mean")
    measured_peak = float(aligned.paired["measured"].max())
    simulated_peak = float(aligned.paired["simulated"].max())
    if measured_peak <= 0:
        raise ValueError("Measured peak must be positive")
    error_pct = 100.0 * (simulated_peak - measured_peak) / measured_peak
    return {
        "available": True,
        "basis": "peak of paired hourly mean kW; not a utility demand-interval substitute",
        "measured_peak_kw": measured_peak,
        "simulated_peak_kw": simulated_peak,
        "peak_error_pct": error_pct,
        "max_peak_error_pct": max_peak_error_pct,
        "passes": abs(error_pct) <= max_peak_error_pct,
        "alignment": aligned.summary(),
    }


def end_use_check(
    measured: Mapping[str, pd.Series],
    simulated: Mapping[str, pd.Series],
    *,
    interval: str = "1h",
    max_total_error_pct: float = 20.0,
) -> dict[str, Any]:
    """Evaluate only positively bound measured end uses; never infer them."""
    names = sorted(set(measured) & set(simulated))
    missing_measured = sorted(set(simulated) - set(measured))
    missing_simulated = sorted(set(measured) - set(simulated))
    checks: dict[str, Any] = {}
    for name in names:
        aligned = align_series(measured[name], simulated[name], interval=interval, aggregation="sum")
        observed = float(aligned.paired["measured"].sum())
        modeled = float(aligned.paired["simulated"].sum())
        if observed == 0:
            checks[name] = {"available": False, "reason": "measured_total_is_zero", "alignment": aligned.summary()}
            continue
        error_pct = 100.0 * (modeled - observed) / observed
        checks[name] = {
            "available": True,
            "measured_total": observed,
            "simulated_total": modeled,
            "total_error_pct": error_pct,
            "max_total_error_pct": max_total_error_pct,
            "passes": abs(error_pct) <= max_total_error_pct,
            "alignment": aligned.summary(),
        }
    available = [row for row in checks.values() if row["available"]]
    return {
        "available": bool(available),
        "bound_end_uses": names,
        "not_compared_missing_measured": missing_measured,
        "not_compared_missing_simulated": missing_simulated,
        "checks": checks,
        "passes": bool(available) and all(row.get("passes", False) for row in available),
    }


def zone_temperature_check(
    measured: Mapping[str, pd.Series],
    simulated: Mapping[str, pd.Series],
    *,
    interval: str = "1h",
    max_mae_c: float = 1.0,
    max_rmse_c: float = 2.0,
) -> dict[str, Any]:
    """Check matched zone sensors; unmatched zone names are evidence gaps."""
    names = sorted(set(measured) & set(simulated))
    checks: dict[str, Any] = {}
    for name in names:
        aligned = align_series(measured[name], simulated[name], interval=interval, aggregation="mean")
        error = aligned.paired["simulated"] - aligned.paired["measured"]
        mae = float(np.abs(error).mean())
        rmse = float(np.sqrt(np.mean(error**2)))
        checks[name] = {
            "available": True,
            "mae_c": mae,
            "rmse_c": rmse,
            "max_mae_c": max_mae_c,
            "max_rmse_c": max_rmse_c,
            "passes": mae <= max_mae_c and rmse <= max_rmse_c,
            "alignment": aligned.summary(),
        }
    available = list(checks.values())
    return {
        "available": bool(available),
        "bound_zones": names,
        "not_compared_missing_measured": sorted(set(simulated) - set(measured)),
        "not_compared_missing_simulated": sorted(set(measured) - set(simulated)),
        "checks": checks,
        "passes": bool(available) and all(row["passes"] for row in available),
    }


def calibration_claim_status(
    *,
    monthly: CalibrationScore | None,
    hourly: CalibrationScore | None,
    provenance_complete: bool,
    month_count_required: int = 12,
    physics_gates_passed: bool = False,
    holdout_passed: bool = False,
) -> str:
    """Return the highest honest status supported by the supplied evidence."""
    if not provenance_complete:
        return "CALIBRATION_BOOTSTRAP"
    if monthly is None:
        return "CALIBRATION_IN_PROGRESS"
    if monthly.n < month_count_required or not monthly.passes:
        return "CALIBRATION_IN_PROGRESS"
    if hourly is None or not hourly.passes or not physics_gates_passed:
        return "MONTHLY_CALIBRATED"
    return "VALIDATED_HOLDOUT" if holdout_passed else "HOURLY_CALIBRATED"


def calibration_scorecard(
    *,
    monthly_alignment: AlignmentResult | None,
    hourly_alignment: AlignmentResult | None,
    provenance_complete: bool,
    peak: Mapping[str, Any] | None = None,
    end_uses: Mapping[str, Any] | None = None,
    zones: Mapping[str, Any] | None = None,
    controls: Mapping[str, Any] | None = None,
    transients: Mapping[str, Any] | None = None,
    holdout_passed: bool = False,
) -> dict[str, Any]:
    """Build a serializable scorecard with optional diagnostic checks.

    Peak/end-use/zone checks are reported independently; they are not silently
    folded into GL14 aggregate energy metrics.
    """
    monthly = score_aligned(monthly_alignment, metric_interval="monthly") if monthly_alignment else None
    hourly = score_aligned(hourly_alignment, metric_interval="hourly") if hourly_alignment else None
    diagnostic_checks = (peak, end_uses, zones, controls, transients)
    physics_gates_passed = all(
        check is not None and bool(check.get("available")) and bool(check.get("passes"))
        for check in diagnostic_checks
    )
    status = calibration_claim_status(
        monthly=monthly,
        hourly=hourly,
        provenance_complete=provenance_complete,
        physics_gates_passed=physics_gates_passed,
        holdout_passed=holdout_passed,
    )
    return {
        "schema": "vibe23.calibration_scorecard.v1",
        "claim_status": status,
        "provenance_complete": provenance_complete,
        "monthly_gl14": None if monthly is None else asdict(monthly),
        "hourly_gl14": None if hourly is None else asdict(hourly),
        "monthly_alignment": None if monthly_alignment is None else monthly_alignment.summary(),
        "hourly_alignment": None if hourly_alignment is None else hourly_alignment.summary(),
        "peak_check": dict(peak) if peak else {"available": False, "reason": "not_bound"},
        "end_use_check": dict(end_uses) if end_uses else {"available": False, "reason": "not_bound"},
        "zone_temperature_check": dict(zones) if zones else {"available": False, "reason": "not_bound"},
        "control_check": dict(controls) if controls else {"available": False, "reason": "not_run"},
        "transient_check": dict(transients) if transients else {"available": False, "reason": "not_run"},
        "physics_gates_passed": physics_gates_passed,
        "notes": [
            "Aggregate GL14 gates alone do not prove transient, end-use, or control fidelity.",
            "HOURLY_CALIBRATED requires passing peak, end-use, zone, control, and transient gates.",
            "No status authorizes BAS control or real tariff settlement.",
        ],
    }
