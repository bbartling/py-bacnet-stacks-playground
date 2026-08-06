"""Train PyTorch heating DSM models and export champion to ONNX.

Alternate stem ``heating_dsm_hourly_torch_v1`` — does **not** overwrite desktop
``heating_dsm_hourly_v1.onnx``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

_ML = Path(__file__).resolve().parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))

from artifact_paths import artifact_paths, train_parquet_path  # noqa: E402
from feature_compile_heating_dsm import FEATURE_COLS, matrix_xy, morning_peak_mask  # noqa: E402

# Indices for hour-aware split (must match FEATURE_COLS order)
_HOUR_ENDING_IDX = FEATURE_COLS.index("hour_ending")
_TIME_COLS = [
    "hour_ending",
    "sin_hour",
    "cos_hour",
    "month",
    "doy",
    "is_weekend",
    "occupied",
]
_TIME_IDX = [FEATURE_COLS.index(c) for c in _TIME_COLS]
_REST_IDX = [i for i in range(len(FEATURE_COLS)) if i not in _TIME_IDX]


# ---------------------------------------------------------------------------
# Architectures
# ---------------------------------------------------------------------------


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


class WideDeep(nn.Module):
    """Linear wide path + deep MLP; concat head (classic tabular)."""

    def __init__(self, n_in: int, deep_hidden: tuple[int, ...] = (128, 64)):
        super().__init__()
        self.wide = nn.Linear(n_in, 1)
        layers: list[nn.Module] = []
        prev = n_in
        for h in deep_hidden:
            layers += [nn.Linear(prev, h), nn.ReLU(), nn.Dropout(0.1)]
            prev = h
        self.deep = nn.Sequential(*layers)
        self.head = nn.Linear(prev + 1, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        w = self.wide(x)
        d = self.deep(x)
        return self.head(torch.cat([w, d], dim=-1)).squeeze(-1)


class GatedResBlock(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.fc = nn.Linear(dim, dim * 2)
        self.drop = nn.Dropout(0.1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h, g = self.fc(x).chunk(2, dim=-1)
        h = torch.nn.functional.gelu(h) * torch.sigmoid(g)
        return x + self.drop(h)


class GatedMLP(nn.Module):
    """GELU + gated residual blocks (TabNet-ish lite)."""

    def __init__(self, n_in: int, dim: int = 96, n_blocks: int = 4):
        super().__init__()
        self.in_proj = nn.Linear(n_in, dim)
        self.blocks = nn.Sequential(*[GatedResBlock(dim) for _ in range(n_blocks)])
        self.out = nn.Linear(dim, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = torch.nn.functional.gelu(self.in_proj(x))
        h = self.blocks(h)
        return self.out(h).squeeze(-1)


class HourAwareMLP(nn.Module):
    """Hour embedding + trunk on non-time features; time continuous features fused."""

    def __init__(self, n_in: int, emb_dim: int = 16, trunk_dim: int = 96):
        super().__init__()
        self.hour_emb = nn.Embedding(25, emb_dim)  # HE 0..24
        n_rest = len(_REST_IDX)
        n_time = len(_TIME_IDX)
        self.rest_proj = nn.Linear(n_rest, trunk_dim)
        self.time_proj = nn.Linear(n_time, 32)
        self.trunk = nn.Sequential(
            nn.Linear(trunk_dim + 32 + emb_dim, 128),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(128, 64),
            nn.GELU(),
            nn.Linear(64, 1),
        )
        self._n_in = n_in

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        he = x[:, _HOUR_ENDING_IDX].clamp(0, 24).round().long()
        emb = self.hour_emb(he)
        rest = x[:, _REST_IDX]
        time = x[:, _TIME_IDX]
        h = torch.cat(
            [
                torch.nn.functional.gelu(self.rest_proj(rest)),
                torch.nn.functional.gelu(self.time_proj(time)),
                emb,
            ],
            dim=-1,
        )
        return self.trunk(h).squeeze(-1)


class FTTransformerLite(nn.Module):
    """Small feature-token Transformer: each feature → token → few encoder layers → pool."""

    def __init__(
        self,
        n_in: int,
        d_token: int = 32,
        n_heads: int = 4,
        n_layers: int = 2,
        dropout: float = 0.1,
    ):
        super().__init__()
        self.n_in = n_in
        self.d_token = d_token
        # Per-feature linear: value → token (weight + bias as embedding of feature id)
        self.weight = nn.Parameter(torch.randn(n_in, d_token) * 0.02)
        self.bias = nn.Parameter(torch.zeros(n_in, d_token))
        self.cls = nn.Parameter(torch.zeros(1, 1, d_token))
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_token,
            nhead=n_heads,
            dim_feedforward=d_token * 2,
            dropout=dropout,
            batch_first=True,
            activation="gelu",
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.head = nn.Sequential(
            nn.LayerNorm(d_token),
            nn.Linear(d_token, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: B,F → tokens B,F,D
        tokens = x.unsqueeze(-1) * self.weight + self.bias
        cls = self.cls.expand(x.size(0), -1, -1)
        h = torch.cat([cls, tokens], dim=1)
        h = self.encoder(h)
        return self.head(h[:, 0, :]).squeeze(-1)


# ---------------------------------------------------------------------------
# Losses + train loop
# ---------------------------------------------------------------------------


def _peak_weighted_mse(
    pred: torch.Tensor,
    y: torch.Tensor,
    peak: torch.Tensor,
    peak_weight: float = 2.5,
) -> torch.Tensor:
    w = torch.ones_like(y)
    w = torch.where(peak > 0.5, w * peak_weight, w)
    return torch.mean(w * (pred - y) ** 2)


def _huber(pred: torch.Tensor, y: torch.Tensor, delta: float = 10.0) -> torch.Tensor:
    return torch.nn.functional.huber_loss(pred, y, delta=delta)


def _pinball(
    pred: torch.Tensor,
    y: torch.Tensor,
    q: float = 0.5,
    peak: torch.Tensor | None = None,
    peak_weight: float = 2.5,
) -> torch.Tensor:
    err = y - pred
    loss = torch.maximum(q * err, (q - 1.0) * err)
    if peak is not None:
        w = torch.where(peak > 0.5, peak_weight, 1.0)
        return torch.mean(w * loss)
    return torch.mean(loss)


LossFn = Callable[[torch.Tensor, torch.Tensor, torch.Tensor], torch.Tensor]


def _loss_for(name: str) -> LossFn:
    if name == "peak_mse":
        return lambda p, y, pk: _peak_weighted_mse(p, y, pk)
    if name == "huber":
        return lambda p, y, pk: _huber(p, y)
    if name == "pinball_q50":
        return lambda p, y, pk: _pinball(p, y, q=0.5, peak=pk)
    if name == "pinball_q90":
        return lambda p, y, pk: _pinball(p, y, q=0.9, peak=pk)
    raise ValueError(name)


def _train_one(
    model: nn.Module,
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    peak_tr: np.ndarray,
    X_va: np.ndarray,
    y_va: np.ndarray,
    peak_va: np.ndarray,
    *,
    epochs: int = 60,
    lr: float = 1e-3,
    batch_size: int = 512,
    device: str = "cpu",
    loss_name: str = "peak_mse",
    patience: int = 12,
) -> dict[str, float]:
    model = model.to(device)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(epochs, 1))
    loss_fn = _loss_for(loss_name)

    Xt = torch.tensor(X_tr, dtype=torch.float32, device=device)
    yt = torch.tensor(y_tr, dtype=torch.float32, device=device)
    pt = torch.tensor(peak_tr.astype(np.float32), dtype=torch.float32, device=device)
    Xv = torch.tensor(X_va, dtype=torch.float32, device=device)
    yv = torch.tensor(y_va, dtype=torch.float32, device=device)
    pv = peak_va

    n = len(Xt)
    best_state: dict[str, Any] | None = None
    best_peak_mae = float("inf")
    stale = 0

    for _ep in range(epochs):
        model.train()
        perm = torch.randperm(n, device=device)
        for i in range(0, n, batch_size):
            idx = perm[i : i + batch_size]
            opt.zero_grad()
            pred = model(Xt[idx])
            loss = loss_fn(pred, yt[idx], pt[idx])
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        sched.step()

        model.eval()
        with torch.no_grad():
            pred = model(Xv).cpu().numpy()
        if pv.any():
            peak_mae = float(np.mean(np.abs(pred[pv] - y_va[pv])))
        else:
            peak_mae = float(np.mean(np.abs(pred - y_va)))
        if peak_mae < best_peak_mae - 1e-4:
            best_peak_mae = peak_mae
            best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        pred = model(Xv).cpu().numpy()
    mae = float(np.mean(np.abs(pred - y_va)))
    rmse = float(np.sqrt(np.mean((pred - y_va) ** 2)))
    peak_mae = (
        float(np.mean(np.abs(pred[pv] - y_va[pv]))) if pv.any() else mae
    )
    return {"mae": mae, "rmse": rmse, "mae_peak_05_09": peak_mae}


def _family_factories(n_in: int) -> dict[str, Callable[[], nn.Module]]:
    """Keep only contenders that beat or approach sklearn on peak MAE.

    Dropped after bake-off: hour_cnn, wide_deep, hour_aware_mlp, ft_transformer_lite,
    quantile_pinball_* (all clearly worse than ResMLP / GB).
    """
    return {
        "resmlp": lambda: ResMLP(n_in),
        "gated_mlp": lambda: GatedMLP(n_in),
        "mlp": lambda: MLP(n_in),
    }


def bake_off_torch(
    df: pd.DataFrame,
    *,
    n_splits: int = 5,
    epochs: int = 50,
    device: str = "cpu",
    include_quantile: bool = True,
) -> dict[str, Any]:
    X, y, groups, cols = matrix_xy(df)
    peak = morning_peak_mask(df)
    uniq = np.unique(groups)
    n_splits = min(n_splits, max(2, len(uniq)))

    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)

    factories = _family_factories(len(cols))
    family_loss: dict[str, str] = {k: "peak_mse" for k in factories}
    family_epochs: dict[str, int] = {k: epochs for k in factories}

    # Quantile ablations removed — ResMLP + peak MSE won the bake-off.
    _ = include_quantile  # kept for CLI compat; ignored

    gkf = GroupKFold(n_splits=n_splits)
    oof: dict[str, list[float]] = {k: [] for k in factories}
    oof_full: dict[str, list[dict[str, float]]] = {k: [] for k in factories}

    for tr, te in gkf.split(Xs, y, groups):
        for name, factory in factories.items():
            model = factory()
            metrics = _train_one(
                model,
                Xs[tr],
                y[tr],
                peak[tr],
                Xs[te],
                y[te],
                peak[te],
                epochs=family_epochs[name],
                device=device,
                loss_name=family_loss[name],
            )
            oof[name].append(metrics["mae_peak_05_09"])
            oof_full[name].append(metrics)

    summary: dict[str, dict[str, float]] = {}
    for k in factories:
        summary[k] = {
            "mae_peak_05_09": float(np.mean(oof[k])),
            "mae": float(np.mean([m["mae"] for m in oof_full[k]])),
            "rmse": float(np.mean([m["rmse"] for m in oof_full[k]])),
        }

    # Persistence baseline
    lag_i = cols.index("facility_kw_lag1")
    pers: list[float] = []
    for tr, te in gkf.split(Xs, y, groups):
        pmask = peak[te]
        pred = X[te, lag_i]
        pers.append(
            float(np.mean(np.abs(pred[pmask] - y[te][pmask]))) if pmask.any() else float(np.mean(np.abs(pred - y[te])))
        )
    summary["persistence"] = {"mae_peak_05_09": float(np.mean(pers))}

    champ_name = min(
        (k for k in factories),
        key=lambda k: summary[k]["mae_peak_05_09"],
    )

    # Fit champion on all data with a small holdout for early stop
    n = len(y)
    n_va = max(64, n // 10)
    # stratified-ish: last chunk after scaler fit on all (acceptable for final fit)
    tr_idx = np.arange(0, n - n_va)
    va_idx = np.arange(n - n_va, n)
    champ = factories[champ_name]()
    _train_one(
        champ,
        Xs[tr_idx],
        y[tr_idx],
        peak[tr_idx],
        Xs[va_idx],
        y[va_idx],
        peak[va_idx],
        epochs=family_epochs[champ_name],
        device=device,
        loss_name=family_loss[champ_name],
        patience=15,
    )
    # Final short pass on all data without early stop (fine-tune)
    _train_one(
        champ,
        Xs,
        y,
        peak,
        Xs[va_idx],
        y[va_idx],
        peak[va_idx],
        epochs=max(10, family_epochs[champ_name] // 5),
        device=device,
        loss_name=family_loss[champ_name],
        patience=20,
        lr=3e-4,
    )
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
        "family_loss": family_loss,
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
    try:
        torch.onnx.export(model, dummy, str(path), dynamo=False, **kwargs)
    except TypeError:
        torch.onnx.export(model, dummy, str(path), **kwargs)


def load_gb_ship_peak_mae(art: Path | None = None) -> float | None:
    paths = artifact_paths(art)
    card = paths["card"]
    if not card.is_file():
        return None
    data = json.loads(card.read_text(encoding="utf-8"))
    champ = data.get("champion") or data.get("desktop_onnx_family")
    cv = data.get("cv_metrics") or {}
    if champ and champ in cv:
        return float(cv[champ].get("mae_peak_05_09", float("nan")))
    return None


def main(argv: list[str] | None = None) -> int:
    """Deprecated hourly torch ship — use real-baseline ResMLP trainer instead."""
    _ = argv
    print(
        "REFUSED: heating_dsm_hourly_torch_v1 path is quarantined.\n"
        "Use: python -u ml/train_real_baseline_torch_15min.py\n"
        "Hybrid ship: python -u scripts/promote_hybrid_ship.py\n"
        "See vibe22_agent_spec/HEATING_DSM.md",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
