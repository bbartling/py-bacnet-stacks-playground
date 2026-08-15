"""Zone 15-min ramp gate: A04 vs real BAS. Do not retune thresholds to pass A04."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from eplus_gym.objective import BAS_ZONE_COLS

VERDICT_FAIL = "NO_GO_LONG_RL_TRAINING_PHYSICS_RAMP_IMPLAUSIBLE"
VERDICT_PASS = "GO_RAMP_PLAUSIBLE"
# Robust BAS p99.9 times engineering margin. Documented, not fitted to A04.
ENGINEERING_MARGIN = 3.0


def abs_15min_deltas(frame: pd.DataFrame, cols: Sequence[str] = BAS_ZONE_COLS) -> np.ndarray:
    arr = frame[list(cols)].astype(float).diff().abs().to_numpy().reshape(-1)
    return arr[np.isfinite(arr)]


def evaluate_ramp_gate(
    *,
    simulated: pd.DataFrame,
    real_bas: pd.DataFrame,
    cols: Sequence[str] = BAS_ZONE_COLS,
    engineering_margin: float = ENGINEERING_MARGIN,
) -> dict[str, Any]:
    real = abs_15min_deltas(real_bas, cols)
    sim = abs_15min_deltas(simulated, cols)
    if real.size == 0 or sim.size == 0:
        raise ValueError("empty ramp samples")
    qs = {
        "median": float(np.quantile(real, 0.5)),
        "p95": float(np.quantile(real, 0.95)),
        "p99": float(np.quantile(real, 0.99)),
        "p99_9": float(np.quantile(real, 0.999)),
        "max": float(np.max(real)),
    }
    threshold = float(qs["p99_9"] * float(engineering_margin))
    sim_max = float(np.max(sim))
    sim_p99 = float(np.quantile(sim, 0.99))
    passed = sim_max <= threshold
    return {
        "schema": "vibe22.physics_ramp_gate.v1",
        "bas_quantiles_f_per_15min": qs,
        "engineering_margin": float(engineering_margin),
        "threshold_f_per_15min": threshold,
        "threshold_rule": "bas_p99_9 * engineering_margin",
        "simulated_max_f_per_15min": sim_max,
        "simulated_p99_f_per_15min": sim_p99,
        "notes": {
            "data_quality_jumps": "BAS max may include sensor spikes; gate uses p99.9 not max",
            "occupied_recovery": "normal recovery should sit near p95–p99 of BAS",
            "setpoint_clipping": "simulated DualSP steps can clip and overshoot recovery speed",
        },
        "passed": passed,
        "verdict": VERDICT_PASS if passed else VERDICT_FAIL,
    }
