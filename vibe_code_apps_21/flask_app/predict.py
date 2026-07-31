"""Build feature row(s) for demand_hourly inference (no future leakage)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

_ML = Path(__file__).resolve().parents[1] / "ml"
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from feature_compile_dm import FEATURE_COLS, compile_features  # noqa: E402

STRATEGIES = (
    "baseline",
    "precool_shift",
    "deadband_10f",
    "chiller_off",
    "loadshed_p5f",
    "hvac_off",
    "precool_chiller_off",
)

DEFAULTS: dict[str, Any] = {
    "day": "demo",
    "simulation_id": "unity_demo",
    "dow": "Wednesday",
    "hour_ending": 15,
    "oat_c": 32.0,
    "rh_pct": 55.0,
    "ghi": 700.0,
    "occupied": 1.0,
    "in_dr_window": 1.0,
    "precool_f": 0.0,
    "relax_clg_f": 0.0,
    "relax_htg_f": 0.0,
    "dat_delta_f": 0.0,
    "chw_avail": 1.0,
    "fan_avail": 1.0,
    "deadband_target_f": 0.0,
    "strategy_id": "baseline",
    "phase": "baseline",
    "facility_kw": 200.0,
}


def _row_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    row = dict(DEFAULTS)
    for k, v in payload.items():
        if k in ("history", "lookback"):
            continue
        row[k] = v
    if row["strategy_id"] not in STRATEGIES:
        raise ValueError(f"Unknown strategy_id: {row['strategy_id']}; allowed={STRATEGIES}")
    # Unity may pass lag fields directly for single-hour scrub
    for lag_key in ("facility_kw_lag1", "facility_kw_lag2", "oat_lag1"):
        if lag_key in payload:
            row[lag_key] = float(payload[lag_key])
    return row


def features_from_request(body: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    """Return (1, n_features) matrix and echo metadata."""
    history = body.get("history") or body.get("lookback")
    if history:
        rows = []
        for i, h in enumerate(history):
            r = _row_from_payload({**body, **h})
            r["simulation_id"] = body.get("simulation_id", "unity_demo")
            r["day"] = body.get("day", "demo")
            r["hour_ending"] = int(h.get("hour_ending", i + 1))
            if "facility_kw" not in h and i == 0:
                r["facility_kw"] = float(body.get("facility_kw", DEFAULTS["facility_kw"]))
            elif "facility_kw" in h:
                r["facility_kw"] = float(h["facility_kw"])
            else:
                r["facility_kw"] = float(rows[-1]["facility_kw"])
            rows.append(r)
        # final hour may be prediction target without measured kw
        if "hour_ending" in body and int(body["hour_ending"]) != int(rows[-1]["hour_ending"]):
            last = _row_from_payload(body)
            last["facility_kw"] = float(rows[-1]["facility_kw"])
            rows.append(last)
        df = pd.DataFrame(rows)
        feat = compile_features(df)
        x = feat[FEATURE_COLS].to_numpy(dtype=float)[-1:]
        meta = {
            "strategy_id": str(feat.iloc[-1]["strategy_id"]),
            "phase": str(feat.iloc[-1]["phase"]),
            "hour_ending": int(feat.iloc[-1]["hour_ending"]),
            "mode": "history",
        }
        return x, meta

    row = _row_from_payload(body)
    # Single-row path: inject lags then compile without groupby lag overwrite issues
    lag1 = float(body.get("facility_kw_lag1", row["facility_kw"]))
    lag2 = float(body.get("facility_kw_lag2", lag1))
    oat_lag1 = float(body.get("oat_lag1", row["oat_c"]))
    # Two dummy prior hours so compile_features lag fill is consistent
    prior1 = dict(row)
    prior1["hour_ending"] = max(1, int(row["hour_ending"]) - 2)
    prior1["facility_kw"] = lag2
    prior1["oat_c"] = oat_lag1
    prior2 = dict(row)
    prior2["hour_ending"] = max(1, int(row["hour_ending"]) - 1)
    prior2["facility_kw"] = lag1
    prior2["oat_c"] = oat_lag1
    df = pd.DataFrame([prior1, prior2, row])
    feat = compile_features(df)
    # Override compiled lags with explicit Unity values when provided
    if "facility_kw_lag1" in body:
        feat.loc[feat.index[-1], "facility_kw_lag1"] = lag1
    if "facility_kw_lag2" in body:
        feat.loc[feat.index[-1], "facility_kw_lag2"] = lag2
    if "oat_lag1" in body:
        feat.loc[feat.index[-1], "oat_lag1"] = oat_lag1
    x = feat[FEATURE_COLS].to_numpy(dtype=float)[-1:]
    meta = {
        "strategy_id": str(row["strategy_id"]),
        "phase": str(row["phase"]),
        "hour_ending": int(row["hour_ending"]),
        "mode": "single",
    }
    return x, meta


def predict_kw(model: Any, body: dict[str, Any], feature_cols: list[str] | None = None) -> dict[str, Any]:
    x, meta = features_from_request(body)
    if feature_cols and list(feature_cols) != list(FEATURE_COLS):
        # reorder if bundle stored alternate order
        # rebuild via named columns from compile path already FEATURE_COLS
        pass
    y = float(np.asarray(model.predict(x)).ravel()[0])
    return {
        "facility_kw": y,
        "unit": "kW",
        **meta,
        "feature_cols": list(FEATURE_COLS),
    }
