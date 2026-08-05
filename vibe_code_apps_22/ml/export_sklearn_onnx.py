"""Export sklearn heating DSM regressor to ONNX for the Rust desktop.

Contract (matches ``desktop/src/model.rs``):
  - input  ``features``  float32 [batch, n_features]
  - output ``facility_kw`` float32 [batch] (or [batch, 1] — Rust reads data[0])

Models are trained on **raw** FEATURE_COLS. Meta writes identity scaler so Rust
``scale_features`` is a no-op (avoids double-scaling vs torch path).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

from feature_compile_heating_dsm import FEATURE_COLS


def _rename_output(model_onnx: Any, new_name: str = "facility_kw") -> None:
    """skl2onnx often emits ``variable`` / ``variable1`` — Rust expects ``facility_kw``."""
    if not model_onnx.graph.output:
        raise ValueError("ONNX graph has no outputs")
    old = model_onnx.graph.output[0].name
    if old == new_name:
        return
    for node in model_onnx.graph.node:
        for i, o in enumerate(list(node.output)):
            if o == old:
                node.output[i] = new_name
    model_onnx.graph.output[0].name = new_name


def export_sklearn_onnx(
    model: Any,
    *,
    n_features: int,
    onnx_path: Path,
    meta_path: Path,
    feature_cols: list[str] | None = None,
    champion: str = "extra_trees",
    model_display_name: str | None = None,
    best_params: dict[str, Any] | None = None,
    training_source: str = "ENERGYPLUS_SIMULATED",
    honesty: str | None = None,
    cv_metrics: dict[str, float] | None = None,
    cv_peak_mae: float | None = None,
) -> dict[str, Any]:
    """Convert regressor → ONNX + feature meta (identity scaler)."""
    cols = list(feature_cols or FEATURE_COLS)
    if len(cols) != n_features:
        raise ValueError(f"feature_cols length {len(cols)} != n_features {n_features}")

    initial_types = [("features", FloatTensorType([None, n_features]))]
    # ExtraTrees / RF: disable zipmap; keep float tensor out
    options: dict[Any, dict[str, Any]] = {type(model): {"zipmap": False}}
    try:
        onnx_model = convert_sklearn(
            model,
            initial_types=initial_types,
            target_opset=17,
            options=options,
        )
    except Exception:
        onnx_model = convert_sklearn(
            model,
            initial_types=initial_types,
            target_opset=17,
        )
    _rename_output(onnx_model, "facility_kw")

    onnx_path = Path(onnx_path)
    meta_path = Path(meta_path)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    with open(onnx_path, "wb") as f:
        f.write(onnx_model.SerializeToString())

    cv = dict(cv_metrics or {})
    if cv_peak_mae is not None and "mae_peak_05_09" not in cv:
        cv["mae_peak_05_09"] = float(cv_peak_mae)
    mae = float(cv.get("mae", cv.get("mae_peak_05_09", 0.0) or 0.0))
    rmse = float(cv.get("rmse", 0.0) or 0.0)
    mae_peak = float(cv.get("mae_peak_05_09", mae) or mae)
    rmse_peak = float(cv.get("rmse_peak_05_09", rmse) or rmse)
    # Desktop ± band uses peak-window MAE (morning HE 05–09) as screening uncertainty
    precision_pm_kw = mae_peak

    display = model_display_name or {
        "extra_trees": "ExtraTreesRegressor",
        "rf": "RandomForestRegressor",
        "gradient_boosting": "GradientBoostingRegressor",
        "hgb": "HistGradientBoostingRegressor",
    }.get(champion, champion)

    honesty = honesty or (
        f"sklearn {display} via ONNX (skl2onnx). "
        f"Source={training_source}. IdealLoads+COP farm when ENERGYPLUS_SIMULATED. "
        "CANDIDATE — not tariff-grade. Desktop kW-only."
    )
    meta = {
        "schema": "lakeside.heating_dsm_hourly.v1",
        "feature_cols": cols,
        "n_features": n_features,
        "scaler_mean": [0.0] * n_features,
        "scaler_scale": [1.0] * n_features,
        "scaler_note": "identity — sklearn model trained on raw features",
        "model_name": display,
        "champion": champion,
        "family": "sklearn",
        "model_backend": "skl2onnx",
        "best_params": best_params or {},
        "cv_metrics": {
            "mae": mae,
            "rmse": rmse,
            "mae_peak_05_09": mae_peak,
            "rmse_peak_05_09": rmse_peak,
        },
        "precision_pm_kw": precision_pm_kw,
        "precision_note": (
            "± band = GroupKFold peak MAE (HE 05–09) — screening uncertainty, "
            "not a formal prediction interval"
        ),
        "training_source": training_source,
        "honesty": honesty,
        "cv_mae_peak_05_09": mae_peak,
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input_name": "features",
        "output_name": "facility_kw",
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return meta


def roundtrip_check(
    model: Any,
    onnx_path: Path,
    X: np.ndarray,
    *,
    n: int = 32,
) -> float:
    """Max |sklearn − ONNX| on first n rows (raw features)."""
    import onnxruntime as ort

    Xs = np.asarray(X[:n], dtype=np.float32)
    sk = np.asarray(model.predict(Xs), dtype=np.float64).reshape(-1)
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    out = sess.run(None, {"features": Xs})[0]
    on = np.asarray(out, dtype=np.float64).reshape(-1)
    return float(np.max(np.abs(sk - on)))


def copy_ship_to_desktop(onnx_path: Path, meta_path: Path, desktop_dir: Path | None = None) -> Path:
    """Copy ship artifacts next to the Rust crate for release-adjacent runs."""
    if desktop_dir is None:
        desktop_dir = Path(__file__).resolve().parents[1] / "desktop" / "artifacts"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(onnx_path, desktop_dir / onnx_path.name)
    shutil.copy2(meta_path, desktop_dir / meta_path.name)
    return desktop_dir


__all__ = [
    "copy_ship_to_desktop",
    "export_sklearn_onnx",
    "roundtrip_check",
]
