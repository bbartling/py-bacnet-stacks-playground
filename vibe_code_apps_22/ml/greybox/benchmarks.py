"""Grey-box identification benchmarks — persistence / OAT / horizons / gates.

Metrics are 15-minute horizon errors. Do **not** label them ASHRAE Guideline 14.
"""
from __future__ import annotations

from typing import Any

import numpy as np

B_FLOOR = 1e-6
A_NEAR_ONE = 0.999
C_FLOOR = 1e-9


def persistence_forecast(t0: float, n: int) -> np.ndarray:
    """Open-loop constant-state persistence: hold measured init for n steps."""
    return np.full(int(n), float(t0), dtype=float)


def simulate_oat_only(t0: float, oat: np.ndarray, *, a: float = 0.9) -> np.ndarray:
    """Naive envelope ARX: T' = a T + (1-a) OAT (no HVAC)."""
    oat = np.asarray(oat, dtype=float)
    b = 1.0 - float(a)
    pred = np.zeros(len(oat), dtype=float)
    t = float(t0)
    for i in range(len(oat)):
        t = a * t + b * float(oat[i])
        pred[i] = t
    return pred


def horizon_mae(y: np.ndarray, yhat: np.ndarray, *, steps: int) -> float:
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    n = min(len(y), len(yhat), int(steps))
    if n <= 0:
        return float("nan")
    return float(np.mean(np.abs(y[:n] - yhat[:n])))


def horizon_rmse(y: np.ndarray, yhat: np.ndarray, *, steps: int) -> float:
    y = np.asarray(y, dtype=float)
    yhat = np.asarray(yhat, dtype=float)
    n = min(len(y), len(yhat), int(steps))
    if n <= 0:
        return float("nan")
    return float(np.sqrt(np.mean((y[:n] - yhat[:n]) ** 2)))


def horizon_table(y: np.ndarray, yhat: np.ndarray) -> dict[str, float]:
    """1h/4h/8h/24h at 15-min steps (4/16/32/96)."""
    out: dict[str, float] = {}
    for name, steps in (("1h", 4), ("4h", 16), ("8h", 32), ("24h", 96)):
        out[f"mae_{name}"] = horizon_mae(y, yhat, steps=steps)
        out[f"rmse_{name}"] = horizon_rmse(y, yhat, steps=steps)
    return out


def residual_autocorr(resid: np.ndarray, *, lag: int = 1) -> float:
    r = np.asarray(resid, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) <= lag + 2:
        return float("nan")
    r = r - r.mean()
    denom = float(np.dot(r, r))
    if denom <= 1e-18:
        return 0.0
    return float(np.dot(r[:-lag], r[lag:]) / denom)


def free_response_mask(
    occupied: np.ndarray | None,
    facility_kw: np.ndarray | None = None,
    *,
    kw_ceiling: float = 40.0,
) -> np.ndarray:
    """True where envelope ID is plausible (unoccupied and/or low facility kW)."""
    n = None
    if occupied is not None:
        occ = np.asarray(occupied, dtype=float)
        n = len(occ)
        mask = occ < 0.5
    else:
        mask = None
    if facility_kw is not None:
        kw = np.asarray(facility_kw, dtype=float)
        n = len(kw) if n is None else n
        low = kw <= float(kw_ceiling)
        mask = low if mask is None else (mask & low)
    if mask is None:
        raise ValueError("need occupied and/or facility_kw for free-response mask")
    return np.asarray(mask, dtype=bool)


def select_free_response_days(
    df,
    *,
    day_col: str = "day",
    occupied_col: str = "occupied",
    kw_col: str = "facility_kw",
    min_frac: float = 0.6,
    kw_ceiling: float = 40.0,
) -> list[str]:
    """Calendar days with mostly free-response intervals."""
    if day_col not in df.columns:
        return []
    days: list[str] = []
    for day, g in df.groupby(day_col, sort=True):
        occ = g[occupied_col].to_numpy(dtype=float) if occupied_col in g.columns else None
        kw = g[kw_col].to_numpy(dtype=float) if kw_col in g.columns else None
        if occ is None and kw is None:
            continue
        m = free_response_mask(occ, kw, kw_ceiling=kw_ceiling)
        if float(m.mean()) >= min_frac and len(g) == 96:
            days.append(str(day))
    return days


def parameter_boundary_flags(
    *,
    a: float,
    b: float,
    c: float,
    a_near: float = A_NEAR_ONE,
    b_floor: float = B_FLOOR,
) -> dict[str, bool]:
    return {
        "a_near_one": bool(a >= a_near),
        "b_at_floor": bool(b <= b_floor * 1.01),
        "c_at_floor": bool(c <= C_FLOOR),
        "bound_hit": bool(a >= a_near and b <= b_floor * 1.01),
    }


def physics_gate_from_params(
    *,
    a: float,
    b: float,
    c: float,
    beats_persistence: bool,
    oat_sign_ok: bool | None = None,
) -> dict[str, Any]:
    """Physics PASS requires identifiable OAT coupling — not MAE alone."""
    flags = parameter_boundary_flags(a=a, b=b, c=c)
    if flags["bound_hit"]:
        return {
            "physics_pass": False,
            "reason": "BOUND_HIT",
            "flags": flags,
            "beats_persistence": bool(beats_persistence),
        }
    if oat_sign_ok is None:
        oat_sign_ok = b > B_FLOOR * 10
    if not oat_sign_ok:
        return {
            "physics_pass": False,
            "reason": "OAT_RESPONSE_WEAK",
            "flags": flags,
            "beats_persistence": bool(beats_persistence),
        }
    if not beats_persistence:
        return {
            "physics_pass": False,
            "reason": "FAILS_PERSISTENCE",
            "flags": flags,
            "beats_persistence": False,
        }
    return {
        "physics_pass": True,
        "reason": "PASS",
        "flags": flags,
        "beats_persistence": True,
    }


def blocking_exit_code(*, physics_pass: bool, deployable_ok: bool) -> int:
    return 0 if (physics_pass and deployable_ok) else 1


def block_bootstrap_params(
    t_meas: np.ndarray,
    oat: np.ndarray,
    q_eff: np.ndarray,
    *,
    zone: str,
    n_boot: int = 40,
    block: int = 96,
    seed: int = 0,
) -> list[dict[str, float]]:
    """Block-bootstrap refits for parameter stability (exploratory ID only)."""
    from greybox.rc_1r1c import fit_1r1c

    t_meas = np.asarray(t_meas, dtype=float)
    oat = np.asarray(oat, dtype=float)
    q_eff = np.asarray(q_eff, dtype=float)
    n = len(t_meas)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, float]] = []
    n_blocks = max(1, (n + block - 1) // block)
    for _ in range(int(n_boot)):
        starts = rng.integers(0, max(1, n - block + 1), size=n_blocks)
        idx = np.concatenate([np.arange(s, min(s + block, n)) for s in starts])
        if len(idx) > n:
            idx = idx[:n]
        elif len(idx) < n:
            # Pad by resampling blocks until length n
            extra = []
            while len(idx) + len(extra) < n:
                s = int(rng.integers(0, max(1, n - block + 1)))
                extra.extend(range(s, min(s + block, n)))
            idx = np.concatenate([idx, np.asarray(extra, dtype=int)])[:n]
        if len(idx) < 50:
            continue
        try:
            p = fit_1r1c(t_meas[idx], oat[idx], q_eff[idx], zone=zone)
        except Exception:
            continue
        rows.append({"a": p.a, "b": p.b, "c": p.c, "R": p.R, "C": p.C})
    return rows
