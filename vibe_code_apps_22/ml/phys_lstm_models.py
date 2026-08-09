"""Physics-informed sequence models for 48-step / residual DSM screening."""
from __future__ import annotations

from typing import Any

import numpy as np

try:
    import torch
    import torch.nn as nn
except ImportError:  # pragma: no cover
    torch = None  # type: ignore
    nn = None  # type: ignore


def hdd65(oat_f: np.ndarray) -> np.ndarray:
    return np.maximum(0.0, 65.0 - oat_f)


if torch is not None:

    class PhysicsResidualLSTM(nn.Module):
        """Encode weather+HDD+RC proxy; predict residual facility_kw + 6 zones."""

        def __init__(self, n_in: int = 8, hidden: int = 32, n_out: int = 7):
            super().__init__()
            self.lstm = nn.LSTM(n_in, hidden, batch_first=True)
            self.head = nn.Linear(hidden, n_out)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            # x: (B, T, F)
            y, _ = self.lstm(x)
            return self.head(y)  # (B, T, 7)

    class MultiHorizonLSTM(nn.Module):
        """Predict next H steps of 7 targets from a context window."""

        def __init__(self, n_in: int = 8, hidden: int = 32, horizon: int = 48, n_out: int = 7):
            super().__init__()
            self.horizon = horizon
            self.n_out = n_out
            self.encoder = nn.LSTM(n_in, hidden, batch_first=True)
            self.head = nn.Linear(hidden, horizon * n_out)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            _, (h, _) = self.encoder(x)
            flat = self.head(h[-1])
            return flat.view(-1, self.horizon, self.n_out)


def smoke_train_phys_lstm(
    *,
    kind: str = "residual",
    steps: int = 32,
    epochs: int = 3,
    seed: int = 0,
) -> dict[str, Any]:
    """Tiny offline train for arch_search CI/smoke — not a ship model."""
    if torch is None:
        return {"ok": False, "reason": "torch_missing", "score": 1e9, "pass": False}
    rng = np.random.default_rng(seed)
    torch.manual_seed(seed)
    T = steps
    oat = 20.0 + 10.0 * np.sin(np.linspace(0, 2 * np.pi, T))
    hdd = hdd65(oat)
    # RC-ish zone proxy
    zone = 68.0 - 0.05 * hdd
    kw = 80.0 + 1.5 * hdd + rng.normal(0, 2, size=T)
    feats = np.column_stack(
        [
            oat,
            hdd,
            zone,
            np.roll(kw, 1),
            np.sin(np.arange(T) / T * 2 * np.pi),
            np.cos(np.arange(T) / T * 2 * np.pi),
            np.ones(T),
            np.zeros(T),
        ]
    ).astype(np.float32)
    feats[0, 3] = kw[0]
    y = np.column_stack([kw, np.tile(zone.reshape(-1, 1), (1, 6))]).astype(np.float32)
    # residual target vs HDD linear
    y_res = y.copy()
    y_res[:, 0] = y[:, 0] - (80.0 + 1.5 * hdd)

    x_t = torch.tensor(feats[None, ...])
    if kind == "multi_horizon":
        model = MultiHorizonLSTM(n_in=8, hidden=24, horizon=min(16, T // 2))
        # train to predict last H from first half context
        H = model.horizon
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        ctx = x_t[:, : T - H, :]
        tgt = torch.tensor(y[None, T - H : T, :])
        loss_v = 0.0
        for _ in range(epochs):
            opt.zero_grad()
            pred = model(ctx)
            loss = nn.functional.smooth_l1_loss(pred, tgt)
            loss.backward()
            opt.step()
            loss_v = float(loss.detach())
        pred_kw = pred.detach().numpy()[0, :, 0]
        peak = float(np.max(np.abs(pred_kw)))
    else:
        model = PhysicsResidualLSTM(n_in=8, hidden=24)
        opt = torch.optim.Adam(model.parameters(), lr=1e-2)
        tgt = torch.tensor(y_res[None, ...])
        loss_v = 0.0
        for _ in range(epochs):
            opt.zero_grad()
            pred = model(x_t)
            loss = nn.functional.smooth_l1_loss(pred, tgt)
            loss.backward()
            opt.step()
            loss_v = float(loss.detach())
        recon = pred.detach().numpy()[0, :, 0] + (80.0 + 1.5 * hdd)
        peak = float(np.max(recon))

    sane = 0.0 <= peak <= 450.0
    score = loss_v + (0.0 if sane else 1e3)
    return {
        "ok": True,
        "kind": kind,
        "loss": loss_v,
        "recon_peak_kw": peak,
        # Smoke gate: plant-cap sanity; loss is ranking only (tiny untrained nets).
        "pass": sane,
        "score": score,
    }
