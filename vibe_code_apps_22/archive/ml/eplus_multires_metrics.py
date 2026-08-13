"""Authoritative EnergyPlus multi-resolution NMBE / CVRMSE engine.

Formula policy (locked): commonly cited calibrated-simulation thresholds
(NREL / older G14 practice). ASHRAE G14-2023 text not purchased for this repo.

  NMBE_pct    = 100 * sum(m − ŷ) / ((n − p) * mean(m))
  CVRMSE_pct  = 100 * sqrt(sum((m − ŷ)²) / (n − p)) / mean(m)

Pass/fail uses absolute NMBE. Default p=1 (calibrated-sim interpretation)
unless a calibration registry overrides p.

Resolutions
-----------
- monthly: gates |NMBE|≤5%, CVRMSE≤15%  (GL14-style monthly)
- hourly:  gates |NMBE|≤10%, CVRMSE≤30% (calibrated-sim hourly screen)
- 15min:   DSM diagnostics only — never labeled as GL14
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

# --- Gate constants (percent) ---
MONTHLY_NMBE_ABS_MAX = 5.0
MONTHLY_CVRMSE_MAX = 15.0
HOURLY_NMBE_ABS_MAX = 10.0
HOURLY_CVRMSE_MAX = 30.0

DEFAULT_P = 1
FORMULA_CITATION = (
    "commonly cited calibrated-simulation thresholds (NREL / older G14 practice); "
    "ASHRAE G14-2023 text not purchased"
)


class ShapeMismatchError(ValueError):
    """Observed and simulated series lengths/shapes disagree — refuse silent truncate."""


def _finite_pairs(
    observed: Iterable[float],
    simulated: Iterable[float],
    *,
    allow_truncate: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    o = np.asarray(list(observed), dtype=float).reshape(-1)
    s = np.asarray(list(simulated), dtype=float).reshape(-1)
    if o.shape != s.shape:
        if not allow_truncate:
            raise ShapeMismatchError(
                f"observed shape {o.shape} != simulated shape {s.shape}; "
                "refuse silent truncation — align by timestamp keys upstream"
            )
        n = min(o.size, s.size)
        o, s = o[:n], s[:n]
    mask = np.isfinite(o) & np.isfinite(s)
    return o[mask], s[mask]


def nmbe_cvrmse_pct(
    observed: Iterable[float],
    simulated: Iterable[float],
    *,
    p: int = DEFAULT_P,
) -> dict[str, Any]:
    """Return NMBE% / CVRMSE% with explicit n, p, mean_obs.

    Residuals are (m − ŷ). Never pass signed DSM deltas as the observed series
    for CVRMSE (that would inflate / mislabel interval skill).
    """
    m, yhat = _finite_pairs(observed, simulated)
    n = int(m.size)
    p_i = int(p)
    out: dict[str, Any] = {
        "n": n,
        "p": p_i,
        "nmbe_pct": float("nan"),
        "cvrmse_pct": float("nan"),
        "mean_obs": float("nan"),
        "formula": FORMULA_CITATION,
    }
    if n == 0:
        return out
    mean_obs = float(np.mean(m))
    out["mean_obs"] = mean_obs
    dof = n - p_i
    if dof < 1 or abs(mean_obs) < 1e-12:
        return out
    resid = m - yhat
    out["nmbe_pct"] = float(100.0 * float(np.sum(resid)) / (dof * mean_obs))
    out["cvrmse_pct"] = float(
        100.0 * math.sqrt(float(np.sum(resid**2)) / dof) / abs(mean_obs)
    )
    return out


def gate_monthly(stats: Mapping[str, Any]) -> str:
    return _gate(
        stats,
        nmbe_abs_max=MONTHLY_NMBE_ABS_MAX,
        cvrmse_max=MONTHLY_CVRMSE_MAX,
    )


def gate_hourly(stats: Mapping[str, Any]) -> str:
    return _gate(
        stats,
        nmbe_abs_max=HOURLY_NMBE_ABS_MAX,
        cvrmse_max=HOURLY_CVRMSE_MAX,
    )


def _gate(
    stats: Mapping[str, Any],
    *,
    nmbe_abs_max: float,
    cvrmse_max: float,
) -> str:
    n = int(stats.get("n") or 0)
    nmbe = stats.get("nmbe_pct")
    cv = stats.get("cvrmse_pct")
    if n == 0 or nmbe is None or cv is None:
        return "insufficient_data"
    try:
        nmbe_f = float(nmbe)
        cv_f = float(cv)
    except (TypeError, ValueError):
        return "insufficient_data"
    if math.isnan(nmbe_f) or math.isnan(cv_f):
        return "insufficient_data"
    if abs(nmbe_f) <= nmbe_abs_max and cv_f <= cvrmse_max:
        return "pass"
    return "fail"


def gl14_distance(
    stats: Mapping[str, Any],
    *,
    nmbe_abs_max: float = MONTHLY_NMBE_ABS_MAX,
    cvrmse_max: float = MONTHLY_CVRMSE_MAX,
) -> float:
    """Scalar distance outside the gate (0 = at/inside)."""
    if _gate(stats, nmbe_abs_max=nmbe_abs_max, cvrmse_max=cvrmse_max) == "insufficient_data":
        return float("nan")
    nmbe_over = max(0.0, abs(float(stats["nmbe_pct"])) - nmbe_abs_max)
    cv_over = max(0.0, float(stats["cvrmse_pct"]) - cvrmse_max)
    return round(nmbe_over + cv_over, 3)


def resolution_block(
    observed: Iterable[float],
    simulated: Iterable[float],
    *,
    resolution: str,
    p: int = DEFAULT_P,
    label_gl14: bool | None = None,
) -> dict[str, Any]:
    """Build one resolution validation block for schema/CLI."""
    stats = nmbe_cvrmse_pct(observed, simulated, p=p)
    res = str(resolution).lower().strip()
    if res == "monthly":
        status = gate_monthly(stats)
        gates = {
            "nmbe_abs_max_pct": MONTHLY_NMBE_ABS_MAX,
            "cvrmse_max_pct": MONTHLY_CVRMSE_MAX,
        }
        is_gl14 = True if label_gl14 is None else bool(label_gl14)
    elif res == "hourly":
        status = gate_hourly(stats)
        gates = {
            "nmbe_abs_max_pct": HOURLY_NMBE_ABS_MAX,
            "cvrmse_max_pct": HOURLY_CVRMSE_MAX,
        }
        is_gl14 = False if label_gl14 is None else bool(label_gl14)
    elif res in {"15min", "15-min", "q15", "dsm"}:
        status = "diagnostic_only"
        gates = None
        is_gl14 = False
    else:
        raise ValueError(f"unknown resolution {resolution!r}")

    n = int(stats["n"])
    partial_year = res == "monthly" and 0 < n < 12
    return {
        "resolution": "15min" if res in {"15min", "15-min", "q15", "dsm"} else res,
        "status": status,
        "n": n,
        "p": int(stats["p"]),
        "nmbe_pct": stats["nmbe_pct"],
        "cvrmse_pct": stats["cvrmse_pct"],
        "mean_obs": stats["mean_obs"],
        "gates": gates,
        "labeled_as_gl14": is_gl14,
        "partial_year_monthly": partial_year,
        "formula": FORMULA_CITATION,
        "distance_to_gate": (
            None
            if gates is None
            else gl14_distance(
                stats,
                nmbe_abs_max=float(gates["nmbe_abs_max_pct"]),
                cvrmse_max=float(gates["cvrmse_max_pct"]),
            )
        ),
    }


def build_validation_document(
    *,
    monthly: Mapping[str, Any] | None = None,
    monthly_utility: Mapping[str, Any] | None = None,
    monthly_interval: Mapping[str, Any] | None = None,
    hourly: Mapping[str, Any] | None = None,
    q15: Mapping[str, Any] | None = None,
    physics_label: str = "IdealLoads + fixed-COP proxy (not GSHP/GLHE)",
    idf_sha256: str | None = None,
    epw_sha256: str | None = None,
    alignment: Mapping[str, Any] | None = None,
    acceptance_policy_id: str = "eplus_dsm_acceptance_policy_v1",
    recommendation_allowed: bool | None = None,
    blocker_reason: str | None = None,
    chronological_periods: Mapping[str, Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble schema-shaped multi-res validation JSON.

    ``monthly`` is a legacy alias. Prefer ``monthly_utility`` and
    ``monthly_interval`` — never present interval aggregates as utility bills.
    """
    util = dict(monthly_utility) if monthly_utility else (dict(monthly) if monthly else None)
    interv = dict(monthly_interval) if monthly_interval else None
    # Never allow interval block to claim utility_bill source
    if interv and interv.get("source_type") == "utility_bill_monthly":
        raise ValueError("monthly_interval must not use source_type=utility_bill_monthly")
    if util and util.get("source_type") == "interval_meter_monthly":
        raise ValueError("monthly_utility must not use source_type=interval_meter_monthly")

    blocks = {
        "monthly_utility": util,
        "monthly_interval": interv,
        # Legacy key: prefer utility when present, else interval — but stamp source
        "monthly": util or interv,
        "hourly": dict(hourly) if hourly else None,
        "q15_dsm": dict(q15) if q15 else None,
    }
    util_ok = (util or {}).get("status") == "pass"
    interv_ok = (interv or {}).get("status") == "pass" if interv else False
    monthly_ok = bool(util_ok)  # utility is the bill calibration product
    hourly_ok = (blocks["hourly"] or {}).get("status") == "pass"
    if recommendation_allowed is None:
        # DSM requires utility monthly screen + hourly — interval monthly alone is insufficient
        recommendation_allowed = bool(monthly_ok and hourly_ok)
    if blocker_reason is None and not recommendation_allowed:
        reasons = []
        if util and util.get("status") != "pass":
            reasons.append(f"monthly_utility={util.get('status')}")
        if blocks["hourly"] and blocks["hourly"].get("status") != "pass":
            reasons.append(f"hourly={blocks['hourly'].get('status')}")
        if not util or not blocks["hourly"]:
            reasons.append("incomplete_resolutions")
        if interv and interv.get("status") != "pass":
            reasons.append(f"monthly_interval={interv.get('status')}")
        blocker_reason = "; ".join(reasons) if reasons else "gates_not_met"

    # Stamp partial-period honesty on monthly products
    for key in ("monthly_utility", "monthly_interval", "monthly"):
        b = blocks.get(key)
        if not b:
            continue
        n = int(b.get("n") or 0)
        if 0 < n < 12:
            b["partial_year_monthly"] = True
            b["labeled_as_gl14"] = False
            b.setdefault(
                "label",
                "PARTIAL-PERIOD MONTHLY THRESHOLD SCREEN",
            )

    doc: dict[str, Any] = {
        "schema": "eplus_multires_validation_v1",
        "acceptance_policy_id": acceptance_policy_id,
        "physics_label": physics_label,
        "idf_sha256": idf_sha256,
        "epw_sha256": epw_sha256,
        "formula": FORMULA_CITATION,
        "resolutions": blocks,
        "overall": {
            "monthly_pass": monthly_ok,
            "monthly_utility_pass": util_ok,
            "monthly_interval_pass": interv_ok,
            "hourly_pass": hourly_ok,
            "recommendation_allowed": bool(recommendation_allowed),
            "blocker_reason": blocker_reason if not recommendation_allowed else None,
            "optimizer_ready": False,
            "operational_dsm_readiness": "BLOCKED",
            "operational_dsm_prohibited_until_gates_clear": True,
        },
        "alignment": dict(alignment) if alignment else None,
        "chronological_periods": dict(chronological_periods) if chronological_periods else None,
    }
    if extra:
        doc["extra"] = dict(extra)
    return doc


def cross_correlation_lags(
    measured: Sequence[float],
    modeled: Sequence[float],
    *,
    max_lag: int = 24,
) -> dict[str, Any]:
    """Cross-correlation at integer lags −max_lag..+max_lag (no auto-shift applied)."""
    m, y = _finite_pairs(measured, modeled)
    n = min(m.size, y.size)
    m, y = m[:n], y[:n]
    if n < max_lag * 2 + 2:
        return {"n": n, "lags": {}, "best_lag": None, "best_corr": None}
    m0 = m - m.mean()
    y0 = y - y.mean()
    denom = float(np.sqrt(np.sum(m0**2) * np.sum(y0**2)))
    lags: dict[str, float] = {}
    best_lag = 0
    best_corr = float("nan")
    if denom < 1e-12:
        return {"n": n, "lags": {}, "best_lag": None, "best_corr": None}
    for lag in range(-max_lag, max_lag + 1):
        if lag < 0:
            a, b = m0[:lag], y0[-lag:]
        elif lag > 0:
            a, b = m0[lag:], y0[:-lag]
        else:
            a, b = m0, y0
        if a.size < 2:
            continue
        corr = float(np.dot(a, b) / denom)
        lags[str(lag)] = corr
        if math.isnan(best_corr) or abs(corr) > abs(best_corr):
            best_corr = corr
            best_lag = lag
    return {
        "n": n,
        "lags": lags,
        "best_lag": best_lag,
        "best_corr": best_corr,
        "note": "Do not apply lag shifts unless physical semantics prove them",
    }
