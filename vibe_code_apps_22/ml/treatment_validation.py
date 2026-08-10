"""Synthetic + real treatment-effect metrics for DSM validation gates."""
from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Any

import numpy as np

_ML = Path(__file__).resolve().parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from billing_month_replay import ILLUSTRATIVE_DEMAND_RATE_PER_KW, ILLUSTRATIVE_ENERGY_RATE_PER_KWH
from simulation_contract import incremental_demand


def treatment_sign_accuracy(
    delta_kw: np.ndarray, *, expected_positive_mask: np.ndarray | None = None
) -> float:
    """Fraction of steps where sign(delta) matches expected positive region."""
    d = np.asarray(delta_kw, dtype=float)
    if expected_positive_mask is None:
        mask = np.abs(d) > 1e-9
        if not mask.any():
            return 1.0
        return float((d[mask] > 0).mean())
    m = np.asarray(expected_positive_mask)
    if m.dtype == bool:
        pos = m
    else:
        pos = np.zeros(len(d), dtype=bool)
        pos[m] = True
    if not pos.any():
        return 1.0
    return float((d[pos] > 0).mean())


def delta_peak_error(
    baseline_kw: np.ndarray, dsm_kw: np.ndarray, *, measured_delta_peak: float
) -> float:
    pred = float(np.max(dsm_kw) - np.max(baseline_kw))
    return pred - float(measured_delta_peak)


def delta_kw_mae_rmse(baseline_kw: np.ndarray, dsm_kw: np.ndarray, measured_delta: np.ndarray) -> tuple[float, float]:
    pred = np.asarray(dsm_kw, dtype=float) - np.asarray(baseline_kw, dtype=float)
    err = pred - np.asarray(measured_delta, dtype=float)
    return float(np.mean(np.abs(err))), float(np.sqrt(np.mean(err**2)))


def delta_kwh_error(baseline_kw: np.ndarray, dsm_kw: np.ndarray, measured_delta_kwh: float) -> float:
    pred_kwh = float((np.asarray(dsm_kw) - np.asarray(baseline_kw)).sum() * 0.25)
    return pred_kwh - float(measured_delta_kwh)


def pairwise_ranking_accuracy(
    scores: dict[str, float], truth_order: list[str]
) -> float:
    """Fraction of pairs where score order matches truth order (lower score better)."""
    ids = list(truth_order)
    if len(ids) < 2:
        return 1.0
    ok = tot = 0
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a, b = ids[i], ids[j]
            # truth: a ranks better than b (earlier in list)
            tot += 1
            if scores[a] <= scores[b]:
                ok += 1
    return ok / tot if tot else 1.0


def economic_regret_vs_bau(
    *,
    bau_peak: float,
    strategy_peak: float,
    bau_kwh: float,
    strategy_kwh: float,
    existing_billing_peak: float,
    energy_rate: float = ILLUSTRATIVE_ENERGY_RATE_PER_KWH,
    demand_rate: float = ILLUSTRATIVE_DEMAND_RATE_PER_KW,
) -> float:
    """Positive regret = strategy costs more incremental $ than BAU (illustrative)."""
    _, _, bau_d = incremental_demand(existing_billing_peak, bau_peak, demand_rate)
    _, _, strat_d = incremental_demand(existing_billing_peak, strategy_peak, demand_rate)
    bau_c = bau_kwh * energy_rate + bau_d
    strat_c = strategy_kwh * energy_rate + strat_d
    return float(strat_c - bau_c)


def score_strategy_day(
    baseline_kw: np.ndarray,
    dsm_kw: np.ndarray,
    *,
    strategy: str,
    measured_delta: np.ndarray | None = None,
) -> dict[str, Any]:
    b = np.asarray(baseline_kw, dtype=float)
    d = np.asarray(dsm_kw, dtype=float)
    delta = d - b
    meas = measured_delta if measured_delta is not None else delta
    mae, rmse = delta_kw_mae_rmse(b, d, meas)
    return {
        "strategy": strategy,
        "delta_peak_err": delta_peak_error(b, d, measured_delta_peak=float(np.max(meas))),
        "delta_kw_mae": mae,
        "delta_kw_rmse": rmse,
        "delta_kwh_err": delta_kwh_error(b, d, measured_delta_kwh=float(meas.sum() * 0.25)),
        "sign_acc": treatment_sign_accuracy(delta),
        "pred_peak_delta": float(np.max(d) - np.max(b)),
    }


def write_treatment_validation_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("strategy,delta_peak_err,sign_acc\n", encoding="utf-8")
        return
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
