"""Rule DR controllers from contracts/control_strategies_v1 (no ML)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parents[1]
_CONTRACTS = _ROOT / "contracts" / "control_strategies_v1"

# Default gap between baseline unocc (~65F) and deep_setback unocc (~60F) in contracts.
DEEP_SETBACK_EXTRA_F = 5.0


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


def effective_htg_setpoints_f(
    strategy_id: str,
    *,
    occ_htg_sp_f: float | None = None,
    unocc_htg_sp_f: float | None = None,
) -> dict[str, float]:
    """Resolve occ/unocc heating °F after optional Site Config overrides."""
    meta = (load_strategy_contract(strategy_id).get("meta") or {})
    contract_occ = float(meta.get("occ_htg_sp_f", 68.0))
    contract_unocc = float(meta.get("unocc_htg_sp_f", 65.0))
    occ = float(occ_htg_sp_f) if occ_htg_sp_f is not None else contract_occ
    unocc = float(unocc_htg_sp_f) if unocc_htg_sp_f is not None else contract_unocc
    if strategy_id == "flat_24_7":
        unocc = occ
    elif strategy_id == "deep_setback" and unocc_htg_sp_f is not None:
        # Keep ~5F deeper than the site's normal unoccupied (contract delta).
        unocc = float(unocc_htg_sp_f) - DEEP_SETBACK_EXTRA_F
    return {
        "occ_htg_sp_f": occ,
        "unocc_htg_sp_f": unocc,
        "contract_occ_htg_sp_f": contract_occ,
        "contract_unocc_htg_sp_f": contract_unocc,
    }


class RuleController:
    """Map 15-min step → heating setpoint °C from a named strategy contract.

    Optional ``occ_htg_sp_f`` / ``unocc_htg_sp_f`` come from Site Config and
    replace the contract's hardcoded °F while keeping each strategy's occupancy
    / DR shape (``sum_occ_frac``).
    """

    def __init__(
        self,
        strategy_id: str = "baseline",
        *,
        occ_htg_sp_f: float | None = None,
        unocc_htg_sp_f: float | None = None,
    ):
        self.strategy_id = strategy_id
        self.contract = load_strategy_contract(strategy_id)
        steps = self.contract.get("steps") or []
        self._htg_f: List[float] = []
        eff = effective_htg_setpoints_f(
            strategy_id,
            occ_htg_sp_f=occ_htg_sp_f,
            unocc_htg_sp_f=unocc_htg_sp_f,
        )
        self.occ_htg_sp_f = eff["occ_htg_sp_f"]
        self.unocc_htg_sp_f = eff["unocc_htg_sp_f"]
        use_site = occ_htg_sp_f is not None or unocc_htg_sp_f is not None
        occ = self.occ_htg_sp_f
        unocc = self.unocc_htg_sp_f
        for row in steps:
            occupied = float(row.get("sum_occ_frac", 0.0)) > 0.05
            if use_site:
                if strategy_id == "flat_24_7":
                    sp = occ
                else:
                    sp = occ if occupied else unocc
            elif "occ_htg_sp_f" in row and "unocc_htg_sp_f" in row:
                sp = (
                    float(row["occ_htg_sp_f"])
                    if occupied
                    else float(row["unocc_htg_sp_f"])
                )
            else:
                sp = occ if occupied else unocc
            self._htg_f.append(sp)
        if not self._htg_f:
            self._htg_f = [occ] * 96
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
