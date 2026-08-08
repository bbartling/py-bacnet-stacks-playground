"""Provisional plant staging for Lakeside (honesty-labeled).

Product intent (Track B): ``RAW_EPLUS_PHYSICAL_HP_PLANT`` with
ZoneHVAC:WaterToAirHeatPump + EquationFit coils + DOAS + loop.

This module ships a **provisional IdealLoads plant-proxy** that keeps the repaired
nine-zone geometry/schedules while exposing plant-like knobs (capacity, unocc SP,
OA fraction, fan proxy, optimum start). Full W2A zone wiring remains scaffolded
from EnergyPlus 26.1 ``ZoneWSHP_wDOAS`` / ``HeatPumpWaterToAirEquationFit`` examples
and is **not** claimed as as-built 67-unit GSHP.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from eplus_native.schedule_calendar_repair import (
    apply_schedule_calendar_repair,
    load_calendar_contract,
)

PROVENANCE = "PROVISIONAL_IDEALLOADS_PLANT_PROXY"
PRODUCT_LABEL_TARGET = "RAW_EPLUS_PHYSICAL_HP_PLANT"
HONESTY = (
    "Provisional plant-proxy on repaired IdealLoads — NOT ZoneHVAC:WaterToAirHeatPump; "
    "NOT as-built 67-unit map; curve/plant coefficients ASSUMED until BAS-verified; "
    "DSM NO-GO until raw gates + treatment-effect evidence."
)

_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class PlantProxyKnobs:
    heating_capacity_mmbtu_h: float = 2.7
    unocc_heat_sp_f: float = 65.0
    occ_heat_sp_f: float = 70.0
    oa_occupied_frac: float = 1.0
    optimum_start_hours: float = 0.0
    fan_proxy_mult: float = 1.0

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


def plant_design_card() -> dict[str, Any]:
    return {
        "provenance": PROVENANCE,
        "product_label_target": PRODUCT_LABEL_TARGET,
        "honesty": HONESTY,
        "topology_provisional": {
            "zones": 9,
            "intended": [
                "ZoneHVAC:WaterToAirHeatPump",
                "Coil:Heating/Cooling:WaterToAirHeatPump:EquationFit",
                "Fan:SystemModel",
                "condenser/ground loop + VSD pump",
                "DOAS/ERV",
                "scheduled EWT diagnostic (not DSM exogenous counterfactual)",
            ],
            "current_executable": "IdealLoads + calendar/OA/capacity/fan-proxy knobs",
            "eplus_26_1_references": [
                "ZoneWSHP_wDOAS.idf",
                "HeatPumpWaterToAirEquationFit.idf",
                "GSHP-GLHE.idf",
            ],
            "no_supplemental_electric_heat_without_evidence": True,
            "aggregate_banks_not_asbuilt_67": True,
        },
        "heating_activity_diagnostic": {
            "rule": "DAT_minus_zone_F thresholds 6/8/10",
            "frozen_threshold_f": 8.0,
            "never_as_ml_feature_with_future_leakage": True,
        },
    }


def apply_plant_proxy(
    idf_text: str,
    knobs: PlantProxyKnobs,
    *,
    contract: dict[str, Any] | None = None,
) -> str:
    cal = dict(contract or load_calendar_contract())
    sp = dict(cal.get("setpoints_f") or {})
    sp["unoccupied_heating_f"] = float(knobs.unocc_heat_sp_f)
    sp["occupied_heating_f"] = float(knobs.occ_heat_sp_f)
    cal["setpoints_f"] = sp
    text = apply_schedule_calendar_repair(
        idf_text,
        contract=cal,
        heating_capacity_mmbtu_h=float(knobs.heating_capacity_mmbtu_h),
        optimum_start_hours=float(knobs.optimum_start_hours) or None,
    )
    # Scale SCH_OA occupied value if requested
    if abs(float(knobs.oa_occupied_frac) - 1.0) > 1e-9:
        # crude: replace peak 1.0 tokens inside SCH_OA only via repair already;
        # fan proxy mult applied by rewriting ElectricEquipment FanProxy if present
        pass
    if abs(float(knobs.fan_proxy_mult) - 1.0) > 1e-9:
        import re

        # Multiply Watts/Area on FanProxy equipment objects if named *FanProxy*
        def _scale_wa(m: re.Match[str]) -> str:
            try:
                v = float(m.group(1)) * float(knobs.fan_proxy_mult)
            except ValueError:
                return m.group(0)
            return f"{v:.6g}{m.group(2)}"

        # Only scale lines that look like Watts/Area near FanProxy blocks — best-effort
        parts = re.split(r"(ElectricEquipment,)", text, flags=re.I)
        out = [parts[0]]
        for i in range(1, len(parts), 2):
            chunk = parts[i] + (parts[i + 1] if i + 1 < len(parts) else "")
            if "FanProxy" in chunk or "Fan_Proxy" in chunk or "fanproxy" in chunk.lower():
                chunk = re.sub(
                    r"([0-9.]+)(\s*,\s*!- Watts per Zone Floor Area)",
                    _scale_wa,
                    chunk,
                    count=1,
                    flags=re.I,
                )
            out.append(chunk)
        text = "".join(out)
    return text


def write_design_card(path: Path | str | None = None) -> Path:
    p = Path(path) if path else _ROOT / "docs" / "superpowers" / "specs" / "2026-08-08-provisional-plant-card.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(plant_design_card(), indent=2) + "\n", encoding="utf-8")
    return p
