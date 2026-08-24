from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np


@dataclass(frozen=True)
class CalibrationScore:
    n: int
    p: int
    interval: str
    nmbe_pct: float
    cvrmse_pct: float
    passes: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _paired(measured, simulated) -> tuple[np.ndarray, np.ndarray]:
    measured = np.asarray(measured, dtype=float)
    simulated = np.asarray(simulated, dtype=float)
    if measured.shape != simulated.shape or measured.ndim != 1:
        raise ValueError("Measured and simulated inputs must be same-length 1D arrays")
    if measured.size < 2:
        raise ValueError("At least two paired samples are required")
    if not np.isfinite(measured).all() or not np.isfinite(simulated).all():
        raise ValueError("Calibration inputs must be finite")
    if float(measured.mean()) == 0.0:
        raise ValueError("Measured mean cannot be zero")
    return measured, simulated


def nmbe(measured, simulated, p: int = 1) -> float:
    measured, simulated = _paired(measured, simulated)
    n = measured.size
    if not 0 <= p < n:
        raise ValueError("p must satisfy 0 <= p < n")
    return float(100.0 * np.sum(measured - simulated) / ((n - p) * measured.mean()))


def cvrmse(measured, simulated, p: int = 1) -> float:
    measured, simulated = _paired(measured, simulated)
    n = measured.size
    if not 0 <= p < n:
        raise ValueError("p must satisfy 0 <= p < n")
    rmse = np.sqrt(np.sum((measured - simulated) ** 2) / (n - p))
    return float(100.0 * rmse / measured.mean())


def score_calibration(measured, simulated, interval: str, p: int = 1) -> CalibrationScore:
    interval = interval.lower()
    gates = {"monthly": (5.0, 15.0), "hourly": (10.0, 30.0)}
    if interval not in gates:
        raise ValueError("interval must be 'monthly' or 'hourly'")
    m, s = _paired(measured, simulated)
    bias = nmbe(m, s, p=p)
    cv = cvrmse(m, s, p=p)
    max_bias, max_cv = gates[interval]
    return CalibrationScore(
        n=m.size,
        p=p,
        interval=interval,
        nmbe_pct=bias,
        cvrmse_pct=cv,
        passes=abs(bias) <= max_bias and cv <= max_cv,
    )
