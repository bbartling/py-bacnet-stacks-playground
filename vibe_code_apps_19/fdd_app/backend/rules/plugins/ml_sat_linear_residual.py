"""Most-basic-of-basic scikit-learn proof of concept.

Fits a plain `LinearRegression` (ordinary least squares) that predicts supply-air
temperature (SAT) from the other AHU air/command signals, then flags samples whose
prediction residual is an outlier (|z| over a threshold) as a candidate fault.

This is deliberately trivial — it exists to prove the pipeline end to end:
    pandas features -> sklearn model.fit/predict -> boolean fault mask -> confirm.
Run it from the ML page; the "Persist to Feather store" button writes the confirmed
fault series back to `.cache/feather/faults/` as the proof-of-concept round trip.

Falls back to a NumPy least-squares fit if scikit-learn is not installed so the page
keeps working (use the pip panel to `pip install scikit-learn`).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from rules.base import ParamSpec, RuleContext, RuleManifest, RuleResult, confirm_fault

RULE = RuleManifest(
    id="ML-SAT-LINREG",
    title="ML SAT linear-regression residual (sklearn PoC)",
    description=(
        "Ordinary least-squares model predicts SAT from OAT/MAT/economizer/cooling; "
        "samples with an outlier residual are flagged. Minimal end-to-end sklearn-in-pandas "
        "proof of concept — persistable to the Feather fault store."
    ),
    kind="ml",
    author="vibe-coder PoC",
    equipment_kinds=["ahu"],
    required_logical_cols=["sat", "oat", "mat"],
    params=[
        ParamSpec(key="resid_z", label="Residual z-score", unit="σ", min=1.0, max=6.0, step=0.5, default=3.0),
        ParamSpec(key="confirm_min", label="Confirm delay", unit="min", min=0, max=60, step=5, default=10.0),
    ],
)

_TARGET = "sat"
_FEATURES = ["oat", "mat", "econ", "clg"]


def _fit_predict(X: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, str]:
    """Return (predictions, engine_name). Prefer sklearn, fall back to numpy lstsq."""
    try:
        from sklearn.linear_model import LinearRegression

        model = LinearRegression()
        model.fit(X, y)
        return model.predict(X), "sklearn LinearRegression"
    except Exception:
        # numpy ordinary least squares with intercept
        Xi = np.column_stack([np.ones(len(X)), X])
        coef, *_ = np.linalg.lstsq(Xi, y, rcond=None)
        return Xi @ coef, "numpy lstsq (sklearn unavailable)"


def compute(ctx: RuleContext) -> RuleResult:
    df = ctx.df
    if _TARGET not in df.columns:
        return RuleResult(message="No SAT column available for ML regression.")

    feats = [c for c in _FEATURES if c in df.columns]
    if not feats:
        return RuleResult(message="No predictor columns (oat/mat/econ/clg) available.")

    data = df[[_TARGET] + feats].apply(pd.to_numeric, errors="coerce")
    valid = data.dropna()
    if len(valid) < 50:
        return RuleResult(message=f"Not enough clean rows to fit ({len(valid)}).")

    y = valid[_TARGET].to_numpy(dtype=float)
    X = valid[feats].to_numpy(dtype=float)
    pred, engine = _fit_predict(X, y)

    resid = y - pred
    std = resid.std(ddof=0) or 1.0
    z = np.abs(resid) / std
    thresh = float(ctx.params["resid_z"])

    # Map the fit-subset flags back onto the full frame index.
    raw = pd.Series(False, index=df.index)
    raw.loc[valid.index] = z > thresh

    confirmed = confirm_fault(
        raw, poll_seconds=ctx.poll_seconds, confirm_seconds=ctx.params["confirm_min"] * 60,
    )

    plot = {"sat_actual": pd.to_numeric(df[_TARGET], errors="coerce")}
    pred_series = pd.Series(np.nan, index=df.index)
    pred_series.loc[valid.index] = pred
    plot["sat_predicted"] = pred_series

    return RuleResult(
        fault_series=confirmed,
        message=(
            f"{engine}: fit on {len(valid)} rows, {int((z > thresh).sum())} residual outliers "
            f"(> {thresh:.1f}σ, residual σ={std:.2f}°F)."
        ),
        plot_series=plot,
        extra={"engine": engine, "features": feats, "resid_std_f": round(float(std), 3)},
    )
