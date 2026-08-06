#!/usr/bin/env python
"""Train multi-head ResMLP on real 15-min baseline (component A). Alternate stem."""
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
    FEATURE_COLS_15MIN_MT,
    matrix_xy_15min_multi,
    morning_peak_mask_15min,
    recursive_rollout_day,
)
from feature_compile_heating_dsm import TARGET_COLS  # noqa: E402
from lakeside.paths import site_root  # noqa: E402

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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--n-splits", type=int, default=3)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--max-days", type=int, default=None)
    ap.add_argument("--winter-only", action="store_true")
    args = ap.parse_args(argv)

    site = site_root()
    pq = args.parquet or (site / "ml" / "artifacts" / "real_baseline_15min_v1.parquet")
    df = pd.read_parquet(pq)
    if args.winter_only:
        df = df[df["month"].isin([11, 12, 1, 2, 3])].copy()
    if args.max_days:
        days = sorted(df["day"].unique())[: args.max_days]
        df = df[df["day"].isin(days)].copy()

    X, Y, groups, cols, tcols, feat = matrix_xy_15min_multi(df)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    Y = np.nan_to_num(Y, nan=0.0, posinf=0.0, neginf=0.0)
    peak = morning_peak_mask_15min(feat)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    gkf = GroupKFold(n_splits=min(args.n_splits, max(2, len(np.unique(groups)))))

    tf_scores, rec_scores = [], []
    last_model, last_scaler = None, None
    for fold, (tr, te) in enumerate(gkf.split(X, Y, groups)):
        print(f"fold {fold+1}", flush=True)
        model, scaler, _ = _train_one(X[tr], Y[tr], X[te], Y[te], epochs=args.epochs, device=device)
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
        for day, sub in feat.iloc[te].groupby("day"):
            if len(sub) < 80:
                continue
            sub = sub.sort_values("step_15")
            yp = recursive_rollout_day(wrap, sub, cols, tcols)
            yt = sub[TARGET_COLS].to_numpy(dtype=float)
            rec_maes.append(float(np.mean(np.abs(yp[:, 0] - yt[:, 0]))))
        rec_scores.append({"facility_kw_mae": float(np.mean(rec_maes)) if rec_maes else float("nan")})
        last_model, last_scaler = model, scaler
        print(f"  TF peak MAE={tf_scores[-1]['facility_kw_mae_peak_05_09']:.3f}", flush=True)

    # refit on all
    model, scaler, _ = _train_one(X, Y, X, Y, epochs=args.epochs, device=device)

    out_dir = args.out_dir or (_ML / "artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    pt_path = out_dir / f"{STEM}.pt"
    torch.save({"state_dict": model.state_dict(), "scaler_mean": scaler.mean_, "scaler_scale": scaler.scale_, "n_in": X.shape[1], "n_out": Y.shape[1]}, pt_path)

    # ONNX
    onnx_path = out_dir / f"{STEM}.onnx"
    model.cpu().eval()
    dummy = torch.zeros(1, X.shape[1], dtype=torch.float32)
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

    def _mean(scores: list[dict]) -> dict:
        keys = scores[0].keys()
        return {k: float(np.nanmean([s[k] for s in scores])) for k in keys}

    card = {
        "stem": STEM,
        "honesty": HONESTY,
        "family": "resmlp_multihead",
        "cv_teacher_forced": _mean(tf_scores),
        "cv_recursive_96": _mean(rec_scores),
        "n_rows": int(len(feat)),
        "n_days": int(feat["day"].nunique()),
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "feature_cols": cols,
        "target_cols": tcols,
    }
    (out_dir / f"{STEM}_model_card.json").write_text(json.dumps(card, indent=2), encoding="utf-8")
    meta = {
        "stem": STEM,
        "feature_cols": cols,
        "target_cols": tcols,
        "n_features": len(cols),
        "n_outputs": len(tcols),
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_scale": scaler.scale_.tolist(),
        "honesty": HONESTY,
    }
    (out_dir / f"{STEM}_feature_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(json.dumps(card["cv_teacher_forced"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
