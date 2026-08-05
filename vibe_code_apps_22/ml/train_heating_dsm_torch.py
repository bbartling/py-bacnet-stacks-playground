"""Train PyTorch heating DSM models and export champion to ONNX."""

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
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from artifact_paths import artifact_paths, bootstrap_parquet_path  # noqa: E402
from feature_compile_heating_dsm import FEATURE_COLS, matrix_xy, morning_peak_mask  # noqa: E402


class MLP(nn.Module):
    def __init__(self, n_in: int, hidden: tuple[int, ...] = (128, 64, 32)):
        super().__init__()
        layers: list[nn.Module] = []
        prev = n_in
        for h in hidden:
            layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(0.1)]
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x).squeeze(-1)


class ResBlock(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.fc1 = nn.Linear(dim, dim)
        self.fc2 = nn.Linear(dim, dim)
        self.act = nn.ReLU()
        self.drop = nn.Dropout(0.1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.drop(self.act(self.fc1(x)))
        h = self.fc2(h)
        return self.act(x + h)


class ResMLP(nn.Module):
    def __init__(self, n_in: int, dim: int = 96, n_blocks: int = 3):
        super().__init__()
        self.in_proj = nn.Linear(n_in, dim)
        self.blocks = nn.Sequential(*[ResBlock(dim) for _ in range(n_blocks)])
        self.out = nn.Linear(dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = torch.relu(self.in_proj(x))
        h = self.blocks(h)
        return self.out(h).squeeze(-1)


class HourCNN(nn.Module):
    """Treat feature vector as 1-channel 'sequence' of length n_features."""

    def __init__(self, n_in: int):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv1d(1, 32, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.Conv1d(32, 64, kernel_size=5, padding=2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(8),
        )
        self.head = nn.Sequential(
            nn.Flatten(),
            nn.Linear(64 * 8, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
        )
        self.n_in = n_in

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        z = x.unsqueeze(1)  # B,1,F
        return self.head(self.conv(z)).squeeze(-1)


def _peak_weighted_mse(
    pred: torch.Tensor,
    y: torch.Tensor,
    peak: torch.Tensor,
    peak_weight: float = 2.5,
) -> torch.Tensor:
    w = torch.ones_like(y)
    w = torch.where(peak > 0.5, w * peak_weight, w)
    return torch.mean(w * (pred - y) ** 2)


def _train_one(
    model: nn.Module,
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    peak_tr: np.ndarray,
    X_va: np.ndarray,
    y_va: np.ndarray,
    *,
    epochs: int = 40,
    lr: float = 1e-3,
    batch_size: int = 512,
    device: str = "cpu",
) -> dict[str, float]:
    model = model.to(device)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    Xt = torch.tensor(X_tr, dtype=torch.float32, device=device)
    yt = torch.tensor(y_tr, dtype=torch.float32, device=device)
    pt = torch.tensor(peak_tr.astype(np.float32), dtype=torch.float32, device=device)
    Xv = torch.tensor(X_va, dtype=torch.float32, device=device)
    yv = torch.tensor(y_va, dtype=torch.float32, device=device)

    n = len(Xt)
    model.train()
    for _ in range(epochs):
        perm = torch.randperm(n, device=device)
        for i in range(0, n, batch_size):
            idx = perm[i : i + batch_size]
            opt.zero_grad()
            pred = model(Xt[idx])
            loss = _peak_weighted_mse(pred, yt[idx], pt[idx])
            loss.backward()
            opt.step()

    model.eval()
    with torch.no_grad():
        pred = model(Xv).cpu().numpy()
    mae = float(np.mean(np.abs(pred - y_va)))
    rmse = float(np.sqrt(np.mean((pred - y_va) ** 2)))
    return {"mae": mae, "rmse": rmse}


def bake_off_torch(
    df: pd.DataFrame,
    *,
    n_splits: int = 3,
    epochs: int = 35,
    device: str = "cpu",
) -> dict[str, Any]:
    X, y, groups, cols = matrix_xy(df)
    peak = morning_peak_mask(df)
    uniq = np.unique(groups)
    n_splits = min(n_splits, max(2, len(uniq)))

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    families = {
        "mlp": lambda: MLP(len(cols)),
        "resmlp": lambda: ResMLP(len(cols)),
        "hour_cnn": lambda: HourCNN(len(cols)),
    }

    gkf = GroupKFold(n_splits=n_splits)
    oof: dict[str, list[float]] = {k: [] for k in families}
    for tr, te in gkf.split(Xs, y, groups):
        for name, factory in families.items():
            model = factory()
            metrics = _train_one(
                model,
                Xs[tr],
                y[tr],
                peak[tr],
                Xs[te],
                y[te],
                epochs=epochs,
                device=device,
            )
            # morning peak MAE on fold
            model.eval()
            with torch.no_grad():
                pred = model(torch.tensor(Xs[te], dtype=torch.float32, device=device)).cpu().numpy()
            pmask = peak[te]
            peak_mae = float(np.mean(np.abs(pred[pmask] - y[te][pmask]))) if pmask.any() else metrics["mae"]
            oof[name].append(peak_mae)

    summary = {k: {"mae_peak_05_09": float(np.mean(v))} for k, v in oof.items()}
    champ_name = min(summary.keys(), key=lambda k: summary[k]["mae_peak_05_09"])

    # Fit champion on all data
    champ = families[champ_name]()
    _train_one(champ, Xs, y, peak, Xs[:512], y[:512], epochs=epochs, device=device)
    champ.eval()

    return {
        "model": champ,
        "scaler": scaler,
        "champion": champ_name,
        "feature_cols": cols,
        "cv": summary,
        "n_rows": int(len(df)),
        "n_days": int(df["day"].nunique()),
        "n_in": len(cols),
    }


def export_onnx(model: nn.Module, n_in: int, path: Path, device: str = "cpu") -> None:
    model = model.to(device).eval()
    dummy = torch.zeros(1, n_in, dtype=torch.float32, device=device)
    path.parent.mkdir(parents=True, exist_ok=True)
    kwargs = dict(
        input_names=["features"],
        output_names=["facility_kw"],
        dynamic_axes={"features": {0: "batch"}, "facility_kw": {0: "batch"}},
        opset_version=17,
    )
    # Prefer legacy exporter when available (avoids onnxscript on some torch builds).
    try:
        torch.onnx.export(model, dummy, str(path), dynamo=False, **kwargs)
    except TypeError:
        torch.onnx.export(model, dummy, str(path), **kwargs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=35)
    ap.add_argument("--n-splits", type=int, default=3)
    ap.add_argument("--device", type=str, default="cpu")
    args = ap.parse_args(argv)

    pq = args.parquet or bootstrap_parquet_path()
    paths = artifact_paths(args.out_dir)
    if not pq.is_file():
        print(f"missing {pq}", file=sys.stderr)
        return 2

    df = pd.read_parquet(pq)
    # Subsample days for faster default train if huge — use full set
    result = bake_off_torch(df, n_splits=args.n_splits, epochs=args.epochs, device=args.device)

    onnx_path = paths["onnx"]
    export_onnx(result["model"], result["n_in"], onnx_path, device=args.device)

    meta = {
        "feature_cols": result["feature_cols"],
        "scaler_mean": result["scaler"].mean_.tolist(),
        "scaler_scale": result["scaler"].scale_.tolist(),
        "champion": result["champion"],
        "cv": result["cv"],
        "schema": "lakeside.heating_dsm_hourly.v1",
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "honesty": "PyTorch CANDIDATE on BAS_BOOTSTRAP_PROXY; ONNX for later sim scrubbing.",
    }
    paths["feature_meta"].write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    # Round-trip check
    import onnxruntime as ort

    X, y, _, _ = matrix_xy(df)
    Xs = result["scaler"].transform(X[:8])
    with torch.no_grad():
        torch_pred = result["model"](torch.tensor(Xs, dtype=torch.float32)).numpy()
    sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
    onnx_pred = sess.run(None, {"features": Xs.astype(np.float32)})[0].reshape(-1)
    max_abs = float(np.max(np.abs(torch_pred - onnx_pred)))

    print(
        json.dumps(
            {
                "champion": result["champion"],
                "cv": result["cv"],
                "onnx": str(onnx_path),
                "feature_meta": str(paths["feature_meta"]),
                "onnx_roundtrip_max_abs": max_abs,
            },
            indent=2,
        )
    )
    return 0 if max_abs < 1e-4 else 1


if __name__ == "__main__":
    raise SystemExit(main())
