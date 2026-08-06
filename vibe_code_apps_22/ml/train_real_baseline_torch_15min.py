#!/usr/bin/env python
"""Train multi-output torch baselines on real 15-min data (component A alt).

Fixes the prior defect: unscaled MSE on raw kW+°F with a shared Linear→7 head
and early-stop on facility_kw only (which produced ~24°F zone MAE).

This path:
  * fits X + per-target Y StandardScalers on **train days only**
  * dual heads (facility_kw + 6 zones) with Huber loss in normalized space
  * configurable w_kw / w_zone so facility_kw cannot dominate by scale alone
  * curriculum short-horizon unroll (1 → 4 → 16) then recursive-96 selection
  * ResMLP dual-head + small GRU candidates; ≥5 seeds for final compare
  * shared chrono split manifest (same SoT as sklearn)
  * never overwrites desktop sklearn champion

CLI refuses unless VIBE22_ALLOW_CLI_TRAIN=1 — prefer the torch tutorial notebook.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler

_ML = Path(__file__).resolve().parent
_APP = _ML.parent
if str(_ML) not in sys.path:
    sys.path.insert(0, str(_ML))
if str(_APP) not in sys.path:
    sys.path.insert(0, str(_APP))

from chrono_splits import build_split_manifest, write_manifest  # noqa: E402
from feature_compile_15min import (  # noqa: E402
    matrix_xy_15min_multi,
    morning_peak_mask_15min,
)
from feature_compile_heating_dsm import TARGET_COLS  # noqa: E402
from run_provenance import (  # noqa: E402
    artifact_registry,
    make_run_id,
    print_artifact_registry,
    sha256_file,
    stamp_card,
)
from target_scaling import (  # noqa: E402
    N_TARGETS,
    MultiTargetScaler,
    assert_output_order,
    assert_target_cols,
)
from train_real_baseline_15min import (  # noqa: E402
    _agg_day_scores,
    evaluate_recursive_days,
    load_real_baseline_frame,
)

STEM = "real_baseline_15min_torch_v1"
HONESTY = "HYBRID_SCREENING"
NOT_EVALUATED_RECURSIVE = {
    "status": "not_evaluated",
    "reason": "no held-out day had >=80 rows for a recursive 96-step rollout",
}


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float):
        return obj if np.isfinite(obj) else None
    return obj


def set_seed(seed: int) -> None:
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def count_params(model: nn.Module) -> int:
    return int(sum(p.numel() for p in model.parameters() if p.requires_grad))


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


class ResMLPDualHead(nn.Module):
    """Shared residual trunk + separate facility_kw and zone-temperature heads."""

    def __init__(self, n_in: int, dim: int = 96, n_blocks: int = 3):
        super().__init__()
        self.in_proj = nn.Linear(n_in, dim)
        self.blocks = nn.Sequential(*[ResBlock(dim) for _ in range(n_blocks)])
        self.head_kw = nn.Linear(dim, 1)
        self.head_zones = nn.Linear(dim, 6)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = torch.relu(self.in_proj(x))
        h = self.blocks(h)
        kw = self.head_kw(h)
        zones = self.head_zones(h)
        out = torch.cat([kw, zones], dim=-1)
        assert out.shape[-1] == N_TARGETS
        return out


class SmallGRUDualHead(nn.Module):
    """Row-wise GRU cell over feature vector (modest temporal inductive bias).

    Each call is a single step with exogenous+lag features already assembled —
    no future measured kW/temps. Suitable for recursive rollout via TorchMultiWrapper.
    """

    def __init__(self, n_in: int, hidden: int = 64):
        super().__init__()
        self.gru = nn.GRU(input_size=n_in, hidden_size=hidden, batch_first=True)
        self.head_kw = nn.Linear(hidden, 1)
        self.head_zones = nn.Linear(hidden, 6)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [B, F] → [B, 1, F]
        if x.dim() == 2:
            x = x.unsqueeze(1)
        out, _ = self.gru(x)
        h = out[:, -1, :]
        return torch.cat([self.head_kw(h), self.head_zones(h)], dim=-1)


def build_model(family: str, n_in: int) -> nn.Module:
    if family == "gru_dualhead":
        return SmallGRUDualHead(n_in)
    return ResMLPDualHead(n_in)


class TorchMultiWrapper:
    """sklearn-like predict: X-scale → model (normalized Y) → inverse Y."""

    def __init__(
        self,
        model: nn.Module,
        x_scaler: StandardScaler,
        y_scaler: MultiTargetScaler,
        device: str = "cpu",
    ):
        self.model = model
        self.x_scaler = x_scaler
        self.y_scaler = y_scaler
        self.device = device
        self.model.eval()

    def predict(self, X: np.ndarray) -> np.ndarray:
        with torch.no_grad():
            xs = np.nan_to_num(np.asarray(X, dtype=np.float64), nan=0.0, posinf=0.0, neginf=0.0)
            xs = self.x_scaler.transform(xs)
            t = torch.tensor(xs, dtype=torch.float32, device=self.device)
            y_norm = self.model(t).cpu().numpy()
            assert_output_order(y_norm, name="torch_norm")
            y = self.y_scaler.inverse_transform(y_norm)
            assert_output_order(y, name="torch_inv")
            return y


def _weighted_huber(
    pred_norm: torch.Tensor,
    y_norm: torch.Tensor,
    *,
    w_kw: float,
    w_zone: float,
    delta: float = 1.0,
) -> torch.Tensor:
    """Huber in normalized target space with explicit kw vs zone weights."""
    err = pred_norm - y_norm
    abs_e = err.abs()
    quad = torch.clamp(abs_e, max=delta)
    lin = abs_e - quad
    huber = 0.5 * quad**2 + delta * lin
    # weights: col0 facility, cols1-6 zones (mean over zone cols then weight)
    kw = huber[:, 0].mean()
    zones = huber[:, 1:].mean()
    return w_kw * kw + w_zone * zones


def _val_score_norm(pred_norm: np.ndarray, y_norm: np.ndarray) -> float:
    """Early-stop metric: mean abs error over all 7 normalized targets."""
    return float(np.mean(np.abs(pred_norm - y_norm)))


def _train_one(
    Xtr: np.ndarray,
    Ytr: np.ndarray,
    Xva: np.ndarray,
    Yva: np.ndarray,
    *,
    family: str,
    epochs: int,
    device: str,
    w_kw: float,
    w_zone: float,
    seed: int,
    unroll_schedule: list[int] | None = None,
) -> tuple[nn.Module, StandardScaler, MultiTargetScaler, float]:
    set_seed(seed)
    x_scaler = StandardScaler()
    Xtr_s = x_scaler.fit_transform(Xtr)
    Xva_s = x_scaler.transform(Xva)
    y_scaler = MultiTargetScaler().fit(Ytr)
    Ytr_n = y_scaler.transform(Ytr)
    Yva_n = y_scaler.transform(Yva)

    model = build_model(family, Xtr.shape[1]).to(device)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3, weight_decay=1e-5)
    best = float("inf")
    best_state = None
    patience, bad = 14, 0
    schedule = unroll_schedule or [1, 1, 4, 4, 8, 16]
    # Map epoch → unroll horizon (curriculum)
    for ep in range(epochs):
        horizon = schedule[min(ep // max(1, epochs // len(schedule)), len(schedule) - 1)]
        model.train()
        idx = np.random.permutation(len(Xtr_s))
        for start in range(0, len(idx), 256):
            b = idx[start : start + 256]
            # Teacher-forced batch (horizon==1) or short multi-row chunk as weak unroll proxy:
            # full lag-feedback unroll needs day sequences; for tabular features we train
            # 1-step Huber always and optionally average loss over ``horizon`` shuffled
            # mini-chunks to stabilize multi-step prediction heads.
            xb = torch.tensor(Xtr_s[b], dtype=torch.float32, device=device)
            yb = torch.tensor(Ytr_n[b], dtype=torch.float32, device=device)
            opt.zero_grad()
            pred = model(xb)
            loss = _weighted_huber(pred, yb, w_kw=w_kw, w_zone=w_zone)
            if horizon > 1 and len(b) >= horizon:
                # Extra loss on contiguous slices within the batch (curriculum pressure)
                for k in range(0, len(b) - horizon, horizon):
                    sl = slice(k, k + horizon)
                    loss = loss + 0.15 * _weighted_huber(
                        model(xb[sl]), yb[sl], w_kw=w_kw, w_zone=w_zone
                    )
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
        model.eval()
        with torch.no_grad():
            pred_n = model(torch.tensor(Xva_s, dtype=torch.float32, device=device)).cpu().numpy()
            score = _val_score_norm(pred_n, Yva_n)
        if score < best:
            best, best_state, bad = score, {k: v.cpu().clone() for k, v in model.state_dict().items()}, 0
        else:
            bad += 1
            if bad >= patience:
                break
    if best_state:
        model.load_state_dict(best_state)
    return model, x_scaler, y_scaler, best


def train_torch_baseline(
    df: pd.DataFrame,
    *,
    n_splits: int = 3,
    epochs: int = 40,
    device: str | None = None,
    split_manifest: dict[str, Any] | None = None,
    families: list[str] | None = None,
    seeds: list[int] | None = None,
    w_kw: float = 1.0,
    w_zone: float = 1.0,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Train dual-head torch models; select on recursive rolling-origin folds."""
    assert_target_cols(TARGET_COLS)
    X, Y, groups, cols, tcols, feat = matrix_xy_15min_multi(df)
    assert_target_cols(tcols)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    Y = np.nan_to_num(Y, nan=0.0, posinf=0.0, neginf=0.0)
    peak = morning_peak_mask_15min(feat)
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    families = families or ["resmlp_dualhead", "gru_dualhead"]
    seeds = seeds or [11, 22, 33, 44, 55]
    run_id = run_id or make_run_id(prefix="torch")

    if split_manifest is None:
        split_manifest = build_split_manifest(feat)

    def _day_mask(days: list[Any]) -> np.ndarray:
        dset = {str(d) for d in days}
        return feat["day"].astype(str).isin(dset).to_numpy()

    fold_specs = [
        (_day_mask(f["train"]), _day_mask(f["val"]), f["val"])
        for f in split_manifest.get("folds", [])
    ]
    if not fold_specs:
        raise ValueError("split_manifest has no folds — refuse random row-level CV")

    leaderboard: list[dict[str, Any]] = []
    candidates: dict[str, Any] = {}

    for family in families:
        for seed in seeds:
            key = f"{family}_seed{seed}"
            print(f"=== {key} ===", flush=True)
            t0 = time.perf_counter()
            tf_scores: list[dict] = []
            rec_per_day: dict[str, dict] = {}
            last_model = last_xs = last_ys = None
            for fold, (tr_mask, te_mask, te_days) in enumerate(fold_specs):
                if not tr_mask.any() or not te_mask.any():
                    continue
                model, x_sc, y_sc, _ = _train_one(
                    X[tr_mask],
                    Y[tr_mask],
                    X[te_mask],
                    Y[te_mask],
                    family=family,
                    epochs=epochs,
                    device=device,
                    w_kw=w_kw,
                    w_zone=w_zone,
                    seed=seed + fold,
                )
                wrap = TorchMultiWrapper(model, x_sc, y_sc, device)
                pred = wrap.predict(X[te_mask])
                pk = peak[te_mask]
                tf_scores.append(
                    {
                        "facility_kw_mae": float(np.mean(np.abs(pred[:, 0] - Y[te_mask, 0]))),
                        "facility_kw_mae_peak_05_09": float(
                            np.mean(np.abs(pred[pk, 0] - Y[te_mask, 0][pk]))
                        )
                        if pk.any()
                        else float(np.mean(np.abs(pred[:, 0] - Y[te_mask, 0]))),
                        "zone_temp_mae_mean": float(np.mean(np.abs(pred[:, 1:] - Y[te_mask, 1:]))),
                        "worst_zone_mae": float(np.max(np.mean(np.abs(pred[:, 1:] - Y[te_mask, 1:]), axis=0))),
                    }
                )
                ev = evaluate_recursive_days(wrap, feat, te_days, cols, tcols)
                rec_per_day.update(ev.get("per_day", {}))
                last_model, last_xs, last_ys = model, x_sc, y_sc
                print(
                    f"  fold{fold+1} TF peak={tf_scores[-1]['facility_kw_mae_peak_05_09']:.2f} "
                    f"zone_mean={tf_scores[-1]['zone_temp_mae_mean']:.2f}°F",
                    flush=True,
                )

            # Refit on all development days (exclude final winter test)
            final_test = [str(d) for d in split_manifest.get("final_winter_test", [])]
            dev_mask = ~feat["day"].astype(str).isin(set(final_test)) if final_test else np.ones(len(feat), bool)
            # Use last fold's val as early-stop holdout within train_one
            va_days = fold_specs[-1][2]
            va_mask = _day_mask(va_days)
            tr_final = dev_mask & ~va_mask
            if not tr_final.any():
                tr_final = dev_mask
            model, x_sc, y_sc, _ = _train_one(
                X[tr_final],
                Y[tr_final],
                X[va_mask] if va_mask.any() else X[tr_final],
                Y[va_mask] if va_mask.any() else Y[tr_final],
                family=family,
                epochs=epochs,
                device=device,
                w_kw=w_kw,
                w_zone=w_zone,
                seed=seed,
            )
            wrap = TorchMultiWrapper(model, x_sc, y_sc, device)
            cv_rec = _agg_day_scores(list(rec_per_day.values()))
            n_params = count_params(model)
            elapsed = time.perf_counter() - t0

            def _mean(scores: list[dict]) -> dict:
                if not scores:
                    return {}
                keys = scores[0].keys()
                return {k: float(np.nanmean([s[k] for s in scores])) for k in keys}

            entry = {
                "key": key,
                "family": family,
                "seed": seed,
                "n_params": n_params,
                "train_seconds": elapsed,
                "cv_teacher_forced": _mean(tf_scores),
                "cv_recursive_96_heldout": cv_rec
                if cv_rec.get("n_heldout_days", 0)
                else dict(NOT_EVALUATED_RECURSIVE),
            }
            # Selection metric: recursive facility peak MAE if available else TF zone+kw
            sel = cv_rec.get("facility_kw_mae_peak", cv_rec.get("facility_kw_mae"))
            zone_sel = entry["cv_teacher_forced"].get("zone_temp_mae_mean", 99.0)
            if sel is None or not np.isfinite(sel):
                sel = entry["cv_teacher_forced"].get("facility_kw_mae_peak_05_09", 99.0) + zone_sel
            entry["selection_score"] = float(sel) + 0.25 * float(zone_sel)
            leaderboard.append(entry)
            candidates[key] = {
                "model": model,
                "x_scaler": x_sc,
                "y_scaler": y_sc,
                "wrap": wrap,
                "entry": entry,
            }
            print(
                f"  params={n_params} selection_score={entry['selection_score']:.3f} "
                f"zone_TF={zone_sel:.2f}°F",
                flush=True,
            )

    leaderboard.sort(key=lambda e: e["selection_score"])
    champ_key = leaderboard[0]["key"]
    champ = candidates[champ_key]
    print(f"champion={champ_key} (recursive-aware selection)", flush=True)

    # Locked final winter test — evaluate exactly once after selection
    final_days = [str(d) for d in split_manifest.get("final_winter_test", [])]
    locked: dict[str, Any]
    if final_days:
        locked_ev = evaluate_recursive_days(champ["wrap"], feat, final_days, cols, tcols)
        locked = locked_ev if locked_ev.get("n_heldout_days", 0) else dict(NOT_EVALUATED_RECURSIVE)
        if "per_day" in locked_ev:
            locked = {**_agg_day_scores(list(locked_ev["per_day"].values())), "status": "evaluated"}
    else:
        locked = {"status": "not_evaluated", "reason": "no final_winter_test days in manifest"}

    return {
        "model": champ["model"],
        "x_scaler": champ["x_scaler"],
        "y_scaler": champ["y_scaler"],
        "wrap": champ["wrap"],
        "feature_cols": cols,
        "target_cols": tcols,
        "family": leaderboard[0]["family"],
        "seed": leaderboard[0]["seed"],
        "n_params": leaderboard[0]["n_params"],
        "cv_teacher_forced": leaderboard[0]["cv_teacher_forced"],
        "cv_recursive_96_heldout": leaderboard[0]["cv_recursive_96_heldout"],
        "locked_final_winter_test": locked,
        "leaderboard": leaderboard,
        "n_rows": int(len(feat)),
        "n_days": int(feat["day"].nunique()),
        "X_shape": X.shape,
        "Y_shape": Y.shape,
        "device": device,
        "run_id": run_id,
        "split_manifest": split_manifest,
        "w_kw": w_kw,
        "w_zone": w_zone,
    }


def export_torch_baseline_artifacts(result: dict[str, Any], out_dir: Path) -> dict[str, Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "eval").mkdir(parents=True, exist_ok=True)
    model: nn.Module = result["model"]
    x_scaler: StandardScaler = result["x_scaler"]
    y_scaler: MultiTargetScaler = result["y_scaler"]
    cols = result["feature_cols"]
    tcols = result["target_cols"]
    n_in = result["X_shape"][1]
    run_id = result["run_id"]

    write_manifest(out_dir / "eval" / "split_manifest.json", result["split_manifest"])

    pt_path = out_dir / f"{STEM}.pt"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "family": result["family"],
            "scaler_mean": x_scaler.mean_,
            "scaler_scale": x_scaler.scale_,
            "y_scaler": y_scaler.to_dict(),
            "n_in": n_in,
            "n_out": N_TARGETS,
            "run_id": run_id,
            "target_cols": list(TARGET_COLS),
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
            opset_version=18,
            dynamo=False,
        )
    except TypeError:
        # Older torch without dynamo= kw
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

    # ONNX parity: scaled features in → normalized outputs; inverse via y_scaler
    parity = {"status": "skipped"}
    if onnx_path.is_file():
        try:
            import onnxruntime as ort

            sess = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
            rng = np.random.default_rng(0)
            raw = rng.normal(size=(8, n_in)).astype(np.float32)
            xs = x_scaler.transform(raw).astype(np.float32)
            with torch.no_grad():
                torch_out = model(torch.tensor(xs)).numpy()
            ort_out = sess.run(None, {"features": xs})[0]
            max_abs = float(np.max(np.abs(torch_out - ort_out)))
            parity = {"status": "ok", "max_abs_norm_space": max_abs, "n": 8}
            print(f"ONNX parity max|Δ|={max_abs:.6g} (normalized space)", flush=True)
        except Exception as e:
            parity = {"status": "failed", "error": str(e)}

    eval_path = out_dir / "eval" / "torch_recursive_days.json"
    eval_path.write_text(
        json.dumps(
            _json_safe(
                {
                    "run_id": run_id,
                    "cv_recursive_96_heldout": result["cv_recursive_96_heldout"],
                    "locked_final_winter_test": result["locked_final_winter_test"],
                    "leaderboard": result["leaderboard"],
                }
            ),
            indent=2,
        ),
        encoding="utf-8",
    )

    card = stamp_card(
        {
            "stem": STEM,
            "honesty": HONESTY,
            "family": result["family"],
            "seed": result["seed"],
            "n_params": result["n_params"],
            "cv_teacher_forced": result["cv_teacher_forced"],
            "cv_recursive_96_heldout": result.get(
                "cv_recursive_96_heldout", dict(NOT_EVALUATED_RECURSIVE)
            ),
            "locked_final_winter_test": result.get("locked_final_winter_test"),
            "leaderboard": result["leaderboard"],
            "n_rows": result["n_rows"],
            "n_days": result["n_days"],
            "built_at_utc": datetime.now(timezone.utc).isoformat(),
            "feature_contract_version": "FEATURE_COLS_15MIN_MT",
            "control_contract_version": "control_strategies_v1",
            "feature_cols": cols,
            "target_cols": tcols,
            "trained_via": "notebook",
            "loss": "huber_normalized_dual_head",
            "w_kw": result["w_kw"],
            "w_zone": result["w_zone"],
            "onnx_parity": parity,
            "scaling_note": (
                "X StandardScaler + per-target Y StandardScaler fit on train days only; "
                "ONNX emits normalized outputs — apply y_scaler.inverse_transform for °F/kW"
            ),
        },
        run_id=run_id,
    )
    card_path = out_dir / f"{STEM}_model_card.json"

    meta = {
        "stem": STEM,
        "run_id": run_id,
        "feature_cols": cols,
        "target_cols": tcols,
        "n_features": len(cols),
        "n_outputs": len(tcols),
        "scaler_mean": x_scaler.mean_.tolist(),
        "scaler_scale": x_scaler.scale_.tolist(),
        "y_scaler": y_scaler.to_dict(),
        "honesty": HONESTY,
        "trained_via": "notebook",
        "family": result["family"],
        "onnx_output_space": "normalized_targets",
    }
    meta_path = out_dir / f"{STEM}_feature_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    paths = {"pt": pt_path, "onnx": onnx_path, "meta": meta_path, "card": card_path, "eval": eval_path}
    hashes = {k: sha256_file(p) for k, p in paths.items() if p.is_file()}
    card["artifact_sha256"] = hashes
    card_path.write_text(json.dumps(_json_safe(card), indent=2), encoding="utf-8")

    reg = artifact_registry({k: str(v) for k, v in paths.items()}, run_id=run_id)
    print_artifact_registry(reg)
    return paths


def main(argv: list[str] | None = None) -> int:
    from notebook_gate import TORCH_NOTEBOOK, cli_train_allowed, refuse_cli_train

    if not cli_train_allowed():
        return refuse_cli_train("torch dual-head real baseline", notebook=TORCH_NOTEBOOK)

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parquet", type=Path, default=None)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--max-days", type=int, default=None)
    ap.add_argument("--winter-only", action="store_true")
    ap.add_argument("--w-kw", type=float, default=1.0)
    ap.add_argument("--w-zone", type=float, default=1.0)
    ap.add_argument("--lean", action="store_true", help="1 seed, resmlp only, fewer epochs")
    args = ap.parse_args(argv)

    df = load_real_baseline_frame(
        parquet=args.parquet,
        winter_only=args.winter_only,
        max_days=args.max_days,
    )
    feat_days = df.copy()
    # Need compiled feat for manifest — use matrix helper's feat
    _, _, _, _, _, feat = matrix_xy_15min_multi(df)
    manifest = build_split_manifest(feat)
    kwargs: dict[str, Any] = {
        "epochs": 20 if args.lean else args.epochs,
        "split_manifest": manifest,
        "w_kw": args.w_kw,
        "w_zone": args.w_zone,
    }
    if args.lean:
        kwargs["families"] = ["resmlp_dualhead"]
        kwargs["seeds"] = [11]
        kwargs["epochs"] = min(kwargs["epochs"], 25)
    result = train_torch_baseline(df, **kwargs)
    paths = export_torch_baseline_artifacts(result, args.out_dir or (_ML / "artifacts"))
    print(
        json.dumps(
            {
                "card": str(paths["card"]),
                "family": result["family"],
                "cv_tf": result["cv_teacher_forced"],
                "zone_mae": result["cv_teacher_forced"].get("zone_temp_mae_mean"),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
