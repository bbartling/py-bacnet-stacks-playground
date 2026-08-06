#!/usr/bin/env python
"""Export versioned 96-step control strategy contracts from farm SoT.

Source of truth: scripts/eplus_heating_dsm_farm.py::build_area_controls
Desktop PRBS is not offered — schedule strategies only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_APP))
sys.path.insert(0, str(_APP / "scripts"))

from eplus_heating_dsm_farm import (  # noqa: E402
    DSM_ZONES,
    build_area_controls,
)
from feature_compile_heating_dsm import (  # noqa: E402
    HP_ON_COLS,
    OCC_FRAC_COLS,
)

CONTRACT_VERSION = "control_strategies_v1"
OUT_DIR = _APP / "contracts" / CONTRACT_VERSION

# Map E+ zone names → short ML feature suffixes (1F_A …)
_ZONE_SHORT = {
    "1F_Area_A": "1F_A",
    "1F_Area_B": "1F_B",
    "1F_Area_C": "1F_C",
    "1F_Area_D": "1F_D",
    "2F_Area_A": "2F_A",
    "2F_Area_B": "2F_B",
}

DESKTOP_STRATEGIES = [
    "baseline",
    "flat_24_7",
    "stagger_preheat",
    "deep_setback",
    "morning_all_on",
]


def _hourly_to_96(hourly: list[float]) -> list[float]:
    out: list[float] = []
    for h in range(24):
        v = float(hourly[h])
        out.extend([v, v, v, v])
    return out


def _occ_from_hp_and_schedule(strategy_id: str, hp96: list[float], step: int) -> float:
    """K-12-ish occ fraction: occupied HE 07–16 when strategy implies occupancy."""
    he = step // 4
    if strategy_id == "flat_24_7":
        return 1.0
    if 7 <= he < 16:
        return 1.0 if hp96[step] > 0.05 or strategy_id == "baseline" else 0.0
    return 0.0


def export_strategy(strategy_id: str, seed: int = 21) -> dict[str, Any]:
    ctrl = build_area_controls(strategy_id, seed=seed)
    meta = dict(ctrl["meta"])
    steps: list[dict[str, Any]] = []
    for step in range(96):
        he = step // 4
        row: dict[str, Any] = {"step_15": step, "hour_ending": he}
        sum_occ = 0.0
        sum_hp = 0.0
        for z_long in DSM_ZONES:
            short = _ZONE_SHORT[z_long]
            hp_h = ctrl["hp_on"][z_long]
            hp96 = _hourly_to_96(hp_h)
            hp = float(hp96[step])
            # occ_frac: occupied hours follow school schedule; flat_24_7 always 1
            if strategy_id == "flat_24_7":
                occ = 1.0
            elif 7 <= he < 16:
                occ = 1.0
            else:
                occ = 0.0
            row[f"occ_frac_{short}"] = occ
            row[f"hp_on_{short}"] = hp
            sum_occ += occ
            sum_hp += hp
        row["sum_occ_frac"] = sum_occ
        row["sum_hp_on"] = sum_hp
        row["preheat_lead_h"] = float(meta.get("preheat_lead_h", 0.0))
        row["stagger_min"] = float(meta.get("stagger_min", 0.0))
        row["unocc_htg_sp_f"] = float(meta.get("unocc_htg_sp_f", 65.0))
        row["occ_htg_sp_f"] = float(meta.get("occ_htg_sp_f", 68.0))
        steps.append(row)

    return {
        "contract_version": CONTRACT_VERSION,
        "strategy_id": strategy_id,
        "control_regime": meta.get("control_regime", strategy_id),
        "desktop_supported": True,
        "prbs_note": "PRBS not offered in desktop; farm-only.",
        "meta": meta,
        "steps": steps,
        "feature_notes": {
            "interval": "quarter-hour interval end / hour-ending",
            "n_steps": 96,
            "zones": list(_ZONE_SHORT.values()),
        },
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index = {
        "contract_version": CONTRACT_VERSION,
        "source": "scripts/eplus_heating_dsm_farm.py::build_area_controls",
        "desktop_strategies": DESKTOP_STRATEGIES,
        "prbs": "not_offered_on_desktop",
        "files": {},
    }
    for sid in DESKTOP_STRATEGIES:
        doc = export_strategy(sid)
        path = OUT_DIR / f"{sid}.json"
        path.write_text(json.dumps(doc, indent=2), encoding="utf-8")
        index["files"][sid] = path.name
        print(f"wrote {path}")
    (OUT_DIR / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"wrote {OUT_DIR / 'index.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
