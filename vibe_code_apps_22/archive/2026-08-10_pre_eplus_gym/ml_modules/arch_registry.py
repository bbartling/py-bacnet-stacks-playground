"""Creative architecture registry for 10×10 iterative search.

Each iteration lists 10 named candidates. Later iterations mutate prior winners.
Physics LSTMs are the majority focus.
"""
from __future__ import annotations

from typing import Any

# Iteration 1 — 10 creative starting points (physics-heavy).
ITER_01: list[dict[str, Any]] = [
    {"name": "phys_lstm_hdd_residual", "family": "torch_phys_lstm", "theme": "HDD residual LSTM"},
    {"name": "phys_lstm_48h_direct", "family": "torch_phys_lstm", "theme": "48h forecast encode"},
    {"name": "phys_gru_rc_state", "family": "torch_phys_gru", "theme": "RC-state GRU"},
    {"name": "phys_tcn_forecast", "family": "torch_phys_tcn", "theme": "TCN over forecast"},
    {"name": "phys_lstm_delta_only", "family": "torch_phys_lstm", "theme": "delta sequence"},
    {"name": "phys_lstm_teacher_sched", "family": "torch_phys_lstm", "theme": "scheduled sampling"},
    {"name": "multi_horizon_48_96", "family": "torch_multi_horizon", "theme": "H=48/96 heads"},
    {"name": "sklearn_hgb_multi", "family": "hist_gradient_boosting", "theme": "HGB MultiOutput"},
    {"name": "sklearn_chain_kw", "family": "regressor_chain_kw_first", "theme": "RegressorChain"},
    {"name": "sklearn_et_native", "family": "extra_trees_native_multi", "theme": "native multi ET"},
]


def mutate_for_next_iter(
    prev_leaderboard: list[dict[str, Any]],
    *,
    iter_n: int,
) -> list[dict[str, Any]]:
    """Build 10 new names from top-3 of previous leaderboard + creative fillers."""
    ranked = sorted(
        prev_leaderboard,
        key=lambda r: (
            0 if r.get("pass") else 1,
            float(r.get("score", 1e9)),
        ),
    )
    top = [r["name"] for r in ranked[:3]] or [c["name"] for c in ITER_01[:3]]
    out: list[dict[str, Any]] = []
    mutators = [
        "wider",
        "deeper",
        "lower_lr",
        "more_dropout",
        "longer_horizon",
        "stronger_physics",
        "weaker_physics",
        "ensemble_pair",
        "ablate_strategy",
        "ablate_forecast",
    ]
    for i in range(10):
        base = top[i % len(top)]
        tag = mutators[i]
        out.append(
            {
                "name": f"{base}__i{iter_n:02d}_{tag}",
                "family": "torch_phys_lstm" if "phys" in base or "horizon" in base else "sklearn_hgb_multi",
                "theme": f"iter{iter_n} mutate {base} via {tag}",
                "parent": base,
                "mutation": tag,
            }
        )
    return out


def candidates_for_iter(iter_n: int, prev_leaderboard: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    if iter_n <= 1:
        return list(ITER_01)
    return mutate_for_next_iter(prev_leaderboard or [], iter_n=iter_n)
