"""Phase 11: SciPy differential evolution day-ahead optimizer arm."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from eplus_gym.mega._json import sha256_obj
from eplus_gym.mega.common_action_contract import decode_action_for_arm

SCHEMA = "vibe22.mega.day_ahead_optimizer.v1"
ARM_LABEL = "DAY_AHEAD_OPTIMIZER"


@dataclass
class OptimizerResult:
    x_best: list[float]
    fun_best: float
    n_evals: int
    energyplus_confirmed: bool = False
    confirmation_score: float | None = None

    def to_dict(self, *, day: str = "2025-12-15") -> dict[str, Any]:
        decoded: dict[str, Any] | str
        try:
            if len(self.x_best) >= 11:
                decoded = decode_action_for_arm(self.x_best, arm=ARM_LABEL, day=day).__dict__
            else:
                decoded = {"partial_search_vector": self.x_best, "note": "subset bounds — not full v2 decode"}
        except (TypeError, ValueError) as exc:
            decoded = {"error": str(exc), "x_best": self.x_best}
        return {
            "x_best": self.x_best,
            "fun_best": self.fun_best,
            "n_evals": self.n_evals,
            "energyplus_confirmed": self.energyplus_confirmed,
            "confirmation_score": self.confirmation_score,
            "decoded_params": decoded,
        }


@dataclass
class DayAheadOptimizerArm:
    bounds: list[tuple[float, float]]
    maxiter: int = 30
    popsize: int = 8
    seed: int = 0

    def optimize(
        self,
        objective: Callable[[Sequence[float]], float],
        *,
        confirm: Callable[[Sequence[float]], float] | None = None,
    ) -> OptimizerResult:
        from scipy.optimize import differential_evolution

        bounds = self.default_bounds()
        res = differential_evolution(
            objective,
            bounds=bounds,
            maxiter=self.maxiter,
            popsize=self.popsize,
            seed=self.seed,
            polish=True,
            updating="immediate",
        )
        x_best = res.x.tolist()
        confirmed = False
        conf_score = None
        if confirm is not None:
            conf_score = float(confirm(x_best))
            confirmed = True
        return OptimizerResult(
            x_best=x_best,
            fun_best=float(res.fun),
            n_evals=int(res.nfev),
            energyplus_confirmed=confirmed,
            confirmation_score=conf_score,
        )

    def default_bounds(self) -> list[tuple[float, float]]:
        if self.bounds:
            return self.bounds
        # Subset of research v2 continuous envelope for day-ahead search
        return [
            (68.0, 72.0),  # occupied heating F — engineering band
            (60.0, 68.0),  # unoccupied heating F
            (0.0, 48.0),   # start step
            (48.0, 80.0),  # end step
        ]

    def stub_objective(self) -> Callable[[Sequence[float]], float]:
        def _obj(x: Sequence[float]) -> float:
            arr = np.asarray(x, dtype=float)
            bounds = self.default_bounds()
            target = np.array([70.0, 64.0, 30.0, 58.0][: len(arr)])
            return float(np.sum((arr - target) ** 2))

        return _obj

    def to_manifest(self, result: OptimizerResult, *, day: str) -> dict[str, Any]:
        body = {
            "schema": SCHEMA,
            "arm": ARM_LABEL,
            "day": day,
            "bounds": self.default_bounds(),
            "result": result.to_dict(day=day),
            "scipy_method": "differential_evolution",
        }
        body["optimizer_sha256"] = sha256_obj(body)
        return body

    def write(self, path: Path, result: OptimizerResult, *, day: str) -> dict[str, Any]:
        body = self.to_manifest(result, day=day)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
        return body
