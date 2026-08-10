#!/usr/bin/env python
"""10×10 creative architecture search — physics LSTMs + sklearn multi-output.

Each --iter runs up to 10 candidates, writes leaderboard, mutates for next iter.
CI smoke: --iter 1 --limit 2
Full offline: for i in 1..10: python scripts/arch_search_10x10.py --iter $i
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

_APP = Path(__file__).resolve().parents[1]
_ML = _APP / "ml"
sys.path[:0] = [str(_ML), str(_APP)]

from arch_registry import candidates_for_iter  # noqa: E402
from hybrid_sanity import PLANT_PEAK_CAP_KW  # noqa: E402
from multioutput_families import lean_family_protos, wrap_family  # noqa: E402
from phys_lstm_models import smoke_train_phys_lstm  # noqa: E402

OUT_ROOT = _ML / "artifacts" / "arch_search"


def _eval_sklearn(name: str, family: str) -> dict[str, Any]:
    protos = lean_family_protos(n_jobs=1)
    key = family if family in protos else "hist_gradient_boosting"
    if key not in protos:
        key = list(protos)[0]
    rng = np.random.default_rng(abs(hash(name)) % (2**31))
    X = rng.normal(size=(60, 12))
    Y = rng.normal(size=(60, 7))
    Y[:, 0] = np.clip(80 + 20 * X[:, 0], 0, 400)
    m = wrap_family(key, protos[key], n_jobs=1)
    m.fit(X[:40], Y[:40])
    pred = np.asarray(m.predict(X[40:]), dtype=float)
    peak = float(np.max(pred[:, 0]))
    mae = float(np.mean(np.abs(pred[:, 0] - Y[40:, 0])))
    ok = 0.0 <= peak <= PLANT_PEAK_CAP_KW and mae < 80.0
    return {
        "name": name,
        "family": key,
        "pass": ok,
        "score": mae + (0.0 if ok else 1e3),
        "peak_kw": peak,
        "mae": mae,
        "backend": "sklearn",
    }


def _eval_torch(name: str, family: str) -> dict[str, Any]:
    kind = "multi_horizon" if "horizon" in name or family == "torch_multi_horizon" else "residual"
    r = smoke_train_phys_lstm(kind=kind, steps=32, epochs=4, seed=abs(hash(name)) % 10_000)
    return {
        "name": name,
        "family": family,
        "pass": bool(r.get("pass")),
        "score": float(r.get("score", 1e9)),
        "peak_kw": r.get("recon_peak_kw"),
        "loss": r.get("loss"),
        "backend": "torch",
        "detail": r,
    }


def _eval_one(cand: dict[str, Any]) -> dict[str, Any]:
    fam = str(cand.get("family") or "")
    name = str(cand["name"])
    if fam.startswith("sklearn") or fam in lean_family_protos(n_jobs=1):
        row = _eval_sklearn(name, fam.replace("sklearn_", "") if fam.startswith("sklearn_") else fam)
    else:
        row = _eval_torch(name, fam)
    row["theme"] = cand.get("theme")
    row["parent"] = cand.get("parent")
    row["mutation"] = cand.get("mutation")
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--iter", type=int, default=1)
    ap.add_argument("--limit", type=int, default=10, help="max candidates this iter (CI use 2)")
    ap.add_argument("--out-root", type=Path, default=OUT_ROOT)
    args = ap.parse_args()

    out_dir = Path(args.out_root) / f"iter_{args.iter:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    prev_path = Path(args.out_root) / f"iter_{args.iter - 1:02d}" / "leaderboard.json"
    prev = []
    if prev_path.is_file():
        prev = json.loads(prev_path.read_text(encoding="utf-8")).get("rows") or []

    cands = candidates_for_iter(args.iter, prev)[: max(1, args.limit)]
    rows = []
    for c in cands:
        print(f"eval {c['name']} ...", flush=True)
        rows.append(_eval_one(c))

    rows_sorted = sorted(rows, key=lambda r: (0 if r["pass"] else 1, r["score"]))
    board = {
        "iter": args.iter,
        "n": len(rows_sorted),
        "n_pass": sum(1 for r in rows_sorted if r["pass"]),
        "plant_peak_cap_kw": PLANT_PEAK_CAP_KW,
        "rows": rows_sorted,
    }
    (out_dir / "leaderboard.json").write_text(json.dumps(board, indent=2), encoding="utf-8")
    print(json.dumps({"iter": args.iter, "n_pass": board["n_pass"], "top": rows_sorted[0]["name"]}, indent=2))
    return 0 if board["n_pass"] > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
