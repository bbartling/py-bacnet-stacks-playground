"""GREYBOX_SHADOW_V1 — discrete 15-min 1R1C thermal zone (non-promotable).

State (simple): T[t+1] = a * T[t] + b * OAT[t] + c * Q_eff[t]
with a,b,c constrained so effective R,C > 0 when interpretable.

Honesty: Q_eff is DIAGNOSTIC / effective — not measured compressor heat.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

DT_H = 0.25  # 15 min in hours
HONESTY = "GREYBOX_SHADOW_V1"
PROMOTE = "NON_PROMOTABLE"
Q_POLICY = "Q_eff_DIAGNOSTIC"


@dataclass(frozen=True)
class RC1R1CParams:
    """Discrete ARX coeffs + positive R,C interpretation (SI-ish °F·h / Btu proxy)."""

    a: float  # T self
    b: float  # OAT
    c: float  # Q_eff
    R: float  # effective resistance (>0)
    C: float  # effective capacitance (>0)
    zone: str
    q_policy: str = Q_POLICY
    honesty: str = HONESTY
    promote: str = PROMOTE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def step_open_loop(
    t: float,
    oat: float,
    q_eff: float,
    *,
    a: float,
    b: float,
    c: float,
) -> float:
    """One 15-min open-loop step — exogenous oat/q only (no y[t] leak into inputs)."""
    return float(a * t + b * oat + c * q_eff)


def simulate(
    t0: float,
    oat: np.ndarray,
    q_eff: np.ndarray,
    *,
    a: float,
    b: float,
    c: float,
) -> np.ndarray:
    """Open-loop roll: ``pred[i]`` is the predicted state *after* step ``i``.

    Init ``t0`` is the measured state *before* the first exogenous sample.
    With ``len(oat)==n``, returns length ``n`` where ``pred[i] ≈ T[i+1]``
    when ``oat[i]/q_eff[i]`` are the inputs for that step. Compare to
    ``t_meas[1:]`` (not ``t_meas`` aligned at index 0).
    """
    oat = np.asarray(oat, dtype=float)
    q_eff = np.asarray(q_eff, dtype=float)
    if len(oat) != len(q_eff):
        raise ValueError("oat and q_eff length mismatch")
    n = len(oat)
    pred = np.zeros(n, dtype=float)
    t = float(t0)
    for i in range(n):
        pred[i] = step_open_loop(t, float(oat[i]), float(q_eff[i]), a=a, b=b, c=c)
        t = pred[i]
    return pred


def _positive_rc_from_abc(a: float, b: float, c: float) -> tuple[float, float]:
    """Map discrete coeffs to positive R,C when possible.

    Continuous 1R1C: C dT/dt = (OAT - T)/R + Q
    Forward Euler dt: T' = (1 - dt/(RC)) T + (dt/(RC)) OAT + (dt/C) Q
    → a = 1 - dt/(RC), b = dt/(RC), c = dt/C, and **a + b = 1**.
    Caller must enforce ``a + b ≈ 1`` before interpreting R,C.
    """
    dt = DT_H
    if abs((a + b) - 1.0) > 0.05:
        raise ValueError(f"a+b must be ~1 for R,C export (got a={a}, b={b})")
    if b <= 1e-9:
        R = 1.0
        C = max(dt / max(abs(c), 1e-6), 1e-3)
        return float(R), float(C)
    rc = dt / b  # R*C product
    if c > 1e-9:
        C = dt / c
        R = rc / max(C, 1e-9)
    else:
        C = 1.0
        R = rc / C
    return max(float(R), 1e-6), max(float(C), 1e-6)


def fit_1r1c(
    t_meas: np.ndarray,
    oat: np.ndarray,
    q_eff: np.ndarray,
    *,
    zone: str = "zone_temp_1F_A_f",
) -> RC1R1CParams:
    """Least-squares fit T[k+1] ~ a T[k] + b OAT[k] + c Q[k] with soft positive constraints."""
    t_meas = np.asarray(t_meas, dtype=float)
    oat = np.asarray(oat, dtype=float)
    q_eff = np.asarray(q_eff, dtype=float)
    if not (len(t_meas) == len(oat) == len(q_eff)):
        raise ValueError("length mismatch")
    if len(t_meas) < 10:
        raise ValueError("need at least 10 samples")

    y = t_meas[1:]
    X = np.column_stack([t_meas[:-1], oat[:-1], q_eff[:-1]])
    # ridge for stability
    lam = 1e-3
    xtx = X.T @ X + lam * np.eye(3)
    xty = X.T @ y
    coef = np.linalg.solve(xtx, xty)
    a, b, c = float(coef[0]), float(coef[1]), float(coef[2])

    # Soft project: a in (0,1), b>0, c>=0, then enforce Euler a+b=1
    a = float(np.clip(a, 1e-4, 0.999))
    b = float(max(b, 1e-6))
    c = float(max(c, 0.0))
    s = a + b
    a, b = a / s, b / s
    if a >= 1.0:
        a = 0.999
        b = 1.0 - a

    R, C = _positive_rc_from_abc(a, b, c)
    return RC1R1CParams(a=a, b=b, c=c, R=R, C=C, zone=zone)


def q_eff_diagnostic(
    facility_kw: np.ndarray,
    occupied: np.ndarray | None = None,
    *,
    non_hvac_floor_kw: float = 25.0,
) -> np.ndarray:
    """Effective heat proxy from facility residual — DIAGNOSTIC only, not compressor Q."""
    kw = np.asarray(facility_kw, dtype=float)
    q = np.maximum(0.0, kw - float(non_hvac_floor_kw))
    if occupied is not None:
        occ = np.asarray(occupied, dtype=float)
        # night / unoccupied: shrink Q toward 0 for free-response emphasis
        q = np.where(occ < 0.5, q * 0.15, q)
    return q


def mae(y: np.ndarray, yhat: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(y, dtype=float) - np.asarray(yhat, dtype=float))))
