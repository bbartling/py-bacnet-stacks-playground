"""Train hourly facility_kw demand surrogate (sklearn) with day-group holdout."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import GroupKFold

_ML = Path(__file__).resolve().parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from feature_compile_dm import FEATURE_COLS, compile_features, matrix_xy, peak_mask  # noqa: E402


def _workspace() -> Path:
    if Path("/data/runs").is_dir():
        return Path("/data")
    return Path.home() / "wattlab_workspace"


def load_farm_frame(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if path.suffix == ".jsonl":
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        # flatten nested if needed
        flat = []
        for r in rows:
            if "facility_kw" in r:
                flat.append(r)
            else:
                flat.append(
                    {
                        **{k: r.get(k) for k in (
                            "schema_version", "simulation_id", "twin_run_id", "day",
                            "hour_ending", "dow", "oat_c", "rh_pct", "ghi", "occupied",
                            "strategy_id", "phase", "in_dr_window",
                        )},
                        **(r.get("actions") or {}),
                        "facility_kw": (r.get("targets") or {}).get("facility_kw"),
                        "cooling_kw": (r.get("targets") or {}).get("cooling_kw"),
                        "provenance_source": (r.get("provenance") or {}).get("source"),
                    }
                )
        return pd.DataFrame(flat)
    raise ValueError(path)


def _metrics(y_true: np.ndarray, y_pred: np.ndarray, peak: np.ndarray | None = None) -> dict[str, float]:
    out = {
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mae": float(mean_absolute_error(y_true, y_pred)),
    }
    if peak is not None and peak.any():
        out["rmse_peak_14_16"] = float(np.sqrt(mean_squared_error(y_true[peak], y_pred[peak])))
        out["mae_peak_14_16"] = float(mean_absolute_error(y_true[peak], y_pred[peak]))
    else:
        out["rmse_peak_14_16"] = out["rmse"]
        out["mae_peak_14_16"] = out["mae"]
    return out


def train(df: pd.DataFrame, *, n_splits: int = 5) -> dict[str, Any]:
    X, y, groups, cols = matrix_xy(df)
    peak = peak_mask(df)
    uniq = np.unique(groups)
    n_splits = min(n_splits, max(2, len(uniq)))

    prototypes = {
        "ridge": Ridge(alpha=1.0),
        "hgb": HistGradientBoostingRegressor(
            max_depth=6, learning_rate=0.08, max_iter=200, random_state=21
        ),
    }
    cv_scores: dict[str, list[dict[str, float]]] = {k: [] for k in prototypes}
    pers_scores: list[dict[str, float]] = []

    gkf = GroupKFold(n_splits=n_splits)
    lag_i = cols.index("facility_kw_lag1")
    for tr, te in gkf.split(X, y, groups):
        y_te = y[te]
        p_te = peak[te]
        pers_scores.append(_metrics(y_te, X[te, lag_i], p_te))
        for name, proto in prototypes.items():
            m = proto.__class__(**proto.get_params())
            m.fit(X[tr], y[tr])
            cv_scores[name].append(_metrics(y_te, m.predict(X[te]), p_te))

    def _mean(scores: list[dict[str, float]]) -> dict[str, float]:
        keys = scores[0].keys()
        return {k: float(np.mean([s[k] for s in scores])) for k in keys}

    summary = {
        "persistence": _mean(pers_scores),
        "ridge": _mean(cv_scores["ridge"]),
        "hgb": _mean(cv_scores["hgb"]),
    }
    champ_name = "hgb"
    if summary["ridge"]["mae_peak_14_16"] <= summary["hgb"]["mae_peak_14_16"]:
        champ_name = "ridge"
    beat = summary[champ_name]["mae_peak_14_16"] < summary["persistence"]["mae_peak_14_16"]

    champ = prototypes[champ_name].__class__(**prototypes[champ_name].get_params())
    champ.fit(X, y)
    return {
        "model": champ,
        "champion": champ_name,
        "feature_cols": cols,
        "cv": summary,
        "beat_persistence_peak": beat,
        "n_rows": int(len(df)),
        "n_days": int(df["day"].nunique()),
        "n_splits": n_splits,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args(argv)

    ws = _workspace()
    pq = args.parquet or (ws / "reports" / "dm_hourly_farm" / "dm_hourly_rows.parquet")
    out_dir = args.out_dir or (ws / "models")
    out_dir.mkdir(parents=True, exist_ok=True)
    if not pq.is_file():
        print(f"missing {pq}", file=sys.stderr)
        return 2

    df = load_farm_frame(pq)
    result = train(df)
    artifact = out_dir / "demand_hourly_v1.joblib"
    joblib.dump(
        {
            "model": result["model"],
            "feature_cols": result["feature_cols"],
            "champion": result["champion"],
            "schema": "vibe21.dm_hourly_row.v1",
        },
        artifact,
    )
    sha = hashlib.sha256(artifact.read_bytes()).hexdigest()
    farm_summary = {}
    fs = pq.parent / "farm_summary.json"
    if fs.is_file():
        farm_summary = json.loads(fs.read_text(encoding="utf-8"))

    card = {
        "schema_version": "vibe21.model_registry.v1",
        "model_id": "demand_hourly_v1",
        "family": "OPERATIONAL_DEMAND",
        "artifact": str(artifact),
        "artifact_sha256": sha,
        "status": "CANDIDATE",
        "targets": ["facility_kw"],
        "champion": result["champion"],
        "cv_metrics": result["cv"],
        "beat_persistence_peak": result["beat_persistence_peak"],
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "training_parquet": str(pq),
        "training_source": farm_summary.get("source", "unknown"),
        "sklearn_version": __import__("sklearn").__version__,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "honesty": (
            "Screening surrogate for Unity DR knobs. "
            "SEEDED_SHAPE_PROXY is not EnergyPlus — re-farm with Docker before APPROVED. "
            "Not BAS-validated."
        ),
        "unity_contract": {
            "inputs": ["oat_c", "rh_pct", "hour_ending", "strategy_id", "action knobs"],
            "output": "facility_kw",
            "note": "Unity scrubbers call Flask later; joblib is offline artifact",
        },
    }
    (out_dir / "demand_hourly_v1_model_card.json").write_text(
        json.dumps(card, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "model_id": card["model_id"],
                "status": card["status"],
                "champion": card["champion"],
                "beat_persistence_peak": card["beat_persistence_peak"],
                "cv_metrics": card["cv_metrics"],
                "artifact": card["artifact"],
                "training_source": card["training_source"],
            },
            indent=2,
        )
    )
    return 0 if result["beat_persistence_peak"] else 0  # still ship CANDIDATE


if __name__ == "__main__":
    raise SystemExit(main())
