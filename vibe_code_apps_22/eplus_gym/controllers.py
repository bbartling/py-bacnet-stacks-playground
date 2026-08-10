"""Rule DR controllers from contracts/control_strategies_v1 (no ML)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[1]
_CONTRACTS = _ROOT / "contracts" / "control_strategies_v1"

# °F → °C for Schedule:Compact heating SP actuator
def f_to_c(f: float) -> float:
    return (float(f) - 32.0) * 5.0 / 9.0


def list_strategies() -> List[str]:
    if not _CONTRACTS.is_dir():
        return []
    return sorted(p.stem for p in _CONTRACTS.glob("*.json"))


def load_strategy_contract(strategy_id: str) -> Dict[str, Any]:
    path = _CONTRACTS / f"{strategy_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"missing strategy contract: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


class RuleController:
    """Map 15-min step → heating setpoint °C from a named strategy contract."""

    def __init__(self, strategy_id: str = "baseline"):
        self.strategy_id = strategy_id
        self.contract = load_strategy_contract(strategy_id)
        steps = self.contract.get("steps") or []
        self._htg_f: List[float] = []
        meta = self.contract.get("meta") or {}
        occ = float(meta.get("occ_htg_sp_f", 68.0))
        unocc = float(meta.get("unocc_htg_sp_f", 65.0))
        for row in steps:
            # Prefer explicit per-step occ SP; fall back using sum_occ_frac
            if "occ_htg_sp_f" in row and "unocc_htg_sp_f" in row:
                sp = (
                    float(row["occ_htg_sp_f"])
                    if float(row.get("sum_occ_frac", 0.0)) > 0.05
                    else float(row["unocc_htg_sp_f"])
                )
            else:
                sp = occ if float(row.get("sum_occ_frac", 0.0)) > 0.05 else unocc
            self._htg_f.append(sp)
        if not self._htg_f:
            self._htg_f = [occ] * 96
        # pad / trim to 96
        if len(self._htg_f) < 96:
            self._htg_f = (self._htg_f * ((96 // len(self._htg_f)) + 1))[:96]
        else:
            self._htg_f = self._htg_f[:96]

    def setpoint_f(self, step: int) -> float:
        return float(self._htg_f[int(step) % 96])

    def action_c(self, step: int) -> float:
        """Actuator value for Schedule:Compact SCH_HtgSP (EnergyPlus °C)."""
        return f_to_c(self.setpoint_f(step))

    def series_f(self) -> List[float]:
        return list(self._htg_f)
