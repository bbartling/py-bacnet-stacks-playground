"""Example ML rule — unsupervised anomaly detection on AHU air temperatures.

Trains an IsolationForest on the fly over the selected logical columns and flags
outlier timestamps as candidate sensor/behavior faults. Demonstrates the ML hook:
features (pandas) -> model.predict -> boolean mask -> confirm -> hours rollup.

Swap the on-the-fly fit for a frozen joblib model in production (see
docs/ROADMAP_ARROW_PLUGINS_ML.md). Falls back to a robust z-score if scikit-learn
is unavailable so the page still works.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from rules.base import ParamSpec, RuleContext, RuleManifest, RuleResult, confirm_fault

RULE = RuleManifest(
    id="ML-AHU-ANOMALY",
    title="ML air-temp anomaly (IsolationForest)",
    description=(
        "Unsupervised anomaly score across supply / mixed / outside / return air "
        "temperatures. High contamination flags more points. Trained per request on "
        "this equipment's history — replace with a frozen joblib model for production."
    ),
    kind="ml",
    author="vibe-coder example",
    equipment_kinds=["ahu"],
    required_logical_cols=["sat", "mat", "oat", "rat"],
    params=[
        ParamSpec(key="contamination_pct", label="Anomaly rate", unit="%", min=0.5, max=15, step=0.5, default=3.0),
        ParamSpec(key="confirm_min", label="Confirm delay", unit="min", min=0, max=60, step=5, default=10.0),
    ],
)

_FEATURES = ["sat", "mat", "oat", "rat"]


def _feature_frame(ctx: RuleContext) -> pd.DataFrame:
    cols = [c for c in _FEATURES if c in ctx.df.columns]
    frame = ctx.df[cols].apply(pd.to_numeric, errors="coerce")
    return frame


def _score_isolation_forest(feats: pd.DataFrame, contamination: float) -> pd.Series | None:
    try:
        from sklearn.ensemble import IsolationForest
    except Exception:
        return None
    filled = feats.ffill().bfill()
    if filled.dropna(how="all").empty:
        return None
    filled = filled.fillna(filled.mean(numeric_only=True)).fillna(0.0)
    model = IsolationForest(
        n_estimators=120,
        contamination=min(max(contamination, 0.005), 0.45),
        random_state=42,
    )
    pred = model.fit_predict(filled.values)
    return pd.Series(pred == -1, index=feats.index)


def _score_zscore(feats: pd.DataFrame, contamination: float) -> pd.Series:
    z = (feats - feats.mean()) / feats.std(ddof=0).replace(0, np.nan)
    score = z.abs().max(axis=1)
    thresh = score.quantile(1.0 - contamination)
    return (score > thresh).fillna(False)


def compute(ctx: RuleContext) -> RuleResult:
    feats = _feature_frame(ctx)
    if feats.empty or feats.notna().sum().sum() == 0:
        return RuleResult(message="No numeric air-temperature features available for ML scoring.")

    contamination = ctx.params["contamination_pct"] / 100.0
    anomalies = _score_isolation_forest(feats, contamination)
    engine = "IsolationForest"
    if anomalies is None:
        anomalies = _score_zscore(feats, contamination)
        engine = "robust z-score (sklearn unavailable)"

    confirmed = confirm_fault(
        anomalies,
        poll_seconds=ctx.poll_seconds,
        confirm_seconds=ctx.params["confirm_min"] * 60,
    )

    plot = {c: pd.to_numeric(ctx.df[c], errors="coerce") for c in _FEATURES if c in ctx.df.columns}
    return RuleResult(
        fault_series=confirmed,
        message=f"{engine}: flagged {int(anomalies.sum())} raw anomaly rows over {len(feats)} samples.",
        plot_series=plot,
        extra={"engine": engine, "features": list(feats.columns)},
    )
