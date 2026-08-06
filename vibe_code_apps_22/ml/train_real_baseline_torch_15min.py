#!/usr/bin/env python
"""Train multi-head ResMLP on real 15-min baseline (component A). Alternate stem.

CLI refuses unless VIBE22_ALLOW_CLI_TRAIN=1 — use the torch notebook instead.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

_ML = Path(__file__).resolve().parent
_APP = _ML.parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from feature_compile_15min import (  # noqa: E402
    matrix_xy_15min_multi,
    morning_peak_mask_15min,
    recursive_rollout_day,
)
from feature_compile_heating_dsm import TARGET_COLS  # noqa: E402
from train_real_baseline_15min import load_real_baseline_frame  # noqa: E402

STEM = "real_baseline_15min_torch_v1"
HONESTY = "HYBRID_SCREENING"


class ResBlock(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.fc1 = nn.Linear(dim, dim)
        self.fc2 = nn.Linear(dim, dim)
        self.act = nn.ReLU()
        self.drop = nn.Dropout(0.1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.drop(self.act(self.fc1(x)))
        return self.act(x + self.fc2(h))


class ResMLPMulti(nn.Module):
    def __init__(self, n_in: int, n_out: int = 7, dim: int = 96, n_blocks: int = 3):
        super().__init__()
        self.in_proj = nn.Linear(n_in, dim)
        self.blocks = nn.Sequential(*[ResBlock(dim) for _ in range(n_blocks)])
        self.out = nn.Linear(dim, n_out)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = torch.relu(self.in_proj(x))
        return self.out(self.blocks(h))


class TorchMultiWrapper:
    """sklearn-like predict for recursive rollout."""

    def __init__(self, model: ResMLPMulti, scaler: StandardScaler, device: str = "cpu"):
        self.model = model
        self.scaler = scaler
        self.device = device
        self.model.eval()

    def predict(self, X: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            xs = np.nan_to_num(np.asarray(X, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
            xs = self.scaler.transform(xs)
            t = torch.tensor(xs, dtype=torch.float32, device=self.device)
            return self.model(t).cpu().numpy()


def _train_one(
    Xtr: np.ndarray,
    Ytr: np.ndarray,
    Xva: np.ndarray,
    Yva: np.ndarray,
    *,
    epochs: int,
    device: str,
) -> tuple[ResMLPMulti, StandardScaler, float]:
    scaler = StandardScaler()
    Xtr_s = scaler.fit_transform(Xtr)
    Xva_s = scaler.transform(Xva)
    model = ResMLPMulti(Xtr.shape[1], Ytr.shape[1]).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    loss_fn = nn.MSELoss()
    best = float("inf")
    best_state = None
    patience, bad = 12, 0
    for _ in range(epochs):
        model.train()
        idx = np.random.permutation(len(Xtr_s))
        for start in range(0, len(idx), 256):
            b = idx[start : start + 256]
            xb = torch.tensor(Xtr_s[b], dtype=torch.float32, device=device)
            yb = torch.tensor(Ytr[b], dtype=torch.float32, device=device)
            opt.zero_grad()
            loss = loss_fn(model(xb), yb)
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            pred = model(torch.tensor(Xva_s, dtype=torch.float32, device=device)).cpu().numpy()
            mae = float(np.mean(np.abs(pred[:, 0] - Yva[:, 0])))
        if mae < best:
            best, best_state, bad = mae, {k: v.cpu().clone() for k, v in model.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state:
        model.load_state_dict(best_state)
    return model, scaler, best


def train_torch_baseline(
    df: pd.DataFrame,
    *,
    n_splits: int = 3,
    epochs: int = 40,
    device: str | None = None,
) -> dict[str, Any]:
    """GroupKFold ResMLP train; returns model/scaler/cv for export."""
    X, Y, groups, cols, tcols, feat = matrix_xy_15min_multi(df)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    Y = np.nan_to_num(Y, nan=0.0, posinf=0.0, neginf=0.0)
    peak = morning_peak_mask_15min(feat)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    gkf = GroupKFold(n_splits=min(n_splits, max(2, len(np.unique(groups)))))

    tf_scores: list[dict] = []
    rec_scores: list[dict] = []
    for fold, (tr, te) in enumerate(gkf.split(X, Y, groups)):
        print(f"fold {fold + 1}/{gkf.get_n_splits()}", flush=True)
        model, scaler, _ = _train_one(X[tr], Y[tr], X[te], Y[te], epochs=epochs, device=device)
        wrap = TorchMultiWrapper(model, scaler, device)
        pred = wrap.predict(X[te])
        tf_scores.append(
            {
                "facility_kw_mae": float(np.mean(np.abs(pred[:, 0] - Y[te, 0]))),
                "facility_kw_mae_peak_05_09": float(
                    np.mean(np.abs(pred[peak[te], 0] - Y[te, 0][peak[te]]))
                )
                if peak[te].any()
                else float(np.mean(np.abs(pred[:, 0] - Y[te, 0]))),
                "zone_temp_mae_mean": float(np.mean(np.abs(pred[:, 1:] - Y[te, 1:]))),
            }
        )
        rec_maes = []
        for _day, sub in feat.iloc[te].groupby("day"):
            if len(sub) < 80:
                continue
            sub = sub.sort_values("step_15")
            yp = recursive_rollout_day(wrap, sub, cols, tcols)
            yt = sub[TARGET_COLS].to_numpy(dtype=float)
            rec_maes.append(float(np.mean(np.abs(yp[:, 0] - yt[:, 0]))))
        rec_scores.append({"facility_kw_mae": float(np.mean(rec_maes)) if rec_maes else float("nan")})
        print(f"  TF peak MAE={tf_scores[-1]['facility_kw_mae_peak_05_09']:.3f}", flush=True)

    model, scaler, _ = _train_one(X, Y, X, Y, epochs=epochs, device=device)

    def _mean(scores: list[dict]) -> dict:
        keys = scores[0].keys()
        return {k: float(np.nanmean([s[k] for s in scores])) for k in keys}

    return {
        "model": model,
        "scaler": scaler,
        "feature_cols": cols,
        "target_cols": tcols,
        "cv_teacher_forced": _mean(tf_scores),
        "cv_recursive_96": _mean(rec_scores),
        "n_rows": int(len(feat)),
        "n_days": int(feat["day"].nunique()),
        "X_shape": X.shape,
        "Y_shape": Y.shape,
        "device": device,
    }


def export_torch_baseline_artifacts(result: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    model: ResMLPMulti = result["model"]
    scaler: StandardScaler = result["scaler"]
    cols = result["feature_cols"]
    tcols = result["target_cols"]
    n_in = result["X_shape"][1]
    n_out = result["Y_shape"][1]

    pt_path = out_dir / f"{STEM}.pt"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "scaler_mean": scaler.mean_,
            "scaler_scale": scaler.scale_,
            "n_in": n_in,
            "n_out": n_out,
        },
        pt_path,
    )

    onnx_path = out_dir / f"{STEM}.onnx"
    model.cpu().eval()
    dummy = torch.zeros(1, n_in, dtype=torch.float32)
    try:
        torch.onnx.export(
            model,
            dummy,
            str(onnx_path),
            input_names=["features"],
            output_names=["outputs"],
            dynamic_axes={"features": {0: "batch"}, "outputs": {0: "batch"}},
            opset_version=17,
        )
    except Exception as e:
        print(f"ONNX export failed: {e}", flush=True)

    card = {
        "stem": STEM,
        "honesty": HONESTY,
        "family": "resmlp_multihead",
        "cv_teacher_forced": result["cv_teacher_forced"],
        "cv_recursive_96": result["cv_recursive_96"],
        "n_rows": result["n_rows"],
        "n_days": result["n_days"],
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "feature_cols": cols,
        "target_cols": tcols,
        "trained_via": "notebook",
    }
    card_path = out_dir / f"{STEM}_model_card.json"
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    meta = {
        "stem": STEM,
        "feature_cols": cols,
        "target_cols": tcols,
        "n_features": len(cols),
        "n_outputs": len(tcols),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "honesty": HONESTY,
        "trained_via": "notebook",
    }
    meta_path = out_dir / f"{STEM}_feature_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {"pt": pt_path, "onnx": onnx_path, "meta": meta_path, "card": card_path}


def main(argv: list[str] | None = None) -> int:
    from notebook_gate import TORCH_NOTEBOOK, cli_train_allowed, refuse_cli_train

    if not cli_train_allowed():
        return refuse_cli_train("ResMLP real baseline (torch alt)", notebook=TORCH_NOTEBOOK)

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--n-splits", type=int, default=3)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--max-days", type=int, default=None)
    ap.add_argument("--winter-only", action="store_true")
    args = ap.parse_args(argv)

    df = load_real_baseline_frame(
        parquet=args.parquet,
        winter_only=args.winter_only,
        max_days=args.max_days,
    )
    result = train_torch_baseline(df, n_splits=args.n_splits, epochs=args.epochs)
    paths = export_torch_baseline_artifacts(result, args.out_dir or (_ML / "artifacts"))
    print(json.dumps({"card": str(paths["card"]), "cv": result["cv_teacher_forced"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
