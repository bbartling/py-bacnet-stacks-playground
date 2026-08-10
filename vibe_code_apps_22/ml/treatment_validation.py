"""Synthetic treatment-effect metrics for DSM validation gates."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import numpy as np


def treatment_sign_accuracy(
    delta_kw: np.ndarray, *, expected_positive_mask: np.ndarray | None = None
) -> float:
    """Fraction of steps where sign(delta) matches expected positive region."""
    d = np.asarray(delta_kw, dtype=float)
    if expected_positive_mask is None:
        # default: any non-zero delta should be positive for heating increase fixtures
        mask = np.abs(d) > 1e-9
        if not mask.any():
            return 1.0
        return float((d[mask] > 0).mean())
    # expected_positive_mask may be boolean or integer indices
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
